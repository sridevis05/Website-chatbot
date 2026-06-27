import os
import hashlib
import pickle
from typing import List
from sentence_transformers import SentenceTransformer
from backend.config import settings

class CachedEmbedder:
    def __init__(self):
        print(f"Loading SentenceTransformer model: {settings.EMBEDDING_MODEL_NAME}...")
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        self.cache_path = os.path.join(settings.CACHE_DIR, "embeddings_cache.pkl")
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "rb") as f:
                    self.cache = pickle.load(f)
                print(f"Loaded {len(self.cache)} cached embeddings from disk.")
            except Exception as e:
                print(f"Error loading embedding cache: {e}")
                self.cache = {}

    def _save_cache(self):
        try:
            # Create parent directories if missing
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "wb") as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"Error saving embedding cache: {e}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of texts using SentenceTransformer. Utilizes SHA-256 text hashing
        to cache and reuse embeddings.
        """
        if not texts:
            return []
            
        hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        embeddings = [None] * len(texts)
        missing_indices = []
        missing_texts = []
        
        for idx, h in enumerate(hashes):
            if h in self.cache:
                embeddings[idx] = self.cache[h]
            else:
                missing_indices.append(idx)
                missing_texts.append(texts[idx])
                
        if missing_texts:
            print(f"Generating embeddings for {len(missing_texts)} new texts...")
            computed_embeddings = self.model.encode(missing_texts, show_progress_bar=False)
            
            for idx, emb in zip(missing_indices, computed_embeddings):
                # Convert numpy array to standard float list
                emb_list = emb.tolist()
                embeddings[idx] = emb_list
                self.cache[hashes[idx]] = emb_list
                
            self._save_cache()
            
        return embeddings

# Global singleton instance
embedder = CachedEmbedder()
