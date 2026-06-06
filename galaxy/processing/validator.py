"""File validator - check integrity, format, data type detection."""
import os
import csv
import json
import logging
from pathlib import Path
from galaxy.types import ValidationResult, DataType

log = logging.getLogger("galaxy.processing")

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'}
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'}
TABULAR_EXTS = {'.csv', '.tsv', '.parquet', '.xlsx', '.xls'}
DOC_EXTS = {'.txt', '.pdf', '.html', '.htm', '.md', '.xml', '.rtf'}


def validate(file_path: str) -> ValidationResult:
    """Validate a file: check it exists, is non-empty, detect type."""
    p = Path(file_path)
    errors = []
    
    if not p.exists():
        return ValidationResult(valid=False, errors=["File does not exist"])
    
    size = p.stat().st_size
    if size == 0:
        return ValidationResult(valid=False, errors=["File is empty"])
    
    if size < 50:
        errors.append("File very small (<50 bytes)")
    
    ext = p.suffix.lower()
    data_type = DataType.GENERIC
    fmt = ext.lstrip('.')
    row_count = 0
    
    # Detect type by extension
    if ext in TABULAR_EXTS:
        data_type = DataType.TABULAR
        # Try to count rows
        if ext in ('.csv', '.tsv'):
            try:
                delimiter = '\t' if ext == '.tsv' else ','
                with open(file_path, 'r', errors='replace') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    row_count = sum(1 for _ in reader) - 1  # minus header
                if row_count < 0:
                    row_count = 0
            except Exception as e:
                errors.append(f"CSV parse error: {e}")
    elif ext in ('.json', '.jsonl'):
        data_type = DataType.TABULAR
        try:
            with open(file_path, 'r', errors='replace') as f:
                if ext == '.jsonl':
                    row_count = sum(1 for line in f if line.strip())
                else:
                    data = json.load(f)
                    row_count = len(data) if isinstance(data, list) else 1
        except Exception as e:
            errors.append(f"JSON parse error: {e}")
    elif ext in IMAGE_EXTS:
        data_type = DataType.IMAGE
    elif ext in AUDIO_EXTS:
        data_type = DataType.AUDIO
    elif ext in VIDEO_EXTS:
        data_type = DataType.VIDEO
    elif ext in DOC_EXTS:
        data_type = DataType.DOCUMENT
        try:
            with open(file_path, 'r', errors='replace') as f:
                row_count = sum(1 for _ in f)
        except Exception:
            pass
    
    valid = len(errors) == 0 or all("very small" in e for e in errors)
    return ValidationResult(valid=valid, format=fmt, row_count=row_count, data_type=data_type, errors=errors)
