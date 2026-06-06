"""Schema detector - detect columns, types, and patterns."""
import csv
import json
import logging
from pathlib import Path
from galaxy.types import Schema

log = logging.getLogger("galaxy.processing")


def _infer_type(values: list[str]) -> str:
    """Infer column type from sample values."""
    int_count = float_count = 0
    for v in values[:100]:
        v = v.strip()
        if not v:
            continue
        try:
            int(v)
            int_count += 1
            continue
        except ValueError:
            pass
        try:
            float(v)
            float_count += 1
        except ValueError:
            pass
    total = len([v for v in values[:100] if v.strip()])
    if total == 0:
        return "empty"
    if int_count / total > 0.8:
        return "integer"
    if (int_count + float_count) / total > 0.8:
        return "float"
    return "string"


def detect(file_path: str) -> Schema:
    """Detect schema of a data file."""
    p = Path(file_path)
    ext = p.suffix.lower()
    columns = {}
    patterns = {}
    
    try:
        if ext in ('.csv', '.tsv'):
            delimiter = '\t' if ext == '.tsv' else ','
            with open(file_path, 'r', errors='replace') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames or []
                # Collect sample values
                samples = {h: [] for h in headers}
                for i, row in enumerate(reader):
                    if i >= 100:
                        break
                    for h in headers:
                        samples[h].append(row.get(h, ''))
                
                for h in headers:
                    columns[h] = _infer_type(samples[h])
                
                patterns["delimiter"] = delimiter
                patterns["columns_count"] = len(headers)
        
        elif ext in ('.json', '.jsonl'):
            with open(file_path, 'r', errors='replace') as f:
                if ext == '.jsonl':
                    lines = [json.loads(line) for line in f if line.strip()][:100]
                else:
                    data = json.load(f)
                    lines = data if isinstance(data, list) else [data]
                    lines = lines[:100]
            
            if lines and isinstance(lines[0], dict):
                all_keys = set()
                for item in lines:
                    all_keys.update(item.keys())
                for key in all_keys:
                    values = [str(item.get(key, '')) for item in lines]
                    columns[key] = _infer_type(values)
                patterns["columns_count"] = len(all_keys)
        
        elif ext == '.txt':
            with open(file_path, 'r', errors='replace') as f:
                first_lines = [f.readline() for _ in range(5)]
            patterns["sample_lines"] = len(first_lines)
            columns["text_content"] = "string"
    
    except Exception as e:
        log.warning(f"Schema detection failed for {file_path}: {e}")
    
    return Schema(columns=columns, patterns=patterns)
