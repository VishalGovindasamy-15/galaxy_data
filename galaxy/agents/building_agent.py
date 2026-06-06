"""Building agent - packages final output with README, reports, lineage."""
import csv
import json
import time
import logging
import shutil
from pathlib import Path
from galaxy.types import DatasetInfo, BuildResult, ProcessingResult
from galaxy.processing.merger import merge_csv_files, merge_json_files

log = logging.getLogger("galaxy.agents")


class BuildingAgent:
    """Package processed datasets into final deliverable."""
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.final_dir = self.workspace / "final"
        self.final_dir.mkdir(parents=True, exist_ok=True)
    
    def build(self, session_id: str, datasets: list[DatasetInfo], query: str = "",
              merge: bool = False) -> BuildResult:
        """Build final package."""
        log.info(f"Building final package: {len(datasets)} datasets")
        
        total_rows = 0
        total_size = 0
        
        if merge and len(datasets) > 1:
            # Group by format and merge
            csv_files = [d.path for d in datasets if d.format in ('csv', 'tsv')]
            json_files = [d.path for d in datasets if d.format in ('json', 'jsonl')]
            other_files = [d.path for d in datasets if d.format not in ('csv', 'tsv', 'json', 'jsonl')]
            
            if csv_files:
                merged = merge_csv_files(csv_files, str(self.final_dir / "merged_dataset.csv"))
                total_size += Path(merged).stat().st_size
            if json_files:
                merged = merge_json_files(json_files, str(self.final_dir / "merged_dataset.json"))
                total_size += Path(merged).stat().st_size
            for f in other_files:
                dest = self.final_dir / Path(f).name
                shutil.copy2(f, dest)
                total_size += dest.stat().st_size
        else:
            # Copy all processed datasets to final
            for ds in datasets:
                dest = self.final_dir / Path(ds.path).name
                if Path(ds.path).exists():
                    shutil.copy2(ds.path, dest)
                    total_size += dest.stat().st_size
        
        for ds in datasets:
            total_rows += ds.row_count
        
        # Generate README
        self._generate_readme(datasets, query)
        
        # Generate quality report
        quality_report_path = self._generate_quality_report(datasets)
        
        # Generate sources list
        self._generate_sources(datasets)
        
        # Copy lineage if exists
        lineage_src = self.workspace / "metadata" / "lineage.json"
        if lineage_src.exists():
            shutil.copy2(lineage_src, self.final_dir / "LINEAGE.json")
        
        # Copy provenance
        prov_src = self.workspace / "metadata" / "provenance.json"
        if prov_src.exists():
            shutil.copy2(prov_src, self.final_dir / "PROVENANCE.json")
        
        avg_quality = sum(d.quality_score for d in datasets) / max(len(datasets), 1)
        
        result = BuildResult(
            session_id=session_id,
            package_path=str(self.final_dir),
            size_bytes=total_size,
            datasets_count=len(datasets),
            total_samples=total_rows,
            quality_score=round(avg_quality, 3),
            reports=[quality_report_path],
        )
        
        log.info(f"Build complete: {result.datasets_count} datasets, {result.total_samples} rows, quality={result.quality_score:.2f}")
        return result
    
    def _generate_readme(self, datasets: list[DatasetInfo], query: str):
        lines = [
            "# Galaxy Data - Dataset Package\n",
            f"\n**Query:** {query}\n",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"**Datasets:** {len(datasets)}\n",
            f"**Total rows:** {sum(d.row_count for d in datasets)}\n",
            "\n## Contents\n",
        ]
        for ds in datasets:
            lines.append(f"- **{Path(ds.path).name}** | {ds.format} | {ds.row_count} rows | quality: {ds.quality_score:.2f} | source: {ds.source_id}\n")
        
        lines.append("\n## Sources\n")
        sources = set(d.source_id for d in datasets)
        for s in sources:
            lines.append(f"- {s}\n")
        
        (self.final_dir / "README.md").write_text("".join(lines))
    
    def _generate_quality_report(self, datasets: list[DatasetInfo]) -> str:
        report = {
            "generated_at": time.time(),
            "datasets_count": len(datasets),
            "avg_quality": round(sum(d.quality_score for d in datasets) / max(len(datasets), 1), 3),
            "datasets": [{
                "name": Path(d.path).name,
                "quality_score": d.quality_score,
                "rows": d.row_count,
                "columns": d.column_count,
                "format": d.format,
                "source": d.source_id,
                "license": d.license,
            } for d in datasets],
        }
        path = str(self.final_dir / "QUALITY_REPORT.json")
        Path(path).write_text(json.dumps(report, indent=2))
        return path
    
    def _generate_sources(self, datasets: list[DatasetInfo]):
        sources = set()
        for d in datasets:
            sources.add(f"Source: {d.source_id} | License: {d.license}")
        (self.final_dir / "SOURCES.txt").write_text("\n".join(sorted(sources)))
