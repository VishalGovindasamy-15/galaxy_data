"""Processing Router — routes files to typed pipelines, organizes output by type."""
import json
import logging
import shutil
from pathlib import Path
from galaxy.types import DataType, DatasetInfo, CollectedFile
from galaxy.processing import validator, schema_detector, quality_scorer
from galaxy.processing.deduplicator import Deduplicator
from galaxy.processing.provenance_tracker import ProvenanceTracker
from galaxy.processing.pipelines import tabular as tabular_pipeline
from galaxy.processing.pipelines import document as document_pipeline
from galaxy.processing.pipelines import image as image_pipeline
from galaxy.processing.pipelines import generic as generic_pipeline

log = logging.getLogger("galaxy.processing")

# Type → pipeline mapping
TYPE_PIPELINE = {
    DataType.TABULAR: tabular_pipeline,
    DataType.DOCUMENT: document_pipeline,
    DataType.IMAGE: image_pipeline,
    DataType.AUDIO: generic_pipeline,
    DataType.VIDEO: generic_pipeline,
    DataType.GENERIC: generic_pipeline,
}

# Extension → DataType mapping
EXT_TYPE_MAP = {
    '.csv': DataType.TABULAR, '.tsv': DataType.TABULAR,
    '.json': DataType.TABULAR, '.jsonl': DataType.TABULAR,
    '.parquet': DataType.TABULAR, '.xlsx': DataType.TABULAR,
    '.txt': DataType.DOCUMENT, '.md': DataType.DOCUMENT,
    '.html': DataType.DOCUMENT, '.htm': DataType.DOCUMENT,
    '.pdf': DataType.DOCUMENT, '.xml': DataType.DOCUMENT,
    '.rtf': DataType.DOCUMENT,
    '.jpg': DataType.IMAGE, '.jpeg': DataType.IMAGE,
    '.png': DataType.IMAGE, '.gif': DataType.IMAGE,
    '.bmp': DataType.IMAGE, '.webp': DataType.IMAGE,
    '.tiff': DataType.IMAGE, '.svg': DataType.IMAGE,
    '.mp3': DataType.AUDIO, '.wav': DataType.AUDIO,
    '.flac': DataType.AUDIO, '.ogg': DataType.AUDIO,
    '.m4a': DataType.AUDIO, '.aac': DataType.AUDIO,
    '.mp4': DataType.VIDEO, '.avi': DataType.VIDEO,
    '.mkv': DataType.VIDEO, '.mov': DataType.VIDEO,
    '.webm': DataType.VIDEO, '.flv': DataType.VIDEO,
}


class ProcessingRouter:
    """Routes collected files to typed processing pipelines.
    Output is organized by data type into separate folders."""
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.processed_dir = self.workspace / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.dedup = Deduplicator()
        self.provenance = ProvenanceTracker(workspace_path)
    
    def process_all(self, collected_files: list[CollectedFile]) -> list[DatasetInfo]:
        """Process all collected files through typed pipelines."""
        results = []
        type_counts = {}
        
        for cf in collected_files:
            try:
                result = self._process_single(cf)
                if result:
                    results.append(result)
                    t = result.data_type.value
                    type_counts[t] = type_counts.get(t, 0) + 1
            except Exception as e:
                log.error(f"Processing failed for {cf.path}: {e}")
                self.provenance.record(cf.path, "processing_error", {"error": str(e)})
        
        # Write per-type metadata
        self._write_type_metadata(results)
        self.provenance.save()
        
        log.info(f"Processing: {len(results)} datasets by type: {type_counts}")
        return results
    
    def _process_single(self, cf: CollectedFile) -> DatasetInfo | None:
        """Process a single file through the appropriate pipeline."""
        file_path = cf.path
        p = Path(file_path)
        
        if not p.exists():
            return None
        
        # 1. Detect type
        data_type = EXT_TYPE_MAP.get(p.suffix.lower(), DataType.GENERIC)
        
        # 2. Validate
        val = validator.validate(file_path)
        self.provenance.record(file_path, "validated", {"valid": val.valid, "type": data_type.value})
        
        if not val.valid:
            log.debug(f"Skipping invalid: {p.name}")
            self.provenance.record(file_path, "skipped", {"reason": "validation_failed"})
            return None
        
        # 3. Dedup
        dedup_result = self.dedup.check_exact(file_path)
        if dedup_result.is_duplicate:
            log.debug(f"Skipping duplicate: {p.name}")
            self.provenance.record(file_path, "skipped", {"reason": "duplicate"})
            return None
        
        # 4. Route to typed pipeline
        pipeline = TYPE_PIPELINE.get(data_type, generic_pipeline)
        output_dir = str(self.processed_dir)
        
        if data_type in (DataType.TABULAR,):
            stats = pipeline.process(file_path, output_dir)
        elif data_type == DataType.DOCUMENT:
            stats = pipeline.process(file_path, output_dir)
        elif data_type == DataType.IMAGE:
            stats = pipeline.process(file_path, output_dir)
        else:
            stats = pipeline.process(file_path, output_dir, data_type=data_type)
        
        output_path = stats.get("output", file_path)
        
        # 5. Quality score
        if data_type == DataType.TABULAR:
            quality = quality_scorer.score(output_path)
        else:
            # Media files: quality based on size validity
            from galaxy.types import QualityReport
            size = Path(output_path).stat().st_size if Path(output_path).exists() else 0
            q = min(size / 10000, 1.0) if size > 0 else 0.0
            quality = QualityReport(score=max(q, 0.5) if stats.get("valid", True) else 0.2,
                                    completeness=1.0 if stats.get("valid", True) else 0.0)
        
        self.provenance.record(file_path, "processed", {
            "type": data_type.value, "output": output_path,
            "quality": quality.score
        })
        
        # 6. Schema (tabular only)
        schema_cols = {}
        row_count = stats.get("rows", stats.get("lines", 0))
        col_count = stats.get("columns", 0)
        if data_type == DataType.TABULAR and Path(output_path).exists():
            schema = schema_detector.detect(output_path)
            schema_cols = schema.columns
            col_count = len(schema_cols)
        
        info = DatasetInfo(
            path=output_path,
            schema=schema_cols,
            quality_score=quality.score,
            row_count=row_count,
            column_count=col_count,
            format=stats.get("format", p.suffix.lstrip('.')),
            source_id=cf.source_id,
            license=cf.metadata.get("license", "unknown"),
            dedup_status="unique",
            data_type=data_type,
        )
        
        log.info(f"Processed: {Path(output_path).name} | type={data_type.value} | quality={quality.score:.2f}")
        return info
    
    def _write_type_metadata(self, results: list[DatasetInfo]):
        """Write metadata.json for each data type folder."""
        type_groups = {}
        for r in results:
            t = r.data_type.value
            type_groups.setdefault(t, []).append(r)
        
        for type_name, items in type_groups.items():
            type_dir = self.processed_dir / type_name
            if type_dir.exists():
                meta = {
                    "type": type_name,
                    "count": len(items),
                    "total_rows": sum(i.row_count for i in items),
                    "avg_quality": round(sum(i.quality_score for i in items) / max(len(items), 1), 3),
                    "formats": list(set(i.format for i in items)),
                    "files": [{"name": Path(i.path).name, "quality": i.quality_score,
                              "rows": i.row_count, "format": i.format} for i in items],
                }
                (type_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
