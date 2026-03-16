"""
Music Search Tool — Last.fm API.

Search for artists, albums, and tracks. Get detailed artist info.
Free tier: unlimited non-commercial use.
Get a key at: https://www.last.fm/api/account/create

Lazy loaded: API key is validated on first call, not at startup.
"""

import os

import requests


# --- Tool Schemas (what the LLM sees) ---

MUSIC_SEARCH_SCHEMA = {
    "name": "search_music",
    "description": (
        "Search for music — artists, albums, or tracks — using Last.fm. "
        "Use this when the user asks about musicians, bands, songs, albums, "
        "or anything music-related. Returns names, listeners, and URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query, e.g. 'Radiohead', 'Dark Side of the Moon', 'Bohemian Rhapsody'"
            },
            "search_type": {
                "type": "string",
                "description": "Type of search: 'artist', 'album', or 'track'. Default 'artist'.",
                "enum": ["artist", "album", "track"],
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return. Default 5."
            },
        },
        "required": ["query"],
    },
}

ARTIST_DETAILS_SCHEMA = {
    "name": "get_artist_details",
    "description": (
        "Get detailed information about a music artist — biography, similar artists, "
        "top tracks, and tags. Use this after search_music to dive deeper into an artist."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "artist_name": {
                "type": "string",
                "description": "Exact artist name, e.g. 'Radiohead', 'Kendrick Lamar'"
            },
        },
        "required": ["artist_name"],
    },
}


# --- Tool Implementation ---

class MusicSearchTool:
    """Last.fm API wrapper with lazy loading."""

    LASTFM_ENDPOINT = "http://ws.audioscrobbler.com/2.0/"

    def __init__(self):
        self._api_key = None

    def _get_api_key(self) -> str:
        """Load API key on first use."""
        if self._api_key is None:
            self._api_key = os.environ.get("LASTFM_API_KEY", "")
            if not self._api_key:
                raise RuntimeError(
                    "LASTFM_API_KEY environment variable not set. "
                    "Get a free key at https://www.last.fm/api/account/create"
                )
            print("[MusicSearch] Last.fm API key loaded.")
        return self._api_key

    def _api_request(self, params: dict) -> dict:
        """Make a request to the Last.fm API."""
        params["api_key"] = self._get_api_key()
        params["format"] = "json"

        try:
            resp = requests.get(
                self.LASTFM_ENDPOINT,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            return {"error": f"Last.fm API request failed: {type(e).__name__}: {e}"}

        return resp.json()

    def search(self, query: str, search_type: str = "artist", max_results: int = 5) -> str:
        """Search for artists, albums, or tracks on Last.fm."""
        search_type = search_type.lower()
        if search_type not in ("artist", "album", "track"):
            return f"Invalid search_type '{search_type}'. Use 'artist', 'album', or 'track'."

        method_map = {
            "artist": "artist.search",
            "album": "album.search",
            "track": "track.search",
        }

        data = self._api_request({
            "method": method_map[search_type],
            f"{search_type}": query,
        })

        if "error" in data:
            return data["error"] if isinstance(data["error"], str) else f"Last.fm API error: {data.get('message', 'Unknown error')}"

        # Parse results based on search type
        results_key = f"{search_type}matches"
        matches_container = data.get("results", {}).get(results_key, {})
        items = matches_container.get(search_type, [])

        # Last.fm sometimes returns a single dict instead of a list
        if isinstance(items, dict):
            items = [items]

        if not items:
            return f"No {search_type} results found for '{query}'. Try different search terms."

        lines = []
        for i, item in enumerate(items[:min(max_results, 10)], 1):
            name = item.get("name", "Unknown")
            url = item.get("url", "")

            if search_type == "artist":
                listeners = item.get("listeners", "N/A")
                lines.append(
                    f"[{i}] {name}\n"
                    f"    Listeners: {listeners}\n"
                    f"    URL: {url}"
                )
            elif search_type == "album":
                artist = item.get("artist", "Unknown artist")
                lines.append(
                    f"[{i}] {name} — by {artist}\n"
                    f"    URL: {url}"
                )
            elif search_type == "track":
                artist = item.get("artist", "Unknown artist")
                listeners = item.get("listeners", "N/A")
                lines.append(
                    f"[{i}] \"{name}\" — by {artist}\n"
                    f"    Listeners: {listeners}\n"
                    f"    URL: {url}"
                )

        return "\n\n".join(lines)

    def get_artist_details(self, artist_name: str) -> str:
        """Get detailed info about an artist: bio, similar artists, top tracks, tags."""
        sections = []

        # Get artist info (bio, tags, similar artists)
        info_data = self._api_request({
            "method": "artist.getinfo",
            "artist": artist_name,
        })

        if "error" in info_data:
            err = info_data["error"]
            if isinstance(err, str):
                return err
            return f"Last.fm API error: {info_data.get('message', 'Artist not found')}"

        artist = info_data.get("artist", {})
        name = artist.get("name", artist_name)
        url = artist.get("url", "")

        # Stats
        stats = artist.get("stats", {})
        listeners = stats.get("listeners", "N/A")
        playcount = stats.get("playcount", "N/A")

        sections.append(f"# {name}")
        sections.append(f"Listeners: {listeners} | Scrobbles: {playcount}")
        sections.append(f"URL: {url}")

        # Bio
        bio = artist.get("bio", {})
        summary = bio.get("summary", "")
        if summary:
            # Strip HTML links Last.fm adds
            import re
            summary = re.sub(r"<a\b[^>]*>.*?</a>", "", summary).strip()
            if len(summary) > 500:
                summary = summary[:500] + "..."
            sections.append(f"\n## Bio\n{summary}")

        # Tags
        tags = artist.get("tags", {}).get("tag", [])
        if tags:
            tag_names = [t.get("name", "") for t in tags[:8]]
            sections.append(f"\n## Tags\n{', '.join(tag_names)}")

        # Similar artists
        similar = artist.get("similar", {}).get("artist", [])
        if similar:
            similar_names = [s.get("name", "") for s in similar[:5]]
            sections.append(f"\n## Similar Artists\n{', '.join(similar_names)}")

        # Get top tracks
        tracks_data = self._api_request({
            "method": "artist.gettoptracks",
            "artist": artist_name,
            "limit": 5,
        })

        top_tracks = tracks_data.get("toptracks", {}).get("track", [])
        if top_tracks:
            track_lines = []
            for i, track in enumerate(top_tracks[:5], 1):
                track_name = track.get("name", "Unknown")
                track_playcount = track.get("playcount", "N/A")
                track_lines.append(f"  {i}. {track_name} ({track_playcount} plays)")
            sections.append(f"\n## Top Tracks\n" + "\n".join(track_lines))

        return "\n".join(sections)
