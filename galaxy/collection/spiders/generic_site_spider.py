"""Generic site spider - crawl any URL and extract downloadable data using lxml."""
import logging
import urllib.request
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
        """Recursively crawl a page for data files using lxml."""
        if url in visited or depth > max_depth:
            return
        visited.add(url)
        
        try:
            from lxml import html as lxml_html
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html_content = resp.read().decode('utf-8', errors='replace')
            tree = lxml_html.fromstring(html_content)
        except Exception as e:
            log.debug(f"Fetch failed: {url}: {e}")
            return
        
        # Find download links
        links = tree.xpath('//a/@href')
        for href in links:
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
                lower_href = href.lower()
                if any(kw in lower_href for kw in ['data', 'dataset', 'download', 'file']):
                    self._crawl_page(full_url, visited, depth + 1, max_depth)
