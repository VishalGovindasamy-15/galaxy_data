"""Base spider - common collection logic."""
import os
import json
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any

from galaxy.types import CollectedFile
from galaxy.utils.hashing import hash_file
from galaxy.collection.rate_limiter import RateLimiter
from galaxy.collection.circuit_breaker import CircuitBreaker
from galaxy.collection.legal_checker import LegalChecker

log = logging.getLogger("galaxy.spiders")


class BaseCollector:
    """Base class for all data collectors."""
    
    source_id: str = "base"
    
    def __init__(self, workspace_raw_dir: str, rate_limiter: RateLimiter = None,
                 circuit_breaker: CircuitBreaker = None):
        self.workspace_raw_dir = Path(workspace_raw_dir)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.legal = LegalChecker()
        self.collected: list[CollectedFile] = []
        self._source_dir = self.workspace_raw_dir / f"source_{self.source_id}"
        self._source_dir.mkdir(parents=True, exist_ok=True)
    
    def _fetch_url(self, url: str, timeout: int = 30) -> bytes:
        """Fetch URL content using Scrapling's Fetcher."""
        from scrapling.fetchers import Fetcher
        domain = urllib.parse.urlparse(url).netloc
        
        if not self.circuit_breaker.can_request(domain):
            raise ConnectionError(f"Circuit open for {domain}")
        
        self.rate_limiter.acquire_sync(domain)
        
        try:
            fetcher = Fetcher(timeout=timeout, auto_match=False)
            response = fetcher.get(url, timeout=timeout)
            self.circuit_breaker.record_success(domain)
            return response.body if hasattr(response, 'body') else b""
        except Exception as e:
            self.circuit_breaker.record_failure(domain)
            raise
    
    def _fetch_text(self, url: str, timeout: int = 30) -> str:
        """Fetch URL and return text content."""
        from scrapling.fetchers import Fetcher
        domain = urllib.parse.urlparse(url).netloc
        self.rate_limiter.acquire_sync(domain)
        try:
            fetcher = Fetcher(timeout=timeout, auto_match=False)
            response = fetcher.get(url, timeout=timeout)
            self.circuit_breaker.record_success(domain)
            if hasattr(response, 'text'):
                return response.text
            return response.body.decode('utf-8', errors='replace') if hasattr(response, 'body') else ""
        except Exception as e:
            self.circuit_breaker.record_failure(domain)
            raise
    
    def _download_file(self, url: str, filename: str = None) -> str | None:
        """Download file to workspace. Returns local path or None."""
        if not filename:
            parsed = urllib.parse.urlparse(url)
            filename = Path(parsed.path).name or "data.bin"
            # Clean filename
            filename = "".join(c for c in filename if c.isalnum() or c in ".-_")
            if not filename:
                filename = f"file_{hash(url) % 100000}"
        
        dest = self._source_dir / filename
        if dest.exists():
            log.debug(f"Already exists: {dest}")
            return str(dest)
        
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                dest.write_bytes(data)
            log.info(f"Downloaded: {url} -> {dest.name} ({len(data)} bytes)")
            return str(dest)
        except Exception as e:
            log.warning(f"Download failed: {url} -> {e}")
            return None
    
    def _register_file(self, path: str, url: str, fmt: str = "", metadata: dict = None) -> CollectedFile:
        """Register a collected file."""
        p = Path(path)
        file_hash = hash_file(path)
        cf = CollectedFile(
            path=path,
            hash=file_hash,
            size_bytes=p.stat().st_size,
            source_id=self.source_id,
            format=fmt or p.suffix.lstrip('.'),
            url=url,
            metadata=metadata or {},
        )
        self.collected.append(cf)
        return cf
    
    def _save_source_metadata(self):
        """Save metadata about what was collected."""
        meta = {
            "source_id": self.source_id,
            "collected_at": time.time(),
            "files_count": len(self.collected),
            "files": [{"path": f.path, "url": f.url, "hash": f.hash, "size": f.size_bytes, "format": f.format}
                      for f in self.collected],
        }
        (self._source_dir / "source_metadata.json").write_text(json.dumps(meta, indent=2))
    
    def collect(self, query: str) -> list[CollectedFile]:
        """Override in subclass. Collect datasets matching query."""
        raise NotImplementedError
