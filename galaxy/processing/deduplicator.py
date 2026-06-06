"""Deduplicator - exact hash and content-based dedup."""
import logging
from galaxy.types import DedupResult
from galaxy.utils.hashing import hash_file

log = logging.getLogger("galaxy.processing")


class Deduplicator:
    """Multi-level deduplication engine."""
    
    def __init__(self):
        self._hash_registry: dict[str, str] = {}  # hash -> first_file_path
    
    def check_exact(self, file_path: str) -> DedupResult:
        """L1: Exact file hash check."""
        file_hash = hash_file(file_path)
        if file_hash in self._hash_registry:
            log.info(f"Duplicate found: {file_path} == {self._hash_registry[file_hash]}")
            return DedupResult(is_duplicate=True, original_hash=file_hash, similarity=1.0)
        self._hash_registry[file_hash] = file_path
        return DedupResult(is_duplicate=False, original_hash=file_hash)
    
    def get_unique_files(self, file_paths: list[str]) -> list[str]:
        """Filter out exact duplicates, return unique files."""
        unique = []
        for fp in file_paths:
            result = self.check_exact(fp)
            if not result.is_duplicate:
                unique.append(fp)
            else:
                log.info(f"Removing duplicate: {fp}")
        return unique
