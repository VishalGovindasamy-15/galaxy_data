"""Crawler pool - manages fetching using urllib + optional Scrapling."""
import logging
import urllib.request
from typing import Any

log = logging.getLogger("galaxy.collection")


class CrawlerPool:
    """Manages HTTP fetching. Uses urllib (always available)."""
    
    def __init__(self, http_pool_size: int = 10, timeout: int = 30):
        self.http_pool_size = http_pool_size
        self.timeout = timeout
    
    def fetch_sync(self, url: str, **kwargs) -> bytes:
        """Synchronous HTTP fetch."""
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except Exception as e:
            log.error(f"Fetch failed: {url} -> {e}")
            raise
    
    def download_file(self, url: str, dest_path: str) -> bool:
        """Download a file from URL to disk."""
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest_path, 'wb') as f:
                    f.write(resp.read())
            log.info(f"Downloaded: {url} -> {dest_path}")
            return True
        except Exception as e:
            log.error(f"Download failed: {url} -> {e}")
            return False
