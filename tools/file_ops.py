"""
File Operations Tool — read, write, and list files in a workspace.

Confined to a workspace directory — Hudson can't roam the filesystem.
Useful for saving notes, research, summaries, and reading user files.
"""

import os

import config


# --- Tool Schemas (what the LLM sees) ---

FILE_READ_SCHEMA = {
    "name": "read_file",
    "description": (
        "Read the contents of a file from the workspace directory. "
        "Use this when the user asks you to look at a file, review something they wrote, "
        "or when you need to read a previously saved file. "
        "Files are in the 'workspace/' directory inside Hudson's project folder."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Name of the file to read (e.g. 'notes.txt', 'research/summary.md')"
            },
        },
        "required": ["filename"],
    },
}

FILE_WRITE_SCHEMA = {
    "name": "write_file",
    "description": (
        "Write or overwrite a file in the workspace directory. "
        "Use this to save notes, research summaries, code snippets, or any output "
        "the user wants to keep. Creates subdirectories if needed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Name of the file to write (e.g. 'notes.txt', 'research/summary.md')"
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file"
            },
        },
        "required": ["filename", "content"],
    },
}

FILE_LIST_SCHEMA = {
    "name": "list_files",
    "description": (
        "List files in the workspace directory. "
        "Use this when the user asks what files are saved, or to check what's available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subdirectory": {
                "type": "string",
                "description": "Subdirectory to list (e.g. 'research'). Leave empty for root workspace."
            },
        },
        "required": [],
    },
}


# --- Tool Implementation ---

WORKSPACE_DIR = os.path.join(config.BASE_DIR, "workspace")


class FileOpsTool:
    """File operations confined to the workspace directory."""

    def __init__(self):
        os.makedirs(WORKSPACE_DIR, exist_ok=True)

    def _safe_path(self, filename: str) -> str:
        """Resolve filename within workspace. Prevent directory traversal."""
        # Normalize and block traversal attempts
        clean = os.path.normpath(filename).lstrip(os.sep)
        if clean.startswith("..") or os.sep + ".." + os.sep in clean:
            raise ValueError("Path traversal not allowed")
        full_path = os.path.join(WORKSPACE_DIR, clean)
        # Double check it's still under workspace
        if not os.path.abspath(full_path).startswith(os.path.abspath(WORKSPACE_DIR)):
            raise ValueError("Path traversal not allowed")
        return full_path

    def read_file(self, filename: str) -> str:
        """Read a file from the workspace."""
        try:
            path = self._safe_path(filename)
        except ValueError as e:
            return f"Error: {e}"

        if not os.path.exists(path):
            return f"File not found: '{filename}'. Use list_files to see available files."

        try:
            with open(path, "r") as f:
                content = f.read()
            size = os.path.getsize(path)
            return f"[{filename} — {size:,} bytes]\n\n{content}"
        except Exception as e:
            return f"Error reading '{filename}': {e}"

    def write_file(self, filename: str, content: str) -> str:
        """Write a file to the workspace."""
        try:
            path = self._safe_path(filename)
        except ValueError as e:
            return f"Error: {e}"

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            size = os.path.getsize(path)
            return f"Saved '{filename}' ({size:,} bytes) to workspace."
        except Exception as e:
            return f"Error writing '{filename}': {e}"

    def list_files(self, subdirectory: str = "") -> str:
        """List files in the workspace."""
        try:
            target = self._safe_path(subdirectory) if subdirectory else WORKSPACE_DIR
        except ValueError as e:
            return f"Error: {e}"

        if not os.path.exists(target):
            return f"Directory not found: '{subdirectory}'"

        entries = []
        for root, dirs, files in os.walk(target):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            rel_root = os.path.relpath(root, WORKSPACE_DIR)
            if rel_root == ".":
                rel_root = ""

            for fname in sorted(files):
                if fname.startswith("."):
                    continue
                rel_path = os.path.join(rel_root, fname) if rel_root else fname
                full = os.path.join(root, fname)
                size = os.path.getsize(full)
                entries.append(f"  {rel_path} ({size:,} bytes)")

        if not entries:
            return "Workspace is empty. Use write_file to save something."

        return f"Workspace files ({len(entries)}):\n" + "\n".join(entries)
