
"""
BFYP Catalog Crawler - STEP 1

What it does:
  1. Reads game IDs from seed_ids.txt
  2. Asks Roblox's PUBLIC web endpoints for info about those games (no login, no API keys)
  3. Saves everything to catalog.json in the shape BFYP uses

What it does NOT do (yet): Open Cloud, web server, Render, finding new games by itself.

Needs only Python 3.9+ . Nothing to install (it uses Python's built-in libraries).
Run it with:   python3 crawler.py     (Windows:  py crawler.py)
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------
# Settings you can change
# ----------------------------------------------------------------------
SEED_FILE = Path("seed_ids.txt")
OUTPUT_FILE = Path("catalog.json")

BATCH_SIZE = 50        # how many games to ask about per request (Roblox allows up to 100)
PAUSE_SECONDS = 1.0    # wait between requests so we are polite to Roblox
MAX_RETRIES = 4        # how many times to retry a failed request
USER_AGENT = "BFYP-Catalog/0.1 (+https://github.com/piiominu/BFYP-Catalog)"

# Public Roblox endpoints. These are unofficial and could change someday.
GAMES_URL = "https://games.roblox.com/v1/games"                 # name, creator, players, visits...
VOTES_URL = "https://games.roblox.com/v1/games/votes"           # thumbs up / thumbs down counts
ICONS_URL = "https://thumbnails.roblox.com/v1/games/icons"      # game icon image links
PLACE_TO_UNIVERSE_URL = "https://apis.roblox.com/universes/v1/places/{place_id}/universe"

# Roblox's own "genre" -> BFYP categories (BFYP's category names live in Constants.lua)
GENRE_TO_CATEGORIES = {
    "Adventure": ["Adventure"],
    "Building": ["Building"],
    "Fighting": ["Fighting"],
    "FPS": ["Shooter"],
    "Horror": ["Horror"],
    "Medieval": ["Medieval"],
    "Military": ["Military"],
    "RPG": ["RPG"],
    "Sci-Fi": ["Sci-Fi"],
    "Sports": ["Sports"],
    "Town and City": ["Roleplay"],
}


# ----------------------------------------------------------------------
# Talking to Roblox
# ----------------------------------------------------------------------
def get_json(url, params=None):
    """Download a URL and return its JSON, retrying politely if Roblox says 'slow down'.
    Returns None if it still fails."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # 429 = "too many requests", 5xx = Roblox having a bad moment: wait and retry
            if error.code == 429 or error.code >= 500:
                retry_after = error.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                print(f"  Roblox said HTTP {error.code}. Waiting {wait}s (try {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            print(f"  Request failed with HTTP {error.code}: {url}")
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"  Network problem: {error} (try {attempt}/{MAX_RETRIES})")
            time.sleep(2 ** attempt)
    return None


def chunks(items, size):
    """Split a list into smaller lists of at most `size` items."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def resolve_place_id(place_id):
    """A Place ID is the number in a game's web address. Convert it to a Universe ID."""
    data = get_json(PLACE_TO_UNIVERSE_URL.format(place_id=place_id))
    time.sleep(PAUSE_SECONDS)
    if data and isinstance(data.get("universeId"), int):
        return data["universeId"]
    print(f"  Could not find a universe for place {place_id}")
    return None


def fetch_games(universe_ids):
    """Returns {universeId: raw game info}"""
    payload = get_json(GAMES_URL, {"universeIds": ",".join(map(str, universe_ids))})
    time.sleep(PAUSE_SECONDS)
    if not payload:
        return {}
    return {item["id"]: item for item in payload.get("data", [])}


def fetch_votes(universe_ids):
    """Returns {universeId: (thumbsUp, thumbsDown)}"""
    payload = get_json(VOTES_URL, {"universeIds": ",".join(map(str, universe_ids))})
    time.sleep(PAUSE_SECONDS)
    if not payload:
        return {}
    return {
        item["id"]: (item.get("upVotes", 0), item.get("downVotes", 0))
        for item in payload.get("data", [])
    }


def fetch_icons(universe_ids):
    """Returns {universeId: image url}"""
    payload = get_json(
        ICONS_URL,
        {
            "universeIds": ",".join(map(str, universe_ids)),
            "size": "256x256",
            "format": "Png",
            "isCircular": "false",
        },
    )
    time.sleep(PAUSE_SECONDS)
    if not payload:
        return {}
    return {
        item["targetId"]: item.get("imageUrl")
        for item in payload.get("data", [])
        if item.get("state") == "Completed"
    }


# ----------------------------------------------------------------------
# Turning Roblox's answers into BFYP's format
# ----------------------------------------------------------------------
def to_unix(iso_text):
    """'2020-05-12T01:23:45.1234567Z' -> 1589246625 (seconds since 1970), or None."""
    if not iso_text:
        return None
    try:
        cleaned = re.sub(r"\.\d+", "", iso_text).replace("Z", "+00:00")
        return int(datetime.fromisoformat(cleaned).timestamp())
    except ValueError:
        return None


def build_record(game, votes, icon_url):
    up, down = votes
    total = up + down
    like_ratio = round(up / total, 3) if total else None
    creator = game.get("creator") or {}
    genre = game.get("genre")

    return {
        "UniverseId": game["id"],
        "PlaceId": game.get("rootPlaceId"),
        "Name": game.get("name", ""),
        "Description": (game.get("description") or "")[:1000],
        "CreatorId": creator.get("id"),
        "CreatorName": creator.get("name"),
        "CreatorType": creator.get("type"),
        "Thumbnail": icon_url,
        "Categories": GENRE_TO_CATEGORIES.get(genre, []),
        "RobloxGenre": genre,
        "Playing": game.get("playing", 0),
        "Visits": game.get("visits", 0),
        "Favorites": game.get("favoritedCount", 0),
        # Roblox's own thumbs-up ratio. This is NOT BFYP's review rating.
        "RobloxLikeRatio": like_ratio,
        "CreatedAt": to_unix(game.get("created")),
        "UpdatedAt": to_unix(game.get("updated")),
        "FetchedAt": int(time.time()),
    }


# ----------------------------------------------------------------------
# Reading the seed list
# ----------------------------------------------------------------------
def read_seed_ids():
    """seed_ids.txt: one ID per line. '123' = Universe ID, 'p:123' = Place ID. '#' starts a comment."""
    if not SEED_FILE.exists():
        raise SystemExit(f"Could not find {SEED_FILE}. Create it next to crawler.py.")

    universe_ids, place_ids = [], []
    for line in SEED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("p:"):
            if line[2:].strip().isdigit():
                place_ids.append(int(line[2:].strip()))
        elif line.isdigit():
            universe_ids.append(int(line))
        else:
            print(f"Skipping line I don't understand: {line!r}")
    return universe_ids, place_ids


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    universe_ids, place_ids = read_seed_ids()
    print(f"Seed file: {len(universe_ids)} universe IDs, {len(place_ids)} place IDs")

    for place_id in place_ids:
        universe_id = resolve_place_id(place_id)
        if universe_id:
            universe_ids.append(universe_id)

    universe_ids = list(dict.fromkeys(universe_ids))  # remove duplicates, keep order
    if not universe_ids:
        raise SystemExit("No usable IDs found. Add some to seed_ids.txt and try again.")

    records = []
    for batch_number, batch in enumerate(chunks(universe_ids, BATCH_SIZE), start=1):
        print(f"Batch {batch_number}: asking Roblox about {len(batch)} games...")
        games = fetch_games(batch)
        votes = fetch_votes(batch)
        icons = fetch_icons(batch)
        for universe_id in batch:
            game = games.get(universe_id)
            if game is None:
                print(f"  No info for {universe_id} (private, removed, or wrong ID) - skipped")
                continue
            records.append(build_record(game, votes.get(universe_id, (0, 0)), icons.get(universe_id)))

    catalog = {
        "GeneratedAt": int(time.time()),
        "Count": len(records),
        "Games": records,
    }
    OUTPUT_FILE.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone! Saved {len(records)} games to {OUTPUT_FILE}")
    for record in records[:5]:
        print(f"  - {record['Name']}  (universe {record['UniverseId']}, {record['Playing']} playing)")
    if not records:
        print("No games were saved. See the 'Troubleshooting' section of the README.")


if __name__ == "__main__":
    main()
