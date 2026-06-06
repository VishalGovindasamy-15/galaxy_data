"""Web extraction agent - create datasets from web pages when no datasets found."""
import csv
import json
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from lxml import html as lxml_html
from galaxy.types import CollectedFile, WebExtractionRequest

log = logging.getLogger("galaxy.agents")

# Multiple sources to extract from
SEARCH_SOURCES = [
    # Wikipedia — always works, rich tables
    "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json&srlimit={limit}",
    # Wikidata structured entities
    "https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json&limit={limit}",
]


class WebExtractionAgent:
    """Scrape web pages and extract structured data to create new datasets.
    Scans multiple sources: Wikipedia, Wikidata, and any accessible web page."""
    
    def __init__(self, workspace_raw_dir: str):
        self.raw_dir = Path(workspace_raw_dir) / "source_web_extraction"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
    
    def extract(self, request: WebExtractionRequest) -> list[CollectedFile]:
        """Extract data from web pages and create dataset files."""
        if not request.user_approved:
            log.info("Web extraction not approved by user, skipping")
            return []
        
        log.info(f"Web extraction: scanning internet for data (max_pages={request.max_pages})")
        collected = []
        all_table_records = []
        all_text_records = []
        all_entity_records = []
        
        for query in request.search_queries[:5]:
            # 1. Wikipedia tables
            try:
                tables = self._extract_wikipedia_tables(query, max_pages=request.max_pages)
                all_table_records.extend(tables)
                log.info(f"Wikipedia tables: {len(tables)} records for '{query}'")
            except Exception as e:
                log.warning(f"Wikipedia tables failed for '{query}': {e}")
            
            # 2. Wikipedia text (articles)
            if request.extract_text:
                try:
                    texts = self._extract_wikipedia_text(query, max_pages=min(request.max_pages, 20))
                    all_text_records.extend(texts)
                    log.info(f"Wikipedia text: {len(texts)} records for '{query}'")
                except Exception as e:
                    log.warning(f"Wikipedia text failed: {e}")
            
            # 3. Wikidata entities
            try:
                entities = self._extract_wikidata(query, limit=min(request.max_pages, 50))
                all_entity_records.extend(entities)
                log.info(f"Wikidata: {len(entities)} entities for '{query}'")
            except Exception as e:
                log.debug(f"Wikidata failed: {e}")
        
        # Save each type as separate file
        files_created = 0
        
        if all_table_records:
            path = self.raw_dir / "extracted_tables.csv"
            self._save_as_csv(all_table_records, str(path))
            if path.exists() and path.stat().st_size > 100:
                collected.append(self._make_cf(str(path), "table_extraction"))
                files_created += 1
        
        if all_text_records:
            path = self.raw_dir / "extracted_text.csv"
            self._save_as_csv(all_text_records, str(path))
            if path.exists() and path.stat().st_size > 100:
                collected.append(self._make_cf(str(path), "text_extraction"))
                files_created += 1
        
        if all_entity_records:
            path = self.raw_dir / "extracted_entities.csv"
            self._save_as_csv(all_entity_records, str(path))
            if path.exists() and path.stat().st_size > 100:
                collected.append(self._make_cf(str(path), "entity_extraction"))
                files_created += 1
        
        # Also save as JSON for richer data
        if all_table_records:
            path = self.raw_dir / "extracted_tables.json"
            path.write_text(json.dumps(all_table_records, indent=2, ensure_ascii=False))
            if path.stat().st_size > 100:
                collected.append(self._make_cf(str(path), "table_extraction_json"))
                files_created += 1
        
        total = len(all_table_records) + len(all_text_records) + len(all_entity_records)
        log.info(f"Web extraction complete: {total} total records in {files_created} files")
        return collected
    
    def _make_cf(self, path: str, method: str) -> CollectedFile:
        from galaxy.utils.hashing import hash_file
        p = Path(path)
        return CollectedFile(
            path=path, hash=hash_file(path), size_bytes=p.stat().st_size,
            source_id="web_extraction", format=p.suffix.lstrip('.'),
            url="web_extraction", metadata={"extraction_method": method},
        )
    
    def _fetch_html(self, url: str) -> str:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0'
        })
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.read().decode('utf-8', errors='replace')
    
    def _extract_wikipedia_tables(self, query: str, max_pages: int = 20) -> list[dict]:
        """Search Wikipedia and extract tables from pages."""
        records = []
        wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_pages}"
        
        try:
            req = urllib.request.Request(wiki_url, headers={'User-Agent': 'GalaxyData/0.1'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            
            search_results = data.get("query", {}).get("search", [])
            log.info(f"Wikipedia: found {len(search_results)} pages for '{query}'")
            
            for result in search_results:
                title = result.get("title", "")
                if not title:
                    continue
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                
                try:
                    html = self._fetch_html(page_url)
                    tree = lxml_html.fromstring(html)
                    
                    # Extract ALL tables (wikitable, sortable, any table with data)
                    tables = tree.xpath('//table[contains(@class,"wikitable") or contains(@class,"sortable") or contains(@class,"infobox")]')
                    if not tables:
                        tables = tree.xpath('//table')
                    
                    for table in tables[:10]:
                        rows = table.xpath('.//tr')
                        if len(rows) < 2:
                            continue
                        
                        header_cells = rows[0].xpath('.//th')
                        if not header_cells:
                            header_cells = rows[0].xpath('.//td')
                        headers = [cell.text_content().strip()[:80] for cell in header_cells if cell.text_content().strip()]
                        
                        if not headers or len(headers) < 2:
                            continue
                        
                        for row in rows[1:]:
                            cells = row.xpath('.//td')
                            values = [cell.text_content().strip()[:300] for cell in cells]
                            if values and len(values) >= len(headers):
                                record = dict(zip(headers, values[:len(headers)]))
                                record["_source_url"] = page_url
                                record["_source_title"] = title
                                record["_extraction_type"] = "table"
                                records.append(record)
                    
                    # Also extract lists if few table records
                    if len(records) < 50:
                        list_items = tree.xpath('//div[@id="mw-content-text"]//ul/li')
                        for li in list_items[:100]:
                            text = li.text_content().strip()
                            if text and len(text) > 20 and not text.startswith('^'):
                                records.append({
                                    "text": text[:500],
                                    "title": title,
                                    "_source_url": page_url,
                                    "_source_title": title,
                                    "_extraction_type": "list",
                                })
                except Exception as e:
                    log.debug(f"Page extraction failed: {title}: {e}")
        except Exception as e:
            log.warning(f"Wikipedia search failed: {e}")
        
        return records
    
    def _extract_wikipedia_text(self, query: str, max_pages: int = 10) -> list[dict]:
        """Extract article text/paragraphs from Wikipedia."""
        records = []
        # Use Wikipedia API to get plain text extracts
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_pages}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GalaxyData/0.1'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            
            for result in data.get("query", {}).get("search", []):
                title = result.get("title", "")
                if not title:
                    continue
                
                # Get article extract via API
                extract_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=extracts&exintro=false&explaintext=true&format=json&exsectionformat=plain"
                try:
                    req = urllib.request.Request(extract_url, headers={'User-Agent': 'GalaxyData/0.1'})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        ext_data = json.loads(resp.read())
                    
                    pages = ext_data.get("query", {}).get("pages", {})
                    for page_id, page in pages.items():
                        extract = page.get("extract", "")
                        if extract and len(extract) > 100:
                            # Split into paragraphs
                            paragraphs = [p.strip() for p in extract.split('\n\n') if p.strip() and len(p.strip()) > 50]
                            for para in paragraphs[:20]:
                                records.append({
                                    "title": title,
                                    "text": para[:2000],
                                    "word_count": len(para.split()),
                                    "_source": "wikipedia",
                                    "_extraction_type": "text",
                                })
                except Exception as e:
                    log.debug(f"Extract failed for {title}: {e}")
        except Exception as e:
            log.warning(f"Wikipedia text extraction failed: {e}")
        
        return records
    
    def _extract_wikidata(self, query: str, limit: int = 50) -> list[dict]:
        """Query Wikidata for structured entities."""
        records = []
        try:
            search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(query)}&language=en&format=json&limit={limit}"
            req = urllib.request.Request(search_url, headers={'User-Agent': 'GalaxyData/0.1'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            
            for entity in data.get("search", []):
                records.append({
                    "entity_id": entity.get("id", ""),
                    "label": entity.get("label", ""),
                    "description": entity.get("description", ""),
                    "url": entity.get("concepturi", ""),
                    "_source": "wikidata",
                    "_extraction_type": "entity",
                })
        except Exception as e:
            log.debug(f"Wikidata failed: {e}")
        return records
    
    def _save_as_csv(self, records: list[dict], output_path: str):
        if not records:
            return
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
