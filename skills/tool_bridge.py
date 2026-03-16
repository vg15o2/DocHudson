"""
Skill-to-Tool Bridge — exposes skills as a single LLM tool.

Instead of registering each skill as a separate tool (which bloats the schema),
we register one "use_skill" tool. The LLM picks the skill by name.
"""


def make_skill_schema(skill_registry) -> dict:
    """Generate the use_skill tool schema dynamically from registered skills."""
    skill_list = skill_registry.get_skill_list()

    return {
        "name": "use_skill",
        "description": (
            "Execute a predefined multi-step skill that chains multiple tools together. "
            "Use this when the user's request matches a skill description. "
            "Skills run multiple searches and compile results automatically.\n\n"
            f"Available skills:\n{skill_list}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to run (e.g. 'deep_research', 'study_guide')"
                },
                "topic": {
                    "type": "string",
                    "description": "The topic or subject to run the skill on"
                },
            },
            "required": ["skill_name", "topic"],
        },
    }


def make_skill_executor(skill_registry, tool_registry):
    """Return a callable that the tool registry can use to execute skills."""

    def execute_skill(skill_name: str, topic: str) -> str:
        return skill_registry.execute(skill_name, tool_registry, topic=topic)

    return execute_skill
