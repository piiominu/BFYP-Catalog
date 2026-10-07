"""classify.py - decides which games are 'slop', which are hidden gems, and how good a game looks.
Edit rules.json to change the rules; no code changes needed."""
import json
import math
import re
import time
from pathlib import Path

RULES_FILE = Path(__file__).with_name("rules.json")


def load_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def clean_name(name):
    """'[UPDATE] 🎃 Grow a Garden' -> 'grow a garden'"""
    name = re.sub(r"\[[^\]]*\]", " ", (name or "").lower())   # drop [UPDATE] / [🎃] tags
    name = re.sub(r"^[^a-z0-9]+", "", name.strip())           # drop leading symbols and emoji
    return re.sub(r"\s+", " ", name)


def wilson_lower_bound(up, down, z=1.96):
    """Honest quality: 20 votes at 100% scores LOWER than 5,000 votes at 95%."""
    total = up + down
    if total == 0:
        return 0.0
    p = up / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / (1 + z * z / total)


def classify(universe_id, name, description, base_categories, up, down, playing, updated_unix, rules):
    lower_name = (name or "").lower()
    lower_desc = (description or "").lower()
    name_start = clean_name(name)

    categories = list(base_categories)
    flags = []

    # --- Brainrot: a keyword in the name, or 2+ different keywords in the description
    keywords = rules["brainrot_keywords"]
    in_name = any(k in lower_name for k in keywords)
    in_desc = sum(1 for k in keywords if k in lower_desc) >= 2
    is_brainrot = in_name or in_desc

    # --- "Grow a ..." / "Steal a ..." style clones
    is_clone = any(name_start.startswith(p) for p in rules["slop_name_prefixes"])

    is_slop = is_brainrot or is_clone
    if universe_id in rules.get("force_slop_universe_ids", []):
        is_slop = True
    if universe_id in rules.get("never_slop_universe_ids", []):
        is_slop, is_brainrot, is_clone = False, False, False

    if is_brainrot:
        flags.append("Brainrot")
        categories = ["Brainrot"] + [c for c in categories if c != "Brainrot"]
    elif is_clone:
        flags.append("GrindClone")
        if "Idle/Clicker" not in categories:
            categories.append("Idle/Clicker")

    # --- Quality + Hidden Gem
    quality = wilson_lower_bound(up, down)
    votes = up + down
    like_ratio = (up / votes) if votes else 0.0
    gem = rules["hidden_gem"]

    days_since_update = None
    if updated_unix:
        days_since_update = (time.time() - updated_unix) / 86400

    is_gem = (
        not is_slop
        and votes >= gem["min_votes"]
        and like_ratio >= gem["min_like_ratio"]
        and gem["min_playing"] <= playing <= gem["max_playing"]
        and days_since_update is not None
        and days_since_update <= gem["max_days_since_update"]
    )

    # Score: honest quality, boosted when few people are playing, and when recently updated
    exposure = 1 / (1 + playing / 500)
    if days_since_update is None:
        recency = 0.6
    elif days_since_update <= 90:
        recency = 1.0
    elif days_since_update <= 365:
        recency = 0.8
    else:
        recency = 0.5
    gem_score = 0.0 if is_slop else quality * exposure * recency

    return {
        "Categories": categories,
        "Flags": flags,
        "FrontpageEligible": not is_slop,
        "QualityScore": round(quality, 4),
        "HiddenGemScore": round(gem_score, 4),
        "IsHiddenGem": is_gem,
        "Upvotes": up,
        "Downvotes": down,
    }
