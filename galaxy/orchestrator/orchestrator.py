"""Main orchestrator — drives the full Galaxy Data pipeline with collection loop."""
import time
import logging
from pathlib import Path
from galaxy.types import (
    GatewayRequest, StructuredQuery, SessionState, CollectedFile,
    BuildResult, WebExtractionRequest,
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
from galaxy.collection.spiders.search_engine_spider import SearchEngineSpider
from galaxy.collection.rate_limiter import RateLimiter
from galaxy.collection.circuit_breaker import CircuitBreaker
from galaxy.processing.router import ProcessingRouter
from galaxy.processing.filter_engine import filter_relevant
from galaxy.agents.building_agent import BuildingAgent
from galaxy.agents.web_extraction_agent import WebExtractionAgent
from galaxy.agents.collection_agent import CollectionAgent

log = logging.getLogger("galaxy")

# Modality → allowed file extensions
MODALITY_EXTENSIONS = {
    "images": {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'},
    "audio": {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'},
    "video": {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'},
    "tabular": {'.csv', '.tsv', '.json', '.jsonl', '.parquet', '.xlsx'},
    "text": {'.txt', '.md', '.html', '.htm', '.pdf', '.xml', '.rtf'},
    "mixed": None,  # allow all
}


class Orchestrator:
    """Main pipeline controller with collection loop until size/quality satisfied."""
    
    def __init__(self):
        Config.ensure_dirs()
        self.source_registry = SourceRegistry()
        self.embeddings = EmbeddingStore()
        self.rate_limiter = RateLimiter(default_rate=1.5)
        self.circuit_breaker = CircuitBreaker()
    
    def run(self, request: GatewayRequest, interactive: bool = False,
            enable_web_extraction: bool = False,
            max_results: int = 10, max_pages: int = 20,
            min_size_bytes: int = 0, modality: str = "mixed") -> BuildResult:
        """Execute the full pipeline with collection loop.
        
        Args:
            request: Gateway request with query
            enable_web_extraction: Enable web extraction mode
            max_results: Max datasets per source per round
            max_pages: Max pages for web extraction
            min_size_bytes: Keep collecting until this size is reached (0=no limit)
            modality: Filter type: images|audio|video|tabular|text|mixed
        """
        session_id = request.session_id
        log.info(f"=== Galaxy Data Pipeline Started === Session: {session_id}")
        log.info(f"Query: {request.query} | max_results={max_results} | modality={modality}")
        if min_size_bytes > 0:
            log.info(f"Min size target: {min_size_bytes / 1024 / 1024:.1f} MB")
        start_time = time.time()
        
        # 1. Create workspace
        workspace = SessionWorkspace(session_id)
        workspace.create()
        log.info(f"Workspace: {workspace.root}")
        
        # 2. Parse query
        query = parse_query(request.query)
        # Modality: user's explicit choice always wins
        # "mixed" = no filter (collect everything). Only filter when user explicitly asks.
        if modality != "mixed":
            query.modality = modality  # user explicitly asked for this type
        else:
            query.modality = "mixed"  # override parser auto-detection
        log.info(f"Parsed: domains={query.domains}, language={query.language}, modality={query.modality}")
        
        # Save embedding
        query.embedding_id = self.embeddings.store(request.query)
        
        # Save session
        metadata_store.save_session(session_id, request.user_id, SessionState.DISCOVERING.value,
                                    request.query, str(workspace.root))
        
        # 3. Setup lineage
        lineage = DatasetLineage(str(workspace.root))
        
        # 4. COLLECTION LOOP — keep collecting until size/quality satisfied
        all_collected = []
        collection_round = 0
        max_rounds = 3 if min_size_bytes > 0 else 1
        
        while collection_round < max_rounds:
            collection_round += 1
            log.info(f"=== Collection Round {collection_round}/{max_rounds} ===")
            
            workspace.update_progress({"state": "collecting", "round": collection_round})
            
            # Collect from all sources
            round_collected = self._collect(
                query, workspace, lineage,
                max_results=max_results, modality=query.modality
            )
            
            # Relevance filtering
            if round_collected:
                round_collected = filter_relevant(round_collected, request.query, threshold=0.05)
            
            all_collected.extend(round_collected)
            log.info(f"Round {collection_round}: {len(round_collected)} files "
                     f"(total: {len(all_collected)})")
            
            # Check if size target met
            total_size = sum(Path(f.path).stat().st_size for f in all_collected
                           if Path(f.path).exists())
            if min_size_bytes > 0 and total_size >= min_size_bytes:
                log.info(f"Size target met: {total_size/1024/1024:.1f} MB >= "
                         f"{min_size_bytes/1024/1024:.1f} MB")
                break
            
            if collection_round < max_rounds and total_size < min_size_bytes:
                # Increase results for next round
                max_results = int(max_results * 1.5)
                log.info(f"Size not met ({total_size/1024/1024:.1f} MB), "
                         f"increasing max_results to {max_results}")
        
        log.info(f"Collection complete: {len(all_collected)} files from all sources")
        
        # 5. WEB EXTRACTION
        if enable_web_extraction:
            log.info(f"Web extraction: scanning {max_pages} pages...")
            extraction_req = WebExtractionRequest(
                session_id=session_id,
                search_queries=query.search_queries,
                max_pages=max_pages,
                user_approved=True,
                extract_text=True,
            )
            extractor = WebExtractionAgent(str(workspace.raw_dir))
            extracted = extractor.extract(extraction_req)
            
            # Modality filter extracted files too
            if modality != "mixed":
                extracted = self._filter_by_modality(extracted, modality)
            
            all_collected.extend(extracted)
            for cf in extracted:
                lineage.create(cf.path, cf.url, "web_extraction")
            log.info(f"Web extraction: {len(extracted)} files")
        
        if len(all_collected) == 0:
            log.warning("No datasets found from any source")
        
        # 6. PROCESS through typed pipelines
        metadata_store.update_session_state(session_id, SessionState.PROCESSING.value)
        workspace.update_progress({"state": "processing", "files": len(all_collected)})
        
        router = ProcessingRouter(str(workspace.root))
        processed = router.process_all(all_collected)
        
        log.info(f"Processing complete: {len(processed)} datasets (from {len(all_collected)} files)")
        
        # 7. BUILD — organize into typed folders
        metadata_store.update_session_state(session_id, SessionState.BUILDING.value)
        workspace.update_progress({"state": "building", "datasets": len(processed)})
        
        builder = BuildingAgent(str(workspace.root))
        result = builder.build(session_id, processed, query=request.query, merge=query.merge)
        
        # 8. Save lineage
        lineage.save()
        
        # 9. Complete
        metadata_store.update_session_state(session_id, SessionState.COMPLETED.value)
        duration = time.time() - start_time
        workspace.update_progress({
            "state": "completed",
            "duration_seconds": round(duration, 1),
            "datasets_collected": len(all_collected),
            "datasets_processed": len(processed),
            "final_path": str(workspace.final_dir),
        })
        
        log.info(f"=== Pipeline Complete === Duration: {duration:.1f}s | "
                 f"Output: {result.package_path}")
        return result
    
    def _collect(self, query: StructuredQuery, workspace: SessionWorkspace,
                 lineage: DatasetLineage, max_results: int = 10,
                 modality: str = "mixed") -> list[CollectedFile]:
        """Run all spiders with modality filtering."""
        all_collected = []
        raw_dir = str(workspace.raw_dir)
        search_query = query.original_query
        
        spiders = [
            ("huggingface", HuggingFaceSpider),
            ("github", GitHubSpider),
            ("web_search", WebSearchSpider),
            ("kaggle", KaggleSpider),
            ("search_engine", SearchEngineSpider),
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
                
                # Modality filter
                if modality != "mixed":
                    collected = self._filter_by_modality(collected, modality)
                
                for cf in collected:
                    lineage.create(cf.path, cf.url, source_id)
                
                all_collected.extend(collected)
                log.info(f"{source_id}: collected {len(collected)} files")
            except Exception as e:
                log.error(f"{source_id} failed: {e}")
                self.circuit_breaker.record_failure(source_id)
        
        return all_collected
    
    def _filter_by_modality(self, files: list[CollectedFile], modality: str) -> list[CollectedFile]:
        """Filter files by modality type."""
        allowed = MODALITY_EXTENSIONS.get(modality)
        if allowed is None:
            return files
        filtered = []
        for f in files:
            ext = Path(f.path).suffix.lower()
            if ext in allowed:
                filtered.append(f)
        if len(filtered) < len(files):
            log.info(f"Modality filter ({modality}): {len(files)} → {len(filtered)}")
        return filtered
