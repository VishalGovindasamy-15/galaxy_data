"""Main orchestrator - drives the full Galaxy Data pipeline."""
import time
import logging
from pathlib import Path
from galaxy.types import (
    GatewayRequest, StructuredQuery, SessionState, CollectedFile,
    CollectionResult, ProcessingResult, BuildResult, WebExtractionRequest,
)
from galaxy.config import Config
from galaxy.intelligence.query_parser import parse_query
from galaxy.intelligence.embeddings import EmbeddingStore
from galaxy.knowledge.source_registry import SourceRegistry
from galaxy.knowledge.dataset_lineage import DatasetLineage
from galaxy.knowledge import metadata_store
from galaxy.storage.session_workspace import SessionWorkspace
from galaxy.collection.spiders.huggingface_spider import HuggingFaceSpider
from galaxy.collection.spiders.github_spider import GitHubSpider
from galaxy.collection.spiders.web_search_spider import WebSearchSpider
from galaxy.collection.spiders.kaggle_spider import KaggleSpider
from galaxy.collection.spiders.generic_site_spider import GenericSiteSpider
from galaxy.collection.rate_limiter import RateLimiter
from galaxy.collection.circuit_breaker import CircuitBreaker
from galaxy.processing.router import ProcessingRouter
from galaxy.agents.building_agent import BuildingAgent
from galaxy.agents.web_extraction_agent import WebExtractionAgent

log = logging.getLogger("galaxy")


class Orchestrator:
    """Main pipeline controller. Drives: Query → Discover → Collect → Process → Build."""
    
    def __init__(self):
        Config.ensure_dirs()
        self.source_registry = SourceRegistry()
        self.embeddings = EmbeddingStore()
        self.rate_limiter = RateLimiter(default_rate=1.5)
        self.circuit_breaker = CircuitBreaker()
    
    def run(self, request: GatewayRequest, interactive: bool = False,
            enable_web_extraction: bool = False,
            max_results: int = 10, max_pages: int = 20) -> BuildResult:
        """Execute the full pipeline.
        
        Args:
            request: Gateway request with query
            interactive: Interactive mode
            enable_web_extraction: Auto-extract from web if no datasets found
            max_results: Max datasets per source (controls collection size)
            max_pages: Max pages to scan for web extraction
        """
        session_id = request.session_id
        log.info(f"=== Galaxy Data Pipeline Started === Session: {session_id}")
        log.info(f"Query: {request.query} | max_results={max_results} | max_pages={max_pages}")
        start_time = time.time()
        
        # 1. Create workspace
        workspace = SessionWorkspace(session_id)
        workspace.create()
        log.info(f"Workspace: {workspace.root}")
        
        # 2. Parse query
        query = parse_query(request.query)
        log.info(f"Parsed: domains={query.domains}, language={query.language}, modality={query.modality}")
        
        # Save embedding
        query.embedding_id = self.embeddings.store(request.query)
        
        # Save session to DB
        metadata_store.save_session(session_id, request.user_id, SessionState.DISCOVERING.value,
                                    request.query, str(workspace.root))
        
        # 3. Setup lineage tracking
        lineage = DatasetLineage(str(workspace.root))
        
        # 4. DISCOVER & COLLECT
        workspace.update_progress({"state": "collecting", "message": "Collecting datasets..."})
        all_collected = self._collect(query, workspace, lineage, max_results=max_results)
        
        log.info(f"Collection complete: {len(all_collected)} files from all sources")
        
        # 5. WEB EXTRACTION (if enabled — runs ALWAYS if --extract flag, not just when empty)
        if enable_web_extraction:
            log.info(f"Web extraction enabled. Scanning {max_pages} pages...")
            extraction_req = WebExtractionRequest(
                session_id=session_id,
                search_queries=query.search_queries,
                max_pages=max_pages,
                user_approved=True,
                extract_text=True,
            )
            extractor = WebExtractionAgent(str(workspace.raw_dir))
            extracted = extractor.extract(extraction_req)
            all_collected.extend(extracted)
            for cf in extracted:
                lineage.create(cf.path, cf.url, "web_extraction")
            log.info(f"Web extraction: {len(extracted)} files created")
        
        if len(all_collected) == 0:
            log.warning("No datasets found from any source")
        
        # 6. PROCESS
        metadata_store.update_session_state(session_id, SessionState.PROCESSING.value)
        workspace.update_progress({"state": "processing", "files": len(all_collected)})
        
        router = ProcessingRouter(str(workspace.root))
        processed = router.process_all(all_collected)
        
        log.info(f"Processing complete: {len(processed)} datasets (from {len(all_collected)} files)")
        
        # 7. BUILD
        metadata_store.update_session_state(session_id, SessionState.BUILDING.value)
        workspace.update_progress({"state": "building", "datasets": len(processed)})
        
        builder = BuildingAgent(str(workspace.root))
        result = builder.build(session_id, processed, query=request.query, merge=query.merge)
        
        # 8. Save lineage
        lineage.save()
        
        # 9. Mark complete
        metadata_store.update_session_state(session_id, SessionState.COMPLETED.value)
        duration = time.time() - start_time
        workspace.update_progress({
            "state": "completed",
            "duration_seconds": round(duration, 1),
            "datasets_collected": len(all_collected),
            "datasets_processed": len(processed),
            "final_path": str(workspace.final_dir),
        })
        
        log.info(f"=== Pipeline Complete === Duration: {duration:.1f}s | Output: {result.package_path}")
        return result
    
    def _collect(self, query: StructuredQuery, workspace: SessionWorkspace,
                 lineage: DatasetLineage, max_results: int = 10) -> list[CollectedFile]:
        """Run all spiders to collect datasets."""
        all_collected = []
        raw_dir = str(workspace.raw_dir)
        search_query = query.original_query
        
        # Spider order: HuggingFace (most reliable) → GitHub → WebSearch → Kaggle
        spiders = [
            ("huggingface", HuggingFaceSpider),
            ("github", GitHubSpider),
            ("web_search", WebSearchSpider),
            ("kaggle", KaggleSpider),
        ]
        
        for source_id, SpiderClass in spiders:
            if not self.circuit_breaker.can_request(source_id):
                log.warning(f"Circuit open for {source_id}, skipping")
                continue
            
            try:
                log.info(f"--- Collecting from: {source_id} ---")
                spider = SpiderClass(
                    workspace_raw_dir=raw_dir,
                    rate_limiter=self.rate_limiter,
                    circuit_breaker=self.circuit_breaker,
                )
                collected = spider.collect(search_query, max_results=max_results)
                
                # Register lineage
                for cf in collected:
                    lineage.create(cf.path, cf.url, source_id)
                
                all_collected.extend(collected)
                log.info(f"{source_id}: collected {len(collected)} files")
            except Exception as e:
                log.error(f"{source_id} failed: {e}")
                self.circuit_breaker.record_failure(source_id)
        
        return all_collected
