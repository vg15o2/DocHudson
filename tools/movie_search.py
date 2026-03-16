"""
Movie Search Tool — TMDB (The Movie Database) API.

Free API, no credit card, 1M requests/day.
Sign up at: https://www.themoviedb.org/settings/api

Lazy loaded: API key validated on first call.
"""

import os
import time
import warnings

import requests

# Suppress InsecureRequestWarning when using verify=False fallback
warnings.filterwarnings("ignore", message="Unverified HTTPS request")


# --- Tool Schema (what the LLM sees) ---

MOVIE_SEARCH_SCHEMA = {
    "name": "search_movies",
    "description": (
        "Search for movies using The Movie Database (TMDB). "
        "Returns movie titles, release years, ratings, overviews, and genres. "
        "Use this when the user asks about movies, films, directors, actors, "
        "movie recommendations, or anything cinema-related."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Movie search query, e.g. 'Inception', 'Christopher Nolan films', 'sci-fi movies about time'"
            },
            "max_results": {
                "type": "integer",
                "description": "Number of movies to return. Default 5."
            },
        },
        "required": ["query"],
    },
}

MOVIE_DETAILS_SCHEMA = {
    "name": "get_movie_details",
    "description": (
        "Get detailed information about a specific movie by its TMDB ID. "
        "Returns cast, crew, runtime, budget, revenue, and full overview. "
        "Use this after search_movies when the user wants deep details about a specific film."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "movie_id": {
                "type": "integer",
                "description": "TMDB movie ID (returned by search_movies)"
            },
        },
        "required": ["movie_id"],
    },
}


# --- Tool Implementation ---

class MovieSearchTool:
    """TMDB API wrapper with lazy loading."""

    TMDB_BASE = "https://api.themoviedb.org/3"

    def __init__(self):
        self._api_key = None

    def _get_api_key(self) -> str:
        """Load API key on first use."""
        if self._api_key is None:
            self._api_key = os.environ.get("TMDB_API_KEY", "")
            if not self._api_key:
                raise RuntimeError(
                    "TMDB_API_KEY environment variable not set. "
                    "Get a free key at https://www.themoviedb.org/settings/api"
                )
            print("[MovieSearch] TMDB API key loaded.")
        return self._api_key

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated GET request to TMDB.
        Retries up to 3 times with verify=False fallback for SSL issues."""
        api_key = self._get_api_key()
        params = params or {}
        params["api_key"] = api_key

        url = f"{self.TMDB_BASE}{endpoint}"

        last_error = None
        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, timeout=15, verify=False)
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.SSLError) as e:
                last_error = e
                time.sleep(0.5 * (attempt + 1))

        raise last_error

    def search(self, query: str, max_results: int = 5) -> str:
        """Search movies by title or keywords."""
        try:
            data = self._get("/search/movie", {"query": query})
        except requests.exceptions.RequestException as e:
            return f"Movie search failed: {type(e).__name__}: {e}"

        results = data.get("results", [])
        if not results:
            return "No movies found. Try different search terms."

        lines = []
        for i, movie in enumerate(results[:max_results], 1):
            title = movie.get("title", "Unknown")
            year = movie.get("release_date", "")[:4] or "N/A"
            rating = movie.get("vote_average", 0)
            votes = movie.get("vote_count", 0)
            overview = movie.get("overview", "No overview available.")
            movie_id = movie.get("id", "")

            if len(overview) > 200:
                overview = overview[:200] + "..."

            stars = f"{rating}/10 ({votes:,} votes)" if votes > 0 else "No ratings yet"

            lines.append(
                f"[{i}] {title} ({year}) — {stars}\n"
                f"    {overview}\n"
                f"    TMDB ID: {movie_id}"
            )

        return "\n\n".join(lines)

    def get_details(self, movie_id: int) -> str:
        """Get detailed info about a specific movie."""
        try:
            movie = self._get(f"/movie/{movie_id}", {"append_to_response": "credits"})
        except requests.exceptions.RequestException as e:
            return f"Movie details failed: {type(e).__name__}: {e}"

        title = movie.get("title", "Unknown")
        year = movie.get("release_date", "")[:4] or "N/A"
        runtime = movie.get("runtime", 0)
        rating = movie.get("vote_average", 0)
        votes = movie.get("vote_count", 0)
        overview = movie.get("overview", "No overview.")
        budget = movie.get("budget", 0)
        revenue = movie.get("revenue", 0)
        genres = ", ".join(g["name"] for g in movie.get("genres", []))
        tagline = movie.get("tagline", "")

        # Cast (top 10)
        credits = movie.get("credits", {})
        cast = credits.get("cast", [])[:10]
        cast_str = ", ".join(f"{a['name']} as {a['character']}" for a in cast)

        # Director
        crew = credits.get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        director_str = ", ".join(directors) if directors else "Unknown"

        lines = [
            f"# {title} ({year})",
            f"Director: {director_str}",
            f"Genres: {genres}",
            f"Runtime: {runtime} min",
            f"Rating: {rating}/10 ({votes:,} votes)",
        ]

        if tagline:
            lines.append(f'Tagline: "{tagline}"')
        if budget > 0:
            lines.append(f"Budget: ${budget:,.0f}")
        if revenue > 0:
            lines.append(f"Revenue: ${revenue:,.0f}")

        lines.append(f"\nOverview: {overview}")

        if cast_str:
            lines.append(f"\nCast: {cast_str}")

        return "\n".join(lines)
