"""
Subagent — a mini agent loop that runs inside a tool call.

When the orchestrator (Hudson) delegates to a subagent, it's like a manager
assigning a task to a specialist. The specialist has:
- Its own system prompt (personality + role)
- Its own subset of tools (narrow focus)
- Its own conversation history (isolated context)
- A limited number of steps (focused execution)

The subagent runs its own LLM loop, uses its tools, and returns a final answer
back to the orchestrator — who then synthesizes it with other results.

This is Option B: subagents as tool calls within the main agent loop.
"""

import json
from openai import OpenAI
from rich.console import Console

console = Console()


class SubAgent:
    """A focused mini-agent with its own prompt, tools, and loop."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        client: OpenAI,
        tool_registry,
        model: str,
        max_steps: int = 10,
        temperature: float = 0.7,
        tracer=None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.client = client
        self.tools = tool_registry
        self.model = model
        self.max_steps = max_steps
        self.temperature = temperature
        self.tracer = tracer

    def run(self, task: str) -> str:
        """Run the subagent on a task. Returns the final text answer."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        tool_schemas = self.tools.get_schemas() if self.tools.list_tools() else None

        for step in range(self.max_steps):
            if self.tracer:
                self.tracer.thinking()

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_schemas,
                    temperature=self.temperature,
                )
            except Exception as e:
                return f"[{self.name}] LLM error: {type(e).__name__}: {e}"

            choice = response.choices[0]

            # Tool calls
            if choice.message.tool_calls:
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    console.print(
                        f"    [dim][{self.name}] Step {step + 1}:[/dim] "
                        f"[magenta]tool:{name}[/magenta] "
                        f"[dim]{json.dumps(args, ensure_ascii=False)}[/dim]"
                    )

                    if self.tracer:
                        self.tracer.tool_start(f"{self.name}/{name}", args)

                    result = self.tools.execute(name, args)

                    if self.tracer:
                        self.tracer.tool_done(f"{self.name}/{name}", len(result))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                continue

            # Text response — done
            answer = choice.message.content or ""
            return answer

        return f"[{self.name}] Reached max steps without completing"
