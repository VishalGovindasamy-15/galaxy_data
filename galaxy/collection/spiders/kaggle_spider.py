"""Kaggle spider - search and find Kaggle dataset references using lxml."""
import re
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from lxml import html as lxml_html

from galaxy.collection.spiders.base_spider import BaseCollector
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.spiders.kaggle")


class KaggleSpider(BaseCollector):
    """Search Kaggle datasets. Kaggle blocks scraping and requires auth
    for downloads, so this spider records metadata references only."""
    
    source_id = "kaggle"
    
    def collect(self, query: str, max_results: int = 5) -> list[CollectedFile]:
        """Search Kaggle and record dataset metadata."""
        log.info(f"Kaggle: searching for '{query}'")
        
        search_url = f"https://www.kaggle.com/datasets?search={urllib.parse.quote(query)}"
        
        try:
            req = urllib.request.Request(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                html_content = resp.read().decode('utf-8', errors='replace')
            
            tree = lxml_html.fromstring(html_content)
            links = tree.xpath('//a/@href')
            dataset_urls = []
            for href in links:
                if '/datasets/' in href and href.count('/') >= 2:
                    full_url = urllib.parse.urljoin("https://www.kaggle.com", href)
                    if full_url not in dataset_urls:
                        dataset_urls.append(full_url)
            
            log.info(f"Kaggle: found {len(dataset_urls)} dataset links")
            
            for url in dataset_urls[:max_results]:
                meta_file = self._source_dir / f"kaggle_ref_{hash(url) % 100000}.json"
                meta_file.write_text(json.dumps({
                    "source": "kaggle", "url": url, "query": query,
                    "note": "Kaggle requires auth for download - reference only"
                }, indent=2))
        except Exception as e:
            log.warning(f"Kaggle search failed (expected - anti-bot): {e}")
        
        self._save_source_metadata()
        return self.collected
