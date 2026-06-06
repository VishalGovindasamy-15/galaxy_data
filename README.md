# 🌌 Galaxy Data — Dataset Intelligence Platform

**Collect, process, and package real-world datasets from the open internet — all in Python.**

Galaxy Data is an automated dataset collection and processing platform. Give it a natural language query and it searches HuggingFace, GitHub, Kaggle, and the open web to find, download, validate, clean, deduplicate, and package datasets — ready for ML training.

---

## Quick Start

```bash
# Install
cd galaxy_data
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# Run
python main.py "sentiment analysis dataset"
```

---

## Usage

```bash
# Basic — search and collect datasets
python main.py "your query here"

# Control collection size (default: 10 per source)
python main.py "iris flower dataset" --max-results 20

# Enable web extraction (scrapes Wikipedia/Wikidata if no datasets found)
python main.py "Indian spice varieties" --extract

# Full options
python main.py "face detection images" --extract --max-results 15 --max-pages 30
```

### CLI Arguments

| Argument | Default | Description |
|---|---|---|
| `query` | (required) | Natural language query for datasets |
| `--max-results` | 10 | Max datasets per source. Higher = more data collected |
| `--extract` | off | Enable web extraction (Wikipedia tables, text, Wikidata entities) |
| `--max-pages` | 20 | Max pages to scan during web extraction |
| `--interactive` | off | Interactive mode (future) |
| `--user-id` | "default" | User identifier |

---

## What It Collects

### Data Types
| Type | Extensions | Sources |
|---|---|---|
| **Tabular** | CSV, TSV, JSON, JSONL, Parquet | HuggingFace, GitHub, WebSearch |
| **Document** | TXT, HTML, MD, PDF | GitHub, WebSearch |
| **Image** | JPG, PNG, GIF, BMP, WebP | GitHub, HuggingFace |
| **Audio** | WAV, MP3, FLAC, OGG | GitHub, HuggingFace |
| **Video** | MP4, AVI, MKV, WebM | GitHub, HuggingFace |

### Data Sources
| Source | Method | Auth Required |
|---|---|---|
| **HuggingFace Hub** | Free API (search + download) | No |
| **GitHub** | Free API (repo search + raw download) | No |
| **Kaggle** | Web scraping (metadata only) | Yes (download) |
| **Web Search** | Portal crawling + GitHub code search | No |
| **Web Extraction** | Wikipedia tables/text + Wikidata | No |

---

## Pipeline Architecture

```
Query → Parse → Discover → Collect → Validate → Dedup → Score → Clean → Build
  │        │         │          │         │         │       │       │       │
  │   NL Parser  Source     Spiders  Format   Hash    Quality  Normalize  Package
  │   (rules)   Registry   (HF,GH)  Check    Check   0-1.0   Encoding   + README
  │              FAISS               Type              Score              + Report
  └─────────────────────────────────────────────────────────────────────────┘
                              Lineage Tracking + Provenance
```

### Pipeline Stages

1. **Query Parser** — Rule-based NLP: detects domains (NLP, CV, medical...), language, modality, quality threshold, output format, merge flag
2. **Source Discovery** — Registry of 5 free sources + FAISS embedding similarity search
3. **Collection** — Per-source spiders with rate limiting + circuit breakers
4. **Validation** — Format detection, type classification (tabular/image/audio/video/document)
5. **Deduplication** — Exact hash matching across all collected files
6. **Quality Scoring** — Completeness, consistency, row count metrics (0-1.0 scale)
7. **Cleaning** — Encoding normalization, whitespace cleanup, row alignment
8. **Building** — Package with README, QUALITY_REPORT.json, SOURCES.txt, PROVENANCE.json, LINEAGE.json

---

## Output Structure

After a run, the workspace looks like:

```
workspace/session_XXXX/
├── raw/                    # Original downloaded files
│   ├── source_huggingface/
│   ├── source_github/
│   ├── source_kaggle/
│   ├── source_web_search/
│   └── source_web_extraction/
├── processed/              # Cleaned + validated files
├── final/                  # Packaged output (your deliverable)
│   ├── README.md           # Auto-generated dataset documentation
│   ├── QUALITY_REPORT.json # Per-file quality scores
│   ├── SOURCES.txt         # Source attribution
│   ├── PROVENANCE.json     # Full processing history
│   ├── LINEAGE.json        # Data origin tracking
│   └── *.csv, *.json, ...  # Cleaned dataset files
└── metadata/
    ├── session_info.json
    ├── progress.json
    ├── lineage.json
    └── provenance.json
```

---

## Key Features

### Lineage Tracking
Every dataset knows where it came from, what happened to it, and what files contributed to it.
```json
{
  "lineage_id": "lin_abc123",
  "dataset_path": "cleaned_iris.csv",
  "source_url": "https://raw.githubusercontent.com/...",
  "source_id": "github",
  "collection_timestamp": 1717680000,
  "transformations": [
    {"action": "validated", "timestamp": 1717680001},
    {"action": "cleaned", "timestamp": 1717680002}
  ]
}
```

### Provenance Tracking
Full event log of every processing step:
- `validated` → `schema_detected` → `quality_scored` → `cleaned` → `skipped` (if duplicate)

### Circuit Breaker
Per-source failure tracking prevents cascading failures. If a source fails 5 times, the circuit opens and skips it for subsequent requests (with exponential backoff recovery).

### Deduplication
Exact file hash matching across ALL sources. In tests, the system caught identical Iris datasets from 3 different GitHub repos and kept only 1.

### Web Extraction (--extract)
When no existing datasets are found, the system scrapes:
- **Wikipedia tables** — Structured data from any topic
- **Wikipedia text** — Article paragraphs as text corpus
- **Wikidata entities** — Structured knowledge graph entities

Creates separate CSV and JSON output files for each extraction type.

### Quality Scoring
Each dataset gets a 0.0-1.0 quality score based on:
- **Completeness** (60%) — % of non-empty cells
- **Consistency** (40%) — Row length consistency with headers
- Files with quality < 0.5 get flagged in the report

---

## Project Structure

```
galaxy_data/
├── main.py                          # CLI entry point
├── pyproject.toml                   # Dependencies
├── galaxy/
│   ├── types.py                     # All dataclasses and enums
│   ├── config.py                    # Configuration
│   ├── utils/                       # Hashing, retry
│   ├── cache/                       # 3-tier cache (L1/L2/L3)
│   ├── storage/                     # Session workspace, dataset store
│   ├── knowledge/                   # Source registry, metadata store, lineage
│   ├── intelligence/                # Query parser, FAISS embeddings
│   ├── collection/                  # Crawler pool, rate limiter, circuit breaker
│   │   └── spiders/                 # HuggingFace, GitHub, Kaggle, WebSearch, Generic
│   ├── processing/                  # Validator, schema detector, quality scorer
│   │   │                            # cleaner, deduplicator, merger, provenance
│   │   └── router.py               # Processing Router (routes by data type)
│   ├── agents/                      # Building agent, web extraction agent
│   └── orchestrator/                # Main pipeline controller
└── scrapling/                       # Scrapling framework (vendored)
```

### Module Count
- **Galaxy modules:** 46 Python files
- **Scrapling (vendored):** 51 Python files

---

## Dependencies

All Python, no external services required.

| Package | Purpose |
|---|---|
| `faiss-cpu` | Vector similarity search (FAISS) |
| `fakeredis` | In-memory Redis (no Redis server needed) |
| `aiosqlite` | Async SQLite for metadata |
| `lxml` | HTML parsing for web extraction |
| `scrapling` | Web scraping framework (vendored) |

Install all:
```bash
pip install -e ".[all]"
```

---

## Examples

### Collect sentiment analysis datasets
```bash
python main.py "sentiment analysis dataset" --max-results 10
# Result: 18 datasets, 151K+ rows from HuggingFace + GitHub
```

### Collect face detection images + videos
```bash
python main.py "face detection image dataset" --max-results 5 --extract
# Result: 15 files (10 images + 2 videos + 3 extracted tables)
```

### Collect speech/audio data
```bash
python main.py "speech recognition audio wav dataset" --max-results 5
# Result: 7 files (WAV audio + images)
```

### Create dataset from any topic (web extraction)
```bash
python main.py "Indian spice varieties" --extract --max-pages 30
# Result: Tables + text extracted from Wikipedia/Wikidata
```

### Classic ML dataset (with dedup)
```bash
python main.py "iris flower classification CSV"
# Result: 1 unique dataset (dedup caught 2 copies), 150 rows, quality 1.00
```

---

## Tested Results

| Query | Files | Rows | Quality | Formats | Duration |
|---|---|---|---|---|---|
| sentiment analysis | 18 | 151,741 | 0.97 | CSV, TSV, JSON, TXT | 48s |
| Indian spice varieties | 4 | 485 | 0.41 | CSV, JSON | 54s |
| iris flower CSV | 1 | 150 | 1.00 | CSV | 42s |
| face detection images | 15 | 623 | 0.93 | JPG, PNG, MP4, CSV | 62s |
| speech audio wav | 7 | 0 | 0.98 | WAV, JPG, PNG | 20s |

---

## Roadmap

- [ ] Authenticated sources (Kaggle download, HuggingFace private)
- [ ] Synthetic data engine
- [ ] Distributed processing layer
- [ ] Interactive CLI mode
- [ ] StealthyFetcher/DynamicFetcher integration (Scrapling browser modes)
- [ ] Parquet native support
- [ ] Dataset versioning

---

## License

Open source. All collected datasets retain their original licenses.
