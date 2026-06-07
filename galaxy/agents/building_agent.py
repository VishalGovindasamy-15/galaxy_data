"""Building agent — packages final datasets into organized, type-separated output."""
import json
import shutil
import time
import logging
from pathlib import Path
from galaxy.types import DatasetInfo, DataType, BuildResult

log = logging.getLogger("galaxy.agents")


class BuildingAgent:
    """Packages processed datasets into final deliverable with typed folders."""
    
    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.final_dir = self.workspace / "final"
        self.processed_dir = self.workspace / "processed"
    
    def build(self, session_id: str, datasets: list[DatasetInfo],
              query: str = "", merge: bool = False) -> BuildResult:
        """Build final package from processed datasets."""
        log.info(f"Building final package: {len(datasets)} datasets")
        
        # Create final directory structure
        self.final_dir.mkdir(parents=True, exist_ok=True)
        
        total_rows = 0
        total_size = 0
        quality_scores = []
        type_stats = {}
        reports = []
        
        # Copy processed files to final, organized by type
        for ds in datasets:
            src = Path(ds.path)
            if not src.exists():
                continue
            
            # Determine type folder
            type_name = ds.data_type.value if ds.data_type != DataType.GENERIC else "other"
            type_dir = self.final_dir / type_name / "data"
            type_dir.mkdir(parents=True, exist_ok=True)
            
            dest = type_dir / src.name
            if not dest.exists():
                shutil.copy2(str(src), str(dest))
            
            total_rows += ds.row_count
            total_size += src.stat().st_size
            quality_scores.append(ds.quality_score)
            
            type_stats.setdefault(type_name, {"count": 0, "rows": 0, "size": 0, "files": []})
            type_stats[type_name]["count"] += 1
            type_stats[type_name]["rows"] += ds.row_count
            type_stats[type_name]["size"] += src.stat().st_size
            type_stats[type_name]["files"].append({
                "name": src.name,
                "format": ds.format,
                "quality": ds.quality_score,
                "rows": ds.row_count,
                "source": ds.source_id,
            })
        
        avg_quality = sum(quality_scores) / max(len(quality_scores), 1) if quality_scores else 0
        
        # Write per-type metadata.json
        for type_name, stats in type_stats.items():
            type_dir = self.final_dir / type_name
            type_dir.mkdir(parents=True, exist_ok=True)
            meta = {
                "type": type_name,
                "count": stats["count"],
                "total_rows": stats["rows"],
                "total_size_bytes": stats["size"],
                "total_size_human": self._human_size(stats["size"]),
                "avg_quality": round(sum(f["quality"] for f in stats["files"]) / max(len(stats["files"]), 1), 3),
                "files": stats["files"],
            }
            (type_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
        
        # Write top-level files
        self._write_readme(query, datasets, type_stats, avg_quality, total_rows, total_size)
        self._write_quality_report(datasets, type_stats, avg_quality)
        self._write_sources(datasets)
        self._write_provenance(datasets)
        self._write_lineage()
        
        reports = [str(f) for f in self.final_dir.rglob("*") if f.is_file()]
        
        result = BuildResult(
            session_id=session_id,
            package_path=str(self.final_dir),
            size_bytes=total_size,
            datasets_count=len(datasets),
            total_samples=total_rows,
            quality_score=round(avg_quality, 3),
            reports=reports,
        )
        
        log.info(f"Build complete: {len(datasets)} datasets in {len(type_stats)} type folders, "
                 f"{total_rows} rows, quality={avg_quality:.2f}, size={self._human_size(total_size)}")
        return result
    
    def _write_readme(self, query, datasets, type_stats, avg_quality, total_rows, total_size):
        lines = [
            f"# Galaxy Data — Dataset Package",
            f"",
            f"**Query:** {query}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## Summary",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Total Datasets | {len(datasets)} |",
            f"| Total Rows | {total_rows:,} |",
            f"| Total Size | {self._human_size(total_size)} |",
            f"| Average Quality | {avg_quality:.2f} |",
            f"| Data Types | {', '.join(type_stats.keys())} |",
            f"",
            f"## Structure",
            f"```",
        ]
        for type_name, stats in type_stats.items():
            lines.append(f"├── {type_name}/")
            lines.append(f"│   ├── data/         ({stats['count']} files, {self._human_size(stats['size'])})")
            lines.append(f"│   └── metadata.json")
        lines.extend([
            f"├── README.md",
            f"├── QUALITY_REPORT.json",
            f"├── SOURCES.txt",
            f"├── PROVENANCE.json",
            f"└── LINEAGE.json",
            f"```",
            f"",
            f"## Data Types",
        ])
        for type_name, stats in type_stats.items():
            lines.append(f"### {type_name.capitalize()}")
            lines.append(f"- **Files:** {stats['count']}")
            lines.append(f"- **Size:** {self._human_size(stats['size'])}")
            if stats['rows'] > 0:
                lines.append(f"- **Rows:** {stats['rows']:,}")
            lines.append("")
        
        (self.final_dir / "README.md").write_text('\n'.join(lines))
    
    def _write_quality_report(self, datasets, type_stats, avg_quality):
        report = {
            "avg_quality": round(avg_quality, 3),
            "datasets_count": len(datasets),
            "type_breakdown": {},
            "datasets": [],
        }
        for type_name, stats in type_stats.items():
            report["type_breakdown"][type_name] = {
                "count": stats["count"],
                "total_rows": stats["rows"],
                "size_bytes": stats["size"],
            }
        for ds in datasets:
            report["datasets"].append({
                "name": Path(ds.path).name,
                "format": ds.format,
                "quality": ds.quality_score,
                "rows": ds.row_count,
                "type": ds.data_type.value,
                "source": ds.source_id,
            })
        (self.final_dir / "QUALITY_REPORT.json").write_text(json.dumps(report, indent=2))
    
    def _write_sources(self, datasets):
        sources = sorted(set(ds.source_id for ds in datasets))
        (self.final_dir / "SOURCES.txt").write_text('\n'.join(sources) + '\n')
    
    def _write_provenance(self, datasets):
        prov_path = self.workspace / "metadata" / "provenance.json"
        if prov_path.exists():
            shutil.copy2(str(prov_path), str(self.final_dir / "PROVENANCE.json"))
        else:
            (self.final_dir / "PROVENANCE.json").write_text("[]")
    
    def _write_lineage(self):
        lin_path = self.workspace / "metadata" / "lineage.json"
        if lin_path.exists():
            shutil.copy2(str(lin_path), str(self.final_dir / "LINEAGE.json"))
        else:
            (self.final_dir / "LINEAGE.json").write_text("[]")
    
    def _human_size(self, size_bytes: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
