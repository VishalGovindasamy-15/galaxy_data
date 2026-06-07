# 🌌 Galaxy Data — Dataset Intelligence Platform

**Collect, process, and package real-world datasets from the open internet — all in Python.**

Galaxy Data is an automated dataset collection and processing platform. Give it a natural language query, specify the data type you want (images, audio, video, tabular, text), and it searches the entire internet to find, download, validate, clean, deduplicate, and package datasets — organized by type and ready for ML training.

---

## Quick Start

```bash
cd galaxy_data
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# Collect sentiment analysis datasets
python main.py "sentiment analysis dataset"

# Collect only images
python main.py "cat and dog images" --modality images

# Interactive mode
python main.py --interactive
```

---

## Usage

### Normal Mode (Source-Based Collection)
```bash
python main.py "your query here"
python main.py "iris flower dataset" --max-results 20
python main.py "face detection" --modality images --max-results 10
python main.py "speech emotion recognition" --modality audio
python main.py "stock market time series" --min-size 50MB --max-results 20
```

### Web Extraction Mode
```bash
python main.py "Indian spice varieties" --extract
python main.py "climate change data" --extract --max-pages 30
python main.py "world GDP statistics" --extract --modality tabular --max-pages 50
```

### Interactive Mode
```bash
python main.py --interactive
```
```
🌌 galaxy> set modality images
🌌 galaxy> set max-results 20
🌌 galaxy> search face detection dataset
🌌 galaxy> extract world population statistics
🌌 galaxy> set min-size 100MB
🌌 galaxy> search NLP sentiment analysis
🌌 galaxy> history
🌌 galaxy> exit
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `query` | (required) | Natural language query for datasets |
| `--modality` | mixed | Filter: `images`, `audio`, `video`, `tabular`, `text`, `mixed` |
| `--max-results` | 10 | Max datasets per source. Higher = more data |
| `--extract` | off | Enable web extraction (Wikipedia + Wikidata) |
| `--max-pages` | 20 | Max pages to scan during web extraction |
| `--min-size` | 0 | Min data size target (e.g. `10MB`, `1GB`). Loops until met |
| `--interactive` | off | Interactive REPL mode |

---

## What It Collects

### Data Types & Modality Filter
| Modality | Extensions | What It Collects |
|---|---|---|
| `images` | JPG, PNG, GIF, BMP, WebP, TIFF, SVG | Only image files |
| `audio` | MP3, WAV, FLAC, OGG, M4A, AAC | Only audio files |
| `video` | MP4, AVI, MKV, MOV, WebM | Only video files |
| `tabular` | CSV, TSV, JSON, JSONL, Parquet, XLSX | Only structured data |
| `text` | TXT, MD, HTML, PDF, XML | Only documents |
| `mixed` | All of the above | Everything (default) |

### Data Sources
| Source | Method | What It Finds |
|---|---|---|
| **HuggingFace Hub** | Free API | ML datasets (all formats) |
| **GitHub** | Free API | Repos with data files |
| **Kaggle** | Web scraping | Dataset metadata |
| **Web Search** | Portal crawling | Open data portals |
| **Search Engine** | DuckDuckGo HTML | Any website on the internet |
| **Web Extraction** | Wikipedia + Wikidata | Tables, text, entities |

---

## Pipeline Architecture

```
Query → Parse → Discover → Collect → Filter → Validate → Dedup → Pipeline → Build
  │        │         │          │        │         │         │        │         │
  │   NL Parser  Sources    Spiders  Relevance  Format   Hash    Type-    Package
  │   (rules)   (5+DDG)    (6 src)  Check      Check    Match   specific  by type
  │              FAISS                                           Pipeline
  └───────────────────────────────────────────────────────────────────────────┘
                     Lineage Tracking + Provenance + Collection Loop
```

### Pipeline Stages

1. **Query Parser** — Detects domains, language, modality, quality threshold
2. **Source Discovery** — Registry of 6 sources + FAISS similarity + search engine
3. **Collection Loop** — Collects from all sources, loops if `--min-size` not met
4. **Modality Filter** — Keeps only files matching `--modality` (images/audio/video/tabular/text)
5. **Relevance Filter** — Scores files against query terms, removes unrelated data
6. **Validation** — Format detection, magic byte verification for media
7. **Deduplication** — Exact hash matching across all files
8. **Typed Pipelines** — Separate processing for tabular, document, image, audio, video
9. **Quality Scoring** — Completeness + consistency metrics (0-1.0)
10. **Building** — Package into type-separated folders with metadata

---

## Output Structure

Every run produces organized output:

```
final/
├── tabular/              # CSV, JSON, TSV files
│   ├── data/
│   │   ├── cleaned_dataset1.csv
│   │   └── cleaned_dataset2.json
│   └── metadata.json
├── images/               # Image files only
│   ├── data/
│   │   ├── photo1.jpg
│   │   └── photo2.png
│   └── metadata.json
├── audio/                # Audio files only
│   ├── data/
│   │   ├── sample1.wav
│   │   └── sample2.mp3
│   └── metadata.json
├── video/                # Video files only
│   ├── data/
│   │   └── clip.mp4
│   └── metadata.json
├── documents/            # Text documents
│   ├── data/
│   │   └── report.txt
│   └── metadata.json
├── README.md             # Auto-generated documentation
├── QUALITY_REPORT.json   # Per-file quality scores
├── SOURCES.txt           # Source attribution
├── PROVENANCE.json       # Full processing history
└── LINEAGE.json          # Data origin tracking
```

---

## Key Features

### Collection Loop (`--min-size`)
When `--min-size` is set, the system loops collection rounds (up to 3), increasing `max_results` each round until the target size is reached.

### Modality-Aware Collection
When `--modality images` is specified, only image files are downloaded. CSVs, TXTs, and videos are filtered out at collection time — not just at the end.

### Relevance Filtering
Files are scored against query terms by:
- **Filename** (40%): Does the filename contain query words?
- **Content** (40%): Does the file content mention query terms?
- **File size** (10%): Larger files score higher
- **Parent directory** (10%): For binary files

### Search Engine Spider
Uses DuckDuckGo HTML search (no API key needed) to find datasets anywhere on the internet. Not limited to fixed sources.

### Typed Processing Pipelines
Each data type has its own pipeline:
- **Tabular**: Row alignment, whitespace cleanup, encoding normalization
- **Image**: Magic byte validation (JPEG/PNG/GIF/BMP/WebP headers)
- **Audio**: Header validation (ID3/RIFF/fLaC/OggS)
- **Video**: Header validation (ftyp/RIFF/MKV magic)
- **Document**: Text cleanup, empty line removal

### Web Extraction (`--extract`)
Scrapes data from the web when existing datasets aren't enough:
- **Wikipedia tables** — Structured tabular data from any topic
- **Wikipedia text** — Article paragraphs as text corpus
- **Wikidata entities** — Structured knowledge graph entities

### Lineage & Provenance
Every dataset tracks: where it came from, what happened to it, every processing step.

---

## Project Structure

```
galaxy_data/
├── main.py                           # CLI entry point
├── pyproject.toml                    # Dependencies
├── README.md                         # This file
├── galaxy/
│   ├── types.py                      # Core dataclasses (25+ types)
│   ├── config.py                     # Configuration
│   ├── utils/                        # Hashing, retry
│   ├── cache/                        # 3-tier cache (L1/L2/L3)
│   ├── storage/                      # Session workspace, dataset store
│   ├── knowledge/                    # Source registry, metadata, lineage
│   ├── intelligence/                 # Query parser, FAISS embeddings
│   ├── collection/                   # Rate limiter, circuit breaker
│   │   └── spiders/                  # 6 spiders (HF, GH, Kaggle, Web, Generic, Search)
│   ├── processing/                   # Validator, schema, quality, dedup, cleaner
│   │   └── pipelines/                # Typed: tabular, document, image, generic
│   ├── agents/                       # Discovery, collection, processing, building, web extraction
│   ├── orchestrator/                 # State machine + main orchestrator
│   └── gateway/                      # Interactive gateway
└── scrapling/                        # Scrapling framework (vendored)
```

### Module Count
- **Galaxy modules:** 57 Python files
- **Scrapling (vendored):** 51 Python files

---

## Dependencies

All Python, no external services required.

| Package | Purpose |
|---|---|
| `faiss-cpu` | Vector similarity search |
| `fakeredis` | In-memory Redis cache |
| `aiosqlite` | Async SQLite metadata |
| `lxml` | HTML parsing |
| `scrapling` | Web scraping (vendored) |

```bash
pip install -e ".[all]"
```

---

## Tested Results

| Query | Mode | Modality | Files | Rows | Quality | Size | Duration |
|---|---|---|---|---|---|---|---|
| cat dog images | Normal | images | 9 | 0 | 1.00 | 6.4 MB | 37s |
| world population | Extract | tabular | 6 | 3,814 | 0.80 | 1.2 MB | 62s |
| music audio wav | Normal | audio | 5 | 0 | 1.00 | 6.3 MB | 34s |
| sentiment NLP | Extract | mixed | 16 | 35,338 | 0.90 | 34.6 MB | 69s |

---

## Roadmap

- [ ] Authenticated sources (Kaggle download, HuggingFace private)
- [ ] Synthetic data engine
- [ ] Distributed processing layer  
- [ ] Parquet/Arrow native support
- [ ] Dataset versioning
- [ ] REST API gateway
- [ ] StealthyFetcher (headless Chrome for JS-heavy sites)

---

## License

Open source. All collected datasets retain their original licenses.
