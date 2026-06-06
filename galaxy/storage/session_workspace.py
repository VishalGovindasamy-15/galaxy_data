"""Session workspace management."""
import shutil
import json
import time
import logging
from pathlib import Path
from galaxy.config import Config

log = logging.getLogger("galaxy.storage")


class SessionWorkspace:
    """Manages temporary workspace for each session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.root = Config.WORKSPACE_DIR / session_id
        self.raw_dir = self.root / "raw"
        self.processed_dir = self.root / "processed"
        self.final_dir = self.root / "final"
        self.metadata_dir = self.root / "metadata"
    
    def create(self) -> "SessionWorkspace":
        """Create workspace directory structure."""
        for d in [self.raw_dir, self.processed_dir, self.final_dir, self.metadata_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self._write_meta({"session_id": self.session_id, "created_at": time.time(), "state": "created"})
        log.info(f"Workspace created: {self.root}")
        return self
    
    def source_dir(self, source_id: str) -> Path:
        """Get/create directory for a specific source."""
        d = self.raw_dir / f"source_{source_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d
    
    def _write_meta(self, data: dict):
        (self.metadata_dir / "session_info.json").write_text(json.dumps(data, indent=2))
    
    def update_progress(self, progress: dict):
        (self.metadata_dir / "progress.json").write_text(json.dumps(progress, indent=2))
    
    def list_raw_files(self) -> list[Path]:
        """List all files in raw directory."""
        if not self.raw_dir.exists():
            return []
        return [f for f in self.raw_dir.rglob("*") if f.is_file() and f.name != "source_metadata.json"]
    
    def list_processed_files(self) -> list[Path]:
        if not self.processed_dir.exists():
            return []
        return [f for f in self.processed_dir.rglob("*") if f.is_file()]
    
    def cleanup(self):
        """Remove the workspace."""
        if self.root.exists():
            shutil.rmtree(self.root)
            log.info(f"Workspace cleaned: {self.root}")
    
    @property
    def exists(self) -> bool:
        return self.root.exists()
