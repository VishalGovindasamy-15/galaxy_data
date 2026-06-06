"""Processing Router - routes files to the correct pipeline by data type."""
import logging
from pathlib import Path
from galaxy.types import DataType, DatasetInfo, CollectedFile, ValidationResult
from galaxy.processing import validator, schema_detector, quality_scorer, cleaner
from galaxy.processing.deduplicator import Deduplicator
from galaxy.processing.provenance_tracker import ProvenanceTracker

log = logging.getLogger("galaxy.processing")


class ProcessingRouter:
    """Routes collected files to appropriate processing pipeline by data type."""
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.processed_dir = self.workspace / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.dedup = Deduplicator()
        self.provenance = ProvenanceTracker(workspace_path)
    
    def process_all(self, collected_files: list[CollectedFile]) -> list[DatasetInfo]:
        """Process all collected files through appropriate pipelines."""
        results = []
        
        for cf in collected_files:
            try:
                result = self._process_single(cf)
                if result:
                    results.append(result)
            except Exception as e:
                log.error(f"Processing failed for {cf.path}: {e}")
                self.provenance.record(cf.path, "processing_error", {"error": str(e)})
        
        self.provenance.save()
        return results
    
    def _process_single(self, cf: CollectedFile) -> DatasetInfo | None:
        """Process a single file through the pipeline."""
        file_path = cf.path
        
        # Stage 1: Validate
        val = validator.validate(file_path)
        self.provenance.record(file_path, "validated", {"valid": val.valid, "type": val.data_type.value})
        
        if not val.valid:
            log.warning(f"Skipping invalid file: {file_path} ({val.errors})")
            self.provenance.record(file_path, "skipped", {"reason": "validation_failed"})
            return None
        
        # Stage 2: Dedup
        dedup_result = self.dedup.check_exact(file_path)
        if dedup_result.is_duplicate:
            log.info(f"Skipping duplicate: {file_path}")
            self.provenance.record(file_path, "skipped", {"reason": "duplicate"})
            return None
        
        # Stage 3: Detect schema
        schema = schema_detector.detect(file_path)
        self.provenance.record(file_path, "schema_detected", {"columns": len(schema.columns)})
        
        # Stage 4: Quality score
        quality = quality_scorer.score(file_path)
        self.provenance.record(file_path, "quality_scored", {"score": quality.score})
        
        # Stage 5: Clean
        cleaned_path = cleaner.clean(file_path, str(self.processed_dir))
        self.provenance.record(file_path, "cleaned", {"output": cleaned_path})
        
        # Build result
        p = Path(cleaned_path)
        info = DatasetInfo(
            path=cleaned_path,
            schema=schema.columns,
            quality_score=quality.score,
            row_count=val.row_count,
            column_count=len(schema.columns),
            format=val.format,
            source_id=cf.source_id,
            license=cf.metadata.get("license", "unknown"),
            dedup_status="unique",
            data_type=val.data_type,
        )
        
        log.info(f"Processed: {p.name} | quality={quality.score:.2f} | rows={val.row_count} | type={val.data_type.value}")
        return info
