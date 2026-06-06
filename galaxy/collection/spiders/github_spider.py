"""GitHub spider - search repos with datasets, download CSV/data files."""
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.github")

# All data file extensions
DATA_EXTS = ('.csv', '.json', '.jsonl', '.tsv', '.txt', '.parquet',
             '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
             '.mp3', '.wav', '.flac', '.ogg',
             '.mp4', '.avi', '.mkv',
             '.zip', '.tar.gz')


class GitHubSpider(BaseCollector):
    """Collect datasets from GitHub using free API (no auth, rate limited)."""
    
    source_id = "github"
    
    def collect(self, query: str, max_results: int = 10, max_files_per_repo: int = 5) -> list[CollectedFile]:
        """Search GitHub for repos with data files and download them."""
        log.info(f"GitHub: searching for '{query}' (max={max_results})")
        
        # Search repos
        search_url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(query + ' dataset')}&sort=stars&per_page={max_results}"
        
        try:
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'GalaxyData/0.1',
                'Accept': 'application/vnd.github.v3+json',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            log.error(f"GitHub search failed: {e}")
            return self.collected
        
        repos = data.get("items", [])
        log.info(f"GitHub: found {len(repos)} repos")
        
        for repo in repos[:max_results]:
            full_name = repo.get("full_name", "")
            if not full_name:
                continue
            
            log.info(f"GitHub: scanning '{full_name}'")
            
            try:
                tree_url = f"https://api.github.com/repos/{full_name}/git/trees/HEAD?recursive=1"
                req = urllib.request.Request(tree_url, headers={
                    'User-Agent': 'GalaxyData/0.1',
                    'Accept': 'application/vnd.github.v3+json',
                })
                with urllib.request.urlopen(req, timeout=30) as resp:
                    tree_data = json.loads(resp.read())
            except Exception as e:
                log.warning(f"GitHub: can't get tree for {full_name}: {e}")
                continue
            
            tree = tree_data.get("tree", [])
            data_files = [f for f in tree
                         if any(f.get("path", "").lower().endswith(ext) for ext in DATA_EXTS)
                         and 0 < f.get("size", 0) < 50_000_000  # <50MB, non-empty
                         and f.get("size", 0) > 200]
            
            if not data_files:
                continue
            
            # Sort by size descending (prefer larger files = more data)
            data_files.sort(key=lambda f: f.get("size", 0), reverse=True)
            
            for file_info in data_files[:max_files_per_repo]:
                fpath = file_info["path"]
                raw_url = f"https://raw.githubusercontent.com/{full_name}/HEAD/{urllib.parse.quote(fpath)}"
                safe_name = f"{full_name.replace('/', '_')}_{Path(fpath).name}"
                # Clean filename
                safe_name = "".join(c for c in safe_name if c.isalnum() or c in ".-_")
                
                local_path = self._download_file(raw_url, safe_name)
                
                if local_path and Path(local_path).stat().st_size > 100:
                    self._register_file(
                        local_path, raw_url,
                        fmt=Path(fpath).suffix.lstrip('.'),
                        metadata={"repo": full_name, "original_path": fpath,
                                  "stars": repo.get("stargazers_count", 0),
                                  "license": repo.get("license", {}).get("spdx_id", "unknown") if repo.get("license") else "unknown"}
                    )
        
        self._save_source_metadata()
        log.info(f"GitHub: collected {len(self.collected)} files")
        return self.collected
