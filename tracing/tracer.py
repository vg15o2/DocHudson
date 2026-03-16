"""
Hudson Tracer — writes JSONL events for the visualizer.

Events are appended to a JSONL file that the browser visualizer polls.
"""

import json
import os
import time


class HudsonTracer:
    def __init__(self, trace_file: str = None):
        if trace_file is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            trace_file = os.path.join(base, "tracing", "trace.jsonl")
        self.trace_file = trace_file
        # Clear previous trace on startup
        os.makedirs(os.path.dirname(trace_file), exist_ok=True)
        with open(trace_file, "w") as f:
            pass  # truncate

    def _write(self, event: dict):
        event["timestamp"] = time.time()
        with open(self.trace_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def user_message(self, message: str):
        self._write({"type": "user_message", "message": message[:100]})

    def tool_start(self, tool_name: str, args: dict):
        self._write({"type": "tool_start", "tool": tool_name, "args": args})

    def tool_done(self, tool_name: str, result_length: int):
        self._write({"type": "tool_done", "tool": tool_name, "result_length": result_length})

    def thinking(self):
        self._write({"type": "thinking"})

    def answer(self, text: str):
        self._write({"type": "answer", "text": text[:100]})

    def idle(self):
        self._write({"type": "idle"})
