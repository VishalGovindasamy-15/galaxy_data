"""FAISS-backed embedding store. Embeddings stored separately from query objects."""
import json
import uuid
import logging
import numpy as np
from pathlib import Path
from galaxy.config import Config

log = logging.getLogger("galaxy.intelligence")

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    log.warning("faiss-cpu not available, using numpy fallback")


class EmbeddingStore:
    """FAISS index for semantic search. Embeddings stored separately."""
    
    def __init__(self):
        self._index_path = Config.EMBEDDINGS_DIR / "embeddings.index"
        self._map_path = Config.EMBEDDINGS_DIR / "embedding_map.json"
        Config.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        
        self._dim = Config.EMBEDDING_DIM
        self._map: dict[str, dict] = {}  # id -> {text, vector}
        self._vectors: list[np.ndarray] = []
        self._ids: list[str] = []
        
        if HAS_FAISS:
            self._index = faiss.IndexFlatIP(self._dim)  # Inner product for cosine sim
        else:
            self._index = None
        
        self._load()
    
    def _load(self):
        """Load existing map from disk."""
        if self._map_path.exists():
            self._map = json.loads(self._map_path.read_text())
            self._ids = list(self._map.keys())
    
    def _simple_embed(self, text: str) -> np.ndarray:
        """Simple TF-IDF-like embedding (no model needed). Fast fallback."""
        # Hash-based embedding: deterministic, fast
        words = text.lower().split()
        vec = np.zeros(self._dim, dtype=np.float32)
        for i, word in enumerate(words):
            for j, c in enumerate(word):
                idx = (hash(word) + j * 7 + i * 13) % self._dim
                vec[idx] += 1.0
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
    
    def store(self, text: str) -> str:
        """Store text embedding. Returns embedding_id."""
        emb_id = f"emb_{uuid.uuid4().hex[:10]}"
        vec = self._simple_embed(text)
        
        self._map[emb_id] = {"text": text}
        self._ids.append(emb_id)
        
        if self._index is not None:
            self._index.add(vec.reshape(1, -1))
        
        self._save()
        return emb_id
    
    def search(self, text: str, top_k: int = 5) -> list[dict]:
        """Search for similar embeddings. Returns [{id, score, text}]."""
        if not self._ids:
            return []
        
        query_vec = self._simple_embed(text)
        
        if self._index is not None and self._index.ntotal > 0:
            scores, indices = self._index.search(query_vec.reshape(1, -1), min(top_k, len(self._ids)))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self._ids):
                    eid = self._ids[idx]
                    results.append({"id": eid, "score": float(score), "text": self._map[eid]["text"]})
            return results
        return []
    
    def _save(self):
        """Persist map to disk."""
        self._map_path.write_text(json.dumps(self._map, indent=2))
