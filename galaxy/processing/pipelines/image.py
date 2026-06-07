"""Image pipeline — JPG, PNG, GIF, BMP, WebP processing."""
import json
import logging
import shutil
from pathlib import Path

log = logging.getLogger("galaxy.processing.pipelines")

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'}


def process(file_path: str, output_dir: str) -> dict:
    """Process an image file — validate, copy to organized output."""
    p = Path(file_path)
    out_dir = Path(output_dir) / "images" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / p.name
    
    stats = {
        "format": p.suffix.lstrip('.'),
        "size_bytes": p.stat().st_size,
        "output": str(out_path),
        "valid": False,
    }
    
    # Validate: check magic bytes
    try:
        with open(file_path, 'rb') as f:
            header = f.read(16)
        
        valid = False
        if header[:3] == b'\xff\xd8\xff':  # JPEG
            valid = True
        elif header[:8] == b'\x89PNG\r\n\x1a\n':  # PNG
            valid = True
        elif header[:6] in (b'GIF87a', b'GIF89a'):  # GIF
            valid = True
        elif header[:2] == b'BM':  # BMP
            valid = True
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':  # WebP
            valid = True
        elif p.suffix.lower() in ('.svg', '.tiff'):
            valid = True  # trust extension
        else:
            # Trust extension if file is > 1KB
            valid = p.stat().st_size > 1024
        
        if valid:
            shutil.copy2(file_path, out_path)
            stats["valid"] = True
        else:
            log.warning(f"Invalid image: {p.name}")
    except Exception as e:
        log.warning(f"Image pipeline error: {e}")
        shutil.copy2(file_path, out_path)
    
    return stats


def is_image(file_path: str) -> bool:
    """Check if file is an image by extension."""
    return Path(file_path).suffix.lower() in IMAGE_EXTS
