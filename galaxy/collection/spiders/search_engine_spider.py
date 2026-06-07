"""Search engine spider — uses Scrapling StealthyFetcher to search the entire internet.
Uses headless Chrome to bypass anti-bot protections and search DuckDuckGo/Google."""
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.search")

# Data file extensions we look for
DATA_EXTS = {'.csv', '.tsv', '.json', '.jsonl', '.parquet', '.txt', '.xlsx',
             '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
             '.mp3', '.wav', '.flac', '.ogg',
             '.mp4', '.avi', '.mkv', '.zip', '.tar.gz', '.gz'}

# Try loading StealthyFetcher
try:
    from scrapling import StealthyFetcher, Fetcher
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False


class SearchEngineSpider(BaseCollector):
    """Search the ENTIRE internet for datasets using StealthyFetcher + DuckDuckGo.
    Uses headless Chrome to get real search results, then crawls found pages."""
    
    source_id = "search_engine"
    
    def collect(self, query: str, max_results: int = 10, max_pages: int = 3) -> list[CollectedFile]:
        """Search the internet for data files."""
        log.info(f"SearchEngine: searching internet for '{query}' (max={max_results})")
        
        if not STEALTH_AVAILABLE:
            log.warning("SearchEngine: StealthyFetcher not available, using urllib fallback")
            return self._fallback_collect(query, max_results)
        
        # Search DuckDuckGo with multiple queries
        search_variations = [
            f"{query} dataset download filetype:csv",
            f"{query} dataset filetype:json",
            f"{query} open data download",
            f"{query} data repository",
        ]
        
        all_urls = set()
        for variation in search_variations:
            try:
                urls = self._search_duckduckgo(variation)
                all_urls.update(urls)
                log.info(f"SearchEngine: found {len(urls)} results for '{variation}'")
                time.sleep(1)
            except Exception as e:
                log.warning(f"Search failed for '{variation}': {e}")
        
        log.info(f"SearchEngine: {len(all_urls)} unique URLs to scan")
        
        # Crawl each result page for data files
        downloaded = 0
        for url in list(all_urls):
            if downloaded >= max_results:
                break
            try:
                new = self._scan_page(url)
                downloaded += new
            except Exception as e:
                log.debug(f"Page scan failed: {url}: {e}")
        
        self._save_source_metadata()
        log.info(f"SearchEngine: collected {len(self.collected)} files")
        return self.collected
    
    def _search_duckduckgo(self, query: str) -> list[str]:
        """Search DuckDuckGo using StealthyFetcher (headless Chrome)."""
        urls = []
        search_url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
        
        try:
            resp = StealthyFetcher.fetch(
                search_url,
                headless=True,
                disable_resources=True,
                block_ads=True,
                network_idle=True,
                timeout=20000,
            )
            
            if resp.status != 200:
                log.warning(f"DDG returned {resp.status}")
                return urls
            
            # Extract result links using Scrapling CSS selectors
            result_links = resp.css('a.result__a') or resp.css('a[data-testid="result-title-a"]')
            for link in result_links:
                href = link.attrib.get('href', '')
                if href and href.startswith('http') and 'duckduckgo' not in href:
                    urls.append(href)
            
            # Also try extracting from all links if CSS selectors don't match
            if not urls:
                all_links = resp.css('a[href]')
                for link in all_links:
                    href = link.attrib.get('href', '')
                    # DDG redirect URLs
                    if '//duckduckgo.com/l/?' in href:
                        real = self._extract_ddg_url(href)
                        if real:
                            urls.append(real)
                    elif href.startswith('http') and 'duckduckgo' not in href:
                        urls.append(href)
            
            log.info(f"DDG: extracted {len(urls)} result URLs")
        except Exception as e:
            log.warning(f"DDG StealthyFetcher error: {e}")
        
        return urls
    
    def _extract_ddg_url(self, ddg_url: str) -> str | None:
        """Extract real URL from DuckDuckGo redirect."""
        try:
            parsed = urllib.parse.urlparse(ddg_url)
            params = urllib.parse.parse_qs(parsed.query)
            if 'uddg' in params:
                return urllib.parse.unquote(params['uddg'][0])
        except Exception:
            pass
        return None
    
    def _scan_page(self, url: str) -> int:
        """Scan a web page for downloadable data files using Scrapling Fetcher."""
        downloaded = 0
        
        try:
            # Use Fetcher (not Stealth) for regular page crawling — faster
            resp = Fetcher.get(url, timeout=15)
            if resp.status != 200:
                return 0
            
            # Find all links using Scrapling selectors
            links = resp.css('a[href]')
            for link in links:
                href = link.attrib.get('href', '')
                if not href:
                    continue
                
                full_url = urllib.parse.urljoin(url, href)
                
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
    
    def _is_data_url(self, url: str) -> bool:
        """Check if URL points to a data file."""
        lower = url.lower()
        return any(lower.endswith(ext) for ext in DATA_EXTS)
    
    def _fallback_collect(self, query: str, max_results: int) -> list[CollectedFile]:
        """Fallback: use urllib + lxml for DuckDuckGo HTML search."""
        try:
            from lxml import html as lxml_html
            
            data = urllib.parse.urlencode({'q': query + ' dataset download'}).encode()
            req = urllib.request.Request(
                'https://html.duckduckgo.com/html/', data=data,
                headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html_content = resp.read().decode('utf-8', errors='replace')
            
            tree = lxml_html.fromstring(html_content)
            result_links = tree.xpath('//a[@class="result__a"]/@href')
            
            for href in result_links[:max_results]:
                real_url = self._extract_ddg_url(href) if '//duckduckgo.com' in href else href
                if real_url and self._is_data_url(real_url):
                    filename = Path(urllib.parse.urlparse(real_url).path).name
                    safe = "".join(c for c in filename if c.isalnum() or c in ".-_")
                    local_path = self._download_file(real_url, safe)
                    if local_path:
                        self._register_file(local_path, real_url)
        except Exception as e:
            log.warning(f"Fallback search failed: {e}")
        
        return self.collected
