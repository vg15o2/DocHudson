"""
Built-in Skills — predefined multi-tool workflows for Hudson.

Each skill is a function: (tool_registry, **kwargs) -> str
It uses the tool registry to call tools in sequence and builds a combined result.
"""

import json


# --- Skill: Deep Research ---

def deep_research(tool_registry, topic: str, **kwargs) -> str:
    """Research a topic across books, web, and movies. Cross-reference everything."""

    sections = []
    sections.append(f"# Deep Research: {topic}\n")

    # Step 1: Search books
    book_results = tool_registry.execute("search_books", {"query": topic, "max_results": 3})
    if book_results and "No results" not in book_results:
        sections.append("## From the Library\n")
        sections.append(book_results)
    else:
        sections.append("## From the Library\n_No relevant books found._")

    # Step 2: Search web
    web_results = tool_registry.execute("web_search", {"query": topic, "max_results": 3})
    if web_results and "No web results" not in web_results:
        sections.append("\n## From the Web\n")
        sections.append(web_results)
    else:
        sections.append("\n## From the Web\n_No relevant web results found._")

    # Step 3: Search movies
    movie_results = tool_registry.execute("search_movies", {"query": topic, "max_results": 3})
    if movie_results and "No movies" not in movie_results:
        sections.append("\n## From Cinema\n")
        sections.append(movie_results)

    # Step 4: Search music
    music_results = tool_registry.execute("search_music", {"query": topic, "max_results": 3})
    if music_results and "No " not in music_results:
        sections.append("\n## From Music\n")
        sections.append(music_results)

    sections.append("\n---\n_Cross-referenced across books, web, film, and music. Synthesize above._")
    return "\n".join(sections)


DEEP_RESEARCH_DESCRIPTION = (
    "Research a topic across all sources — books, web, movies, and music. "
    "Use when the user wants a comprehensive overview of a subject."
)


# --- Skill: Movie + Book Connection ---

def movie_book_bridge(tool_registry, topic: str, **kwargs) -> str:
    """Find connections between movies and books on a theme."""

    sections = []
    sections.append(f"# Books × Cinema: {topic}\n")

    # Step 1: Search books
    book_results = tool_registry.execute("search_books", {"query": topic, "max_results": 3})
    sections.append("## Literary Side\n")
    sections.append(book_results if book_results else "_No book results._")

    # Step 2: Search movies
    movie_results = tool_registry.execute("search_movies", {"query": topic, "max_results": 3})
    sections.append("\n## Cinematic Side\n")
    sections.append(movie_results if movie_results else "_No movie results._")

    sections.append(
        "\n---\n"
        "_Draw the connections: adaptations, shared themes, how each medium handles the topic differently._"
    )
    return "\n".join(sections)


MOVIE_BOOK_BRIDGE_DESCRIPTION = (
    "Find connections between books and movies on a theme. "
    "Use when the user asks about adaptations, shared themes, or book-to-film comparisons."
)


# --- Skill: Study Guide ---

def study_guide(tool_registry, topic: str, **kwargs) -> str:
    """Generate a study guide from book passages and web context."""

    sections = []
    sections.append(f"# Study Guide: {topic}\n")

    # Step 1: Deep book search
    book_results = tool_registry.execute("search_books", {"query": topic, "max_results": 5})
    sections.append("## Key Passages\n")
    sections.append(book_results if book_results else "_No relevant passages found._")

    # Step 2: Web context for modern perspective
    web_results = tool_registry.execute("web_search", {"query": f"{topic} analysis summary", "max_results": 3})
    sections.append("\n## Modern Context & Analysis\n")
    sections.append(web_results if web_results else "_No web context found._")

    sections.append(
        "\n---\n"
        "_Organize the above into: key themes, important quotes, discussion questions, and further reading._"
    )

    # Step 3: Save to workspace
    tool_registry.execute("write_file", {
        "filename": f"study_guides/{topic.replace(' ', '_').lower()}.md",
        "content": "\n".join(sections),
    })
    sections.append(f"\n_Saved to workspace: study_guides/{topic.replace(' ', '_').lower()}.md_")

    return "\n".join(sections)


STUDY_GUIDE_DESCRIPTION = (
    "Generate a study guide on a literary topic with key passages and analysis. "
    "Searches books and web, then saves the guide to the workspace."
)


# --- Skill: Soundtrack Analysis ---

def soundtrack_analysis(tool_registry, topic: str, **kwargs) -> str:
    """Analyze the intersection of movies and music on a theme."""

    sections = []
    sections.append(f"# Soundtrack Analysis: {topic}\n")

    # Step 1: Search movies
    movie_results = tool_registry.execute("search_movies", {"query": topic, "max_results": 3})
    sections.append("## Films\n")
    sections.append(movie_results if movie_results else "_No movie results._")

    # Step 2: Search music (artists/tracks related to the theme)
    music_results = tool_registry.execute("search_music", {"query": topic, "max_results": 3})
    sections.append("\n## Music\n")
    sections.append(music_results if music_results else "_No music results._")

    # Step 3: Search for soundtrack-specific music
    soundtrack_results = tool_registry.execute(
        "search_music", {"query": f"{topic} soundtrack", "search_type": "album", "max_results": 3}
    )
    if soundtrack_results and "No " not in soundtrack_results:
        sections.append("\n## Soundtracks & Scores\n")
        sections.append(soundtrack_results)

    sections.append(
        "\n---\n"
        "_Analyze the interplay: how does the music serve the film? "
        "Which scores defined the genre? How do soundtracks shape our memory of cinema?_"
    )
    return "\n".join(sections)


SOUNDTRACK_ANALYSIS_DESCRIPTION = (
    "Analyze the intersection of movies and music on a theme. "
    "Searches films and music together — great for soundtrack discussions, "
    "score analysis, or exploring how music and cinema connect."
)


# --- Register all built-in skills ---

def register_builtin_skills(skill_registry):
    """Register all built-in skills."""
    skill_registry.register("deep_research", DEEP_RESEARCH_DESCRIPTION, deep_research)
    skill_registry.register("movie_book_bridge", MOVIE_BOOK_BRIDGE_DESCRIPTION, movie_book_bridge)
    skill_registry.register("study_guide", STUDY_GUIDE_DESCRIPTION, study_guide)
    skill_registry.register("soundtrack_analysis", SOUNDTRACK_ANALYSIS_DESCRIPTION, soundtrack_analysis)
