# Hudson

**A local AI agent runtime built from scratch. No frameworks. No training wheels.**

Hudson is a fully local AI agent that runs on your machine using Ollama. It has tools, skills, subagents, composite search over 50 classic books, a pixel art visualizer, and a personality that's somewhere between a literature professor and a film critic who won't shut up about Nolan.

This is not a wrapper around LangChain. Every line -- the agent loop, the tool registry, the orchestrator, the search pipeline -- is written from scratch in Python.

---

## Architecture

```
                          +------------------+
                          |      User        |
                          +--------+---------+
                                   |
                                   v
                     +-------------+-------------+
                     |     Hudson (Orchestrator)  |
                     |     agent/runtime.py       |
                     +---+--------+----------+---+
                         |        |          |
              +----------+   +----+----+   +-+----------+
              |              |         |               |
         +----v----+   +----v----+  +-v--------+  +---v-------+
         |  Tools  |   | Skills  |  | Subagents|  |  Tracer   |
         +---------+   +---------+  +----------+  +-----------+
         | search_ |   | deep_   |  | BookAgent|  | JSONL     |
         |  books  |   | research|  | Spillberg|  | events    |
         | web_    |   | movie_  |  | Research |  | pixel art |
         |  search |   |  book_  |  |  Agent   |  | visualizer|
         | search_ |   |  bridge |  | CodeAgent|  +-----------+
         |  movies |   | study_  |  | Ozzy     |
         | get_    |   |  guide  |  +----------+
         |  movie_ |   | sound-  |
         |  details|   |  track_ |
         | search_ |   | analysis|
         |  music  |   +---------+
         | get_    |
         |  artist_|
         |  details|
         | calcu-  |
         |  lator  |
         | run_    |
         |  python |
         | read_   |
         |  file   |
         | write_  |
         |  file   |
         | list_   |
         |  files  |
         +---------+
```

---

## Features

### 11 Tools
| Tool | What it does |
|------|-------------|
| `search_books` | Composite BM25 + vector search over 50 Project Gutenberg classics |
| `web_search` | Live web search via Tavily API |
| `search_movies` | Movie search via TMDB API |
| `get_movie_details` | Full movie info -- cast, crew, budget, ratings |
| `search_music` | Music search via Last.fm API |
| `get_artist_details` | Artist info, top tracks, similar artists |
| `calculator` | Safe math evaluation using AST parsing (no eval/exec) |
| `run_python` | Sandboxed Python execution in a subprocess with 30s timeout |
| `read_file` | Read files from a confined workspace directory |
| `write_file` | Write files to workspace (notes, research, code) |
| `list_files` | List workspace contents |

### 4 Skills (Multi-Tool Workflows)
Skills chain multiple tools in sequence and return a compiled result. One tool call, multiple steps.

| Skill | What it does |
|-------|-------------|
| `deep_research` | Searches books + web + movies on a topic, cross-references everything |
| `movie_book_bridge` | Finds connections between literature and cinema on a theme |
| `study_guide` | Generates a study guide with key passages and analysis, saves to workspace |
| `soundtrack_analysis` | Analyzes film soundtracks and their musical influences |

### 5 Subagents
Each subagent has its own system prompt, personality, tool subset, and isolated conversation history. They run their own LLM loops.

| Agent | Role | Tools |
|-------|------|-------|
| **BookAgent** | Literature scholar -- analyzes themes, finds connections across works | search_books, write_file |
| **Spillberg** | Film critic -- cinematic analysis with real opinions | search_movies, get_movie_details |
| **ResearchAgent** | Web researcher -- synthesizes sources, cites everything | web_search, calculator, write_file |
| **CodeAgent** | Programmer -- writes, runs, and debugs Python | run_python, calculator, write_file, read_file |
| **Ozzy** | Music specialist -- soundtrack and music analysis | search_music, get_artist_details, write_file |

### Composite Search (BM25 + Vector + RRF)
Book search uses two retrieval methods and merges them with Reciprocal Rank Fusion:
- **BM25** catches exact keyword matches
- **Vector** (all-MiniLM-L6-v2 embeddings) catches semantic meaning
- **RRF** merges both ranked lists so you get the best of both worlds

Falls back gracefully to BM25-only if the vector index or sentence-transformers is unavailable.

### Pixel Art Visualizer
A browser-based pixel art animation that shows Hudson's state in real time -- thinking, calling tools, answering. The agent writes JSONL trace events; the visualizer polls and animates.

### JSONL Tracing
Every agent action (user message, tool start, tool done, thinking, answer) is logged to `tracing/trace.jsonl` with timestamps. Useful for debugging, visualization, and understanding what the agent actually did.

---

## Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) with `qwen3.5:9b` pulled
- GPU recommended (runs on CPU but slower)

### Setup

```bash
# Clone the repo
git clone <your-repo-url> hudson
cd hudson

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file and add your API keys
cp .env.example .env
# Edit .env with your keys (see API Keys section below)

# Download 50 classic books from Project Gutenberg
python -m scripts.download_books

# Build search indexes (BM25 + vector)
python -m scripts.index_books
```

### Run

```bash
# Interactive chat mode
python main.py

# Single query mode
python main.py "What does Dostoevsky say about suffering?"
```

### Visualizer

In a separate terminal:

```bash
python -m tracing.serve
```

Open [http://localhost:8420/visualizer.html](http://localhost:8420/visualizer.html) in your browser. The pixel art character animates in real time as Hudson thinks, calls tools, and responds.

---

## API Keys

All keys are free, no credit card required.

| Service | What for | Get it at |
|---------|----------|-----------|
| **Tavily** | Web search | [https://tavily.com](https://tavily.com) -- sign up, copy key from dashboard |
| **TMDB** | Movie search | [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) -- create account, request API key |
| **Last.fm** | Music search | [https://www.last.fm/api/account/create](https://www.last.fm/api/account/create) -- create API account |

Add them to your `.env` file:

```
TAVILY_API_KEY=your_key_here
TMDB_API_KEY=your_key_here
LASTFM_API_KEY=your_key_here
```

---

## Project Structure

```
hudson/
├── main.py                    # Entry point -- builds tools, starts agent
├── config.py                  # Model, paths, temperature, .env loader
├── requirements.txt           # Python dependencies
├── .env.example               # Template for API keys
│
├── agent/
│   ├── runtime.py             # Core agent loop (LLM call → tool → loop)
│   └── prompts.py             # System prompt with personality and instructions
│
├── tools/
│   ├── registry.py            # Tool registry -- connects LLM schemas to functions
│   ├── book_search.py         # BM25 + vector composite search with RRF
│   ├── web_search.py          # Tavily web search
│   ├── movie_search.py        # TMDB movie search + details
│   ├── calculator.py          # Safe math eval via AST parsing
│   ├── code_executor.py       # Sandboxed Python subprocess execution
│   └── file_ops.py            # Workspace file read/write/list
│
├── skills/
│   ├── registry.py            # Skill registry -- named multi-tool workflows
│   ├── builtin.py             # Built-in skills (deep_research, study_guide, etc.)
│   └── tool_bridge.py         # Exposes skills as a single "use_skill" tool
│
├── agents/
│   ├── subagent.py            # SubAgent class -- mini agent loop inside a tool call
│   ├── definitions.py         # Subagent definitions (name, prompt, tool subset)
│   └── orchestrator.py        # Exposes subagents as a "delegate" tool
│
├── tracing/
│   ├── tracer.py              # JSONL event writer
│   ├── serve.py               # HTTP server for the visualizer
│   └── visualizer.html        # Pixel art browser visualizer
│
├── scripts/
│   ├── download_books.py      # Downloads 50 classics from Project Gutenberg
│   └── index_books.py         # Builds BM25 + vector indexes from book text
│
├── data/                      # Generated at setup (not committed)
│   ├── books/raw/             # Raw .txt files
│   ├── metadata/books.json    # Book metadata (title, author, genre)
│   ├── bm25_index.pkl         # BM25 search index
│   └── vector_index.pkl       # Vector embeddings index
│
└── workspace/                 # User-generated files (notes, research, code)
```

---

## How It Works

### The Agent Loop

The core loop in `agent/runtime.py` is straightforward:

1. User sends a message
2. Assemble context: system prompt + conversation history + tool schemas
3. Call the LLM (Ollama via OpenAI-compatible API)
4. If the LLM returns **tool calls** -- execute each tool, append results, go back to step 3
5. If the LLM returns **text** -- that's the final answer, return it to the user

That's it. No state machines, no graphs, no orchestration framework. Just a loop.

### Tool Calling

Tools are registered in a `ToolRegistry` -- a dictionary mapping tool names to `{schema, function}` pairs. The LLM sees the schemas (OpenAI function-calling format). When it requests a tool, the registry looks up the function and calls it. The result goes back into the conversation as a tool message.

### Skills

Skills are multi-tool workflows exposed as a single tool. Instead of registering each skill separately (which bloats the tool schema), there's one `use_skill` tool. The LLM picks a skill by name, the skill function chains multiple tool calls internally, and returns a compiled result.

### Subagent Delegation

When Hudson delegates to a subagent, it calls the `delegate` tool. This spawns a `SubAgent` with:
- Its own system prompt (personality and role)
- A filtered copy of the tool registry (only the tools it needs)
- Its own conversation history (isolated from the main loop)
- A limited step count (max 10 steps)

The subagent runs its own LLM loop, does its work, and returns a text result. To the main agent loop, it looks like any other tool call. Nested loops, clean abstraction.

---

## Configuration

All configuration lives in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL` | `qwen3.5:9b` | Ollama model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint |
| `TEMPERATURE` | `0.7` | LLM temperature -- creative but coherent |
| `MAX_AGENT_STEPS` | `20` | Max tool-call loops before the agent gives up |
| `MAX_TOOL_OUTPUT_CHARS` | `10000` | Truncate tool output to fit context window |

The `.env` file is loaded automatically at import time -- no dotenv dependency needed. Hudson rolls its own parser.

---

## Example Conversations

**Literature search:**
```
You: What does Dostoevsky say about the nature of suffering?
Hudson: [calls search_books → finds passages from Crime and Punishment,
         The Brothers Karamazov, Notes from the Underground]
        Dostoevsky basically invented the existential crisis speedrun...
```

**Movie deep dive:**
```
You: Tell me about Blade Runner 2049
Hudson: [delegates to Spillberg → search_movies → get_movie_details]
        Villeneuve did something almost nobody pulls off -- he made a sequel
        to a masterpiece that stands entirely on its own...
```

**Cross-domain research:**
```
You: How do books and films handle the theme of isolation differently?
Hudson: [uses movie_book_bridge skill → searches books + movies simultaneously]
        On paper, isolation is internal -- Kafka's Gregor Samsa, Dostoevsky's
        Underground Man. On screen, isolation is spatial -- think the Overlook
        Hotel, or Ryan Stone tumbling through space in Gravity...
```

**Code execution:**
```
You: Write a script that calculates the readability score of a text
Hudson: [delegates to CodeAgent → writes Python → runs it → verifies output]
        Here's a Flesch-Kincaid readability calculator. I ran it and it works...
```

**Study guide generation:**
```
You: Make me a study guide on existentialism in literature
Hudson: [uses study_guide skill → searches books + web → saves to workspace]
        Done. Saved to workspace/study_guides/existentialism_in_literature.md
        Here are the highlights...
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | [Ollama](https://ollama.com) with qwen3.5:9b (local, no API costs) |
| LLM Client | [openai](https://pypi.org/project/openai/) Python SDK (Ollama is OpenAI-compatible) |
| Keyword Search | [rank-bm25](https://pypi.org/project/rank-bm25/) (BM25Okapi) |
| Vector Search | [sentence-transformers](https://pypi.org/project/sentence-transformers/) (all-MiniLM-L6-v2) |
| Rank Fusion | Reciprocal Rank Fusion (implemented from scratch) |
| Terminal UI | [Rich](https://pypi.org/project/rich/) |
| Web Search | [Tavily API](https://tavily.com) |
| Movie Data | [TMDB API](https://www.themoviedb.org/documentation/api) |
| Music Data | [Last.fm API](https://www.last.fm/api) |
| Book Corpus | [Project Gutenberg](https://www.gutenberg.org/) (50 classics) |
| Visualizer | Vanilla HTML/CSS/JS with canvas pixel art |
| Math | Python `ast` module (safe expression parsing, no eval) |
| Code Sandbox | `subprocess` with timeout and restricted environment |

---

Built from scratch. No LangChain. No LlamaIndex. No AutoGen. Just Python and a good idea.
