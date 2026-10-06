# BFYP-Catalog

Collects public Roblox game info for **BFYP (Better For You Page)** and saves it as `catalog.json`.

**Step 1 (this version):** read a list of game IDs, fetch public info, write `catalog.json`.
No API keys, no Open Cloud, no web server yet.

## Files

| File | What it does |
|---|---|
| `crawler.py` | The whole crawler. Reads `seed_ids.txt`, asks Roblox's public web endpoints about those games, writes `catalog.json`. |
| `seed_ids.txt` | The list of games to look up (one ID per line). Edit this to add games. |
| `.gitignore` | Tells Git not to upload `catalog.json` (it's generated) or secrets. |
| `README.md` | This file. |

## Run it

You need **Python 3.9 or newer** and nothing else (no `pip install`).

```bash
git clone https://github.com/piiominu/BFYP-Catalog.git
cd BFYP-Catalog
python3 crawler.py        # Windows: py crawler.py
```

A successful run prints something like:

```text
Seed file: 4 universe IDs, 1 place IDs
Batch 1: asking Roblox about 5 games...

Done! Saved 5 games to catalog.json
  - <game name>  (universe 123..., 4521 playing)
```

Open `catalog.json`. Each game looks like this:

```json
{
  "UniverseId": 123456789,
  "PlaceId": 987654321,
  "Name": "Example Game",
  "Description": "...",
  "CreatorName": "SomeStudio",
  "Thumbnail": "https://tr.rbxcdn.com/...",
  "Categories": ["Adventure"],
  "Playing": 4521,
  "Visits": 91234567,
  "RobloxLikeRatio": 0.87,
  "CreatedAt": 1589246625
}
```

## How to find a game's ID

Open the game on roblox.com. The number in the address (`roblox.com/games/920587237/...`) is the **Place ID**.
Put `p:920587237` in `seed_ids.txt` and the crawler converts it to a Universe ID.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3: command not found` | Install Python from python.org (tick "Add to PATH" on Windows), or use `py crawler.py` |
| `No info for ... skipped` | That ID is wrong, private, or removed. Try another |
| `Saved 0 games` | Roblox changed an endpoint or your network blocks it. Copy the output and send it to me |
| `HTTP 429` messages | Roblox is rate limiting. The script waits and retries by itself. If it keeps happening, raise `PAUSE_SECONDS` in `crawler.py` |

## Notes

- These are Roblox's **public, unofficial** endpoints. They can change or rate-limit, so keep requests small and polite.
- `RobloxLikeRatio` is Roblox's thumbs-up ratio, not BFYP's review rating.

## Roadmap

1. ✅ Fetch games from a seed list into `catalog.json` (this step)
2. Discover many more games automatically (thousands)
3. Run it on a schedule on Render (free tier)
4. Upload the catalog to BFYP through Roblox Open Cloud
5. Read it inside BFYP with a `CatalogService`
