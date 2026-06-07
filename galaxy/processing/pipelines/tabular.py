"""Tabular pipeline — CSV, TSV, JSON, Parquet processing."""
import csv
import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger("galaxy.processing.pipelines")


def process(file_path: str, output_dir: str) -> dict:
    """Process a tabular file. Returns stats dict."""
    p = Path(file_path)
    ext = p.suffix.lower()
    out_dir = Path(output_dir) / "tabular" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cleaned_{p.name}"
    
    stats = {"rows": 0, "columns": 0, "format": ext.lstrip('.'), "output": str(out_path)}
    
    try:
        if ext in ('.csv', '.tsv'):
            delimiter = '\t' if ext == '.tsv' else ','
            with open(file_path, 'r', errors='replace', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
            
            if not rows:
                shutil.copy2(file_path, out_path)
                return stats
            
            header = [h.strip() for h in rows[0]]
            data = []
            for row in rows[1:]:
                cleaned = [c.strip() for c in row]
                if any(c for c in cleaned):
                    if len(cleaned) < len(header):
                        cleaned.extend([''] * (len(header) - len(cleaned)))
                    elif len(cleaned) > len(header):
                        cleaned = cleaned[:len(header)]
                    data.append(cleaned)
            
            with open(out_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=delimiter)
                writer.writerow(header)
                writer.writerows(data)
            
            stats["rows"] = len(data)
            stats["columns"] = len(header)
        
        elif ext in ('.json', '.jsonl'):
            with open(file_path, 'r', errors='replace') as f:
                if ext == '.jsonl':
                    records = [json.loads(l) for l in f if l.strip()]
                else:
                    data = json.load(f)
                    records = data if isinstance(data, list) else [data]
            
            cleaned = [{k: v.strip() if isinstance(v, str) else v
                        for k, v in r.items() if v is not None}
                       for r in records if isinstance(r, dict)]
            
            with open(out_path, 'w', encoding='utf-8') as f:
                if ext == '.jsonl':
                    for r in cleaned:
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
                else:
                    json.dump(cleaned, f, indent=2, ensure_ascii=False)
            
            stats["rows"] = len(cleaned)
            if cleaned and isinstance(cleaned[0], dict):
                stats["columns"] = len(cleaned[0])
        
        else:
            shutil.copy2(file_path, out_path)
    
    except Exception as e:
        log.warning(f"Tabular pipeline error: {e}")
        shutil.copy2(file_path, out_path)
    
    return stats
