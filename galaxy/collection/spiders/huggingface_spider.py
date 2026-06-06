"""HuggingFace Hub spider - search and download datasets via free API."""
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.huggingface")

# File size limit per file
MAX_FILE_SIZE = 100_000_000  # 100MB


class HuggingFaceSpider(BaseCollector):
    """Collect datasets from HuggingFace Hub using their free API."""
    
    source_id = "huggingface"
    
    def collect(self, query: str, max_results: int = 10, max_files_per_dataset: int = 5) -> list[CollectedFile]:
        """Search HuggingFace and download dataset files."""
        log.info(f"HuggingFace: searching for '{query}' (max={max_results})")
        
        # Search datasets via API (no auth needed) — get more results
        search_url = f"https://huggingface.co/api/datasets?search={urllib.parse.quote(query)}&limit={max_results}&sort=downloads"
        
        try:
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                datasets = json.loads(resp.read())
        except Exception as e:
            log.error(f"HuggingFace search failed: {e}")
            return self.collected
        
        log.info(f"HuggingFace: found {len(datasets)} datasets")
        
        for ds in datasets[:max_results]:
            ds_id = ds.get("id", "")
            if not ds_id:
                continue
            
            log.info(f"HuggingFace: processing '{ds_id}'")
            
            # Get file listing
            try:
                tree_url = f"https://huggingface.co/api/datasets/{ds_id}/tree/main"
                req = urllib.request.Request(tree_url, headers={
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    files = json.loads(resp.read())
            except Exception as e:
                log.warning(f"HuggingFace: can't list files for {ds_id}: {e}")
                continue
            
            # Downloadable extensions (all data types)
            DATA_EXTS = ('.csv', '.json', '.jsonl', '.parquet', '.tsv', '.txt',
                         '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',  # images
                         '.mp3', '.wav', '.flac', '.ogg',                   # audio
                         '.mp4', '.avi', '.mkv', '.webm',                   # video
                         '.zip', '.tar.gz', '.gz')
            
            downloadable = [f for f in files if isinstance(f, dict) and
                           any(f.get("path", "").lower().endswith(ext) for ext in DATA_EXTS)
                           and f.get("size", 0) < MAX_FILE_SIZE
                           and f.get("size", 0) > 50]
            
            if not downloadable:
                log.debug(f"No downloadable data files in {ds_id}")
                continue
            
            for file_info in downloadable[:max_files_per_dataset]:
                fname = file_info["path"]
                download_url = f"https://huggingface.co/datasets/{ds_id}/resolve/main/{fname}"
                
                safe_name = f"{ds_id.replace('/', '_')}_{Path(fname).name}"
                local_path = self._download_file(download_url, safe_name)
                
                if local_path and Path(local_path).stat().st_size > 50:
                    self._register_file(
                        local_path, download_url,
                        fmt=Path(fname).suffix.lstrip('.'),
                        metadata={"dataset_id": ds_id, "original_path": fname,
                                  "downloads": ds.get("downloads", 0),
                                  "license": ds.get("cardData", {}).get("license", "unknown") if isinstance(ds.get("cardData"), dict) else "unknown"}
                    )
        
        self._save_source_metadata()
        log.info(f"HuggingFace: collected {len(self.collected)} files")
        return self.collected
