"""
Skill Registry — predefined multi-tool workflows.

A skill is a named workflow that chains multiple tool calls in a specific order.
The LLM triggers a skill through a single tool call; the skill orchestrates the rest.

Think of tools as individual instruments and skills as sheet music.
"""


class SkillRegistry:
    def __init__(self):
        self.skills = {}  # name → {"description": str, "steps": callable}

    def register(self, name: str, description: str, execute_fn: callable):
        """Register a skill.

        execute_fn(tool_registry, **kwargs) -> str
            Takes the tool registry (to call tools) and skill-specific args.
            Returns the final result string.
        """
        self.skills[name] = {
            "description": description,
            "function": execute_fn,
        }

    def get_skill_list(self) -> str:
        """Return a formatted list of available skills for the system prompt."""
        if not self.skills:
            return "No skills available."
        lines = []
        for name, info in self.skills.items():
            lines.append(f"- {name}: {info['description']}")
        return "\n".join(lines)

    def execute(self, name: str, tool_registry, **kwargs) -> str:
        """Execute a skill by name."""
        if name not in self.skills:
            available = list(self.skills.keys())
            return f"Unknown skill '{name}'. Available: {available}"

        try:
            return self.skills[name]["function"](tool_registry, **kwargs)
        except Exception as e:
            return f"Skill '{name}' failed: {type(e).__name__}: {e}"

    def list_skills(self) -> list:
        """List registered skill names."""
        return list(self.skills.keys())
