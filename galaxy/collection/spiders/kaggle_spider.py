"""Kaggle spider - search and download from Kaggle using Scrapling."""
import re
import json
import logging
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.kaggle")


class KaggleSpider(BaseCollector):
    """Search Kaggle datasets using web scraping (no API key needed)."""
    
    source_id = "kaggle"
    
    def collect(self, query: str, max_results: int = 5) -> list[CollectedFile]:
        """Search Kaggle and try to find downloadable dataset info."""
        log.info(f"Kaggle: searching for '{query}'")
        
        # Kaggle blocks most scraping, so we use their sitemap/search page
        # with Scrapling for parsing
        search_url = f"https://www.kaggle.com/datasets?search={urllib.parse.quote(query)}"
        
        try:
            from scrapling.fetchers import Fetcher
            fetcher = Fetcher(timeout=30, auto_match=False)
            page = fetcher.get(search_url, timeout=30)
            
            # Extract dataset links from search results
            dataset_urls = []
            if hasattr(page, 'find_all'):
                links = page.find_all('a')
                for link in links:
                    href = link.attrib.get('href', '')
                    if '/datasets/' in href and href.count('/') >= 2:
                        full_url = urllib.parse.urljoin("https://www.kaggle.com", href)
                        if full_url not in dataset_urls:
                            dataset_urls.append(full_url)
            
            log.info(f"Kaggle: found {len(dataset_urls)} dataset links")
            
            # Note: Kaggle requires auth for downloads, so we record metadata only
            # The actual data will come from other sources (HuggingFace mirrors, GitHub)
            for url in dataset_urls[:max_results]:
                meta_file = self._source_dir / f"kaggle_ref_{hash(url) % 100000}.json"
                meta_file.write_text(json.dumps({
                    "source": "kaggle",
                    "url": url,
                    "query": query,
                    "note": "Kaggle requires auth for download - reference only"
                }, indent=2))
        except Exception as e:
            log.warning(f"Kaggle search failed (expected - anti-bot): {e}")
        
        self._save_source_metadata()
        return self.collected
