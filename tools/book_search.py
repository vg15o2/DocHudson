"""
Book Search Tool — Composite search (BM25 + Vector) with Reciprocal Rank Fusion.

BM25 catches keyword matches. Vector catches semantic meaning.
RRF merges both result sets so you get the best of both worlds.

Lazy loaded: indexes and embedding model only load on first search call.
"""

import json
import os
import pickle

import numpy as np
from rank_bm25 import BM25Okapi


# --- Tool Schema (what the LLM sees) ---

BOOK_SEARCH_SCHEMA = {
    "name": "search_books",
    "description": (
        "Search a library of classic books from Project Gutenberg. "
        "Finds relevant passages by content using keyword AND semantic search. "
        "Can filter by author or genre. "
        "Use this when the user asks about literature, quotes, themes, authors, or book content."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'themes of isolation in Moby Dick' or 'love poems'"
            },
            "filter_author": {
                "type": "string",
                "description": "Filter results to a specific author, e.g. 'Shakespeare'. Optional."
            },
            "filter_genre": {
                "type": "string",
                "description": "Filter by genre: fiction, poetry, drama, philosophy, history, science, biography. Optional."
            },
            "max_results": {
                "type": "integer",
                "description": "Number of passages to return. Default 5."
            },
        },
        "required": ["query"],
    },
}


# --- Tool Implementation ---

class BookSearchTool:
    """Composite BM25 + Vector search with RRF. Lazy loaded."""

    RRF_K = 60  # standard RRF constant

    def __init__(self, metadata_file: str, index_file: str, vector_index_file: str):
        self.metadata_file = metadata_file
        self.index_file = index_file
        self.vector_index_file = vector_index_file

        # Lazy — loaded on first search
        self._bm25 = None
        self._chunks = None
        self._metadata = None
        self._embeddings = None
        self._embed_model = None
        self._vector_available = False

    def _load(self):
        """Load indexes on first search call."""
        if self._bm25 is not None:
            return

        if not os.path.exists(self.index_file):
            raise FileNotFoundError(
                f"BM25 index not found at {self.index_file}. "
                f"Run: python -m scripts.index_books"
            )

        # Load BM25 (always available)
        print("[BookSearch] Loading BM25 index...")
        with open(self.index_file, "rb") as f:
            data = pickle.load(f)
        self._bm25 = data["bm25"]
        self._chunks = data["chunks"]

        with open(self.metadata_file) as f:
            self._metadata = json.load(f)

        # Load vector index (optional — falls back to BM25-only if missing)
        if os.path.exists(self.vector_index_file):
            try:
                from sentence_transformers import SentenceTransformer
                print("[BookSearch] Loading vector index + embedding model...")
                with open(self.vector_index_file, "rb") as f:
                    vec_data = pickle.load(f)
                self._embeddings = vec_data["embeddings"]
                self._embed_model = SentenceTransformer("all-MiniLM-L6-v2")
                self._vector_available = True
                print("[BookSearch] Composite search ready (BM25 + Vector).")
            except Exception as e:
                print(f"[BookSearch] Vector search unavailable ({e}). Using BM25 only.")
        else:
            print("[BookSearch] No vector index found. Using BM25 only.")

        print(f"[BookSearch] Loaded {len(self._chunks)} chunks from {len(self._metadata)} books.")

    def _bm25_search(self, query: str, n: int) -> list[tuple[int, float]]:
        """Return top N (chunk_index, score) by BM25."""
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        # Get top indices
        top_indices = np.argsort(scores)[::-1][:n]
        return [(int(i), float(scores[i])) for i in top_indices if scores[i] > 0]

    def _vector_search(self, query: str, n: int) -> list[tuple[int, float]]:
        """Return top N (chunk_index, score) by vector similarity."""
        query_embedding = self._embed_model.encode(query)
        # Normalize
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        # Cosine similarity via dot product (embeddings are pre-normalized)
        similarities = self._embeddings @ query_embedding
        top_indices = np.argsort(similarities)[::-1][:n]
        return [(int(i), float(similarities[i])) for i in top_indices]

    def _rrf_merge(self, bm25_results: list, vector_results: list,
                   n: int) -> list[int]:
        """Merge two ranked lists using Reciprocal Rank Fusion."""
        scores = {}

        for rank, (idx, _) in enumerate(bm25_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (self.RRF_K + rank + 1)

        for rank, (idx, _) in enumerate(vector_results):
            scores[idx] = scores.get(idx, 0) + 1.0 / (self.RRF_K + rank + 1)

        # Sort by combined score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in ranked[:n]]

    def search(self, query: str, filter_author: str = None,
               filter_genre: str = None, max_results: int = 5) -> str:
        """Search books using composite BM25 + vector search."""
        self._load()

        # Fetch more candidates than needed (filters will reduce the set)
        fetch_n = max_results * 10

        bm25_results = self._bm25_search(query, fetch_n)

        if self._vector_available:
            vector_results = self._vector_search(query, fetch_n)
            candidate_indices = self._rrf_merge(bm25_results, vector_results, fetch_n)
        else:
            candidate_indices = [idx for idx, _ in bm25_results]

        # Apply filters and collect top results
        results = []
        for idx in candidate_indices:
            if len(results) >= max_results:
                break

            chunk = self._chunks[idx]

            if filter_author:
                if filter_author.lower() not in chunk["author"].lower():
                    continue
            if filter_genre:
                if filter_genre.lower() != chunk.get("genre", "").lower():
                    continue

            results.append(chunk)

        if not results:
            return "No matching passages found. Try different keywords or remove filters."

        # Format results
        lines = []
        for rank, chunk in enumerate(results, 1):
            lines.append(
                f"[{rank}] \"{chunk['title']}\" by {chunk['author']} ({chunk.get('genre', 'unknown')})\n"
                f"    {chunk['text'][:500]}"
            )

        return "\n\n".join(lines)
