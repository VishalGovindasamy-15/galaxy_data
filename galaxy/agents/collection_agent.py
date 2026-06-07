"""Collection agent — coordinates all spiders."""
import logging
from pathlib import Path
from galaxy.types import StructuredQuery, CollectedFile
from galaxy.collection.rate_limiter import RateLimiter
from galaxy.collection.circuit_breaker import CircuitBreaker

log = logging.getLogger("galaxy.agents")

# Modality → allowed file extensions
MODALITY_EXTENSIONS = {
    "images": {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'},
    "audio": {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'},
    "video": {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'},
    "tabular": {'.csv', '.tsv', '.json', '.jsonl', '.parquet', '.xlsx'},
    "text": {'.txt', '.md', '.html', '.htm', '.pdf', '.xml', '.rtf'},
    "mixed": None,  # allow all
}


class CollectionAgent:
    """Coordinates all spiders with modality filtering."""
    
    def __init__(self, raw_dir: str, rate_limiter: RateLimiter = None,
                 circuit_breaker: CircuitBreaker = None):
        self.raw_dir = raw_dir
        self.rate_limiter = rate_limiter or RateLimiter()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
    
    def collect_from_source(self, source_id: str, query: str,
                            modality: str = "mixed", max_results: int = 10) -> list[CollectedFile]:
        """Collect from a single source with modality filtering."""
        from galaxy.collection.spiders.huggingface_spider import HuggingFaceSpider
        from galaxy.collection.spiders.github_spider import GitHubSpider
        from galaxy.collection.spiders.web_search_spider import WebSearchSpider
        from galaxy.collection.spiders.kaggle_spider import KaggleSpider
        from galaxy.collection.spiders.search_engine_spider import SearchEngineSpider
        
        SPIDER_MAP = {
            "huggingface": HuggingFaceSpider,
            "github": GitHubSpider,
            "web_search": WebSearchSpider,
            "kaggle": KaggleSpider,
            "search_engine": SearchEngineSpider,
        }
        
        SpiderClass = SPIDER_MAP.get(source_id)
        if not SpiderClass:
            log.warning(f"Unknown source: {source_id}")
            return []
        
        if not self.circuit_breaker.can_request(source_id):
            log.warning(f"Circuit open for {source_id}")
            return []
        
        try:
            spider = SpiderClass(
                workspace_raw_dir=self.raw_dir,
                rate_limiter=self.rate_limiter,
                circuit_breaker=self.circuit_breaker,
            )
            collected = spider.collect(query, max_results=max_results)
            
            # Filter by modality
            filtered = self._filter_by_modality(collected, modality)
            log.info(f"{source_id}: {len(collected)} raw → {len(filtered)} after modality filter ({modality})")
            return filtered
        except Exception as e:
            log.error(f"{source_id} collection failed: {e}")
            self.circuit_breaker.record_failure(source_id)
            return []
    
    def _filter_by_modality(self, files: list[CollectedFile], modality: str) -> list[CollectedFile]:
        """Keep only files matching the requested modality."""
        allowed = MODALITY_EXTENSIONS.get(modality)
        if allowed is None:  # mixed = allow all
            return files
        
        filtered = []
        for f in files:
            ext = Path(f.path).suffix.lower()
            if ext in allowed:
                filtered.append(f)
            else:
                log.debug(f"Filtered out {Path(f.path).name} (ext={ext} not in {modality})")
        return filtered
