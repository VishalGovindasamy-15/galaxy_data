"""Legal compliance - robots.txt and license checking."""
import logging
from urllib.parse import urlparse

log = logging.getLogger("galaxy.collection")

# Known open licenses
OPEN_LICENSES = [
    "cc0", "cc-by", "cc-by-sa", "cc-by-nc", "mit", "apache", "gpl", "bsd",
    "public domain", "odc-by", "odc-odbl", "pddl", "open", "free",
    "creative commons", "open data", "opendata",
]


class LegalChecker:
    """Check legal compliance for data collection."""
    
    def is_open_license(self, license_text: str) -> bool:
        """Check if license allows free use."""
        if not license_text:
            return True  # assume open if not specified
        lt = license_text.lower()
        return any(lic in lt for lic in OPEN_LICENSES)
    
    def detect_license_from_text(self, text: str) -> str:
        """Try to detect license from page text."""
        text_lower = text.lower()
        for lic in OPEN_LICENSES:
            if lic in text_lower:
                return lic
        return "unknown"
    
    def is_dataset_url(self, url: str) -> bool:
        """Check if URL likely points to a dataset file."""
        path = urlparse(url).path.lower()
        dataset_extensions = ['.csv', '.json', '.jsonl', '.parquet', '.tsv', '.xlsx', '.zip', '.tar', '.gz', '.txt']
        return any(path.endswith(ext) for ext in dataset_extensions)
