"""
Web Search Tool — Tavily Search API.

Built for AI agents. Returns clean, pre-formatted results.
Free tier: 1,000 queries/month, no credit card required.
Get a key at: https://tavily.com

Lazy loaded: API key is validated on first call, not at startup.
"""

import os

import requests


# --- Tool Schema (what the LLM sees) ---

WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for current information. "
        "Use this when the user asks about recent events, current documentation, "
        "technology, news, or anything that is NOT classic literature. "
        "Returns titles, snippets, and URLs from web results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'Python 3.13 new features' or 'latest AI research 2026'"
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return. Default 5."
            },
        },
        "required": ["query"],
    },
}


# --- Tool Implementation ---

class WebSearchTool:
    """Tavily Search API wrapper with lazy loading."""

    TAVILY_ENDPOINT = "https://api.tavily.com/search"

    def __init__(self):
        self._api_key = None

    def _get_api_key(self) -> str:
        """Load API key on first use."""
        if self._api_key is None:
            self._api_key = os.environ.get("TAVILY_API_KEY", "")
            if not self._api_key:
                raise RuntimeError(
                    "TAVILY_API_KEY environment variable not set. "
                    "Get a free key at https://tavily.com"
                )
            print("[WebSearch] Tavily API key loaded.")
        return self._api_key

    def search(self, query: str, max_results: int = 5) -> str:
        """Search the web using Tavily Search API."""
        api_key = self._get_api_key()

        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": min(max_results, 10),
            "include_answer": True,
        }

        try:
            resp = requests.post(
                self.TAVILY_ENDPOINT,
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            return f"Web search failed: {type(e).__name__}: {e}"

        data = resp.json()

        # Tavily can return a direct AI-generated answer
        answer = data.get("answer", "")
        results = data.get("results", [])

        if not results and not answer:
            return "No web results found. Try different search terms."

        lines = []

        if answer:
            lines.append(f"Quick answer: {answer}\n")

        for i, item in enumerate(results[:max_results], 1):
            title = item.get("title", "No title")
            url = item.get("url", "")
            content = item.get("content", "No description")
            # Tavily returns longer content — trim for context window
            if len(content) > 300:
                content = content[:300] + "..."

            lines.append(
                f"[{i}] {title}\n"
                f"    {content}\n"
                f"    URL: {url}"
            )

        return "\n\n".join(lines)
