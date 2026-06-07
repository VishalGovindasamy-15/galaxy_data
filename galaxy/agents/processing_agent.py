"""Processing agent — coordinates the full processing pipeline."""
import logging
from pathlib import Path
from galaxy.types import CollectedFile, DatasetInfo
from galaxy.processing.router import ProcessingRouter

log = logging.getLogger("galaxy.agents")


class ProcessingAgent:
    """Runs the processing pipeline on collected files."""
    
    def __init__(self, workspace_path: str):
        self.router = ProcessingRouter(workspace_path)
    
    def process(self, files: list[CollectedFile]) -> list[DatasetInfo]:
        """Process all files through validation, dedup, quality, cleaning."""
        log.info(f"Processing agent: {len(files)} files")
        results = self.router.process_all(files)
        log.info(f"Processing complete: {len(results)} datasets")
        return results
