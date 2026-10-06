import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


# ============================================================
# BFYP CATALOG SERVER
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CATALOG_FILE = BASE_DIR / "catalog.json"
CRAWLER_FILE = BASE_DIR / "crawler.py"

HOST = "0.0.0.0"

# Render provides PORT automatically.
# Local testing uses 8000.
PORT = int(os.environ.get("PORT", "8000"))

# Run the crawler every 30 minutes.
REFRESH_INTERVAL = 30 * 60

# Give the crawler plenty of time.
# Your crawler can discover hundreds/thousands of games.
CRAWLER_TIMEOUT = 60 * 60


# ============================================================
# CRAWLER STATUS
# ============================================================

crawler_status = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_success": None,
    "last_error": None,
}


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now():
    """Return the current UTC time as an ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# CATALOG HELPERS
# ============================================================

def load_catalog():
    """Load catalog.json and return the parsed JSON."""

    if not CATALOG_FILE.exists():
        return None

    try:
        with open(CATALOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(
            f"[BFYP] Could not read catalog.json: {e}",
            flush=True
        )
        return None


def get_catalog_info():
    """Return useful information about the current catalog."""

    catalog = load_catalog()

    if catalog is None:
        return {
            "exists": False,
            "count": 0,
            "generated_at": None,
        }

    count = 0
    generated_at = None

    if isinstance(catalog, dict):
        generated_at = catalog.get("GeneratedAt")

        if isinstance(catalog.get("Games"), list):
            count = len(catalog["Games"])

        elif isinstance(catalog.get("games"), list):
            count = len(catalog["games"])

        elif isinstance(catalog.get("items"), list):
            count = len(catalog["items"])

    elif isinstance(catalog, list):
        count = len(catalog)

    return {
        "exists": True,
        "count": count,
        "generated_at": generated_at,
    }


# ============================================================
# CRAWLER
# ============================================================

def run_crawler():
    """Run crawler.py and regenerate catalog.json."""

    crawler_status["running"] = True
    crawler_status["last_started"] = utc_now()
    crawler_status["last_error"] = None

    print("=" * 60, flush=True)
    print("[BFYP] STARTING CRAWLER", flush=True)
    print(f"[BFYP] Started: {crawler_status['last_started']}", flush=True)
    print(f"[BFYP] Crawler: {CRAWLER_FILE}", flush=True)
    print("=" * 60, flush=True)

    try:
        if not CRAWLER_FILE.exists():
            raise FileNotFoundError(
                f"crawler.py was not found at {CRAWLER_FILE}"
            )

        result = subprocess.run(
            [sys.executable, "-u", str(CRAWLER_FILE)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=CRAWLER_TIMEOUT,
        )

        # Print crawler output into Render logs.
        if result.stdout:
            print(
                "[BFYP] ---------- CRAWLER OUTPUT ----------",
                flush=True
            )
            print(result.stdout, flush=True)
            print(
                "[BFYP] -------- END CRAWLER OUTPUT --------",
                flush=True
            )

        if result.stderr:
            print(
                "[BFYP] ---------- CRAWLER ERRORS ----------",
                flush=True
            )
            print(result.stderr, flush=True)
            print(
                "[BFYP] -------- END CRAWLER ERRORS --------",
                flush=True
            )

        if result.returncode == 0:

            crawler_status["last_success"] = True
            crawler_status["last_finished"] = utc_now()

            catalog_info = get_catalog_info()

            print("=" * 60, flush=True)
            print("[BFYP] CRAWLER FINISHED SUCCESSFULLY", flush=True)
            print(
                f"[BFYP] Finished: "
                f"{crawler_status['last_finished']}",
                flush=True
            )
            print(
                f"[BFYP] Catalog exists: "
                f"{catalog_info['exists']}",
                flush=True
            )
            print(
                f"[BFYP] Games in catalog: "
                f"{catalog_info['count']}",
                flush=True
            )
            print(
                f"[BFYP] GeneratedAt: "
                f"{catalog_info['generated_at']}",
                flush=True
            )
            print("=" * 60, flush=True)

            return True

        else:

            crawler_status["last_success"] = False
            crawler_status["last_finished"] = utc_now()
            crawler_status["last_error"] = (
                f"Crawler exited with code {result.returncode}"
            )

            print("=" * 60, flush=True)
            print("[BFYP] CRAWLER FAILED", flush=True)
            print(
                f"[BFYP] Exit code: {result.returncode}",
                flush=True
            )
            print("=" * 60, flush=True)

            return False

    except subprocess.TimeoutExpired:

        crawler_status["last_success"] = False
        crawler_status["last_finished"] = utc_now()
        crawler_status["last_error"] = "Crawler timed out"

        print("=" * 60, flush=True)
        print("[BFYP] CRAWLER TIMED OUT", flush=True)
        print("=" * 60, flush=True)

        return False

    except Exception as e:

        crawler_status["last_success"] = False
        crawler_status["last_finished"] = utc_now()
        crawler_status["last_error"] = str(e)

        print("=" * 60, flush=True)
        print(f"[BFYP] CRAWLER ERROR: {e}", flush=True)
        print("=" * 60, flush=True)

        return False

    finally:
        crawler_status["running"] = False


# ============================================================
# BACKGROUND CRAWLER LOOP
# ============================================================

def crawler_loop():
    """
    Run the crawler immediately, then repeat every 30 minutes.
    """

    print(
        "[BFYP] Crawler background thread started.",
        flush=True
    )

    # Small delay so the HTTP server can start first.
    time.sleep(3)

    while True:

        run_crawler()

        print(
            f"[BFYP] Next crawler run in "
            f"{REFRESH_INTERVAL // 60} minutes.",
            flush=True
        )

        time.sleep(REFRESH_INTERVAL)


# ============================================================
# HTTP SERVER
# ============================================================

class BFYPRequestHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status_code=200):
        """Send a JSON response."""

        body = json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ).encode("utf-8")

        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        # Allow Roblox/web clients to access the catalog.
        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Cache-Control",
            "no-cache, no-store, must-revalidate"
        )

        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        # Parse only the path, ignoring query parameters.
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        print(
            f"[BFYP] GET {path}",
            flush=True
        )

        # ----------------------------------------------------
        # ROOT / HEALTH
        # ----------------------------------------------------

        if path == "":
            self.send_json({
                "status": "ok",
                "service": "BFYP Catalog Server",
                "catalog": "/catalog.json",
                "health": "/health",
                "status_endpoint": "/status",
                "stats": "/stats",
            })
            return

        if path == "/health":

            catalog_info = get_catalog_info()

            self.send_json({
                "status": "ok",
                "service": "BFYP Catalog Server",
                "catalog_exists": catalog_info["exists"],
                "games": catalog_info["count"],
                "crawler_running": crawler_status["running"],
            })
            return

        # ----------------------------------------------------
        # DETAILED STATUS
        # ----------------------------------------------------

        if path == "/status":

            catalog_info = get_catalog_info()

            self.send_json({
                "status": "ok",

                "server": {
                    "service": "BFYP Catalog Server",
                    "port": PORT,
                    "time_utc": utc_now(),
                },

                "catalog": {
                    "exists": catalog_info["exists"],
                    "games": catalog_info["count"],
                    "generated_at": catalog_info["generated_at"],
                },

                "crawler": {
                    "running": crawler_status["running"],
                    "last_started": crawler_status["last_started"],
                    "last_finished": crawler_status["last_finished"],
                    "last_success": crawler_status["last_success"],
                    "last_error": crawler_status["last_error"],
                    "refresh_interval_minutes": (
                        REFRESH_INTERVAL // 60
                    ),
                },
            })
            return

        # ----------------------------------------------------
        # CATALOG
        # ----------------------------------------------------

        if path in ("/catalog", "/catalog.json"):

            catalog = load_catalog()

            if catalog is None:
                self.send_json({
                    "error": "catalog.json is not available yet"
                }, 503)
                return

            self.send_json(catalog)
            return

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        if path == "/stats":

            catalog_info = get_catalog_info()

            self.send_json({
                "status": "ok",
                "games": catalog_info["count"],
                "generated_at": catalog_info["generated_at"],
                "crawler_running": crawler_status["running"],
            })
            return

        # ----------------------------------------------------
        # NOT FOUND
        # ----------------------------------------------------

        self.send_json({
            "error": "Not found",
            "path": path,
        }, 404)

    def do_OPTIONS(self):

        self.send_response(204)

        self.send_header(
            "Access-Control-Allow-Origin",
            "*"
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, OPTIONS"
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type"
        )

        self.end_headers()

    def log_message(self, format, *args):
        """Use our own cleaner logging."""

        print(
            f"[BFYP] HTTP {self.address_string()} - "
            f"{format % args}",
            flush=True
        )


# ============================================================
# START SERVER
# ============================================================

def main():

    print("=" * 60, flush=True)
    print("BFYP CATALOG SERVER", flush=True)
    print("=" * 60, flush=True)

    print(
        f"[BFYP] Server starting on {HOST}:{PORT}",
        flush=True
    )

    print(
        f"[BFYP] Catalog file: {CATALOG_FILE}",
        flush=True
    )

    print(
        f"[BFYP] Crawler file: {CRAWLER_FILE}",
        flush=True
    )

    print(
        f"[BFYP] Refresh interval: "
        f"{REFRESH_INTERVAL // 60} minutes",
        flush=True
    )

    catalog_info = get_catalog_info()

    print(
        f"[BFYP] Existing catalog: "
        f"{catalog_info['exists']}",
        flush=True
    )

    print(
        f"[BFYP] Existing games: "
        f"{catalog_info['count']}",
        flush=True
    )

    print(
        f"[BFYP] Existing GeneratedAt: "
        f"{catalog_info['generated_at']}",
        flush=True
    )

    print("=" * 60, flush=True)

    # Start crawler in the background.
    crawler_thread = threading.Thread(
        target=crawler_loop,
        daemon=True,
        name="BFYP-Crawler"
    )

    crawler_thread.start()

    # Start HTTP server.
    server = ThreadingHTTPServer(
        (HOST, PORT),
        BFYPRequestHandler
    )

    print(
        f"[BFYP] HTTP SERVER IS RUNNING",
        flush=True
    )

    print(
        f"[BFYP] Catalog URL: "
        f"http://{HOST}:{PORT}/catalog.json",
        flush=True
    )

    print(
        "[BFYP] Status URL: "
        f"http://{HOST}:{PORT}/status",
        flush=True
    )

    print("=" * 60, flush=True)

    try:
        server.serve_forever()

    except KeyboardInterrupt:

        print(
            "[BFYP] Server shutting down...",
            flush=True
        )

    finally:
        server.server_close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    main()
