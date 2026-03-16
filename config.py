"""Hudson configuration."""

import os

# --- Model ---
MODEL = "qwen3.5:9b"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
OLLAMA_API_KEY = "ollama"
TEMPERATURE = 0.7  # personality sweet spot: creative but coherent

# --- Agent ---
MAX_AGENT_STEPS = 20
MAX_TOOL_OUTPUT_CHARS = 10000

# --- Paths (cross-platform) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKS_RAW_DIR = os.path.join(BASE_DIR, "data", "books", "raw")
BOOKS_METADATA_FILE = os.path.join(BASE_DIR, "data", "metadata", "books.json")
BM25_INDEX_FILE = os.path.join(BASE_DIR, "data", "bm25_index.pkl")
VECTOR_INDEX_FILE = os.path.join(BASE_DIR, "data", "vector_index.pkl")

# --- .env support ---
# Load .env file if it exists (for API keys)
_env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:
                    os.environ[key] = value
