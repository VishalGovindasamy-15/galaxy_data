"""Core types for Galaxy Data platform."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time, uuid


# --- Session States ---

class SessionState(Enum):
    RECEIVED = "received"
    VALIDATING = "validating"
    PLANNING = "planning"
    CACHE_CHECK = "cache_check"
    DISCOVERING = "discovering"
    COLLECTING = "collecting"
    WEB_EXTRACTING = "web_extracting"
    PROCESSING = "processing"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataType(Enum):
    TABULAR = "tabular"
    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    GENERIC = "generic"


# --- Core Request/Response Types ---

@dataclass
class GatewayRequest:
    query: str
    user_id: str = "default"
    session_id: str = ""
    options: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.session_id:
            self.session_id = f"session_{uuid.uuid4().hex[:12]}"


@dataclass
class StructuredQuery:
    original_query: str
    domains: list[str] = field(default_factory=list)
    language: str = "en"
    modality: str = "mixed"
    min_samples: int = 0
    quality_threshold: float = 0.5
    license_filter: str = "open"
    merge: bool = False
    output_format: str = "csv"
    embedding_id: str = ""
    search_queries: list[str] = field(default_factory=list)


@dataclass
class SourceCandidate:
    source_id: str
    url: str
    priority: int = 50
    crawler_type: str = "http"
    reliability_score: float = 0.8
    estimated_time: float = 30.0


@dataclass
class ExecutionPlan:
    session_id: str
    sources: list[SourceCandidate] = field(default_factory=list)
    estimated_total_time: float = 0.0


@dataclass
class CollectedFile:
    path: str
    hash: str
    size_bytes: int
    source_id: str
    format: str
    url: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CollectionResult:
    session_id: str
    files: list[CollectedFile] = field(default_factory=list)
    sources_crawled: int = 0
    sources_failed: int = 0
    total_size_bytes: int = 0
    duration_seconds: float = 0.0


@dataclass
class DatasetInfo:
    path: str
    schema: dict = field(default_factory=dict)
    quality_score: float = 0.0
    row_count: int = 0
    column_count: int = 0
    format: str = ""
    source_id: str = ""
    license: str = "unknown"
    dedup_status: str = "unique"
    lineage_id: str = ""
    data_type: DataType = DataType.GENERIC


@dataclass
class LineageRecord:
    lineage_id: str
    dataset_path: str
    source_url: str
    source_id: str
    collection_timestamp: float = 0.0
    transformations: list[dict] = field(default_factory=list)
    parent_files: list[str] = field(default_factory=list)
    removal_reason: str = ""
    quality_score_history: list[float] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.collection_timestamp:
            self.collection_timestamp = time.time()


@dataclass
class ProcessingResult:
    session_id: str
    datasets: list[DatasetInfo] = field(default_factory=list)
    quality_report: dict = field(default_factory=dict)
    dedup_report: dict = field(default_factory=dict)
    datasets_input: int = 0
    datasets_output: int = 0


@dataclass
class BuildResult:
    session_id: str
    package_path: str = ""
    size_bytes: int = 0
    datasets_count: int = 0
    total_samples: int = 0
    quality_score: float = 0.0
    reports: list[str] = field(default_factory=list)


@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    state: SessionState
    query: StructuredQuery
    workspace_path: str
    created_at: float = 0.0
    updated_at: float = 0.0
    progress: dict = field(default_factory=dict)
    error: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = time.time()


@dataclass
class AgentMessage:
    type: str
    session_id: str
    agent: str
    payload: dict = field(default_factory=dict)
    priority: int = 0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# --- Web Extraction Types ---

@dataclass
class WebExtractionRequest:
    session_id: str
    search_queries: list[str] = field(default_factory=list)
    max_pages: int = 50
    extract_tables: bool = True
    extract_text: bool = True
    extract_images: bool = True
    user_approved: bool = False


@dataclass
class ExtractedRecord:
    source_url: str
    data: dict = field(default_factory=dict)
    extraction_method: str = "table"
    confidence: float = 0.0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


# --- Processing Types ---

@dataclass
class ValidationResult:
    valid: bool
    format: str = ""
    row_count: int = 0
    errors: list[str] = field(default_factory=list)
    data_type: DataType = DataType.GENERIC


@dataclass
class Schema:
    columns: dict = field(default_factory=dict)
    patterns: dict = field(default_factory=dict)


@dataclass
class DedupResult:
    is_duplicate: bool = False
    original_hash: str = ""
    similarity: float = 0.0


@dataclass
class QualityReport:
    score: float = 0.0
    completeness: float = 0.0
    consistency: float = 0.0
    issues: list[str] = field(default_factory=list)
