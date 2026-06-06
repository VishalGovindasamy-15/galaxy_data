"""Crawler pool - manages Scrapling fetcher instances."""
import logging
from typing import Any

log = logging.getLogger("galaxy.collection")

# Import Scrapling fetchers
from scrapling.fetchers import Fetcher, AsyncFetcher


class CrawlerPool:
    """Manages Scrapling fetcher instances for HTTP and browser crawling."""
    
    def __init__(self, http_pool_size: int = 10, timeout: int = 30):
        self.http_pool_size = http_pool_size
        self.timeout = timeout
        self._fetcher = Fetcher(timeout=timeout, auto_match=False)
    
    def fetch_sync(self, url: str, **kwargs) -> Any:
        """Synchronous HTTP fetch using Scrapling's Fetcher."""
        try:
            response = self._fetcher.get(url, timeout=self.timeout, **kwargs)
            log.debug(f"Fetched: {url} -> {response.status}")
            return response
        except Exception as e:
            log.error(f"Fetch failed: {url} -> {e}")
            raise
    
    def download_file(self, url: str, dest_path: str) -> bool:
        """Download a file from URL to disk."""
        import urllib.request
        try:
            urllib.request.urlretrieve(url, dest_path)
            log.info(f"Downloaded: {url} -> {dest_path}")
            return True
        except Exception as e:
            log.error(f"Download failed: {url} -> {e}")
            return False
