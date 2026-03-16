"""
Hudson CLI — entry point.

Usage:
  python main.py                          # interactive chat mode
  python main.py "search for X"           # single query mode
"""

import os
import sys

from openai import OpenAI
from rich.console import Console

import config
from agent.runtime import HudsonAgent
from tools.registry import ToolRegistry
from tools.book_search import BookSearchTool, BOOK_SEARCH_SCHEMA
from tools.web_search import WebSearchTool, WEB_SEARCH_SCHEMA
from tools.movie_search import MovieSearchTool, MOVIE_SEARCH_SCHEMA, MOVIE_DETAILS_SCHEMA
from tools.music_search import MusicSearchTool, MUSIC_SEARCH_SCHEMA, ARTIST_DETAILS_SCHEMA
from tools.calculator import CalculatorTool, CALCULATOR_SCHEMA
from tools.code_executor import CodeExecutorTool, CODE_EXECUTOR_SCHEMA
from tools.file_ops import FileOpsTool, FILE_READ_SCHEMA, FILE_WRITE_SCHEMA, FILE_LIST_SCHEMA
from skills.registry import SkillRegistry
from skills.builtin import register_builtin_skills
from skills.tool_bridge import make_skill_schema, make_skill_executor
from agents.orchestrator import make_delegate_schema, make_delegate_executor
from tracing.tracer import HudsonTracer

console = Console()


def build_tools(client: OpenAI = None, tracer=None) -> ToolRegistry:
    """Register all tools, skills, and subagents."""
    registry = ToolRegistry()

    # Book search (BM25 + Vector composite) — lazy loaded
    book_tool = BookSearchTool(
        metadata_file=config.BOOKS_METADATA_FILE,
        index_file=config.BM25_INDEX_FILE,
        vector_index_file=config.VECTOR_INDEX_FILE,
    )
    registry.register("search_books", BOOK_SEARCH_SCHEMA, book_tool.search)

    # Web search (Tavily) — lazy loaded
    web_tool = WebSearchTool()
    registry.register("web_search", WEB_SEARCH_SCHEMA, web_tool.search)

    # Movie search (TMDB) — lazy loaded
    movie_tool = MovieSearchTool()
    registry.register("search_movies", MOVIE_SEARCH_SCHEMA, movie_tool.search)
    registry.register("get_movie_details", MOVIE_DETAILS_SCHEMA, movie_tool.get_details)

    # Music search (Last.fm) — lazy loaded
    music_tool = MusicSearchTool()
    registry.register("search_music", MUSIC_SEARCH_SCHEMA, music_tool.search)
    registry.register("get_artist_details", ARTIST_DETAILS_SCHEMA, music_tool.get_artist_details)

    # Calculator — safe math eval
    calc_tool = CalculatorTool()
    registry.register("calculator", CALCULATOR_SCHEMA, calc_tool.calculate)

    # Code executor — sandboxed Python subprocess
    code_tool = CodeExecutorTool()
    registry.register("run_python", CODE_EXECUTOR_SCHEMA, code_tool.run)

    # File operations — workspace read/write/list
    file_tool = FileOpsTool()
    registry.register("read_file", FILE_READ_SCHEMA, file_tool.read_file)
    registry.register("write_file", FILE_WRITE_SCHEMA, file_tool.write_file)
    registry.register("list_files", FILE_LIST_SCHEMA, file_tool.list_files)

    # Skills — multi-tool workflows exposed as a single tool
    skill_registry = SkillRegistry()
    register_builtin_skills(skill_registry)
    skill_schema = make_skill_schema(skill_registry)
    skill_executor = make_skill_executor(skill_registry, registry)
    registry.register("use_skill", skill_schema, skill_executor)

    # Subagents — specialist agents exposed as a "delegate" tool
    if client:
        delegate_schema = make_delegate_schema()
        delegate_executor = make_delegate_executor(
            client=client,
            full_registry=registry,
            model=config.MODEL,
            temperature=config.TEMPERATURE,
            tracer=tracer,
        )
        registry.register("delegate", delegate_schema, delegate_executor)

    return registry


def check_setup():
    """Check if books are downloaded and indexed."""
    if not os.path.exists(config.BM25_INDEX_FILE):
        console.print("[bold red]Books not set up yet.[/bold red]\n")
        console.print("Run these commands first:")
        console.print("  [cyan]python -m scripts.download_books[/cyan]  (downloads 50 books)")
        console.print("  [cyan]python -m scripts.index_books[/cyan]     (builds search index)")
        console.print()
        sys.exit(1)


def main():
    check_setup()

    # Connect to Ollama
    client = OpenAI(
        base_url=config.OLLAMA_BASE_URL,
        api_key=config.OLLAMA_API_KEY,
    )

    # Initialize tracer for visualizer
    tracer = HudsonTracer()

    # Build tool registry (needs client + tracer for subagents)
    tools = build_tools(client=client, tracer=tracer)

    console.print(f"[dim]Model: {config.MODEL}[/dim]")
    console.print(f"[dim]Tools: {tools.list_tools()}[/dim]")
    console.print()

    # Build agent
    agent = HudsonAgent(
        client=client,
        tool_registry=tools,
        model=config.MODEL,
        max_steps=config.MAX_AGENT_STEPS,
        temperature=config.TEMPERATURE,
        tracer=tracer,
    )

    # Single query mode or interactive
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        answer = agent.run(query)
        console.print(f"\n[bold cyan]Hudson:[/bold cyan] {answer}")
    else:
        agent.chat()


if __name__ == "__main__":
    main()
