"""Galaxy Data configuration."""
from pathlib import Path
import os


class Config:
    # Base paths
    PROJECT_DIR = Path(os.environ.get("GALAXY_DATA_DIR", "/mnt/78CA356BCA352732/Galaxy Data/galaxy_data"))
    WORKSPACE_DIR = PROJECT_DIR / "workspace"
    PERMANENT_STORE_DIR = PROJECT_DIR / "store"
    CACHE_DIR = PROJECT_DIR / ".cache"
    EMBEDDINGS_DIR = PROJECT_DIR / ".embeddings"
    
    # Collection settings
    HTTP_POOL_SIZE = 10
    BROWSER_POOL_SIZE = 2
    MAX_CONCURRENT_SPIDERS = 4
    DOWNLOAD_DELAY = 1.0
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30
    MAX_FILE_SIZE_MB = 500
    
    # Rate limiting
    DEFAULT_RATE_LIMIT = 2.0  # requests per second per domain
    RATE_LIMIT_WINDOW = 60    # seconds
    
    # Circuit breaker
    CB_FAILURE_THRESHOLD = 5
    CB_OPEN_DURATION = 60     # seconds
    CB_HALF_OPEN_REQUESTS = 3
    
    # Processing
    QUALITY_THRESHOLD = 0.3
    DEDUP_SIMILARITY_THRESHOLD = 0.85
    MAX_ROWS_PER_DATASET = 1_000_000
    
    # Cache TTLs (seconds)
    CACHE_L1_TTL = 3600       # 1 hour
    CACHE_L2_TTL = 86400      # 24 hours
    CACHE_L3_TTL = 604800     # 7 days
    
    # Embeddings
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384
    
    # Web extraction
    WEB_EXTRACT_MAX_PAGES = 30
    
    # User agent
    USER_AGENT = "GalaxyData/0.1 (Dataset Intelligence Platform)"
    
    @classmethod
    def ensure_dirs(cls):
        """Create all required directories."""
        for d in [cls.WORKSPACE_DIR, cls.PERMANENT_STORE_DIR, cls.CACHE_DIR, cls.EMBEDDINGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)
