"""
Code Executor Tool — run Python in a sandboxed subprocess.

Runs code in a separate process with a timeout.
No access to Hudson's internals — clean isolation.
Captures stdout, stderr, and return values.
"""

import subprocess
import sys
import tempfile
import os


# --- Tool Schema (what the LLM sees) ---

CODE_EXECUTOR_SCHEMA = {
    "name": "run_python",
    "description": (
        "Execute a Python code snippet and return the output. "
        "Use this when the user asks you to run code, test something, "
        "do data processing, or when you need to compute something complex. "
        "The code runs in an isolated subprocess. Print results with print(). "
        "Available: standard library + numpy. Timeout: 30 seconds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use print() to produce output."
            },
        },
        "required": ["code"],
    },
}


# --- Tool Implementation ---

class CodeExecutorTool:
    """Run Python code in a sandboxed subprocess with timeout."""

    TIMEOUT = 30  # seconds
    MAX_OUTPUT = 5000  # chars

    def run(self, code: str) -> str:
        """Execute Python code and return stdout + stderr."""
        if not code.strip():
            return "Error: empty code"

        # Write code to temp file
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, prefix="hudson_"
            ) as f:
                f.write(code)
                tmp_path = f.name
        except OSError as e:
            return f"Error creating temp file: {e}"

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
                cwd=tempfile.gettempdir(),
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": os.environ.get("HOME", ""),
                    "PYTHONPATH": "",
                },
            )

            output_parts = []

            if result.stdout:
                stdout = result.stdout
                if len(stdout) > self.MAX_OUTPUT:
                    stdout = stdout[:self.MAX_OUTPUT] + "\n[OUTPUT TRUNCATED]"
                output_parts.append(stdout)

            if result.stderr:
                stderr = result.stderr
                if len(stderr) > self.MAX_OUTPUT:
                    stderr = stderr[:self.MAX_OUTPUT] + "\n[STDERR TRUNCATED]"
                output_parts.append(f"STDERR:\n{stderr}")

            if result.returncode != 0:
                output_parts.append(f"[Exit code: {result.returncode}]")

            return "\n".join(output_parts) if output_parts else "[No output — use print() to see results]"

        except subprocess.TimeoutExpired:
            return f"Error: code execution timed out after {self.TIMEOUT} seconds"
        except Exception as e:
            return f"Error running code: {type(e).__name__}: {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
