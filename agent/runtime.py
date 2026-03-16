"""
Hudson Agent Runtime — the core agent loop.

This is the actual agent. It:
1. Assembles context (system prompt + history + tools)
2. Calls the LLM
3. If tool call → execute tool → append result → loop back
4. If text → return to user → done
"""

import json
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

from .prompts import SYSTEM_PROMPT

console = Console()


class HudsonAgent:
    def __init__(self, client: OpenAI, tool_registry, model: str,
                 max_steps: int = 20, temperature: float = 0.7):
        self.client = client
        self.tools = tool_registry
        self.model = model
        self.max_steps = max_steps
        self.temperature = temperature
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.total_steps = 0

    def run(self, user_input: str) -> str:
        """Run the agent loop for a user message. Returns the final text answer."""
        self.messages.append({"role": "user", "content": user_input})

        for step in range(self.max_steps):
            self.total_steps += 1

            # Call LLM with full context + tool schemas
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools.get_schemas() if self.tools.list_tools() else None,
                    temperature=self.temperature,
                )
            except Exception as e:
                error_msg = f"LLM call failed: {type(e).__name__}: {e}"
                console.print(f"  [red]{error_msg}[/red]")
                return error_msg

            choice = response.choices[0]

            # CASE 1: LLM wants to call tool(s)
            if choice.message.tool_calls:
                # Append the assistant message (contains tool call info)
                self.messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    # Show what's happening
                    console.print(
                        f"  [dim]Step {step + 1}:[/dim] "
                        f"[cyan]tool:{name}[/cyan] "
                        f"[dim]{json.dumps(args, ensure_ascii=False)}[/dim]"
                    )

                    # Execute the tool via registry
                    result = self.tools.execute(name, args)

                    # Show truncated result
                    preview = result[:200] + "..." if len(result) > 200 else result
                    console.print(f"  [dim]  → {preview}[/dim]")

                    # Append tool result to messages
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                continue  # Loop back — LLM needs to process tool results

            # CASE 2: LLM returned text — this is the final answer
            answer = choice.message.content or ""
            self.messages.append({"role": "assistant", "content": answer})
            return answer

        # Safety: max steps reached
        return "[Hudson reached maximum steps without completing the task]"

    def chat(self):
        """Interactive chat loop."""
        console.print(Panel("Hudson Agent — type 'quit' to exit", style="cyan"))

        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break

            console.print()
            answer = self.run(user_input)
            console.print()
            console.print(f"[bold cyan]Hudson:[/bold cyan] {answer}")
            console.print()
