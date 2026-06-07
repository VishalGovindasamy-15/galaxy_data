"""Document pipeline — TXT, HTML, MD, PDF processing."""
import logging
import shutil
from pathlib import Path

log = logging.getLogger("galaxy.processing.pipelines")


def process(file_path: str, output_dir: str) -> dict:
    """Process a document file."""
    p = Path(file_path)
    out_dir = Path(output_dir) / "documents" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cleaned_{p.name}"
    
    stats = {"lines": 0, "format": p.suffix.lstrip('.'), "output": str(out_path)}
    
    try:
        if p.suffix.lower() in ('.txt', '.md', '.html', '.htm', '.xml', '.rtf'):
            with open(file_path, 'r', errors='replace') as f:
                lines = f.readlines()
            
            # Clean: strip, remove empty lines, normalize encoding
            cleaned = [line.rstrip() + '\n' for line in lines if line.strip()]
            
            with open(out_path, 'w', encoding='utf-8') as f:
                f.writelines(cleaned)
            
            stats["lines"] = len(cleaned)
        else:
            # PDF or other binary docs — copy as-is
            shutil.copy2(file_path, out_path)
            stats["lines"] = 0
    except Exception as e:
        log.warning(f"Document pipeline error: {e}")
        shutil.copy2(file_path, out_path)
    
    return stats
