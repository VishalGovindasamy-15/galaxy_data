"""Generic site spider - crawl any URL and extract downloadable data using Scrapling."""
import logging
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.generic")


class GenericSiteSpider(BaseCollector):
    """Crawl any URL using Scrapling to find and download data files."""
    
    source_id = "generic"
    
    def collect(self, query: str, urls: list[str] = None, max_depth: int = 2) -> list[CollectedFile]:
        """Crawl given URLs to find dataset files using Scrapling."""
        if not urls:
            log.info("GenericSite: no URLs provided, skipping")
            return self.collected
        
        log.info(f"GenericSite: crawling {len(urls)} URLs")
        visited = set()
        
        for url in urls:
            self._crawl_page(url, visited, depth=0, max_depth=max_depth)
        
        self._save_source_metadata()
        log.info(f"GenericSite: collected {len(self.collected)} files")
        return self.collected
    
    def _crawl_page(self, url: str, visited: set, depth: int, max_depth: int):
        """Recursively crawl a page for data files."""
        if url in visited or depth > max_depth:
            return
        visited.add(url)
        
        try:
            from scrapling.fetchers import Fetcher
            fetcher = Fetcher(timeout=20, auto_match=False)
            page = fetcher.get(url, timeout=20)
        except Exception as e:
            log.debug(f"Fetch failed: {url}: {e}")
            return
        
        # Find download links
        if hasattr(page, 'find_all'):
            links = page.find_all('a')
            for link in links:
                href = link.attrib.get('href', '')
                if not href:
                    continue
                
                full_url = urllib.parse.urljoin(url, href)
                
                if self.legal.is_dataset_url(full_url):
                    parsed = urllib.parse.urlparse(full_url)
                    filename = Path(parsed.path).name
                    local_path = self._download_file(full_url, filename)
                    if local_path and Path(local_path).stat().st_size > 100:
                        self._register_file(local_path, full_url, metadata={"crawled_from": url})
                elif depth < max_depth and full_url.startswith('http'):
                    # Follow links that might lead to datasets
                    lower_href = href.lower()
                    if any(kw in lower_href for kw in ['data', 'dataset', 'download', 'file']):
                        self._crawl_page(full_url, visited, depth + 1, max_depth)
