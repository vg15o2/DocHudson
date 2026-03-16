"""
Web Search Tool — Brave Search API.

Lazy loaded: API key is validated on first call, not at startup.
"""

import os

import requests


# --- Tool Schema (what the LLM sees) ---

WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": (
        "Search the web for current information using Brave Search. "
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
    """Brave Search API wrapper with lazy loading."""

    BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self):
        self._api_key = None

    def _get_api_key(self) -> str:
        """Load API key on first use."""
        if self._api_key is None:
            self._api_key = os.environ.get("BRAVE_API_KEY", "")
            if not self._api_key:
                raise RuntimeError(
                    "BRAVE_API_KEY environment variable not set. "
                    "Get a free key at https://brave.com/search/api/"
                )
            print("[WebSearch] API key loaded.")
        return self._api_key

    def search(self, query: str, max_results: int = 5) -> str:
        """Search the web using Brave Search API."""
        api_key = self._get_api_key()

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        }
        params = {
            "q": query,
            "count": min(max_results, 20),  # Brave caps at 20
        }

        try:
            resp = requests.get(
                self.BRAVE_ENDPOINT,
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            return f"Web search failed: {type(e).__name__}: {e}"

        data = resp.json()
        web_results = data.get("web", {}).get("results", [])

        if not web_results:
            return "No web results found. Try different search terms."

        lines = []
        for i, item in enumerate(web_results[:max_results], 1):
            title = item.get("title", "No title")
            url = item.get("url", "")
            desc = item.get("description", "No description")
            age = item.get("age", "")

            age_str = f" ({age})" if age else ""
            lines.append(
                f"[{i}] {title}{age_str}\n"
                f"    {desc}\n"
                f"    URL: {url}"
            )

        return "\n\n".join(lines)
