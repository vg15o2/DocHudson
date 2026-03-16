"""
Simple HTTP server for the Hudson visualizer.

Serves visualizer.html and trace.jsonl from the tracing/ directory.

Usage: python -m tracing.serve
Then open http://localhost:8420 in your browser.
"""

import http.server
import os

PORT = 8420
DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def translate_path(self, path):
        # Serve trace.jsonl from the tracing directory
        if path.startswith('/trace.jsonl'):
            return os.path.join(DIR, 'trace.jsonl')
        return super().translate_path(path)

    def end_headers(self):
        # No caching for trace.jsonl (needs to be fresh every poll)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress poll spam in terminal
        if '/trace.jsonl' in str(args[0]):
            return
        super().log_message(format, *args)


def main():
    # Create empty trace file if it doesn't exist
    trace_file = os.path.join(DIR, 'trace.jsonl')
    if not os.path.exists(trace_file):
        open(trace_file, 'w').close()

    server = http.server.HTTPServer(('', PORT), Handler)
    print(f"Hudson Visualizer running at http://localhost:{PORT}")
    print(f"Serving from: {DIR}")
    print(f"Open http://localhost:{PORT}/visualizer.html in your browser")
    print("Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
