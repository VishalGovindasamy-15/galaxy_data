"""Generic pipeline — handles audio, video, and unknown formats."""
import json
import logging
import shutil
from pathlib import Path
from galaxy.types import DataType

log = logging.getLogger("galaxy.processing.pipelines")

AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'}
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'}


def process(file_path: str, output_dir: str, data_type: DataType = DataType.GENERIC) -> dict:
    """Process audio/video/generic files — validate and copy to typed folder."""
    p = Path(file_path)
    ext = p.suffix.lower()
    
    # Determine output subfolder by type
    if data_type == DataType.AUDIO or ext in AUDIO_EXTS:
        type_dir = "audio"
    elif data_type == DataType.VIDEO or ext in VIDEO_EXTS:
        type_dir = "video"
    else:
        type_dir = "other"
    
    out_dir = Path(output_dir) / type_dir / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / p.name
    
    stats = {
        "format": ext.lstrip('.'),
        "size_bytes": p.stat().st_size,
        "data_type": type_dir,
        "output": str(out_path),
        "valid": False,
    }
    
    # Basic validation: check file is non-trivial
    if p.stat().st_size < 100:
        log.warning(f"File too small: {p.name} ({p.stat().st_size} bytes)")
        return stats
    
    # Validate audio by checking common headers
    if type_dir == "audio":
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
            if (header[:3] == b'ID3' or header[:2] == b'\xff\xfb' or  # MP3
                header[:4] == b'RIFF' or header[:4] == b'fLaC' or     # WAV, FLAC
                header[:4] == b'OggS'):                                 # OGG
                stats["valid"] = True
            else:
                stats["valid"] = p.stat().st_size > 1000  # trust if substantial
        except Exception:
            stats["valid"] = True
    
    # Validate video by checking headers
    elif type_dir == "video":
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
            if (header[4:8] == b'ftyp' or  # MP4
                header[:4] == b'RIFF' or   # AVI
                header[:4] == b'\x1a\x45\xdf\xa3'):  # MKV/WebM
                stats["valid"] = True
            else:
                stats["valid"] = p.stat().st_size > 10000
        except Exception:
            stats["valid"] = True
    else:
        stats["valid"] = True
    
    if stats["valid"]:
        shutil.copy2(file_path, out_path)
    
    return stats
