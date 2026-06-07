"""Search engine spider — uses DuckDuckGo to find datasets across the entire internet."""
import json
import logging
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path
from lxml import html as lxml_html

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.search")

# DuckDuckGo HTML search (no API key, no auth, free)
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


class SearchEngineSpider(BaseCollector):
    """Search the entire internet for datasets using DuckDuckGo.
    Discovers new sources dynamically — not limited to fixed sources."""
    
    source_id = "search_engine"
    
    def collect(self, query: str, max_results: int = 10, max_pages: int = 3) -> list[CollectedFile]:
        """Search DuckDuckGo for data files across the internet."""
        log.info(f"SearchEngine: searching internet for '{query}' (max={max_results})")
        
        # Multiple search variations to find more data
        search_variations = [
            f"{query} filetype:csv download",
            f"{query} dataset download",
            f"{query} data filetype:json",
            f"{query} open data",
        ]
        
        all_urls = set()
        
        for variation in search_variations:
            try:
                urls = self._search_ddg(variation, max_pages=max_pages)
                all_urls.update(urls)
                log.info(f"SearchEngine: DDG found {len(urls)} results for '{variation}'")
                time.sleep(1)  # respect rate limits
            except Exception as e:
                log.warning(f"DDG search failed: {e}")
        
        log.info(f"SearchEngine: {len(all_urls)} unique URLs to scan")
        
        # Crawl each result page for downloadable data
        downloaded = 0
        for url in list(all_urls):
            if downloaded >= max_results:
                break
            
            try:
                new = self._scan_page_for_data(url)
                downloaded += new
            except Exception as e:
                log.debug(f"Page scan failed: {url}: {e}")
        
        self._save_source_metadata()
        log.info(f"SearchEngine: collected {len(self.collected)} files")
        return self.collected
    
    def _search_ddg(self, query: str, max_pages: int = 2) -> list[str]:
        """Search DuckDuckGo HTML and extract result URLs."""
        urls = []
        
        for page in range(max_pages):
            try:
                data = urllib.parse.urlencode({
                    'q': query,
                    's': str(page * 30),
                    'dc': str(page * 30 + 1),
                    'v': 'l',
                    'o': 'json',
                    'api': 'd.js',
                }).encode()
                
                req = urllib.request.Request(DUCKDUCKGO_URL, data=data, headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': 'https://html.duckduckgo.com/',
                })
                
                with urllib.request.urlopen(req, timeout=15) as resp:
                    html_content = resp.read().decode('utf-8', errors='replace')
                
                tree = lxml_html.fromstring(html_content)
                
                # Extract result links
                result_links = tree.xpath('//a[@class="result__a"]/@href')
                for link in result_links:
                    # DDG wraps URLs in redirect — extract real URL
                    real_url = self._extract_real_url(link)
                    if real_url and real_url.startswith('http'):
                        urls.append(real_url)
                
                # Also try alternate selectors
                if not result_links:
                    all_links = tree.xpath('//a/@href')
                    for link in all_links:
                        if link.startswith('http') and 'duckduckgo' not in link:
                            urls.append(link)
                
                time.sleep(0.5)
            except Exception as e:
                log.debug(f"DDG page {page} failed: {e}")
        
        return urls
    
    def _extract_real_url(self, ddg_url: str) -> str:
        """Extract real URL from DuckDuckGo redirect."""
        if ddg_url.startswith('//duckduckgo.com/l/?uddg='):
            parsed = urllib.parse.urlparse(ddg_url)
            params = urllib.parse.parse_qs(parsed.query)
            if 'uddg' in params:
                return urllib.parse.unquote(params['uddg'][0])
        elif ddg_url.startswith('http'):
            return ddg_url
        return ddg_url
    
    def _scan_page_for_data(self, url: str) -> int:
        """Scan a web page for downloadable data files. Returns count downloaded."""
        downloaded = 0
        
        try:
            html_content = self._fetch_page(url)
            if not html_content:
                return 0
            
            tree = lxml_html.fromstring(html_content)
            links = tree.xpath('//a/@href')
            
            for href in links:
                if not href:
                    continue
                
                full_url = urllib.parse.urljoin(url, href)
                
                # Check if it's a data file
                if self._is_data_url(full_url):
                    parsed = urllib.parse.urlparse(full_url)
                    filename = Path(parsed.path).name
                    if filename and len(filename) > 3:
                        safe = "".join(c for c in filename if c.isalnum() or c in ".-_")
                        local_path = self._download_file(full_url, safe)
                        if local_path and Path(local_path).stat().st_size > 100:
                            self._register_file(local_path, full_url,
                                              metadata={"found_on": url, "source": "search_engine"})
                            downloaded += 1
        except Exception as e:
            log.debug(f"Scan failed: {url}: {e}")
        
        return downloaded
    
    def _fetch_page(self, url: str) -> str | None:
        """Fetch a web page."""
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception:
            return None
    
    def _is_data_url(self, url: str) -> bool:
        """Check if URL points to a data file."""
        lower = url.lower()
        data_exts = ('.csv', '.tsv', '.json', '.jsonl', '.parquet', '.txt',
                     '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
                     '.mp3', '.wav', '.flac', '.ogg',
                     '.mp4', '.avi', '.mkv',
                     '.zip', '.tar.gz', '.gz', '.xlsx')
        return any(lower.endswith(ext) for ext in data_exts)
