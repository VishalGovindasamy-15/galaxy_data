"""Query parser - natural language to structured query (rule-based, fast)."""
import re
import logging
from galaxy.types import StructuredQuery

log = logging.getLogger("galaxy.intelligence")

# Known domains
DOMAIN_KEYWORDS = {
    "ocr": ["ocr", "optical character recognition", "text recognition"],
    "nlp": ["nlp", "natural language", "text", "sentiment", "translation", "ner", "chatbot"],
    "cv": ["image", "vision", "object detection", "segmentation", "classification", "face"],
    "medical": ["medical", "health", "clinical", "diagnosis", "radiology", "pathology"],
    "audio": ["audio", "speech", "voice", "music", "sound"],
    "tabular": ["tabular", "csv", "excel", "structured", "table"],
    "video": ["video", "action recognition", "tracking"],
    "time_series": ["time series", "stock", "weather", "sensor", "iot"],
    "recommendation": ["recommendation", "collaborative filtering", "rating"],
}

# Languages
LANGUAGES = {
    "tamil": "ta", "english": "en", "hindi": "hi", "french": "fr", "german": "de",
    "spanish": "es", "chinese": "zh", "japanese": "ja", "korean": "ko", "arabic": "ar",
    "telugu": "te", "kannada": "kn", "malayalam": "ml", "bengali": "bn", "urdu": "ur",
}

# Modalities
MODALITY_KEYWORDS = {
    "images": ["image", "photo", "picture", "visual", "cv", "face"],
    "text": ["text", "nlp", "corpus", "document", "article"],
    "tabular": ["csv", "tabular", "table", "excel", "structured"],
    "audio": ["audio", "speech", "voice", "sound", "music"],
    "video": ["video", "clip", "footage"],
}

# Format keywords
FORMAT_KEYWORDS = {
    "csv": ["csv"], "json": ["json", "jsonl"], "parquet": ["parquet"],
}


def parse_query(query: str) -> StructuredQuery:
    """Parse natural language query into StructuredQuery."""
    q_lower = query.lower().strip()
    
    # Detect domains
    domains = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            domains.append(domain)
    
    # Detect language
    language = "en"
    for lang_name, code in LANGUAGES.items():
        if lang_name in q_lower:
            language = code
            break
    
    # Detect modality
    modality = "mixed"
    for mod, keywords in MODALITY_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            modality = mod
            break
    
    # Detect min_samples
    min_samples = 0
    match = re.search(r'(?:>|more than|at least|min(?:imum)?)\s*(\d+)\s*(?:samples?|rows?|records?|entries?)', q_lower)
    if match:
        min_samples = int(match.group(1))
    
    # Detect quality threshold
    quality = 0.5
    match = re.search(r'quality\s*(?:>|above|over)\s*([\d.]+)', q_lower)
    if match:
        quality = float(match.group(1))
    
    # Detect merge request
    merge = any(w in q_lower for w in ["merge", "combine", "consolidate", "merge all"])
    
    # Detect output format
    output_format = "csv"
    for fmt, keywords in FORMAT_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            output_format = fmt
            break
    
    # Generate search queries
    search_queries = [query]
    # Add domain-specific variations
    for d in domains:
        search_queries.append(f"{query} {d} dataset")
    search_queries.append(f"{query} dataset download")
    
    return StructuredQuery(
        original_query=query,
        domains=domains,
        language=language,
        modality=modality,
        min_samples=min_samples,
        quality_threshold=quality,
        license_filter="open",
        merge=merge,
        output_format=output_format,
        search_queries=list(set(search_queries)),
    )
