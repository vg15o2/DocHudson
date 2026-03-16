"""
Index books into a BM25 search index.

Reads downloaded .txt files, chunks them, builds BM25 index, saves to disk.

Usage: python -m scripts.index_books
Run from the hudson/ directory.
"""

import json
import os
import pickle

from rank_bm25 import BM25Okapi


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METADATA_FILE = os.path.join(BASE_DIR, "data", "metadata", "books.json")
INDEX_FILE = os.path.join(BASE_DIR, "data", "bm25_index.pkl")

# Chunking config
CHUNK_SIZE = 400      # words per chunk
CHUNK_OVERLAP = 50    # words overlap between chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def main():
    if not os.path.exists(METADATA_FILE):
        print(f"Metadata not found at {METADATA_FILE}")
        print("Run first: python -m scripts.download_books")
        return

    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    print(f"Indexing {len(metadata)} books...\n")

    all_chunks = []       # list of {text, title, author, genre, book_id}
    all_tokenized = []    # list of tokenized chunks (for BM25)

    for book in metadata:
        filepath = book["file"]
        if not os.path.exists(filepath):
            print(f"  [skip] {book['title']} — file not found")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)

        for chunk_text_str in chunks:
            all_chunks.append({
                "text": chunk_text_str,
                "title": book["title"],
                "author": book["author"],
                "genre": book["genre"],
                "book_id": book["gutenberg_id"],
            })
            # BM25 needs tokenized (list of words)
            all_tokenized.append(chunk_text_str.lower().split())

        print(f"  [ok] {book['title']}: {len(chunks)} chunks")

    print(f"\nTotal chunks: {len(all_chunks)}")
    print("Building BM25 index...")

    bm25 = BM25Okapi(all_tokenized)

    # Save index + chunks
    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": all_chunks}, f)

    print(f"Index saved to {INDEX_FILE}")
    size_mb = os.path.getsize(INDEX_FILE) / (1024 * 1024)
    print(f"Index size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
