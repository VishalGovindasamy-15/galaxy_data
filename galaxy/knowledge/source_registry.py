"""Source registry - known free/open dataset sources."""
import logging
from dataclasses import dataclass, field

log = logging.getLogger("galaxy.knowledge")


@dataclass
class SourceInfo:
    source_id: str
    name: str
    base_url: str
    search_url_template: str
    crawler_type: str = "http"
    reliability: float = 0.9
    free: bool = True
    needs_auth: bool = False
    description: str = ""


# Free-only sources, no auth required
SOURCES = {
    "kaggle": SourceInfo(
        source_id="kaggle",
        name="Kaggle Datasets",
        base_url="https://www.kaggle.com",
        search_url_template="https://www.kaggle.com/datasets?search={query}",
        crawler_type="http",
        reliability=0.95,
        description="Community datasets"
    ),
    "huggingface": SourceInfo(
        source_id="huggingface",
        name="HuggingFace Hub",
        base_url="https://huggingface.co",
        search_url_template="https://huggingface.co/api/datasets?search={query}&limit=20",
        crawler_type="http",
        reliability=0.95,
        description="ML datasets hub"
    ),
    "github": SourceInfo(
        source_id="github",
        name="GitHub",
        base_url="https://github.com",
        search_url_template="https://github.com/search?q={query}+dataset&type=repositories",
        crawler_type="http",
        reliability=0.85,
        description="Code repos with datasets"
    ),
    "papers_with_code": SourceInfo(
        source_id="papers_with_code",
        name="Papers With Code",
        base_url="https://paperswithcode.com",
        search_url_template="https://paperswithcode.com/datasets?q={query}",
        crawler_type="http",
        reliability=0.8,
        description="Academic datasets"
    ),
    "uci": SourceInfo(
        source_id="uci",
        name="UCI ML Repository",
        base_url="https://archive.ics.uci.edu",
        search_url_template="https://archive.ics.uci.edu/datasets?search={query}",
        crawler_type="http",
        reliability=0.9,
        description="Classic ML datasets"
    ),
}


class SourceRegistry:
    """Registry of known free dataset sources."""
    
    def __init__(self):
        self._sources = SOURCES.copy()
    
    def get_all(self) -> list[SourceInfo]:
        return list(self._sources.values())
    
    def get(self, source_id: str) -> SourceInfo | None:
        return self._sources.get(source_id)
    
    def get_sources(self, query: str) -> list[SourceInfo]:
        """Get all applicable sources for a query (all free sources)."""
        return [s for s in self._sources.values() if s.free and not s.needs_auth]
    
    def get_search_url(self, source_id: str, query: str) -> str:
        """Generate search URL for a source."""
        src = self._sources.get(source_id)
        if src:
            return src.search_url_template.format(query=query.replace(" ", "+"))
        return ""
