"""Dataset lineage tracking - where data came from, what happened to it."""
import json
import time
import uuid
import logging
from pathlib import Path
from galaxy.types import LineageRecord
from galaxy.config import Config

log = logging.getLogger("galaxy.lineage")


class DatasetLineage:
    """Track full provenance of every dataset."""
    
    def __init__(self, workspace_path: str = None):
        self._records: dict[str, LineageRecord] = {}
        self._storage = Path(workspace_path) / "metadata" / "lineage.json" if workspace_path else None
    
    def create(self, dataset_path: str, source_url: str, source_id: str,
               parent_files: list[str] = None) -> LineageRecord:
        """Create a new lineage record for a dataset."""
        record = LineageRecord(
            lineage_id=f"lin_{uuid.uuid4().hex[:10]}",
            dataset_path=dataset_path,
            source_url=source_url,
            source_id=source_id,
            parent_files=parent_files or [],
        )
        self._records[record.lineage_id] = record
        log.debug(f"Lineage created: {record.lineage_id} for {dataset_path}")
        return record
    
    def add_transformation(self, lineage_id: str, action: str, details: dict = None):
        """Record a transformation step."""
        if lineage_id in self._records:
            self._records[lineage_id].transformations.append({
                "action": action,
                "timestamp": time.time(),
                "details": details or {},
            })
    
    def mark_removed(self, lineage_id: str, reason: str):
        """Record why a dataset was removed."""
        if lineage_id in self._records:
            self._records[lineage_id].removal_reason = reason
    
    def update_quality(self, lineage_id: str, score: float):
        if lineage_id in self._records:
            self._records[lineage_id].quality_score_history.append(score)
    
    def get(self, lineage_id: str) -> LineageRecord | None:
        return self._records.get(lineage_id)
    
    def get_all(self) -> list[LineageRecord]:
        return list(self._records.values())
    
    def save(self):
        """Persist lineage records to disk."""
        if self._storage:
            self._storage.parent.mkdir(parents=True, exist_ok=True)
            data = []
            for r in self._records.values():
                data.append({
                    "lineage_id": r.lineage_id,
                    "dataset_path": r.dataset_path,
                    "source_url": r.source_url,
                    "source_id": r.source_id,
                    "collection_timestamp": r.collection_timestamp,
                    "transformations": r.transformations,
                    "parent_files": r.parent_files,
                    "removal_reason": r.removal_reason,
                    "quality_score_history": r.quality_score_history,
                })
            self._storage.write_text(json.dumps(data, indent=2))
