"""Web extraction agent - create datasets from web pages when no datasets found."""
import csv
import json
import time
import logging
import urllib.parse
from pathlib import Path
from galaxy.types import CollectedFile, WebExtractionRequest

log = logging.getLogger("galaxy.agents")


class WebExtractionAgent:
    """Scrape web pages and extract structured data to create new datasets."""
    
    def __init__(self, workspace_raw_dir: str):
        self.raw_dir = Path(workspace_raw_dir) / "source_web_extraction"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
    
    def extract(self, request: WebExtractionRequest) -> list[CollectedFile]:
        """Extract data from web pages and create dataset files."""
        if not request.user_approved:
            log.info("Web extraction not approved by user, skipping")
            return []
        
        log.info(f"Web extraction: searching for content to extract")
        collected = []
        all_records = []
        
        for query in request.search_queries[:3]:
            try:
                records = self._search_and_extract(query, request.max_pages)
                all_records.extend(records)
            except Exception as e:
                log.warning(f"Extraction failed for query '{query}': {e}")
        
        if not all_records:
            log.info("No data extracted from web pages")
            return collected
        
        # Save extracted data as CSV
        output_path = self.raw_dir / "web_extracted_data.csv"
        self._save_as_csv(all_records, str(output_path))
        
        if output_path.exists() and output_path.stat().st_size > 100:
            from galaxy.utils.hashing import hash_file
            cf = CollectedFile(
                path=str(output_path),
                hash=hash_file(str(output_path)),
                size_bytes=output_path.stat().st_size,
                source_id="web_extraction",
                format="csv",
                url="web_extraction",
                metadata={"extraction_method": "web_scraping", "queries": request.search_queries},
            )
            collected.append(cf)
            log.info(f"Web extraction: created dataset with {len(all_records)} records")
        
        return collected
    
    def _search_and_extract(self, query: str, max_pages: int) -> list[dict]:
        """Search web and extract structured data from pages."""
        records = []
        
        # Use Scrapling to fetch and parse pages
        try:
            from scrapling.fetchers import Fetcher
            fetcher = Fetcher(timeout=20, auto_match=False)
            
            # Search for relevant Wikipedia/reference pages
            search_urls = [
                f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit=5",
            ]
            
            for search_url in search_urls:
                try:
                    import urllib.request
                    req = urllib.request.Request(search_url, headers={'User-Agent': 'GalaxyData/0.1'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = json.loads(resp.read())
                    
                    search_results = data.get("query", {}).get("search", [])
                    
                    for result in search_results[:max_pages]:
                        title = result.get("title", "")
                        if title:
                            page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                            page_records = self._extract_from_page(fetcher, page_url, title)
                            records.extend(page_records)
                except Exception as e:
                    log.debug(f"Search failed: {e}")
        except Exception as e:
            log.warning(f"Scrapling import failed: {e}")
        
        return records
    
    def _extract_from_page(self, fetcher, url: str, title: str) -> list[dict]:
        """Extract tables and structured data from a web page using Scrapling."""
        records = []
        try:
            page = fetcher.get(url, timeout=20)
            
            # Extract tables
            if hasattr(page, 'find_all'):
                tables = page.find_all('table')
                for table_idx, table in enumerate(tables[:3]):  # max 3 tables per page
                    rows = table.find_all('tr')
                    if len(rows) < 2:
                        continue
                    
                    # Get headers
                    header_cells = rows[0].find_all('th')
                    if not header_cells:
                        header_cells = rows[0].find_all('td')
                    headers = [cell.text.strip()[:50] for cell in header_cells if cell.text.strip()]
                    
                    if not headers:
                        continue
                    
                    # Get data rows
                    for row in rows[1:]:
                        cells = row.find_all('td')
                        values = [cell.text.strip()[:200] for cell in cells]
                        if values and len(values) >= len(headers):
                            record = dict(zip(headers, values[:len(headers)]))
                            record["_source_url"] = url
                            record["_source_title"] = title
                            records.append(record)
            
            log.debug(f"Extracted {len(records)} records from {url}")
        except Exception as e:
            log.debug(f"Page extraction failed: {url}: {e}")
        
        return records
    
    def _save_as_csv(self, records: list[dict], output_path: str):
        """Save extracted records as CSV."""
        if not records:
            return
        
        # Collect all keys
        all_keys = []
        seen = set()
        for r in records:
            for k in r.keys():
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)
