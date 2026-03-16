"""
Book Search Tool — BM25-based search over Project Gutenberg books.

Lazy loaded: the BM25 index and metadata are only loaded on first search call.
"""

import json
import os
import pickle

from rank_bm25 import BM25Okapi


# --- Tool Schema (what the LLM sees) ---

BOOK_SEARCH_SCHEMA = {
    "name": "search_books",
    "description": (
        "Search a library of classic books from Project Gutenberg. "
        "Finds relevant passages by content, and can filter by author or genre. "
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
    """BM25-based book search with lazy loading."""

    def __init__(self, metadata_file: str, index_file: str):
        self.metadata_file = metadata_file
        self.index_file = index_file

        # Lazy — loaded on first search
        self._bm25 = None
        self._chunks = None  # list of {text, title, author, genre, book_id}
        self._metadata = None

    def _load(self):
        """Load BM25 index and chunk data. Called once on first search."""
        if self._bm25 is not None:
            return

        if not os.path.exists(self.index_file):
            raise FileNotFoundError(
                f"BM25 index not found at {self.index_file}. "
                f"Run: python -m scripts.index_books"
            )

        print("[BookSearch] Loading BM25 index...")
        with open(self.index_file, "rb") as f:
            data = pickle.load(f)

        self._bm25 = data["bm25"]
        self._chunks = data["chunks"]

        with open(self.metadata_file) as f:
            self._metadata = json.load(f)

        print(f"[BookSearch] Loaded {len(self._chunks)} chunks from {len(self._metadata)} books.")

    def search(self, query: str, filter_author: str = None,
               filter_genre: str = None, max_results: int = 5) -> str:
        """Search books and return formatted results."""
        self._load()

        # Tokenize query (simple whitespace split — matches how we indexed)
        query_tokens = query.lower().split()

        # Score all chunks
        scores = self._bm25.get_scores(query_tokens)

        # Build scored results
        scored = []
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            chunk = self._chunks[i]

            # Apply filters
            if filter_author:
                if filter_author.lower() not in chunk["author"].lower():
                    continue
            if filter_genre:
                if filter_genre.lower() != chunk.get("genre", "").lower():
                    continue

            scored.append((score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max_results]

        if not top:
            return "No matching passages found. Try different keywords or remove filters."

        # Format results
        lines = []
        for rank, (score, chunk) in enumerate(top, 1):
            lines.append(
                f"[{rank}] \"{chunk['title']}\" by {chunk['author']} ({chunk.get('genre', 'unknown')})\n"
                f"    {chunk['text'][:500]}\n"
                f"    [Relevance: {score:.2f}]"
            )

        return "\n\n".join(lines)
