"""
Index books into BM25 + vector search indexes.

Reads downloaded .txt files, chunks them, builds both indexes, saves to disk.

Usage: python -m scripts.index_books
Run from the hudson/ directory.
"""

import json
import os
import pickle
import numpy as np

from rank_bm25 import BM25Okapi


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METADATA_FILE = os.path.join(BASE_DIR, "data", "metadata", "books.json")
INDEX_FILE = os.path.join(BASE_DIR, "data", "bm25_index.pkl")
VECTOR_INDEX_FILE = os.path.join(BASE_DIR, "data", "vector_index.pkl")

# Chunking config
CHUNK_SIZE = 400      # words per chunk (~520 tokens, ~1.5 paragraphs)
CHUNK_OVERLAP = 50    # words overlap between chunks (~12% overlap)


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


def build_chunks(metadata):
    """Read all books and build chunk list."""
    all_chunks = []
    all_tokenized = []

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
            all_tokenized.append(chunk_text_str.lower().split())

        print(f"  [ok] {book['title']}: {len(chunks)} chunks")

    return all_chunks, all_tokenized


def build_bm25_index(all_tokenized, all_chunks):
    """Build and save BM25 index."""
    print("\nBuilding BM25 index...")
    bm25 = BM25Okapi(all_tokenized)

    os.makedirs(os.path.dirname(INDEX_FILE), exist_ok=True)
    with open(INDEX_FILE, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": all_chunks}, f)

    size_mb = os.path.getsize(INDEX_FILE) / (1024 * 1024)
    print(f"BM25 index saved to {INDEX_FILE} ({size_mb:.1f} MB)")


def build_vector_index(all_chunks):
    """Build and save vector embeddings index."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("\n[skip] Vector index — sentence-transformers not installed")
        print("  Install with: pip install sentence-transformers")
        return

    print("\nBuilding vector index (this takes a few minutes on CPU)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [c["text"] for c in all_chunks]

    # Encode in batches to show progress
    batch_size = 256
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False)
        all_embeddings.append(embeddings)
        done = min(i + batch_size, len(texts))
        print(f"  Embedded {done}/{len(texts)} chunks...")

    embeddings_matrix = np.vstack(all_embeddings)

    # Normalize for cosine similarity (dot product on normalized = cosine)
    norms = np.linalg.norm(embeddings_matrix, axis=1, keepdims=True)
    embeddings_matrix = embeddings_matrix / norms

    os.makedirs(os.path.dirname(VECTOR_INDEX_FILE), exist_ok=True)
    with open(VECTOR_INDEX_FILE, "wb") as f:
        pickle.dump({"embeddings": embeddings_matrix}, f)

    size_mb = os.path.getsize(VECTOR_INDEX_FILE) / (1024 * 1024)
    print(f"Vector index saved to {VECTOR_INDEX_FILE} ({size_mb:.1f} MB)")


def main():
    if not os.path.exists(METADATA_FILE):
        print(f"Metadata not found at {METADATA_FILE}")
        print("Run first: python -m scripts.download_books")
        return

    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    print(f"Indexing {len(metadata)} books...\n")

    all_chunks, all_tokenized = build_chunks(metadata)
    print(f"\nTotal chunks: {len(all_chunks)}")

    build_bm25_index(all_tokenized, all_chunks)
    build_vector_index(all_chunks)

    print("\nDone!")


if __name__ == "__main__":
    main()
