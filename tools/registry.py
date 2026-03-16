"""
Tool Registry — the bridge between LLM requests and Python functions.

The LLM sees schemas. The runtime calls functions. This connects them.
"""

import json


class ToolRegistry:
    def __init__(self):
        self.tools = {}  # name → {"schema": dict, "function": callable}

    def register(self, name: str, schema: dict, function: callable):
        """Register a tool with its schema and implementation."""
        self.tools[name] = {"schema": schema, "function": function}

    def get_schemas(self) -> list:
        """Return all tool schemas in OpenAI function-calling format.
        This gets sent to the LLM at every call."""
        return [
            {
                "type": "function",
                "function": tool["schema"],
            }
            for tool in self.tools.values()
        ]

    def execute(self, name: str, arguments: dict, max_output: int = 10000) -> str:
        """Execute a tool by name with the given arguments.
        Called by the agent loop when the LLM requests a tool."""
        if name not in self.tools:
            return f"Error: Unknown tool '{name}'. Available tools: {list(self.tools.keys())}"

        func = self.tools[name]["function"]

        try:
            result = func(**arguments)
            result = str(result)
            if len(result) > max_output:
                result = result[:max_output] + "\n\n[OUTPUT TRUNCATED]"
            return result
        except Exception as e:
            return f"Error executing {name}: {type(e).__name__}: {str(e)}"

    def list_tools(self) -> list:
        """List registered tool names."""
        return list(self.tools.keys())
