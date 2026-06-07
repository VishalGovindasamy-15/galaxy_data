"""Web extraction agent — searches the ENTIRE internet using StealthyFetcher.
Extracts tables, text, images, audio, video from found web pages.
Not limited to Wikipedia — crawls any website found via search engines."""
import csv
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from galaxy.types import CollectedFile, WebExtractionRequest

log = logging.getLogger("galaxy.agents")

# Import Scrapling
try:
    from scrapling import StealthyFetcher, Fetcher
    SCRAPLING_AVAILABLE = True
except ImportError:
    SCRAPLING_AVAILABLE = False

# Media extensions
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff'}
AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'}
VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv'}
DATA_EXTS = {'.csv', '.tsv', '.json', '.jsonl', '.parquet', '.xlsx', '.zip'}


class WebExtractionAgent:
    """Extracts data from the ENTIRE internet — not just Wikipedia.
    Uses StealthyFetcher to search, then Fetcher to crawl found pages.
    Collects: tables, text, images, audio, video, data files."""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir) / "source_web_extraction"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract(self, request: WebExtractionRequest) -> list[CollectedFile]:
        """Extract data from web pages."""
        if not request.user_approved:
            log.info("Web extraction not approved, skipping")
            return []
        
        log.info(f"Web extraction: scanning internet (max_pages={request.max_pages})")
        collected = []
        all_table_records = []
        all_text_records = []
        visited_urls = set()
        
        # Phase 1: Search the internet for relevant pages
        search_urls = self._search_internet(request.search_queries, max_pages=request.max_pages)
        log.info(f"Web extraction: found {len(search_urls)} pages to scan")
        
        # Phase 2: Crawl each found page for data
        for url in search_urls:
            if url in visited_urls:
                continue
            visited_urls.add(url)
            
            try:
                page_data = self._extract_from_page(url, request)
                all_table_records.extend(page_data.get("tables", []))
                all_text_records.extend(page_data.get("text", []))
                
                # Download media files found on the page
                for media_url in page_data.get("media", []):
                    try:
                        cf = self._download_media(media_url, url)
                        if cf:
                            collected.append(cf)
                    except Exception as e:
                        log.debug(f"Media download failed: {media_url}: {e}")
                
                # Download data files found on the page
                for data_url in page_data.get("data_files", []):
                    try:
                        cf = self._download_data_file(data_url, url)
                        if cf:
                            collected.append(cf)
                    except Exception as e:
                        log.debug(f"Data download failed: {data_url}: {e}")
                
            except Exception as e:
                log.debug(f"Page extraction failed: {url}: {e}")
        
        # Phase 3: Also get Wikipedia data (reliable structured source)
        for query in request.search_queries[:3]:
            try:
                wiki_tables = self._extract_wikipedia_tables(query, max_pages=min(request.max_pages, 10))
                all_table_records.extend(wiki_tables)
            except Exception as e:
                log.debug(f"Wikipedia tables failed: {e}")
            
            if request.extract_text:
                try:
                    wiki_text = self._extract_wikipedia_text(query, max_pages=min(request.max_pages, 10))
                    all_text_records.extend(wiki_text)
                except Exception as e:
                    log.debug(f"Wikipedia text failed: {e}")
        
        # Phase 4: Save extracted records as files
        if all_table_records:
            cf = self._save_records_csv(all_table_records, "extracted_tables.csv")
            if cf:
                collected.append(cf)
            cf2 = self._save_records_json(all_table_records, "extracted_tables.json")
            if cf2:
                collected.append(cf2)
        
        if all_text_records:
            cf = self._save_records_csv(all_text_records, "extracted_text.csv")
            if cf:
                collected.append(cf)
        
        log.info(f"Web extraction complete: {len(collected)} files, "
                 f"{len(all_table_records)} table records, {len(all_text_records)} text records")
        return collected
    
    def _search_internet(self, queries: list[str], max_pages: int = 20) -> list[str]:
        """Search the internet using StealthyFetcher + DuckDuckGo."""
        all_urls = []
        
        for query in queries[:5]:
            # Search DuckDuckGo
            try:
                urls = self._search_ddg(query + " data", max_pages)
                all_urls.extend(urls)
                log.info(f"DDG search: {len(urls)} pages for '{query}'")
                time.sleep(1)
            except Exception as e:
                log.debug(f"DDG search failed: {e}")
        
        # Deduplicate
        seen = set()
        unique = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique.append(url)
        
        return unique[:max_pages]
    
    def _search_ddg(self, query: str, max_results: int = 20) -> list[str]:
        """Search DuckDuckGo using StealthyFetcher."""
        urls = []
        
        if SCRAPLING_AVAILABLE:
            try:
                search_url = f"https://duckduckgo.com/?q={urllib.parse.quote(query)}&ia=web"
                resp = StealthyFetcher.fetch(
                    search_url,
                    headless=True,
                    disable_resources=True,
                    block_ads=True,
                    network_idle=True,
                    timeout=20000,
                )
                
                if resp.status == 200:
                    # Extract links using Scrapling selectors
                    links = resp.css('a[href]')
                    for link in links:
                        href = link.attrib.get('href', '')
                        if href.startswith('http') and 'duckduckgo' not in href:
                            urls.append(href)
                        elif '//duckduckgo.com/l/?' in href:
                            parsed = urllib.parse.urlparse(href)
                            params = urllib.parse.parse_qs(parsed.query)
                            if 'uddg' in params:
                                urls.append(urllib.parse.unquote(params['uddg'][0]))
                    
                    log.info(f"StealthyFetcher: found {len(urls)} URLs from DDG")
                    return urls[:max_results]
            except Exception as e:
                log.debug(f"StealthyFetcher DDG failed: {e}")
        
        # Fallback: DuckDuckGo HTML POST
        try:
            from lxml import html as lxml_html
            data = urllib.parse.urlencode({'q': query}).encode()
            req = urllib.request.Request(
                'https://html.duckduckgo.com/html/', data=data,
                headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/x-www-form-urlencoded'}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            tree = lxml_html.fromstring(html)
            for href in tree.xpath('//a[@class="result__a"]/@href'):
                if '//duckduckgo.com/l/?' in href:
                    parsed = urllib.parse.urlparse(href)
                    params = urllib.parse.parse_qs(parsed.query)
                    if 'uddg' in params:
                        urls.append(urllib.parse.unquote(params['uddg'][0]))
                elif href.startswith('http'):
                    urls.append(href)
        except Exception as e:
            log.debug(f"DDG HTML fallback failed: {e}")
        
        return urls[:max_results]
    
    def _extract_from_page(self, url: str, request: WebExtractionRequest) -> dict:
        """Extract all data from a single web page using Scrapling."""
        result = {"tables": [], "text": [], "media": [], "data_files": []}
        
        try:
            if SCRAPLING_AVAILABLE:
                resp = Fetcher.get(url, timeout=15)
                if resp.status != 200:
                    return result
                
                # Extract tables using Scrapling selectors
                if request.extract_tables:
                    tables = resp.css('table')
                    for table in tables:
                        rows = table.css('tr')
                        for row in rows:
                            cells = row.css('td, th')
                            if cells:
                                record = {"source_url": url}
                                for i, cell in enumerate(cells):
                                    text = cell.text.strip() if cell.text else ""
                                    record[f"col_{i}"] = text
                                if any(v for k, v in record.items() if k != "source_url"):
                                    result["tables"].append(record)
                
                # Extract text paragraphs
                if request.extract_text:
                    paragraphs = resp.css('p')
                    for p in paragraphs:
                        text = p.text.strip() if p.text else ""
                        if text and len(text) > 50:
                            result["text"].append({
                                "source_url": url,
                                "text": text[:2000],
                                "type": "paragraph",
                            })
                
                # Find media links (images, audio, video)
                if request.extract_images:
                    # Images
                    for img in resp.css('img[src]'):
                        src = img.attrib.get('src', '')
                        if src:
                            full_url = urllib.parse.urljoin(url, src)
                            ext = Path(urllib.parse.urlparse(full_url).path).suffix.lower()
                            if ext in IMAGE_EXTS and not any(x in full_url for x in ['icon', 'logo', 'avatar', '1x1', 'pixel', 'tracking']):
                                result["media"].append(full_url)
                    
                    # Audio/Video
                    for tag in resp.css('audio source[src], video source[src], a[href]'):
                        src = tag.attrib.get('src', '') or tag.attrib.get('href', '')
                        if src:
                            full_url = urllib.parse.urljoin(url, src)
                            ext = Path(urllib.parse.urlparse(full_url).path).suffix.lower()
                            if ext in AUDIO_EXTS or ext in VIDEO_EXTS:
                                result["media"].append(full_url)
                
                # Find data file links
                for a in resp.css('a[href]'):
                    href = a.attrib.get('href', '')
                    if href:
                        full_url = urllib.parse.urljoin(url, href)
                        ext = Path(urllib.parse.urlparse(full_url).path).suffix.lower()
                        if ext in DATA_EXTS:
                            result["data_files"].append(full_url)
            
            else:
                # Fallback: urllib + lxml
                result = self._extract_with_lxml(url, request)
        
        except Exception as e:
            log.debug(f"Page extraction error: {url}: {e}")
        
        return result
    
    def _extract_with_lxml(self, url: str, request: WebExtractionRequest) -> dict:
        """Fallback extraction using urllib + lxml."""
        result = {"tables": [], "text": [], "media": [], "data_files": []}
        try:
            from lxml import html as lxml_html
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            tree = lxml_html.fromstring(html)
            
            # Tables
            for table in tree.xpath('//table'):
                for row in table.xpath('.//tr'):
                    cells = row.xpath('.//td/text() | .//th/text()')
                    if cells:
                        record = {"source_url": url}
                        for i, cell in enumerate(cells):
                            record[f"col_{i}"] = cell.strip()
                        result["tables"].append(record)
            
            # Links to data files
            for href in tree.xpath('//a/@href'):
                full_url = urllib.parse.urljoin(url, href)
                ext = Path(urllib.parse.urlparse(full_url).path).suffix.lower()
                if ext in DATA_EXTS:
                    result["data_files"].append(full_url)
                elif ext in IMAGE_EXTS:
                    result["media"].append(full_url)
        except Exception as e:
            log.debug(f"lxml extraction error: {e}")
        
        return result
    
    def _download_media(self, url: str, found_on: str) -> CollectedFile | None:
        """Download a media file (image/audio/video)."""
        try:
            parsed = urllib.parse.urlparse(url)
            filename = Path(parsed.path).name
            if not filename or len(filename) < 3:
                return None
            
            safe = "".join(c for c in filename if c.isalnum() or c in ".-_")[:100]
            dest = self.output_dir / safe
            if dest.exists():
                return None
            
            if SCRAPLING_AVAILABLE:
                resp = Fetcher.get(url, timeout=30)
                dest.write_bytes(resp.body)
            else:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    dest.write_bytes(resp.read())
            
            if dest.stat().st_size < 500:
                dest.unlink()
                return None
            
            from galaxy.utils.hashing import hash_file
            cf = CollectedFile(
                path=str(dest), hash=hash_file(str(dest)),
                size_bytes=dest.stat().st_size, source_id="web_extraction",
                format=dest.suffix.lstrip('.'), url=url,
                metadata={"found_on": found_on},
            )
            log.info(f"Downloaded media: {safe} ({dest.stat().st_size} bytes)")
            return cf
        except Exception as e:
            log.debug(f"Media download failed: {url}: {e}")
            return None
    
    def _download_data_file(self, url: str, found_on: str) -> CollectedFile | None:
        """Download a data file (CSV, JSON, etc.)."""
        return self._download_media(url, found_on)  # Same logic
    
    def _extract_wikipedia_tables(self, query: str, max_pages: int = 10) -> list[dict]:
        """Extract tables from Wikipedia (reliable structured source)."""
        records = []
        try:
            from lxml import html as lxml_html
            search_url = f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(query)}&limit={max_pages}"
            req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode()
            tree = lxml_html.fromstring(html)
            result_links = tree.xpath('//div[@class="mw-search-result-heading"]//a/@href')
            
            for link in result_links[:max_pages]:
                page_url = f"https://en.wikipedia.org{link}"
                try:
                    req2 = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, timeout=15) as resp2:
                        page_html = resp2.read().decode()
                    page_tree = lxml_html.fromstring(page_html)
                    
                    for table in page_tree.xpath('//table[contains(@class,"wikitable")]'):
                        headers = [th.text_content().strip() for th in table.xpath('.//th')][:20]
                        for row in table.xpath('.//tr')[1:]:
                            cells = [td.text_content().strip() for td in row.xpath('.//td')]
                            if cells:
                                record = {"source_url": page_url}
                                for i, cell in enumerate(cells[:20]):
                                    col_name = headers[i] if i < len(headers) else f"col_{i}"
                                    record[col_name] = cell
                                records.append(record)
                    time.sleep(0.3)
                except Exception:
                    pass
            
            log.info(f"Wikipedia tables: {len(records)} records for '{query}'")
        except Exception as e:
            log.warning(f"Wikipedia search failed: {e}")
        return records
    
    def _extract_wikipedia_text(self, query: str, max_pages: int = 10) -> list[dict]:
        """Extract text from Wikipedia articles."""
        records = []
        try:
            api_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={max_pages}&format=json"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            
            titles = data[1] if len(data) > 1 else []
            for title in titles[:max_pages]:
                try:
                    text_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=extracts&explaintext=1&format=json"
                    req2 = urllib.request.Request(text_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        result = json.loads(resp2.read())
                    pages = result.get("query", {}).get("pages", {})
                    for page_id, page in pages.items():
                        extract = page.get("extract", "")
                        if extract and len(extract) > 100:
                            records.append({
                                "title": title,
                                "text": extract[:5000],
                                "source_url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                            })
                    time.sleep(0.3)
                except Exception:
                    pass
            
            log.info(f"Wikipedia text: {len(records)} records for '{query}'")
        except Exception as e:
            log.warning(f"Wikipedia text failed: {e}")
        return records
    
    def _save_records_csv(self, records: list[dict], filename: str) -> CollectedFile | None:
        """Save records to CSV file."""
        if not records:
            return None
        path = self.output_dir / filename
        all_keys = []
        for r in records:
            for k in r:
                if k not in all_keys:
                    all_keys.append(k)
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)
        
        from galaxy.utils.hashing import hash_file
        return CollectedFile(
            path=str(path), hash=hash_file(str(path)),
            size_bytes=path.stat().st_size, source_id="web_extraction",
            format="csv", url="extracted",
        )
    
    def _save_records_json(self, records: list[dict], filename: str) -> CollectedFile | None:
        """Save records to JSON file."""
        if not records:
            return None
        path = self.output_dir / filename
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)
        from galaxy.utils.hashing import hash_file
        return CollectedFile(
            path=str(path), hash=hash_file(str(path)),
            size_bytes=path.stat().st_size, source_id="web_extraction",
            format="json", url="extracted",
        )
