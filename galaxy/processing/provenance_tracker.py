"""Provenance tracker - records what happened to each dataset."""
import json
import time
import logging
from pathlib import Path

log = logging.getLogger("galaxy.processing")


class ProvenanceTracker:
    """Track all transformations applied to datasets."""
    
    def __init__(self, workspace_path: str):
        self._workspace = Path(workspace_path)
        self._events: list[dict] = []
    
    def record(self, dataset_path: str, action: str, details: dict = None):
        """Record a processing event."""
        event = {
            "dataset": dataset_path,
            "action": action,
            "timestamp": time.time(),
            "details": details or {},
        }
        self._events.append(event)
        log.debug(f"Provenance: {action} on {Path(dataset_path).name}")
    
    def save(self):
        """Save provenance log."""
        out = self._workspace / "metadata" / "provenance.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self._events, indent=2))
    
    def get_history(self, dataset_path: str) -> list[dict]:
        """Get all events for a dataset."""
        return [e for e in self._events if e["dataset"] == dataset_path]
