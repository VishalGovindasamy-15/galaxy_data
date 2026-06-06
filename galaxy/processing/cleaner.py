"""Data cleaner - normalize encoding, clean whitespace, fix formatting."""
import csv
import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger("galaxy.processing")


def clean(file_path: str, output_dir: str) -> str:
    """Clean a data file. Returns path to cleaned file."""
    p = Path(file_path)
    ext = p.suffix.lower()
    out_path = Path(output_dir) / f"cleaned_{p.name}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        if ext in ('.csv', '.tsv'):
            return _clean_csv(file_path, str(out_path), '\t' if ext == '.tsv' else ',')
        elif ext in ('.json', '.jsonl'):
            return _clean_json(file_path, str(out_path), ext)
        elif ext == '.txt':
            return _clean_text(file_path, str(out_path))
        else:
            # For unsupported formats, just copy
            shutil.copy2(file_path, out_path)
            return str(out_path)
    except Exception as e:
        log.warning(f"Cleaning failed for {file_path}: {e}, copying as-is")
        shutil.copy2(file_path, out_path)
        return str(out_path)


def _clean_csv(file_path: str, out_path: str, delimiter: str) -> str:
    """Clean CSV: trim whitespace, remove empty rows, normalize encoding."""
    with open(file_path, 'r', errors='replace', encoding='utf-8') as fin:
        reader = csv.reader(fin, delimiter=delimiter)
        rows = list(reader)
    
    if not rows:
        shutil.copy2(file_path, out_path)
        return out_path
    
    # Clean: trim whitespace, skip fully empty rows
    cleaned = []
    header = [h.strip() for h in rows[0]]
    cleaned.append(header)
    
    for row in rows[1:]:
        cleaned_row = [cell.strip() for cell in row]
        if any(cell for cell in cleaned_row):  # skip fully empty
            # Pad or trim to match header length
            if len(cleaned_row) < len(header):
                cleaned_row.extend([''] * (len(header) - len(cleaned_row)))
            elif len(cleaned_row) > len(header):
                cleaned_row = cleaned_row[:len(header)]
            cleaned.append(cleaned_row)
    
    with open(out_path, 'w', newline='', encoding='utf-8') as fout:
        writer = csv.writer(fout, delimiter=delimiter)
        writer.writerows(cleaned)
    
    log.info(f"Cleaned CSV: {len(rows)} -> {len(cleaned)} rows")
    return out_path


def _clean_json(file_path: str, out_path: str, ext: str) -> str:
    """Clean JSON: normalize, remove nulls."""
    with open(file_path, 'r', errors='replace') as f:
        if ext == '.jsonl':
            records = [json.loads(l) for l in f if l.strip()]
        else:
            data = json.load(f)
            records = data if isinstance(data, list) else [data]
    
    # Clean: strip string values
    cleaned = []
    for record in records:
        if isinstance(record, dict):
            clean_rec = {k: v.strip() if isinstance(v, str) else v for k, v in record.items() if v is not None}
            cleaned.append(clean_rec)
        else:
            cleaned.append(record)
    
    with open(out_path, 'w', encoding='utf-8') as f:
        if ext == '.jsonl':
            for r in cleaned:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        else:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
    
    return out_path


def _clean_text(file_path: str, out_path: str) -> str:
    """Clean text: normalize line endings, strip whitespace."""
    with open(file_path, 'r', errors='replace') as f:
        lines = f.readlines()
    
    cleaned = [line.rstrip() + '\n' for line in lines if line.strip()]
    
    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(cleaned)
    
    return out_path
