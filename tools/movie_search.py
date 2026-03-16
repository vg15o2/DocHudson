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

# Persistent session — reuses TCP connections instead of opening new ones each time.
# This dramatically reduces SSL handshake failures on Windows with antivirus.
_session = requests.Session()
_session.verify = False


# --- Tool Schema (what the LLM sees) ---

MOVIE_SEARCH_SCHEMA = {
    "name": "search_movies",
    "description": (
        "Search for movies using The Movie Database (TMDB). "
        "Returns movie titles, release years, ratings, overviews, and genres. "
        "Use this when the user asks about movies, films, directors, actors, "
        "movie recommendations, or anything cinema-related. "
        "For searching by director or actor name, this tool will automatically "
        "look up the person and find their movies."
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
    """TMDB API wrapper with lazy loading and connection reuse."""

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
        Uses persistent session for connection reuse. Retries up to 5 times."""
        api_key = self._get_api_key()
        params = params or {}
        params["api_key"] = api_key

        url = f"{self.TMDB_BASE}{endpoint}"

        last_error = None
        for attempt in range(5):
            try:
                resp = _session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.SSLError) as e:
                last_error = e
                time.sleep(1 * (attempt + 1))

        raise last_error

    def _search_person_movies(self, query: str, max_results: int) -> str:
        """Search for a person (director/actor) and return their movies."""
        data = self._get("/search/person", {"query": query})
        results = data.get("results", [])
        if not results:
            return None

        person = results[0]
        person_name = person.get("name", query)
        known_for = person.get("known_for", [])

        # Get full filmography via person credits
        person_id = person.get("id")
        if person_id:
            try:
                credits = self._get(f"/person/{person_id}/movie_credits")
                # Combine cast and crew, prefer crew (directing) for directors
                crew_movies = [m for m in credits.get("crew", []) if m.get("job") == "Director"]
                cast_movies = credits.get("cast", [])

                # Use director credits if available, otherwise cast
                movies = crew_movies if crew_movies else cast_movies

                # Sort by rating (weighted by vote count)
                movies.sort(key=lambda m: m.get("vote_average", 0) * min(m.get("vote_count", 0), 1000), reverse=True)
            except Exception:
                # Fall back to known_for from search
                movies = known_for
        else:
            movies = known_for

        if not movies:
            return None

        lines = [f"Films by {person_name}:\n"]
        for i, movie in enumerate(movies[:max_results], 1):
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

    def search(self, query: str, max_results: int = 5) -> str:
        """Search movies by title, keywords, or person name."""
        try:
            # First try movie title search
            data = self._get("/search/movie", {"query": query})
            results = data.get("results", [])

            # If no movie results, try person search (director/actor name)
            if not results:
                person_result = self._search_person_movies(query, max_results)
                if person_result:
                    return person_result
                return "No movies found. Try different search terms."

        except requests.exceptions.RequestException as e:
            return f"Movie search failed: {type(e).__name__}: {e}"

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

        # Director + Cinematographer
        crew = credits.get("crew", [])
        directors = [c["name"] for c in crew if c.get("job") == "Director"]
        dps = [c["name"] for c in crew if c.get("job") == "Director of Photography"]
        composers = [c["name"] for c in crew if c.get("job") in ("Original Music Composer", "Music")]
        director_str = ", ".join(directors) if directors else "Unknown"

        lines = [
            f"# {title} ({year})",
            f"Director: {director_str}",
            f"Genres: {genres}",
            f"Runtime: {runtime} min",
            f"Rating: {rating}/10 ({votes:,} votes)",
        ]

        if dps:
            lines.append(f"Cinematographer: {', '.join(dps)}")
        if composers:
            lines.append(f"Composer: {', '.join(composers)}")
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
