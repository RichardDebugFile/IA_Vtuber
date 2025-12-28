"""Simple HTTP health server for monitoring the face service."""
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            response = {
                "ok": True,
                "service": "face-service-2D-simple",
                "status": "running",
                "type": "GUI"
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_health_server(port: int = 8805):
    """Start health check server in background thread.

    Args:
        port: Port to listen on (default: 8805)
    """
    def run_server():
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        print(f"[FACE-SERVICE] Health server running on port {port}")
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread
