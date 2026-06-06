"""Content-addressable permanent dataset store."""
import shutil
import json
import logging
from pathlib import Path
from galaxy.config import Config
from galaxy.utils.hashing import hash_file

log = logging.getLogger("galaxy.storage")


class DatasetStore:
    """Permanent store indexed by content hash."""
    
    def __init__(self):
        self.root = Config.PERMANENT_STORE_DIR
        self.root.mkdir(parents=True, exist_ok=True)
    
    def store(self, file_path: str, metadata: dict = None) -> str:
        """Store a file, returns its hash."""
        file_hash = hash_file(file_path)
        dest_dir = self.root / file_hash[:2] / file_hash
        if dest_dir.exists():
            log.debug(f"File already stored: {file_hash}")
            return file_hash
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = Path(file_path)
        shutil.copy2(src, dest_dir / src.name)
        if metadata:
            (dest_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        log.info(f"Stored: {src.name} -> {file_hash}")
        return file_hash
    
    def retrieve(self, file_hash: str) -> Path | None:
        """Get file path by hash."""
        dest_dir = self.root / file_hash[:2] / file_hash
        if not dest_dir.exists():
            return None
        files = [f for f in dest_dir.iterdir() if f.name != "metadata.json"]
        return files[0] if files else None
    
    def exists(self, file_hash: str) -> bool:
        return (self.root / file_hash[:2] / file_hash).exists()
