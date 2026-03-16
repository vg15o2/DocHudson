"""
Orchestrator Bridge — exposes subagents as a tool for the main agent loop.

Hudson (the orchestrator) calls "delegate" → this spawns a subagent with
its own mini loop → subagent returns result → Hudson synthesizes.

The key insight: to the main agent loop, a subagent looks like any other tool.
It takes input, returns output. But internally, it's running its own LLM loop
with its own tools and prompt. Nested loops, clean abstraction.
"""

from openai import OpenAI

from tools.registry import ToolRegistry
from .subagent import SubAgent
from .definitions import ALL_AGENTS


# --- Tool Schema (what the LLM sees) ---

def make_delegate_schema() -> dict:
    """Generate the delegate tool schema from registered agents."""
    agent_descriptions = []
    for name, defn in ALL_AGENTS.items():
        tools = ", ".join(defn["tools"])
        agent_descriptions.append(f"  - {name}: {defn['prompt'].split(chr(10))[2].strip()} Tools: [{tools}]")

    agent_list = "\n".join(agent_descriptions)

    return {
        "name": "delegate",
        "description": (
            "Delegate a task to a specialist subagent. The subagent has its own "
            "personality, tools, and focus area. Use this when a task clearly falls "
            "into one agent's domain, or when you want a specialist's perspective.\n\n"
            f"Available agents:\n{agent_list}\n\n"
            "The subagent will run its own research/analysis and return a result. "
            "You can then synthesize multiple agent results into your final answer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Which agent to delegate to (e.g. 'BookAgent', 'Spillberg', 'CodeAgent')",
                    "enum": list(ALL_AGENTS.keys()),
                },
                "task": {
                    "type": "string",
                    "description": "Clear description of what you want the agent to do. Be specific."
                },
            },
            "required": ["agent_name", "task"],
        },
    }


# --- Executor ---

def make_delegate_executor(client: OpenAI, full_registry: ToolRegistry,
                           model: str, temperature: float, tracer=None):
    """Create the delegate function that spawns subagents.

    Args:
        client: The OpenAI client (shared — one GPU, sequential calls)
        full_registry: The main tool registry (we'll create filtered copies)
        model: Model name for subagents (same model, different prompt)
        temperature: Temperature for subagent LLM calls
        tracer: Optional tracer for visualizer events
    """

    def delegate(agent_name: str, task: str) -> str:
        if agent_name not in ALL_AGENTS:
            return f"Unknown agent '{agent_name}'. Available: {list(ALL_AGENTS.keys())}"

        defn = ALL_AGENTS[agent_name]

        # Create a filtered tool registry — subagent only sees its own tools
        sub_registry = ToolRegistry()
        for tool_name in defn["tools"]:
            if tool_name in full_registry.tools:
                tool_info = full_registry.tools[tool_name]
                sub_registry.register(tool_name, tool_info["schema"], tool_info["function"])

        # Spawn the subagent
        agent = SubAgent(
            name=defn["name"],
            system_prompt=defn["prompt"],
            client=client,
            tool_registry=sub_registry,
            model=model,
            max_steps=10,
            temperature=temperature,
            tracer=tracer,
        )

        return agent.run(task)

    return delegate
