"""Filter engine — relevance filtering to remove unrelated data."""
import csv
import json
import logging
from pathlib import Path
from galaxy.types import CollectedFile

log = logging.getLogger("galaxy.processing")


def compute_relevance(file_path: str, query_terms: list[str]) -> float:
    """Score how relevant a file is to the query. Returns 0.0-1.0."""
    p = Path(file_path)
    name = p.stem.lower()
    ext = p.suffix.lower()
    score = 0.0
    
    # 1. Filename relevance (most important)
    terms_lower = [t.lower() for t in query_terms if len(t) > 2]
    if not terms_lower:
        return 0.5  # no terms to match
    
    name_hits = sum(1 for t in terms_lower if t in name)
    score += (name_hits / max(len(terms_lower), 1)) * 0.4
    
    # 2. Content relevance (sample first N bytes for text files)
    if ext in ('.csv', '.tsv', '.json', '.jsonl', '.txt', '.md', '.html'):
        try:
            with open(file_path, 'r', errors='replace') as f:
                sample = f.read(5000).lower()
            content_hits = sum(1 for t in terms_lower if t in sample)
            score += (content_hits / max(len(terms_lower), 1)) * 0.4
        except Exception:
            pass
    else:
        # For binary files (images/audio/video), rely more on filename + parent dir
        parent = p.parent.name.lower()
        parent_hits = sum(1 for t in terms_lower if t in parent)
        score += (parent_hits / max(len(terms_lower), 1)) * 0.2
        # Binary files get a base score since we can't read content
        score += 0.15
    
    # 3. File size bonus (non-trivial files are more likely useful)
    size = p.stat().st_size if p.exists() else 0
    if size > 10000:
        score += 0.1
    elif size > 1000:
        score += 0.05
    
    # 4. Metadata from source
    # (handled by caller if available)
    
    return min(score, 1.0)


def filter_relevant(files: list[CollectedFile], query: str,
                    threshold: float = 0.1) -> list[CollectedFile]:
    """Filter collected files by relevance to query. Keeps files above threshold."""
    if not files:
        return files
    
    terms = [w for w in query.lower().split() if len(w) > 2
             and w not in {'the', 'and', 'for', 'with', 'from', 'that', 'this',
                          'dataset', 'data', 'download', 'free', 'open'}]
    
    scored = []
    for f in files:
        rel = compute_relevance(f.path, terms)
        scored.append((f, rel))
    
    # Sort by relevance
    scored.sort(key=lambda x: x[1], reverse=True)
    
    kept = [f for f, r in scored if r >= threshold]
    removed = len(files) - len(kept)
    if removed > 0:
        log.info(f"Relevance filter: {len(files)} → {len(kept)} (removed {removed} irrelevant)")
    
    return kept
