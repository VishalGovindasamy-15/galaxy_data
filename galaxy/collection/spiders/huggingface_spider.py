"""HuggingFace Hub spider - search and download datasets via free API."""
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.huggingface")


class HuggingFaceSpider(BaseCollector):
    """Collect datasets from HuggingFace Hub using their free API."""
    
    source_id = "huggingface"
    
    def collect(self, query: str, max_results: int = 5) -> list[CollectedFile]:
        """Search HuggingFace and download dataset files."""
        log.info(f"HuggingFace: searching for '{query}'")
        
        # Step 1: Search datasets via API (no auth needed)
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
        
        # Step 2: For each dataset, try to download files
        for ds in datasets[:max_results]:
            ds_id = ds.get("id", "")
            if not ds_id:
                continue
            
            log.info(f"HuggingFace: processing dataset '{ds_id}'")
            
            # Try to get file listing
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
            
            # Download data files (CSV, JSON, Parquet, TXT)
            downloadable = [f for f in files if isinstance(f, dict) and 
                           f.get("path", "").lower().endswith(('.csv', '.json', '.jsonl', '.parquet', '.tsv', '.txt'))
                           and f.get("size", 0) < 50_000_000]  # <50MB limit
            
            if not downloadable:
                # Try README at least for metadata
                log.debug(f"No downloadable data files in {ds_id}")
                continue
            
            for file_info in downloadable[:3]:  # max 3 files per dataset
                fname = file_info["path"]
                download_url = f"https://huggingface.co/datasets/{ds_id}/resolve/main/{fname}"
                
                safe_name = f"{ds_id.replace('/', '_')}_{Path(fname).name}"
                local_path = self._download_file(download_url, safe_name)
                
                if local_path and Path(local_path).stat().st_size > 100:  # non-empty
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
