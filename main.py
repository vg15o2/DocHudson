"""
Hudson CLI — entry point.

Usage:
  python main.py                          # interactive chat mode
  python main.py "search for X"           # single query mode
"""

import sys

from openai import OpenAI
from rich.console import Console

import config
from agent.runtime import HudsonAgent
from tools.registry import ToolRegistry
from tools.book_search import BookSearchTool, BOOK_SEARCH_SCHEMA
from tools.web_search import WebSearchTool, WEB_SEARCH_SCHEMA

console = Console()


def build_tools() -> ToolRegistry:
    """Register all tools."""
    registry = ToolRegistry()

    # Book search (BM25) — lazy loaded
    book_tool = BookSearchTool(
        metadata_file=config.BOOKS_METADATA_FILE,
        index_file=config.BM25_INDEX_FILE,
    )
    registry.register("search_books", BOOK_SEARCH_SCHEMA, book_tool.search)

    # Web search (Brave) — lazy loaded
    web_tool = WebSearchTool()
    registry.register("web_search", WEB_SEARCH_SCHEMA, web_tool.search)

    return registry


def main():
    # Connect to Ollama
    client = OpenAI(
        base_url=config.OLLAMA_BASE_URL,
        api_key=config.OLLAMA_API_KEY,
    )

    # Build tool registry
    tools = build_tools()

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
