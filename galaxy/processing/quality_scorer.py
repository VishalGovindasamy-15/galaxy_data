"""Quality scorer - score datasets on completeness, consistency, format."""
import csv
import json
import logging
from pathlib import Path
from galaxy.types import QualityReport

log = logging.getLogger("galaxy.processing")


def score(file_path: str) -> QualityReport:
    """Score dataset quality. Returns 0.0-1.0."""
    p = Path(file_path)
    ext = p.suffix.lower()
    issues = []
    completeness = 1.0
    consistency = 1.0
    
    try:
        if ext in ('.csv', '.tsv'):
            delimiter = '\t' if ext == '.tsv' else ','
            with open(file_path, 'r', errors='replace') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
            
            if len(rows) < 2:
                issues.append("Too few rows")
                return QualityReport(score=0.1, completeness=0.0, issues=issues)
            
            header = rows[0]
            data_rows = rows[1:]
            
            # Completeness: check for empty cells
            total_cells = len(header) * len(data_rows)
            empty_cells = sum(1 for row in data_rows for cell in row if not cell.strip())
            completeness = 1.0 - (empty_cells / max(total_cells, 1))
            
            # Consistency: check row lengths match header
            inconsistent = sum(1 for row in data_rows if len(row) != len(header))
            consistency = 1.0 - (inconsistent / max(len(data_rows), 1))
            
            if completeness < 0.5:
                issues.append(f"Low completeness: {completeness:.1%} cells filled")
            if consistency < 0.8:
                issues.append(f"Inconsistent row lengths: {inconsistent} mismatches")
            if len(data_rows) < 10:
                issues.append("Very few data rows")
        
        elif ext in ('.json', '.jsonl'):
            with open(file_path, 'r', errors='replace') as f:
                if ext == '.jsonl':
                    records = [json.loads(l) for l in f if l.strip()]
                else:
                    data = json.load(f)
                    records = data if isinstance(data, list) else [data]
            
            if not records:
                return QualityReport(score=0.1, completeness=0.0, issues=["Empty JSON"])
            
            if isinstance(records[0], dict):
                all_keys = set()
                for r in records:
                    all_keys.update(r.keys())
                total = len(all_keys) * len(records)
                present = sum(1 for r in records for k in all_keys if k in r and r[k] is not None)
                completeness = present / max(total, 1)
            
            if len(records) < 10:
                issues.append("Very few records")
        
        elif ext == '.txt':
            with open(file_path, 'r', errors='replace') as f:
                lines = f.readlines()
            if len(lines) < 5:
                issues.append("Very few lines")
            completeness = min(len(lines) / 100, 1.0)
        
        else:
            # For other formats, basic size check
            size = p.stat().st_size
            completeness = min(size / 10000, 1.0)
    
    except Exception as e:
        issues.append(f"Error scoring: {e}")
        completeness = 0.3
    
    # Final score
    final_score = (completeness * 0.6 + consistency * 0.4)
    if issues:
        final_score *= 0.9
    
    return QualityReport(score=round(final_score, 3), completeness=round(completeness, 3),
                        consistency=round(consistency, 3), issues=issues)
