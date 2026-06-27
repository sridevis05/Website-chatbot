import os
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
from backend.config import settings

class ChromaDBManager:
    def __init__(self):
        print(f"Initializing ChromaDB Client at: {settings.CHROMA_DB_DIR}")
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
        # Create or load the main collection
        self.collection = self.client.get_or_create_collection(
            name="website_rag_collection",
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )

    def add_chunks(self, ids: List[str], embeddings: List[List[float]], documents: List[str], metadatas: List[Dict[str, Any]]):
        """
        Upserts chunks, their embeddings, and metadata into ChromaDB.
        """
        if not ids:
            return
            
        # ChromaDB supports upsert to avoid duplicate IDs
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        print(f"Upserted {len(ids)} documents into ChromaDB.")

    def query(self, query_embedding: List[float], website_url: Optional[str] = None, k: int = 4) -> List[Dict[str, Any]]:
        """
        Queries the ChromaDB collection. Filters by website base URL if provided.
        """
        where_filter = {}
        if website_url:
            # We filter chunks where the 'website' metadata field matches
            where_filter = {"website": website_url}
            
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter if where_filter else None
        )
        
        formatted_results = []
        if not results or not results["documents"] or not results["documents"][0]:
            return formatted_results
            
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        ids = results["ids"][0]
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)
        
        for doc, meta, doc_id, dist in zip(docs, metas, ids, distances):
            # In ChromaDB, distance is cosine distance, convert to similarity: 1 - distance
            similarity = 1.0 - dist
            formatted_results.append({
                "id": doc_id,
                "chunk": doc,
                "metadata": meta,
                "score": max(0.0, min(1.0, similarity)) # clamp to [0.0, 1.0]
            })
            
        return formatted_results

    def delete_website(self, website_url: str):
        """
        Deletes all chunks associated with a specific website base URL.
        """
        self.collection.delete(where={"website": website_url})
        print(f"Deleted all records for website: {website_url} from ChromaDB.")

    def get_indexed_websites(self) -> List[Dict[str, Any]]:
        """
        Scans all records and aggregates distinct websites, counting pages and fetching titles.
        """
        # Fetch metadata for all documents in the collection
        all_data = self.collection.get(include=["metadatas"])
        metadatas = all_data.get("metadatas", [])
        
        websites = {}
        for meta in metadatas:
            if not meta or "website" not in meta:
                continue
            website = meta["website"]
            source = meta.get("source", "")
            title = meta.get("title", "Untitled Site")
            
            if website not in websites:
                websites[website] = {
                    "url": website,
                    "title": title, # Use title from first page
                    "pages": set(),
                    "chunk_count": 0
                }
            websites[website]["pages"].add(source)
            websites[website]["chunk_count"] += 1
            
        result = []
        for web in websites.values():
            result.append({
                "url": web["url"],
                "title": web["title"],
                "pages_count": len(web["pages"]),
                "chunk_count": web["chunk_count"]
            })
            
        return result

# Global singleton database manager instance
db_manager = ChromaDBManager()
