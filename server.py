import base64
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
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
# GITHUB PUBLISHING
# ============================================================
# After each successful crawl, catalog.json is committed to GitHub so
# raw.githubusercontent.com (BFYP's backup source) always has a recent copy.
#
# Set these in Render -> your service -> Environment:
#   GITHUB_TOKEN   (required) fine-grained token with "Contents: Read and write"
#                  on piiominu/BFYP-Catalog only
#   GITHUB_REPO    (optional) defaults to piiominu/BFYP-Catalog
#   GITHUB_BRANCH  (optional) defaults to main
#
# If GITHUB_TOKEN is missing, publishing is skipped and everything else works as before.

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "piiominu/BFYP-Catalog").strip()
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main").strip()
GITHUB_PATH = "catalog.json"

# Commit when the list of games changes, or at least this often (to refresh player counts etc.).
# Committing a ~1 MB file every 30 minutes would grow the repo by ~50 MB a day.
GITHUB_MIN_PUSH_INTERVAL = 6 * 60 * 60

github_status = {
    "enabled": bool(GITHUB_TOKEN),
    "last_push": None,
    "last_push_success": None,
    "last_push_error": None,
    "last_skipped_reason": None,
}

_last_pushed_ids = None
_last_pushed_time = 0.0

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
# GITHUB PUBLISHING
# ============================================================

def github_request(method, url, payload=None):
    """Call the GitHub REST API. Returns (status_code, parsed_json_or_None)."""

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "BFYP-Catalog-Server")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return response.status, (json.loads(body) if body else None)

    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"null")
        except Exception:
            body = None
        return e.code, body

def publish_catalog_to_github():
    """Commit catalog.json to GitHub if the game list changed (or it's been a while)."""

    global _last_pushed_ids, _last_pushed_time

    if not GITHUB_TOKEN:
        github_status["last_skipped_reason"] = "GITHUB_TOKEN is not set"
        return

    catalog = load_catalog()
    if not isinstance(catalog, dict) or not isinstance(catalog.get("Games"), list) or not catalog["Games"]:
        github_status["last_skipped_reason"] = "catalog.json is missing or empty"
        return

    ids = frozenset(
        g.get("UniverseId") for g in catalog["Games"] if isinstance(g, dict)
    )
    now = time.time()
    if (
        _last_pushed_ids is not None
        and ids == _last_pushed_ids
        and now - _last_pushed_time < GITHUB_MIN_PUSH_INTERVAL
    ):
        github_status["last_skipped_reason"] = "game list unchanged since last push"
        return

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"

    try:
        # The file's current sha is required to update it
        status_code, current = github_request("GET", f"{api_url}?ref={GITHUB_BRANCH}")
        sha = None
        if status_code == 200 and isinstance(current, dict):
            sha = current.get("sha")
        elif status_code != 404:
            raise RuntimeError(f"GitHub GET returned {status_code}: {current}")

        content = CATALOG_FILE.read_bytes()
        payload = {
            "message": (
                f"Catalog update: {len(catalog['Games'])} games "
                f"(GeneratedAt {catalog.get('GeneratedAt')})"
            ),
            "content": base64.b64encode(content).decode("ascii"),
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        status_code, result = github_request("PUT", api_url, payload)
        if status_code not in (200, 201):
            raise RuntimeError(f"GitHub PUT returned {status_code}: {result}")

        _last_pushed_ids = ids
        _last_pushed_time = now
        github_status["last_push"] = utc_now()
        github_status["last_push_success"] = True
        github_status["last_push_error"] = None
        github_status["last_skipped_reason"] = None

        print(
            f"[BFYP] Published catalog.json to GitHub "
            f"({GITHUB_REPO}@{GITHUB_BRANCH}, {len(catalog['Games'])} games)",
            flush=True
        )

    except Exception as e:
        # Never print the token; the error text from GitHub doesn't include it
        github_status["last_push"] = utc_now()
        github_status["last_push_success"] = False
        github_status["last_push_error"] = str(e)[:300]

        print(f"[BFYP] GitHub publish failed: {e}", flush=True)

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

            publish_catalog_to_github()

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

                "github": {
                    "enabled": github_status["enabled"],
                    "repo": GITHUB_REPO,
                    "branch": GITHUB_BRANCH,
                    "last_push": github_status["last_push"],
                    "last_push_success": github_status["last_push_success"],
                    "last_push_error": github_status["last_push_error"],
                    "last_skipped_reason": github_status["last_skipped_reason"],
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

    print(
        f"[BFYP] GitHub publishing: "
        f"{'on (' + GITHUB_REPO + '@' + GITHUB_BRANCH + ')' if GITHUB_TOKEN else 'off (set GITHUB_TOKEN to enable)'}",
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
