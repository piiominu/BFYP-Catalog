import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ============================================================
# BFYP CATALOG SERVER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CATALOG_FILE = BASE_DIR / "catalog.json"
CRAWLER_FILE = BASE_DIR / "crawler.py"

# How often the crawler refreshes the catalog.
# 30 minutes = 1800 seconds.
REFRESH_INTERVAL = 30 * 60

# Render provides the PORT environment variable.
# Local testing uses 8000.
PORT = int(os.environ.get("PORT", "8000"))

HOST = "0.0.0.0"


# ============================================================
# CATALOG HELPERS
# ============================================================

def load_catalog():
    """Load catalog.json and return it as Python data."""
    if not CATALOG_FILE.exists():
        return None

    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[BFYP] Could not read catalog.json: {e}")
        return None


def run_crawler():
    """Run crawler.py and regenerate catalog.json."""
    print("[BFYP] Starting crawler...")

    try:
        result = subprocess.run(
            [sys.executable, str(CRAWLER_FILE)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30 * 60
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:
            print("[BFYP] Crawler finished successfully.")
            return True

        print(f"[BFYP] Crawler exited with code {result.returncode}.")
        return False

    except subprocess.TimeoutExpired:
        print("[BFYP] Crawler timed out.")
        return False

    except Exception as e:
        print(f"[BFYP] Crawler error: {e}")
        return False


# ============================================================
# BACKGROUND REFRESHER
# ============================================================

def crawler_loop():
    """
    Run the crawler periodically.

    The first crawl happens immediately when the server starts.
    After that, the catalog refreshes every REFRESH_INTERVAL seconds.
    """

    # Give the server a moment to start.
    time.sleep(2)

    while True:
        try:
            run_crawler()
        except Exception as e:
            print(f"[BFYP] Unexpected crawler error: {e}")

        print(
            f"[BFYP] Next catalog refresh in "
            f"{REFRESH_INTERVAL // 60} minutes."
        )

        time.sleep(REFRESH_INTERVAL)


# ============================================================
# HTTP SERVER
# ============================================================

class BFYPRequestHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status_code=200):
        """Send JSON response."""

        body = json.dumps(
            data,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):
        """Handle GET requests."""

        # ----------------------------------------------------
        # Health check
        # ----------------------------------------------------

        if self.path == "/" or self.path == "/health":
            self.send_json({
                "status": "ok",
                "service": "BFYP Catalog Server",
                "catalog_exists": CATALOG_FILE.exists()
            })
            return

        # ----------------------------------------------------
        # Catalog endpoint
        # ----------------------------------------------------

        if self.path == "/catalog.json" or self.path == "/catalog":
            catalog = load_catalog()

            if catalog is None:
                self.send_json({
                    "error": "catalog.json is not available yet"
                }, 503)
                return

            self.send_json(catalog)
            return

        # ----------------------------------------------------
        # Simple stats endpoint
        # ----------------------------------------------------

        if self.path == "/stats":
            catalog = load_catalog()

            if catalog is None:
                self.send_json({
                    "error": "catalog.json is not available yet"
                }, 503)
                return

            if isinstance(catalog, list):
                game_count = len(catalog)

            elif isinstance(catalog, dict):
                # Try several common catalog structures.
                if isinstance(catalog.get("games"), list):
                    game_count = len(catalog["games"])

                elif isinstance(catalog.get("items"), list):
                    game_count = len(catalog["items"])

                else:
                    game_count = len(catalog)

            else:
                game_count = 0

            self.send_json({
                "status": "ok",
                "games": game_count
            })
            return

        # ----------------------------------------------------
        # 404
        # ----------------------------------------------------

        self.send_json({
            "error": "Not found"
        }, 404)

    def do_OPTIONS(self):
        """Allow CORS preflight requests."""

        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Cleaner server logging."""
        print(f"[BFYP] {self.address_string()} - {format % args}")


# ============================================================
# START SERVER
# ============================================================

def main():
    print("=" * 60)
    print("BFYP Catalog Server")
    print("=" * 60)
    print(f"[BFYP] Port: {PORT}")
    print(f"[BFYP] Catalog: {CATALOG_FILE}")
    print(f"[BFYP] Crawler: {CRAWLER_FILE}")
    print("=" * 60)

    # Start crawler in the background.
    crawler_thread = threading.Thread(
        target=crawler_loop,
        daemon=True
    )

    crawler_thread.start()

    # Start HTTP server.
    server = ThreadingHTTPServer(
        (HOST, PORT),
        BFYPRequestHandler
    )

    print(f"[BFYP] Server running on port {PORT}")
    print("[BFYP] Endpoints:")
    print("[BFYP]   /")
    print("[BFYP]   /health")
    print("[BFYP]   /catalog.json")
    print("[BFYP]   /catalog")
    print("[BFYP]   /stats")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\n[BFYP] Server shutting down...")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
