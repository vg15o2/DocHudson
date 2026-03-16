# Hudson

**A local AI agent runtime built from scratch. No frameworks. No training wheels.**

Hudson is a fully local AI agent that runs on your machine using Ollama and Qwen3.5-9B. It has 12 tools, 4 skills, 5 subagents, composite search (BM25 + Vector + RRF) over 50 classic books, a pixel art visualizer, and a personality somewhere between a literature professor and a film critic who won't shut up about Nolan.

This is not a wrapper around LangChain. Every line -- the agent loop, the tool registry, the orchestrator, the search pipeline -- is written from scratch in Python.

---

## Architecture

```
User Input
    |
    v
+----------------------------------------------+
|          Hudson (Orchestrator)                |
|          agent/runtime.py                     |
|                                               |
|  System Prompt (~2,500 tokens)                |
|  + Message History (grows per turn)           |
|  + Tool Schemas (~1,000 tokens)               |
|  = Full Context sent to LLM every call        |
+---+----------+-----------+---------+----------+
    |          |           |         |
    v          v           v         v
 +------+  +-------+  +--------+  +--------+
 | Tools |  | Skills|  |Subagents| | Tracer |
 | (12)  |  | (4)   |  | (5)     | | JSONL  |
 +------+  +-------+  +--------+  +--------+
```

### The Agent Loop (runtime.py)

This is the core of Hudson. It's a simple loop:

```
1. User sends message
2. Assemble context: system prompt + history + tool schemas
3. Call LLM (Qwen 3.5 via Ollama OpenAI-compatible API)
4. LLM returns tool calls? -> execute each, append results, GOTO 3
5. LLM returns text? -> that's the answer, return to user
6. Safety: max 20 iterations, then hard stop
```

Every iteration sends the FULL context to the LLM -- system prompt, all previous messages, all tool results, and all tool schemas. This is how the context window fills up.

---

## Context Window: How It Fills Up

Qwen3.5-9B has a **32,768 token context window**. Here's how Hudson uses it at each stage:

### Token Budget Breakdown (per LLM call)

| Component | Tokens (approx) | Notes |
|-----------|-----------------|-------|
| System prompt | ~2,500 | Personality, capabilities, routing rules, subagent docs, skill docs |
| Tool schemas (12 tools) | ~1,000 | Sent with every call -- JSON function definitions |
| User message | ~20-100 | Depends on query length |
| **Per tool result** | **500-2,600** | **This is where context grows fast** |
| LLM response | ~200-800 | Final answer or tool call request |

### How Context Grows During a Query

Take a query like `"Do a deep research on existentialism"`:

```
Call 1: system(2500) + schemas(1000) + user(30) = ~3,530 tokens
        LLM decides: call use_skill("deep_research", "existentialism")

        Skill internally runs 4 tool calls:
          search_books   -> ~2,600 tokens of results
          web_search     -> ~1,200 tokens of results
          search_movies  -> ~1,000 tokens of results
          search_music   -> ~500 tokens of results
        Total skill output: ~5,300 tokens

Call 2: system(2500) + schemas(1000) + user(30) + tool_call(50) + tool_result(5300) = ~8,880 tokens
        LLM generates final answer: ~500 tokens

Total context at peak: ~9,380 tokens out of 32,768
```

Now take a subagent delegation like `"Have your literature expert analyze guilt"`:

```
Call 1 (main):  ~3,530 tokens -> LLM calls delegate("BookAgent", task)

  BookAgent runs its OWN loop (separate context):
    Call 1 (sub): subagent_prompt(800) + sub_schemas(200) + task(80) = ~1,080 tokens
                  BookAgent calls search_books 4 times
    Call 2 (sub): 1,080 + 4 tool results(~10,400) = ~11,480 tokens
                  BookAgent generates analysis: ~400 tokens

  BookAgent result returned to main loop: ~400 tokens

Call 2 (main):  3,530 + tool_call(80) + delegate_result(400) = ~4,010 tokens
                LLM generates final answer with personality

Total main context at peak: ~4,510 tokens
Total sub context at peak: ~11,880 tokens (isolated, discarded after)
```

**Key insight**: subagents protect the main context. BookAgent consumed ~12K tokens internally, but only ~400 tokens of its result entered the main loop.

### Context Danger Zone

Without context management, a multi-turn conversation fills up fast:

```
Turn 1:  system(2500) + schemas(1000) + exchange(3000) = ~6,500
Turn 2:  6,500 + exchange(3000) = ~9,500
Turn 3:  9,500 + exchange(3000) = ~12,500
...
Turn 10: ~32,500 -> approaching limit
```

Each "exchange" includes user message + tool calls + tool results + assistant response. After ~10 tool-heavy turns, you're at the edge. Hudson currently has **no context pruning** -- this is a known limitation.

---

## Composite Search: BM25 + Vector + RRF

### The Pipeline

```
User Query: "What do classic authors say about the loneliness of power?"
    |
    +---> BM25 Search (keyword matching)
    |     - Tokenizes query: ["classic", "authors", "loneliness", "power"]
    |     - Scores all 17,938 chunks by term frequency
    |     - Returns top N ranked by BM25 score
    |
    +---> Vector Search (semantic matching)
    |     - Encodes query with all-MiniLM-L6-v2 -> 384-dim vector
    |     - Dot product against all 17,938 chunk embeddings
    |     - Returns top N ranked by cosine similarity
    |
    +---> RRF Merge (Reciprocal Rank Fusion)
          - For each chunk, score = sum( 1/(K + rank + 1) ) across both lists
          - K = 60 (standard RRF constant)
          - A chunk ranked #1 in both: 1/(60+1+1) + 1/(60+1+1) = 0.032
          - A chunk ranked #1 in vector, #50 in BM25: 0.016 + 0.009 = 0.025
          - Sort by combined score, return top 5
```

### Why Two Search Methods?

| Query Type | BM25 Wins | Vector Wins |
|-----------|-----------|-------------|
| `"Raskolnikov"` | Exact name match | Might miss if name not in training data |
| `"existential dread"` | Only if exact words appear | Finds passages about anxiety, meaninglessness, despair |
| `"morality in Dostoevsky"` | Matches "morality" + "Dostoevsky" | Also finds passages about ethics, guilt, conscience |

BM25 catches what you typed. Vector catches what you meant. RRF gives you both.

### Chunking Parameters

| Parameter | Value | Why This Value |
|-----------|-------|----------------|
| **CHUNK_SIZE** | 400 words | ~530 tokens per chunk. 5 chunks = ~2,650 tokens. Leaves room in 32K context for system prompt, tool schemas, history, and LLM response. Also ~1.5 paragraphs -- enough for a coherent thought without losing context. |
| **CHUNK_OVERLAP** | 50 words | ~12% overlap. Prevents sentences from being cut mid-thought at chunk boundaries. A sentence that starts at word 390 still appears complete in the next chunk. |
| **Total chunks** | 17,938 | 50 books chunked. Average ~359 chunks per book. |

### Embedding Model: all-MiniLM-L6-v2

| Property | Value |
|----------|-------|
| Model | `sentence-transformers/all-MiniLM-L6-v2` |
| Embedding dimension | 384 |
| Max sequence length | 256 tokens (~190 words) |
| Speed | ~1,000 chunks/sec on GPU |
| Similarity | Cosine (via dot product on normalized vectors) |

**Why this model?** It's small (80MB), fast, and good enough for passage retrieval. Larger models (768-dim, 1024-dim) give marginal accuracy gains but 2-4x slower encoding and 2-4x larger index files. For 50 books on a local machine, MiniLM is the sweet spot.

### Index Files

| File | Size | Contents |
|------|------|----------|
| `bm25_index.pkl` | ~89 MB | BM25Okapi index + all tokenized chunks + raw text chunks + metadata |
| `vector_index.pkl` | ~27 MB | 17,938 x 384 float32 embedding matrix + raw chunks + metadata |

### Fallback Behavior

If `vector_index.pkl` doesn't exist (e.g., sentence-transformers not installed), book search silently falls back to BM25-only. No crashes, no errors -- just keyword search instead of hybrid.

---

## Tools: What They Do and What They Cost

Every tool call adds to the context window. Here's what each tool returns and how many tokens it costs.

### search_books
- **What**: Composite BM25 + Vector search over 50 Project Gutenberg classics
- **Output**: Up to 5 passages, each ~500 chars with title/author/genre header
- **Token cost**: ~2,600 tokens for 5 results
- **Truncation**: Passages capped at 500 chars
- **Lazy loading**: BM25 index + vector index + embedding model loaded on first call

### web_search
- **What**: Live web search via Tavily API
- **Output**: Quick AI answer + up to 5 results with title, 300-char snippet, URL
- **Token cost**: ~1,200 tokens for 5 results
- **Truncation**: Content per result capped at 300 chars
- **API limit**: 1,000 queries/month (free tier)

### search_movies
- **What**: Movie title search via TMDB API, with automatic person search fallback
- **Output**: Up to 5 movies with title, year, rating, 200-char overview, TMDB ID
- **Token cost**: ~1,000 tokens for 5 results
- **Truncation**: Overview capped at 200 chars
- **Connection handling**: Persistent session, 5 retries with backoff, verify=False for Windows SSL issues
- **Smart routing**: If no title match, strips noise words and searches TMDB person database for director/actor filmography

### get_movie_details
- **What**: Deep info on one movie -- cast (top 10), director, cinematographer, composer, budget, revenue, tagline, full overview
- **Output**: Formatted multi-line report
- **Token cost**: ~800-1,200 tokens
- **Accepts**: Both `movie_id` and `tmdb_id` parameters (LLM sends either)

### search_music
- **What**: Search Last.fm for artists, albums, or tracks
- **Output**: Name, listener count, URL per result
- **Token cost**: ~400-600 tokens for 5 results
- **Search types**: `artist`, `album`, `track` (enum)
- **Protocol**: HTTP (not HTTPS) -- avoids SSL issues entirely

### get_artist_details
- **What**: Artist bio (500 chars max), genre tags (8), similar artists (5), top tracks (5 with play counts)
- **Output**: Multi-section formatted report
- **Token cost**: ~800-1,200 tokens
- **HTML stripping**: Removes Last.fm's injected HTML links from bio text

### calculator
- **What**: Safe math evaluation using Python AST parsing
- **Output**: Single line: `"expression = result"`
- **Token cost**: ~10 tokens (minimal)
- **Security**: No eval/exec -- only allows whitelisted operations via AST node traversal
- **Supported**: +, -, *, /, **, %, sqrt, sin, cos, tan, log, factorial, pi, e
- **Limit**: Expression max 500 chars

### run_python
- **What**: Execute Python code in a sandboxed subprocess
- **Output**: stdout + stderr, truncated to 5,000 chars each
- **Token cost**: Up to ~2,500 tokens (if output fills 5K chars)
- **Isolation**: Separate process, temp directory as CWD, stripped environment (only PATH + HOME)
- **Timeout**: 30 seconds hard kill
- **Cleanup**: Temp file deleted after execution

### read_file / write_file / list_files
- **What**: File operations confined to `workspace/` directory
- **Output**: File contents (read), confirmation message (write), file listing (list)
- **Token cost**: Varies -- large files can consume significant context
- **Security**: Path traversal prevention via normpath + abspath check
- **Auto-creation**: write_file creates subdirectories as needed

### use_skill
- **What**: Single tool that triggers multi-tool workflows
- **Output**: Compiled results from multiple internal tool calls
- **Token cost**: Sum of all internal tool calls (can be 3,000-6,000 tokens)
- **Available skills**: deep_research, movie_book_bridge, study_guide, soundtrack_analysis
- **Design choice**: One tool instead of 4 separate tools -- reduces schema bloat

### delegate
- **What**: Spawns a subagent with its own LLM loop, tools, and prompt
- **Output**: Subagent's final text answer (typically 200-600 tokens)
- **Token cost in main context**: Only the final answer (~200-600 tokens)
- **Token cost internally**: Subagent runs its own context (up to ~12K tokens, isolated)
- **Available agents**: BookAgent, Spillberg, Ozzy, ResearchAgent, CodeAgent
- **Max steps**: 10 per subagent (vs 20 for main agent)

---

## Token Cost Summary Table

| Tool | Typical Output | Tokens Added to Context |
|------|---------------|------------------------|
| search_books | 5 passages | ~2,600 |
| web_search | 5 results + answer | ~1,200 |
| search_movies | 5 movies | ~1,000 |
| get_movie_details | 1 movie deep dive | ~1,000 |
| search_music | 5 results | ~500 |
| get_artist_details | 1 artist profile | ~1,000 |
| calculator | 1 line | ~10 |
| run_python | code output | ~500-2,500 |
| read_file | file contents | varies |
| write_file | confirmation | ~20 |
| list_files | file listing | ~50-200 |
| use_skill | multi-tool composite | ~3,000-6,000 |
| delegate | subagent answer | ~200-600 |

---

## Skills (Multi-Tool Workflows)

Skills chain multiple tool calls automatically. The LLM calls `use_skill` once; the skill handles the rest.

### deep_research
```
search_books(topic, 3) -> ~1,500 tokens
web_search(topic, 3)   -> ~700 tokens
search_movies(topic, 3) -> ~600 tokens
search_music(topic, 3)  -> ~300 tokens
                          -----------
                          ~3,100 tokens total
```

### movie_book_bridge
```
search_books(topic, 3)  -> ~1,500 tokens
search_movies(topic, 3) -> ~600 tokens
                           -----------
                           ~2,100 tokens total
```

### study_guide
```
search_books(topic, 5)           -> ~2,600 tokens
web_search(topic + "analysis", 3) -> ~700 tokens
write_file(guide)                 -> ~20 tokens
                                    -----------
                                    ~3,320 tokens total
```
Also saves the compiled guide to `workspace/study_guides/`.

### soundtrack_analysis
```
search_movies(topic, 3)                -> ~600 tokens
search_music(topic, 3)                 -> ~300 tokens
search_music(topic + "soundtrack", 3)  -> ~300 tokens
                                         -----------
                                         ~1,200 tokens total
```

---

## Subagents (Option B: Nested Loops)

Subagents are mini-agents that run inside a tool call. The main agent delegates; the subagent does focused work and returns a result.

### Why Subagents?

At 12 tools, the LLM has a lot of choices. Subagents solve this by **narrowing scope**:
- BookAgent only sees 2 tools (search_books, write_file)
- Spillberg only sees 2 tools (search_movies, get_movie_details)
- This reduces schema size per subagent and improves focus

### How Delegation Works

```
Main Agent                          SubAgent (BookAgent)
-----------                         --------------------
1. User asks about guilt
2. LLM calls delegate(BookAgent)
3. orchestrator.py creates          -> 1. Receives task
   filtered ToolRegistry            -> 2. Gets own system prompt
   (only search_books, write_file)  -> 3. Runs own LLM loop (max 10 steps)
                                    -> 4. Calls search_books 4 times
                                    -> 5. Generates analysis
4. Receives result string    <----- -> 6. Returns final text
5. LLM synthesizes with personality
6. Returns to user
```

### Subagent Specifications

| Agent | Tools | Prompt Tokens | Max Steps | Focus |
|-------|-------|--------------|-----------|-------|
| BookAgent | search_books, write_file | ~400 | 10 | Literary analysis, thematic connections |
| Spillberg | search_movies, get_movie_details | ~350 | 10 | Cinematic analysis, film criticism |
| Ozzy | search_music, get_artist_details, write_file | ~400 | 10 | Music analysis, cultural connections |
| ResearchAgent | web_search, calculator, write_file | ~350 | 10 | Web research, data synthesis |
| CodeAgent | run_python, calculator, write_file, read_file | ~350 | 10 | Code execution, debugging |

### Context Isolation

Each subagent runs in **completely isolated context**:
- Own system prompt (role-specific, ~350-400 tokens vs main's ~2,500)
- Own message history (starts fresh, discarded after)
- Own tool schemas (2-4 tools vs main's 12)
- Result fed back to main as a single tool result string

This means a subagent can use ~12K tokens internally but only inject ~400 tokens into the main context.

---

## Pixel Art Visualizer

A browser-based real-time visualization of Hudson's internal state.

### How It Works

```
Agent Loop (runtime.py)
    |
    v
Tracer (tracer.py) --writes--> trace.jsonl
                                    |
HTTP Server (serve.py) --serves--> Browser
                                    |
                                    v
                    visualizer.html polls every 300ms
                    Canvas 2D renders pixel art scene
```

### Event Types

| Event | Visualization | Character State |
|-------|--------------|----------------|
| `user_message` | Thinking bubble (amber) | Reading pose |
| `tool_start` | Tool bubble with icon + color | Typing animation |
| `tool_done` | Processing bubble | Reading pose |
| `thinking` | Thinking diamond (amber) | Reading pose |
| `answer` | Done checkmark (green, 3s) | Standing idle |
| `idle` | No bubble | Standing with breathing |

### Tool-Specific Colors

| Tool | Color | Icon |
|------|-------|------|
| search_books | Red (#E06060) | Books |
| web_search | Blue (#58a6ff) | Globe |
| search_movies | Gold (#d29922) | Clapperboard |
| search_music | Purple (#bc8cff) | Music note |
| calculator | Green (#3fb950) | Numbers |
| run_python | Green (#3fb950) | Laptop |
| File ops | Gray (#8b949e) | Document |
| use_skill | Purple (#bc8cff) | Lightning |
| delegate | Pink (#f778ba) | Robot |

### Subagent Visualization

When Hudson delegates to a subagent, the visualizer shows:
- Agent name in speech bubble (e.g., "Delegating to BookAgent")
- Agent-specific color (BookAgent=red, Spillberg=gold, Ozzy=purple)
- Subagent tool calls show as `AgentName/tool_name` with agent color
- Screen color changes to match active agent

### Activity Log

Scrolling timeline at the bottom with timestamped, color-coded entries for every event.

---

## Hardcoded Limits

Every limit exists to protect the context window or prevent runaway execution.

| Parameter | Value | Location | Purpose |
|-----------|-------|----------|---------|
| MAX_AGENT_STEPS | 20 | config.py | Hard stop on main loop iterations |
| MAX_TOOL_OUTPUT_CHARS | 10,000 | config.py / registry.py | Truncate any tool output that could blow context |
| Subagent max_steps | 10 | orchestrator.py | Limit nested loop depth |
| TEMPERATURE | 0.7 | config.py | Creative but coherent personality |
| CHUNK_SIZE | 400 words | index_books.py | ~530 tokens per chunk, 5 chunks fits in budget |
| CHUNK_OVERLAP | 50 words | index_books.py | 12% overlap to preserve sentence boundaries |
| RRF_K | 60 | book_search.py | Standard RRF constant for rank fusion |
| Code timeout | 30 sec | code_executor.py | Kill runaway scripts |
| Code max output | 5,000 chars | code_executor.py | ~1,250 tokens max from code |
| Web content trim | 300 chars | web_search.py | Per result, keeps web results lean |
| Book passage preview | 500 chars | book_search.py | Per passage from search results |
| Music bio max | 500 chars | music_search.py | Artist biography truncation |
| Movie overview max | 200 chars | movie_search.py | Per movie in search results |
| Expression max | 500 chars | calculator.py | Prevent abuse of math parser |
| TMDB retries | 5 | movie_search.py | Handle flaky SSL connections |
| Embedding batch size | 256 | index_books.py | GPU memory management during indexing |

---

## Quick Start

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com) with `qwen3.5:9b` pulled (`ollama pull qwen3.5:9b`)
- GPU recommended (RTX 5060 Ti 16GB used in development)

### Setup

```bash
git clone https://github.com/vg15o2/DocHudson.git
cd DocHudson

python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

### API Keys (all free, no card)

| Service | Get it at | Free tier |
|---------|-----------|-----------|
| Tavily | [tavily.com](https://tavily.com) | 1,000 queries/month |
| TMDB | [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) | 1M requests/day |
| Last.fm | [last.fm/api/account/create](https://www.last.fm/api/account/create) | Unlimited non-commercial |

### Download Books and Build Indexes

```bash
python -m scripts.download_books    # 50 classics from Project Gutenberg
python -m scripts.index_books       # BM25 + vector indexes (~5 min on GPU)
```

### Run

```bash
python main.py                                    # interactive mode
python main.py "What does Dostoevsky say about suffering?"  # single query
```

### Visualizer

```bash
python -m tracing.serve    # separate terminal
# Open http://localhost:8420/visualizer.html
```

---

## Project Structure

```
hudson/
├── main.py                     # Entry point: builds tools, skills, subagents, starts agent
├── config.py                   # Model, paths, temperature, .env loader
├── requirements.txt            # 6 dependencies
├── .env.example                # API key template
│
├── agent/
│   ├── runtime.py              # Core agent loop (LLM -> tool -> loop -> answer)
│   └── prompts.py              # System prompt (personality + routing + capabilities)
│
├── tools/
│   ├── registry.py             # Tool registry: schema + function + execute with truncation
│   ├── book_search.py          # BM25 + vector composite search with RRF (lazy loaded)
│   ├── web_search.py           # Tavily API (lazy loaded)
│   ├── movie_search.py         # TMDB API + person search + retry + SSL workaround
│   ├── music_search.py         # Last.fm API (lazy loaded)
│   ├── calculator.py           # Safe math via AST parsing
│   ├── code_executor.py        # Sandboxed Python subprocess
│   └── file_ops.py             # Workspace file I/O with path traversal protection
│
├── skills/
│   ├── registry.py             # Skill registry: named multi-tool workflows
│   ├── builtin.py              # 4 skills: deep_research, movie_book_bridge, study_guide, soundtrack_analysis
│   └── tool_bridge.py          # Exposes all skills as single "use_skill" tool
│
├── agents/
│   ├── subagent.py             # SubAgent class: mini agent loop (max 10 steps, isolated context)
│   ├── definitions.py          # 5 agent definitions: BookAgent, Spillberg, Ozzy, ResearchAgent, CodeAgent
│   └── orchestrator.py         # Exposes subagents as single "delegate" tool
│
├── tracing/
│   ├── tracer.py               # JSONL event writer (user_message, tool_start/done, thinking, answer, idle)
│   ├── serve.py                # HTTP server on port 8420 with no-cache headers
│   └── visualizer.html         # Pixel art Canvas 2D app with tool colors, agent colors, activity log
│
├── scripts/
│   ├── download_books.py       # Fetches 50 curated classics from Project Gutenberg
│   └── index_books.py          # Builds BM25 + vector indexes (400-word chunks, 50-word overlap)
│
├── data/                       # Generated at setup (gitignored)
│   ├── books/raw/              # 50 .txt files
│   ├── metadata/books.json     # Title, author, genre, Gutenberg ID
│   ├── bm25_index.pkl          # ~89 MB keyword search index
│   └── vector_index.pkl        # ~27 MB embedding matrix (17,938 x 384)
│
└── workspace/                  # User files (notes, research, code -- gitignored)
```

---

## Configuration

All in `config.py`:

| Setting | Default | What it does |
|---------|---------|-------------|
| `MODEL` | `qwen3.5:9b` | Ollama model name. Change to any Ollama model. |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint. Change if Ollama runs on another machine. |
| `OLLAMA_API_KEY` | `ollama` | Placeholder -- Ollama doesn't need real auth. |
| `TEMPERATURE` | `0.7` | Creative but coherent. Lower = more factual, higher = more personality. |
| `MAX_AGENT_STEPS` | `20` | Max tool-call loops before hard stop. |
| `MAX_TOOL_OUTPUT_CHARS` | `10,000` | Truncate any single tool output. Protects context window. |

The `.env` file is loaded at import time with a manual parser -- no python-dotenv dependency.

---

## Example Sessions

### 1. Movie Search with Director Lookup

```
You: What are Denis Villeneuve's best rated films?

  Step 1: tool:search_movies {"query": "Denis Villeneuve films", "max_results": 10}
    -> No movies found. (TMDB title search doesn't match director names)
    -> Auto-fallback: person search for "Denis Villeneuve"
    -> Finds person ID, pulls directing credits, sorts by weighted rating
    -> Returns: Dune Part Two (8.1), Blade Runner 2049 (7.6), Arrival (7.9),
       Incendies (8.1), Prisoners (8.1), Sicario (7.6), Enemy (6.9)...

Hudson: [Delivers full filmography breakdown with cinematic analysis,
         connects films to literary themes, ranks by quality]
```

**What happened internally**: TMDB's `/search/movie` endpoint searches titles, not people. When it returned 0 results, the tool stripped noise words ("films") and searched `/search/person` for "Denis Villeneuve", found his person ID, hit `/person/{id}/movie_credits`, filtered for directing credits, sorted by `vote_average * min(vote_count, 1000)`, and returned the ranked filmography.

### 2. Subagent Delegation (BookAgent)

```
You: Have your literature expert analyze the theme of guilt across your book collection

  Step 1: tool:delegate {"agent_name": "BookAgent", "task": "Analyze the theme of guilt..."}
    [BookAgent] Step 1: tool:search_books {"query": "guilt theme moral responsibility"}
    [BookAgent] Step 1: tool:search_books {"query": "guilt psychological torment"}
    [BookAgent] Step 1: tool:search_books {"query": "guilt redemption forgiveness"}
    [BookAgent] Step 1: tool:search_books {"query": "guilt existential burden"}
    -> BookAgent returns: Analysis covering Hawthorne (confession as liberation),
       Dostoevsky (suffering as inversion), Wilde (transactional sin),
       Dickens (compounding burden)

Hudson: [Synthesizes BookAgent's analysis with personality layer,
         adds film references -- Godfather, Truman Show, Dark Knight]
```

**What happened internally**: The main agent called `delegate("BookAgent", task)`. The orchestrator created a filtered ToolRegistry with only `search_books` and `write_file`, spawned a SubAgent with BookAgent's literary scholar prompt, ran it for 4 tool calls in its own isolated context (~12K tokens internally), then returned the analysis (~400 tokens) back to the main loop. Hudson's main context only grew by ~400 tokens, not ~12K.

### 3. Calculator (Preventing Math Hallucination)

```
You: What's 47 * 83 + 19 * 7?

  Step 1: tool:calculator {"expression": "47 * 83 + 19 * 7"}
    -> 47 * 83 + 19 * 7 = 4034

Hudson: 4034. Math's pretty reliable when you're not trying to do it
        while quoting Proust.
```

**What happened internally**: The expression was parsed by Python's `ast` module into an AST tree, evaluated node-by-node using only whitelisted operations. No `eval()` or `exec()` -- safe from code injection.

### 4. Code Execution (Sandboxed)

```
You: Write a Python script that generates the first 20 Fibonacci numbers

  Step 1: tool:run_python {"code": "def fibonacci(n):\n    fib = []\n    ..."}
    -> First 20 Fibonacci numbers:
       1. 0, 2. 1, 3. 1, 4. 2, 5. 3, 6. 5, 7. 8, 8. 13, ...

Hudson: [Shows results, explains the sequence, offers to extend or visualize]
```

**What happened internally**: Code was written to a temp file, executed via `subprocess.run()` with a 30-second timeout, minimal environment (`PATH` + `HOME` only, empty `PYTHONPATH`), temp directory as CWD. Stdout captured, temp file deleted. The subprocess has no access to Hudson's internals.

### 5. Deep Research Skill (Multi-Tool Chain)

```
You: Do a deep research on existentialism

  Step 1: tool:use_skill {"skill_name": "deep_research", "topic": "existentialism"}
    [internally] search_books("existentialism", 3)
      -> Nietzsche's Beyond Good and Evil, Wilde's Dorian Gray, Marcus Aurelius
    [internally] web_search("existentialism", 3)
      -> Current analysis, Stanford Encyclopedia entry, modern perspectives
    [internally] search_movies("existentialism", 3)
      -> Seventh Seal, Eternal Sunshine, existentialist cinema
    [internally] search_music("existentialism", 3)
      -> Related artists and albums

Hudson: [Synthesizes all 4 sources into cross-referenced analysis,
         connects Nietzsche to Blade Runner, Radiohead to existential dread]
```

**What happened internally**: The `use_skill` tool triggered `deep_research()` in `skills/builtin.py`, which called 4 tools sequentially via the tool registry. All results were compiled into a formatted string (~5,300 tokens) and returned as a single tool result. The LLM then synthesized the compiled research into a conversational answer.

### 6. Music Search + Artist Details

```
You: Let's talk about Taylor Swift's "All Too Well"

  Step 1: tool:search_music {"query": "Taylor Swift All Too Well", "search_type": "track"}
    -> Lush Life track info with 1.4M listeners
  Step 2: tool:get_artist_details {"artist_name": "Taylor Swift"}
    -> Bio, 5.8M listeners, 3.6B scrobbles, top tracks, similar artists, genre tags

Hudson: [Delivers analysis of Taylor's evolution, songwriting craft,
         connects her narrative style to literary traditions]
```

**What happened internally**: Last.fm's API was called twice -- once for track search, once for artist details. The artist detail call hit two endpoints: `artist.getinfo` (bio, tags, similar artists) and `artist.gettoptracks` (top 5 tracks with play counts). HTML links were stripped from the bio text.

### 7. Cross-Domain: Movie Details with Cinematographer

```
You: Give me the full breakdown on Blade Runner 2049

  Step 1: tool:search_movies {"query": "Blade Runner 2049"}
    -> Found: TMDB ID 335984, 7.6/10, 14,875 votes
  Step 2: tool:get_movie_details {"tmdb_id": "335984"}
    -> Director: Denis Villeneuve
       Cinematographer: Roger Deakins
       Composer: Hans Zimmer, Benjamin Wallfisch
       Budget: $150,000,000
       Revenue: $259,239,658
       Cast: Ryan Gosling, Harrison Ford, Ana de Armas...

Hudson: [Full cinematic analysis -- Deakins' photography, Zimmer's score,
         connects to original Blade Runner and Frankenstein themes]
```

**What happened internally**: The LLM sent `tmdb_id` instead of `movie_id` (schema says "TMDB ID"). The `get_details` method accepts both parameter names. The details endpoint used `?append_to_response=credits` to get cast and crew in a single API call. Director, cinematographer, and composer were extracted from the crew list by filtering on `job` field.

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| LLM | Qwen3.5-9B via Ollama | Local, free, fits in 16GB VRAM, good tool calling |
| LLM Client | openai Python SDK | Ollama exposes OpenAI-compatible API |
| Keyword Search | rank-bm25 (BM25Okapi) | Fast, no dependencies, proven IR algorithm |
| Vector Search | sentence-transformers (all-MiniLM-L6-v2) | 384-dim, 80MB model, fast on GPU |
| Rank Fusion | Reciprocal Rank Fusion (from scratch) | Simple, effective, no tuning needed |
| Terminal UI | Rich | Pretty console output without complexity |
| Web Search | Tavily API | Built for AI agents, clean results, free tier |
| Movie Data | TMDB API | Same data as Letterboxd, proper free API |
| Music Data | Last.fm API | Simple API key auth, good artist metadata |
| Math | Python ast module | Safe expression parsing, no eval/exec |
| Code Sandbox | subprocess with timeout | Process isolation, restricted environment |
| Visualizer | Vanilla HTML/Canvas | Zero dependencies, pixel art, real-time polling |
| Tracing | JSONL file | Append-only, human-readable, easy to parse |

---

Built from scratch. No LangChain. No LlamaIndex. No AutoGen. Just Python and a clear understanding of how agents actually work.
