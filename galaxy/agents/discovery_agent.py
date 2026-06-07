"""Discovery agent — finds sources for a query."""
import logging
from galaxy.types import StructuredQuery, SourceCandidate
from galaxy.knowledge.source_registry import SourceRegistry

log = logging.getLogger("galaxy.agents")


class DiscoveryAgent:
    """Discovers dataset sources for a query."""
    
    def __init__(self):
        self.registry = SourceRegistry()
    
    def discover(self, query: StructuredQuery) -> list[SourceCandidate]:
        """Find all applicable sources for the query."""
        candidates = []
        sources = self.registry.get_sources(query.original_query)
        
        for src in sources:
            candidates.append(SourceCandidate(
                source_id=src.source_id,
                url=self.registry.get_search_url(src.source_id, query.original_query),
                priority=int(src.reliability * 100),
                crawler_type=src.crawler_type,
                reliability_score=src.reliability,
            ))
        
        # Always add search engine source (dynamic)
        candidates.append(SourceCandidate(
            source_id="search_engine",
            url="",
            priority=70,
            crawler_type="search",
            reliability_score=0.7,
        ))
        
        # Sort by priority descending
        candidates.sort(key=lambda c: c.priority, reverse=True)
        log.info(f"Discovery: {len(candidates)} sources for '{query.original_query}'")
        return candidates
