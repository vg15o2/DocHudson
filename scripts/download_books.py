"""
Download 50 classic books from Project Gutenberg as .txt files.

Usage: python -m scripts.download_books
Run from the hudson/ directory.
"""

import os
import time
import urllib.request

# 50 curated classics — diverse genres and authors
BOOKS = [
    # (gutenberg_id, title, author, genre)
    (1342, "Pride and Prejudice", "Jane Austen", "fiction"),
    (11, "Alice's Adventures in Wonderland", "Lewis Carroll", "fiction"),
    (1661, "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "fiction"),
    (84, "Frankenstein", "Mary Shelley", "fiction"),
    (1260, "Jane Eyre", "Charlotte Bronte", "fiction"),
    (2701, "Moby Dick", "Herman Melville", "fiction"),
    (98, "A Tale of Two Cities", "Charles Dickens", "fiction"),
    (1952, "The Yellow Wallpaper", "Charlotte Perkins Gilman", "fiction"),
    (174, "The Picture of Dorian Gray", "Oscar Wilde", "fiction"),
    (345, "Dracula", "Bram Stoker", "fiction"),
    (1080, "A Modest Proposal", "Jonathan Swift", "fiction"),
    (76, "Adventures of Huckleberry Finn", "Mark Twain", "fiction"),
    (219, "Heart of Darkness", "Joseph Conrad", "fiction"),
    (5200, "Metamorphosis", "Franz Kafka", "fiction"),
    (2554, "Crime and Punishment", "Fyodor Dostoevsky", "fiction"),
    (28054, "The Brothers Karamazov", "Fyodor Dostoevsky", "fiction"),
    (600, "Notes from the Underground", "Fyodor Dostoevsky", "fiction"),
    (2600, "War and Peace", "Leo Tolstoy", "fiction"),
    (1399, "Anna Karenina", "Leo Tolstoy", "fiction"),
    (4300, "Ulysses", "James Joyce", "fiction"),
    (16, "Peter Pan", "J.M. Barrie", "fiction"),
    (1232, "The Prince", "Niccolo Machiavelli", "philosophy"),
    (3600, "Thus Spake Zarathustra", "Friedrich Nietzsche", "philosophy"),
    (4363, "Beyond Good and Evil", "Friedrich Nietzsche", "philosophy"),
    (5827, "The Problems of Philosophy", "Bertrand Russell", "philosophy"),
    (1497, "The Republic", "Plato", "philosophy"),
    (10616, "Meditations", "Marcus Aurelius", "philosophy"),
    (55, "The Wonderful Wizard of Oz", "L. Frank Baum", "fiction"),
    (120, "Treasure Island", "Robert Louis Stevenson", "fiction"),
    (1400, "Great Expectations", "Charles Dickens", "fiction"),
    (25344, "The Scarlet Letter", "Nathaniel Hawthorne", "fiction"),
    (2591, "Grimms' Fairy Tales", "Brothers Grimm", "fiction"),
    (244, "A Study in Scarlet", "Arthur Conan Doyle", "fiction"),
    (1184, "The Count of Monte Cristo", "Alexandre Dumas", "fiction"),
    (35, "The Time Machine", "H.G. Wells", "fiction"),
    (36, "The War of the Worlds", "H.G. Wells", "fiction"),
    (43, "The Strange Case of Dr. Jekyll and Mr. Hyde", "Robert Louis Stevenson", "fiction"),
    (46, "A Christmas Carol", "Charles Dickens", "fiction"),
    (1251, "Le Morte d'Arthur", "Thomas Malory", "fiction"),
    (2500, "Siddhartha", "Hermann Hesse", "fiction"),
    (2814, "Dubliners", "James Joyce", "fiction"),
    (158, "Emma", "Jane Austen", "fiction"),
    (161, "Sense and Sensibility", "Jane Austen", "fiction"),
    (1727, "The Odyssey", "Homer", "poetry"),
    (6130, "The Iliad", "Homer", "poetry"),
    (1041, "Shakespeare's Sonnets", "William Shakespeare", "poetry"),
    (1524, "Hamlet", "William Shakespeare", "drama"),
    (1533, "Macbeth", "William Shakespeare", "drama"),
    (1513, "Romeo and Juliet", "William Shakespeare", "drama"),
    (23, "Narrative of the Life of Frederick Douglass", "Frederick Douglass", "biography"),
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "books", "raw")
METADATA_FILE = os.path.join(BASE_DIR, "data", "metadata", "books.json")


def download_book(book_id: int, title: str) -> str | None:
    """Download a single book from Gutenberg. Returns file path or None."""
    filepath = os.path.join(RAW_DIR, f"{book_id}.txt")

    if os.path.exists(filepath):
        print(f"  [skip] {title} (already downloaded)")
        return filepath

    # Try UTF-8 plain text first, then fall back to ASCII
    urls = [
        f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
        f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt",
    ]

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HudsonAgent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"  [ok] {title}")
            return filepath
        except Exception:
            continue

    print(f"  [FAIL] {title} (id={book_id})")
    return None


def strip_gutenberg_header_footer(text: str) -> str:
    """Remove Project Gutenberg boilerplate from start and end."""
    lines = text.split("\n")
    start = 0
    end = len(lines)

    for i, line in enumerate(lines):
        if "*** START OF" in line.upper() or "***START OF" in line.upper():
            start = i + 1
            break

    for i in range(len(lines) - 1, -1, -1):
        if "*** END OF" in lines[i].upper() or "***END OF" in lines[i].upper():
            end = i
            break

    return "\n".join(lines[start:end]).strip()


def main():
    import json

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)

    metadata = []
    downloaded = 0

    print(f"Downloading {len(BOOKS)} books from Project Gutenberg...\n")

    for book_id, title, author, genre in BOOKS:
        filepath = download_book(book_id, title)
        if filepath:
            # Strip headers
            with open(filepath, "r", encoding="utf-8") as f:
                raw = f.read()
            cleaned = strip_gutenberg_header_footer(raw)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(cleaned)

            metadata.append({
                "gutenberg_id": book_id,
                "title": title,
                "author": author,
                "genre": genre,
                "file": filepath,
            })
            downloaded += 1

        # Be polite to Gutenberg servers
        time.sleep(1)

    # Save metadata
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nDone. {downloaded}/{len(BOOKS)} books downloaded.")
    print(f"Metadata saved to {METADATA_FILE}")


if __name__ == "__main__":
    main()
