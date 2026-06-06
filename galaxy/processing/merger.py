"""Merger - merge multiple datasets into one."""
import csv
import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger("galaxy.processing")


def merge_csv_files(file_paths: list[str], output_path: str) -> str:
    """Merge multiple CSV files into one. Aligns columns."""
    if not file_paths:
        return output_path
    
    if len(file_paths) == 1:
        shutil.copy2(file_paths[0], output_path)
        return output_path
    
    # Collect all headers
    all_headers = []
    seen = set()
    for fp in file_paths:
        try:
            with open(fp, 'r', errors='replace') as f:
                reader = csv.reader(f)
                headers = next(reader, [])
                for h in headers:
                    h = h.strip()
                    if h and h not in seen:
                        all_headers.append(h)
                        seen.add(h)
        except Exception:
            continue
    
    # Merge all rows
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as fout:
        writer = csv.DictWriter(fout, fieldnames=all_headers, extrasaction='ignore')
        writer.writeheader()
        
        for fp in file_paths:
            try:
                with open(fp, 'r', errors='replace') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        cleaned = {k.strip(): v for k, v in row.items() if k}
                        writer.writerow(cleaned)
            except Exception as e:
                log.warning(f"Error merging {fp}: {e}")
    
    log.info(f"Merged {len(file_paths)} files -> {output_path}")
    return output_path


def merge_json_files(file_paths: list[str], output_path: str) -> str:
    """Merge multiple JSON/JSONL files."""
    all_records = []
    for fp in file_paths:
        try:
            ext = Path(fp).suffix.lower()
            with open(fp, 'r', errors='replace') as f:
                if ext == '.jsonl':
                    records = [json.loads(l) for l in f if l.strip()]
                else:
                    data = json.load(f)
                    records = data if isinstance(data, list) else [data]
                all_records.extend(records)
        except Exception as e:
            log.warning(f"Error merging {fp}: {e}")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    
    log.info(f"Merged {len(file_paths)} JSON files -> {len(all_records)} records")
    return output_path
