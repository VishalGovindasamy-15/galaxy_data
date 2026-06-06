"""Web search spider - find datasets from any website using Scrapling."""
import re
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.web_search")

# Known open dataset portals
DATASET_PORTALS = [
    "https://data.gov.in/search?title={query}",
    "https://data.world/search?q={query}",
    "https://datasetsearch.research.google.com/search?query={query}",
]


class WebSearchSpider(BaseCollector):
    """Search the web for datasets using Scrapling for page parsing."""
    
    source_id = "web_search"
    
    def collect(self, query: str, max_results: int = 5) -> list[CollectedFile]:
        """Search for downloadable datasets across the web."""
        log.info(f"WebSearch: searching for '{query}'")
        
        # Strategy: use known open data portals + direct file search
        found_urls = set()
        
        # 1. Search data portals
        for portal_template in DATASET_PORTALS:
            try:
                search_url = portal_template.format(query=urllib.parse.quote(query))
                self._search_portal(search_url, found_urls)
            except Exception as e:
                log.debug(f"Portal search failed: {e}")
        
        # 2. Try direct GitHub search for CSV files
        try:
            self._search_github_code(query, found_urls)
        except Exception as e:
            log.debug(f"GitHub code search failed: {e}")
        
        # 3. Download found files
        for url in list(found_urls)[:max_results]:
            try:
                parsed = urllib.parse.urlparse(url)
                filename = Path(parsed.path).name or f"web_data_{hash(url) % 100000}"
                local_path = self._download_file(url, filename)
                if local_path and Path(local_path).stat().st_size > 100:
                    self._register_file(local_path, url, metadata={"source": "web_search"})
            except Exception as e:
                log.debug(f"Download failed: {url}: {e}")
        
        self._save_source_metadata()
        log.info(f"WebSearch: collected {len(self.collected)} files")
        return self.collected
    
    def _search_portal(self, url: str, found_urls: set):
        """Search a data portal page for dataset download links using lxml."""
        try:
            from lxml import html as lxml_html
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html_content = resp.read().decode('utf-8', errors='replace')
            
            tree = lxml_html.fromstring(html_content)
            links = tree.xpath('//a/@href')
            for href in links:
                if self.legal.is_dataset_url(href):
                    if href.startswith('http'):
                        found_urls.add(href)
                    elif href.startswith('/'):
                        parsed = urllib.parse.urlparse(url)
                        found_urls.add(f"{parsed.scheme}://{parsed.netloc}{href}")
        except Exception as e:
            log.debug(f"Portal parse failed: {url}: {e}")
    
    def _search_github_code(self, query: str, found_urls: set):
        """Search GitHub for raw CSV/data files."""
        search_url = f"https://api.github.com/search/code?q={urllib.parse.quote(query)}+extension:csv&per_page=5"
        try:
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'GalaxyData/0.1',
                'Accept': 'application/vnd.github.v3+json',
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            
            for item in data.get("items", [])[:5]:
                repo = item.get("repository", {}).get("full_name", "")
                path = item.get("path", "")
                if repo and path:
                    raw_url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
                    found_urls.add(raw_url)
        except Exception as e:
            log.debug(f"GitHub code search failed: {e}")
