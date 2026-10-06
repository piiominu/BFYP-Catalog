"""
BFYP Catalog Crawler - STEP 2

What it does:
  1. Reads optional game IDs from seed_ids.txt
  2. Automatically discovers Roblox games through Search + Explore
  3. Gets detailed information about discovered games
  4. Gets votes and icons
  5. Automatically assigns BFYP categories
  6. Calculates catalog-level discovery tags
  7. Saves everything to catalog.json

Needs:
  Python 3.9+

Nothing needs to be installed.

Run on Windows:
  py crawler.py

Run on Mac/Linux:
  python3 crawler.py
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ======================================================================
# SETTINGS
# ======================================================================

SEED_FILE = Path("seed_ids.txt")
OUTPUT_FILE = Path("catalog.json")

# Number of games requested in each detailed Roblox request.
BATCH_SIZE = 50

# Delay between Roblox requests.
PAUSE_SECONDS = 1.0

# Number of times a failed request is retried.
MAX_RETRIES = 4

# ----------------------------------------------------------------------
# DISCOVERY
# ----------------------------------------------------------------------

USE_SEARCH_DISCOVERY = True
USE_EXPLORE_DISCOVERY = True

# Search terms used to discover different types of Roblox games.
SEARCH_TERMS = [
    "action",
    "adventure",
    "arcade",
    "anime",
    "battle",
    "building",
    "casual",
    "competitive",
    "fighting",
    "horror",
    "obby",
    "puzzle",
    "racing",
    "RPG",
    "roleplay",
    "sandbox",
    "simulation",
    "sports",
    "strategy",
    "survival",
    "tycoon",
    "story",
    "social",
    "parkour",
    "fashion",
    "farming",
    "cooking",
    "fishing",
    "military",
    "mystery",
    "space",
    "superhero",
    "zombie",
    "school",
    "family",
    "pets",
    "restaurant",
    "escape",
    "tower defense",
    "battle royale",
    "PvP",
    "co-op",
    "multiplayer",
]

MAX_RESULTS_PER_SEARCH = 20
MAX_RESULTS_PER_SORT = 50

# Prevent a discovery run from becoming unnecessarily huge.
MAX_DISCOVERED_GAMES = 2500


# ======================================================================
# URLS
# ======================================================================

SEARCH_URL = "https://apis.roblox.com/search-api/omni-search"

EXPLORE_SORTS_URL = (
    "https://apis.roblox.com/explore-api/v1/get-sorts"
)

EXPLORE_SORT_CONTENT_URL = (
    "https://apis.roblox.com/explore-api/v1/get-sort-content"
)

GAMES_URL = "https://games.roblox.com/v1/games"

VOTES_URL = "https://games.roblox.com/v1/games/votes"

ICONS_URL = "https://thumbnails.roblox.com/v1/games/icons"

PLACE_TO_UNIVERSE_URL = (
    "https://apis.roblox.com/universes/v1/places/{place_id}/universe"
)

USER_AGENT = (
    "BFYP-Catalog/0.2 "
    "(+https://github.com/piiominu/BFYP-Catalog)"
)

SESSION_ID = str(uuid.uuid4())


# ======================================================================
# FULL BFYP CATEGORY VOCABULARY
#
# These are the ONLY category names the crawler is allowed to assign.
# Keep this synchronized with Constants.lua.
# ======================================================================

VALID_CATEGORIES = [
    # ------------------------------------------------------------------
    # BROAD
    # ------------------------------------------------------------------

    "Staff Picks",
    "Trending Online",
    "Hidden Gems",
    "Action",
    "Adventure",
    "Arcade",
    "Casual",
    "Competitive",
    "Horror",
    "RPG",
    "Simulation",
    "Strategy",
    "Survival",
    "Social",
    "Roleplay",
    "Sports",
    "Racing",
    "Fighting",
    "Shooter",
    "Tycoon",
    "Obby",
    "Puzzle",
    "Party",
    "Story",
    "Educational",
    "Sandbox",
    "Anime",
    "Military",
    "Fantasy",
    "Sci-Fi",
    "Mystery",
    "Exploration",
    "Superhero",
    "Remake",
    "Meme",
    "Brainrot",

    # ------------------------------------------------------------------
    # NICHE
    # ------------------------------------------------------------------

    "Parkour",
    "Platformer",
    "Tower Defense",
    "Tower Climb",
    "Wave Defense",
    "Hack & Slash",
    "Baddies",
    "Roguelike",
    "Roguelite",
    "Dungeon Crawler",
    "Boss Rush",
    "Battle Royale",
    "Arena",
    "1v1",
    "Team-Based",
    "PvP",
    "PvE",
    "PvPvE",
    "Co-op",
    "Singleplayer",
    "Open World",
    "Linear",
    "Procedural",
    "Physics-Based",
    "Idle",
    "Incremental",
    "Clicker",
    "AFK",
    "Grinding",
    "Progression",
    "Permadeath",

    "Easy Obby",
    "Hard Obby",
    "Rage Obby",
    "Speedrun",
    "Time Trial",
    "Precision Platforming",
    "Puzzle Obby",
    "Story Obby",
    "Multiplayer Obby",
    "Infinite Obby",
    "Troll Obby",

    "Psychological Horror",
    "Survival Horror",
    "Mascot Horror",
    "Analog Horror",
    "Backrooms",
    "Escape Horror",
    "Asymmetrical Horror",
    "Jumpscare",
    "Found Footage",
    "SCP",
    "Paranormal",
    "Mystery Horror",

    "Life Sim",
    "Town Roleplay",
    "School Roleplay",
    "Family Roleplay",
    "Workplace Roleplay",
    "Fantasy Roleplay",
    "Military Roleplay",
    "Police Roleplay",
    "Medical Roleplay",
    "Hangout",
    "Voice Chat",
    "Avatar Customization",
    "Fashion",
    "Makeover",
    "Social Deduction",

    "Action RPG",
    "MMORPG",
    "Turn-Based RPG",
    "Dungeon RPG",
    "Open-World RPG",
    "Character Collection",
    "Gacha",
    "Loot-Based",
    "Leveling",
    "Classes",
    "Quests",
    "Skill Trees",
    "Crafting",
    "Equipment",
    "Bosses",
    "Raids",

    "Life Simulation",
    "Vehicle Simulation",
    "Business Simulation",
    "Farming",
    "Restaurant",
    "Cooking",
    "Pet Simulation",
    "Fishing",
    "Mining",
    "Factory",
    "City Builder",
    "House Building",
    "Flight Simulation",
    "Driving Simulation",
    "Job Simulation",

    "Business",
    "Trading",
    "Economy",
    "Market",
    "Shop Management",
    "Restaurant Management",
    "Factory Management",
    "Property",
    "Collecting",
    "Auction",
    "Trading Cards",

    "Ranked",
    "Leaderboards",
    "Tournament",
    "Esports",

    "Tactical Shooter",
    "Hero Shooter",
    "Military Shooter",
    "Zombie Shooter",
    "Sniper",
    "Gun Game",
    "Team Deathmatch",
    "Capture the Flag",
    "Extraction",

    "Football",
    "Basketball",
    "Soccer",
    "Baseball",
    "Volleyball",
    "Tennis",
    "Hockey",
    "Golf",
    "Boxing",
    "Wrestling",
    "Skateboarding",
    "Surfing",
    "Swimming",
    "Track & Field",

    "Street Racing",
    "Racing Sim",
    "Arcade Racing",
    "Kart Racing",
    "Drag Racing",
    "Drift",
    "Motorcycle Racing",
    "Boat Racing",
    "Air Racing",
    "Obstacle Racing",

    "RTS",
    "Turn-Based Strategy",
    "4X",
    "Resource Management",
    "Tactical",
    "Deck Building",
    "Auto Battler",

    "Logic",
    "Word Puzzle",
    "Trivia",
    "Escape Room",
    "Matching",
    "Physics Puzzle",
    "Memory",
    "Maze",
    "Riddles",
    "Detective",
    "Brain Teaser",

    "Collectathon",
    "Pets",
    "Eggs",
    "Limited Items",
    "Cosmetics",
    "Badges",
    "Achievements",
    "Discoveries",
    "Upgrades",
    "Prestige",
    "Rebirth",
    "Unlockables",
    "Rare Items",

    "Building",
    "Construction",
    "Designing",
    "Interior Design",
    "Fashion Design",
    "Vehicle Building",
    "World Building",
    "Level Creation",
    "Sandbox Creation",
    "Art",
    "Music",
    "Animation",

    "Modern",
    "Medieval",
    "Historical",
    "Futuristic",
    "Cyberpunk",
    "Post-Apocalyptic",
    "Western",
    "Pirate",
    "Underwater",
    "Space",
    "Superhero",
    "Magic",
    "Ninja",
    "Samurai",

    "Chill",
    "Relaxing",
    "Funny",
    "Meme",
    "Chaotic",
    "Immersive",
    "Story-Driven",
    "Replayable",
    "Short Sessions",
    "Long Sessions",
    "Family-Friendly",
    "Beginner-Friendly",

    "Underrated",
    "Trending",
    "New Release",
    "Classic",
    "Nostalgic",
    "Popular",
    "Viral",
    "Small Community",
    "Large Community",
    "Solo Friendly",
    "Friend Group",
    "Good With Friends",
    "Quick Play",
    "Long Session",
    "Challenging",
    "High Skill Ceiling",
    "Controller Friendly",
    "Mobile Friendly",
    "Low-End Friendly",
]


VALID_CATEGORY_SET = set(VALID_CATEGORIES)


# ======================================================================
# ROBLOX GENRE -> BFYP CATEGORIES
# ======================================================================

GENRE_TO_CATEGORIES = {
    "Adventure": [
        "Adventure",
        "Exploration",
    ],

    "Building": [
        "Building",
        "Construction",
    ],

    "Fighting": [
        "Fighting",
        "Action",
    ],

    "FPS": [
        "Shooter",
        "Action",
    ],

    "Horror": [
        "Horror",
    ],

    "Medieval": [
        "Medieval",
        "Fantasy",
    ],

    "Military": [
        "Military",
    ],

    "RPG": [
        "RPG",
        "Progression",
    ],

    "Sci-Fi": [
        "Sci-Fi",
        "Futuristic",
    ],

    "Sports": [
        "Sports",
    ],

    "Town and City": [
        "Roleplay",
        "Town Roleplay",
    ],
}


# ======================================================================
# CATEGORY KEYWORD RULES
#
# These are intentionally conservative.
#
# Format:
#
#   "BFYP Category": [
#       "keyword 1",
#       "keyword 2",
#   ]
#
# A category is added when one or more keywords appear in the game's
# name or description.
# ======================================================================

CATEGORY_KEYWORDS = {

    # ------------------------------------------------------------------
    # GENERAL
    # ------------------------------------------------------------------

    "Action": [
        "action",
        "combat",
        "battle",
        "war",
        "fight",
    ],

    "Adventure": [
        "adventure",
        "adventur",
        "journey",
        "explore",
    ],

    "Arcade": [
        "arcade",
        "high score",
        "score attack",
    ],

    "Casual": [
        "casual",
        "simple",
        "relax",
        "easygoing",
    ],

    "Competitive": [
        "competitive",
        "compete",
        "competition",
        "ranked",
        "leaderboard",
    ],

    "Horror": [
        "horror",
        "scary",
        "scare",
        "haunted",
        "terror",
        "creepy",
        "monster",
    ],

    "RPG": [
        "rpg",
        "role playing",
        "role-playing",
        "character level",
    ],

    "Simulation": [
        "simulator",
        "simulation",
        "simulate",
    ],

    "Strategy": [
        "strategy",
        "strategic",
        "tactics",
    ],

    "Survival": [
        "survive",
        "survival",
        "survivor",
    ],

    "Social": [
        "social",
        "friends",
        "friend",
        "community",
    ],

    "Roleplay": [
        "roleplay",
        "role-play",
        "rp",
        "live as",
        "become a",
    ],

    "Sports": [
        "sports",
        "sport",
        "athletic",
    ],

    "Racing": [
        "racing",
        "race",
        "racer",
    ],

    "Fighting": [
        "fighting",
        "fighter",
        "fight",
        "combat",
        "brawl",
    ],

    "Shooter": [
        "shooter",
        "shooting",
        "gun",
        "guns",
        "weapon",
        "weapons",
        "fps",
    ],

    "Tycoon": [
        "tycoon",
        "build your empire",
        "grow your business",
    ],

    "Obby": [
        "obby",
        "obstacle course",
        "obstacles",
    ],

    "Puzzle": [
        "puzzle",
        "puzzles",
        "solve",
        "brain",
    ],

    "Party": [
        "party",
        "party game",
        "minigames",
        "mini games",
    ],

    "Story": [
        "story",
        "storyline",
        "chapter",
        "chapters",
        "narrative",
    ],

    "Educational": [
        "educational",
        "education",
        "learn",
        "learning",
        "school",
        "math",
        "science",
        "history",
    ],

    "Sandbox": [
        "sandbox",
        "build anything",
        "create anything",
        "your own world",
    ],

    "Anime": [
        "anime",
        "manga",
        "otaku",
    ],

    "Military": [
        "military",
        "army",
        "soldier",
        "war",
        "battlefield",
        "marine",
    ],

    "Fantasy": [
        "fantasy",
        "fantasy world",
        "wizard",
        "dragon",
        "elf",
        "kingdom",
    ],

    "Sci-Fi": [
        "sci-fi",
        "scifi",
        "science fiction",
        "spaceship",
        "alien",
    ],

    "Mystery": [
        "mystery",
        "mysterious",
        "investigate",
        "investigation",
        "unknown",
    ],

    "Exploration": [
        "explore",
        "exploration",
        "discover",
        "discovery",
        "uncharted",
    ],

    "Superhero": [
        "superhero",
        "super hero",
        "hero",
        "villain",
        "superpower",
        "super powers",
    ],

    "Remake": [
        "remake",
        "reimagined",
        "recreated",
        "classic remake",
    ],

    "Meme": [
        "meme",
        "memes",
    ],

    "Brainrot": [
        "brainrot",
        "brain rot",
        "skibidi",
        "sigma",
        "gyatt",
        "rizz",
    ],

    # ------------------------------------------------------------------
    # PLATFORMING / OBBY
    # ------------------------------------------------------------------

    "Parkour": [
        "parkour",
        "wall run",
        "wallrun",
        "freerun",
        "free run",
    ],

    "Platformer": [
        "platformer",
        "platforming",
        "platform",
    ],

    "Tower Defense": [
        "tower defense",
        "tower defence",
        "td",
        "defend your base",
    ],

    "Tower Climb": [
        "tower climb",
        "climb the tower",
        "climbing tower",
    ],

    "Wave Defense": [
        "wave defense",
        "wave defence",
        "waves of enemies",
        "survive waves",
    ],

    "Hack & Slash": [
        "hack and slash",
        "hack & slash",
        "slash enemies",
        "sword combat",
    ],

    "Roguelike": [
        "roguelike",
        "rogue-like",
        "permadeath dungeon",
    ],

    "Roguelite": [
        "roguelite",
        "rogue-lite",
        "rogue lite",
    ],

    "Dungeon Crawler": [
        "dungeon crawler",
        "dungeon crawl",
        "explore dungeons",
    ],

    "Boss Rush": [
        "boss rush",
        "boss rushes",
        "fight bosses",
    ],

    "Battle Royale": [
        "battle royale",
        "last player standing",
        "last man standing",
        "last person standing",
    ],

    "Arena": [
        "arena",
        "battle arena",
    ],

    "1v1": [
        "1v1",
        "1v1s",
        "one versus one",
        "one v one",
    ],

    "Team-Based": [
        "team based",
        "team-based",
        "team battle",
        "teams",
    ],

    "PvP": [
        "pvp",
        "player versus player",
        "player vs player",
        "players vs players",
    ],

    "PvE": [
        "pve",
        "player versus environment",
        "fight enemies",
    ],

    "PvPvE": [
        "pvpve",
        "player versus player versus environment",
    ],

    "Co-op": [
        "co-op",
        "coop",
        "co op",
        "cooperative",
        "play together",
    ],

    "Singleplayer": [
        "singleplayer",
        "single player",
        "solo game",
        "play alone",
    ],

    "Open World": [
        "open world",
        "open-world",
        "huge world",
        "vast world",
    ],

    "Linear": [
        "linear",
        "linear story",
        "linear progression",
    ],

    "Procedural": [
        "procedural",
        "procedurally generated",
        "randomly generated",
        "random generation",
    ],

    "Physics-Based": [
        "physics",
        "physics-based",
        "ragdoll",
        "realistic physics",
    ],

    "Idle": [
        "idle",
        "idle game",
        "idle simulator",
    ],

    "Incremental": [
        "incremental",
        "increment",
        "numbers go up",
    ],

    "Clicker": [
        "clicker",
        "click clicks",
        "clicking game",
    ],

    "AFK": [
        "afk",
        "away from keyboard",
        "earn while afk",
    ],

    "Grinding": [
        "grind",
        "grinding",
        "farm for",
        "farm xp",
    ],

    "Progression": [
        "progression",
        "progress",
        "level up",
        "leveling",
    ],

    "Permadeath": [
        "permadeath",
        "perma death",
        "death resets",
    ],

    "Easy Obby": [
        "easy obby",
        "easy obstacle",
        "beginner obby",
    ],

    "Hard Obby": [
        "hard obby",
        "difficult obby",
        "hard obstacle",
    ],

    "Rage Obby": [
        "rage obby",
        "rage game",
        "rage inducing",
    ],

    "Speedrun": [
        "speedrun",
        "speed run",
        "speedrunning",
    ],

    "Time Trial": [
        "time trial",
        "against the clock",
        "beat the clock",
    ],

    "Precision Platforming": [
        "precision platform",
        "precision platforming",
        "precise jumps",
    ],

    "Puzzle Obby": [
        "puzzle obby",
        "puzzle obstacle",
    ],

    "Story Obby": [
        "story obby",
        "story obstacle",
    ],

    "Multiplayer Obby": [
        "multiplayer obby",
        "multiplayer obstacle",
    ],

    "Infinite Obby": [
        "infinite obby",
        "endless obby",
        "infinite obstacle",
    ],

    "Troll Obby": [
        "troll obby",
        "troll obstacle",
        "troll game",
    ],

    # ------------------------------------------------------------------
    # HORROR
    # ------------------------------------------------------------------

    "Psychological Horror": [
        "psychological horror",
        "psychological",
        "mind game horror",
    ],

    "Survival Horror": [
        "survival horror",
        "survive the horror",
    ],

    "Mascot Horror": [
        "mascot horror",
        "mascot",
        "evil mascot",
    ],

    "Analog Horror": [
        "analog horror",
        "analog",
        "vhs horror",
        "vhs",
    ],

    "Backrooms": [
        "backrooms",
        "backrooms level",
        "backroom",
    ],

    "Escape Horror": [
        "escape horror",
        "escape the monster",
        "escape the killer",
        "escape the creature",
    ],

    "Asymmetrical Horror": [
        "asymmetrical horror",
        "asymmetric horror",
        "one killer",
        "one monster",
    ],

    "Jumpscare": [
        "jumpscare",
        "jump scare",
        "jump-scare",
    ],

    "Found Footage": [
        "found footage",
        "found-footage",
        "camera footage",
    ],

    "SCP": [
        "scp",
        "scp foundation",
        "scp-",
    ],

    "Paranormal": [
        "paranormal",
        "ghost",
        "ghosts",
        "demon",
        "spirit",
        "haunting",
    ],

    "Mystery Horror": [
        "horror mystery",
        "mystery horror",
        "solve the mystery",
    ],

    # ------------------------------------------------------------------
    # ROLEPLAY / SOCIAL
    # ------------------------------------------------------------------

    "Life Sim": [
        "life sim",
        "life simulator",
        "live your life",
    ],

    "Town Roleplay": [
        "town roleplay",
        "town rp",
        "town roleplay",
    ],

    "School Roleplay": [
        "school roleplay",
        "school rp",
        "high school",
        "school life",
    ],

    "Family Roleplay": [
        "family roleplay",
        "family rp",
        "raise a family",
        "family simulator",
    ],

    "Workplace Roleplay": [
        "workplace roleplay",
        "workplace rp",
        "work at",
        "job roleplay",
    ],

    "Fantasy Roleplay": [
        "fantasy roleplay",
        "fantasy rp",
        "kingdom roleplay",
    ],

    "Military Roleplay": [
        "military roleplay",
        "military rp",
        "army roleplay",
    ],

    "Police Roleplay": [
        "police roleplay",
        "police rp",
        "cop roleplay",
        "law enforcement",
    ],

    "Medical Roleplay": [
        "medical roleplay",
        "medical rp",
        "hospital roleplay",
        "doctor roleplay",
    ],

    "Hangout": [
        "hangout",
        "hang out",
        "chill with friends",
    ],

    "Voice Chat": [
        "voice chat",
        "vc",
        "talk with players",
    ],

    "Avatar Customization": [
        "avatar customization",
        "customize your avatar",
        "customize avatar",
        "avatar editor",
    ],

    "Fashion": [
        "fashion",
        "outfit",
        "outfits",
        "style",
        "styling",
    ],

    "Makeover": [
        "makeover",
        "make up",
        "makeup",
        "glow up",
    ],

    "Social Deduction": [
        "social deduction",
        "imposter",
        "impostor",
        "find the traitor",
        "traitor",
        "murder mystery",
    ],

    # ------------------------------------------------------------------
    # RPG
    # ------------------------------------------------------------------

    "Action RPG": [
        "action rpg",
        "action roleplaying",
    ],

    "MMORPG": [
        "mmorpg",
        "massively multiplayer",
    ],

    "Turn-Based RPG": [
        "turn based rpg",
        "turn-based rpg",
        "turn based roleplay",
    ],

    "Dungeon RPG": [
        "dungeon rpg",
        "dungeon roleplay",
    ],

    "Open-World RPG": [
        "open world rpg",
        "open-world rpg",
    ],

    "Character Collection": [
        "character collection",
        "collect characters",
        "collect heroes",
    ],

    "Gacha": [
        "gacha",
        "summon characters",
        "summoning",
        "pull characters",
    ],

    "Loot-Based": [
        "loot",
        "loot-based",
        "loot based",
        "loot drops",
    ],

    "Leveling": [
        "leveling",
        "level up",
        "levels",
        "xp",
        "experience",
    ],

    "Classes": [
        "classes",
        "class system",
        "choose your class",
    ],

    "Quests": [
        "quest",
        "quests",
        "missions",
    ],

    "Skill Trees": [
        "skill tree",
        "skill trees",
        "skills",
        "talent tree",
    ],

    "Crafting": [
        "crafting",
        "craft",
        "recipes",
        "craft items",
    ],

    "Equipment": [
        "equipment",
        "equip",
        "gear",
        "armor",
        "weapons",
    ],

    "Bosses": [
        "boss",
        "bosses",
        "boss fight",
    ],

    "Raids": [
        "raid",
        "raids",
        "raid boss",
    ],

    # ------------------------------------------------------------------
    # SIMULATION / MANAGEMENT
    # ------------------------------------------------------------------

    "Life Simulation": [
        "life simulation",
        "life simulator",
        "simulate life",
    ],

    "Vehicle Simulation": [
        "vehicle simulator",
        "vehicle simulation",
    ],

    "Business Simulation": [
        "business simulator",
        "business simulation",
    ],

    "Farming": [
        "farming",
        "farm",
        "farmer",
        "crops",
        "harvest",
    ],

    "Restaurant": [
        "restaurant",
        "restaurant game",
        "restaurant simulator",
    ],

    "Cooking": [
        "cooking",
        "cook food",
        "chef",
        "chef game",
    ],

    "Pet Simulation": [
        "pet simulator",
        "pet simulation",
        "raise pets",
    ],

    "Fishing": [
        "fishing",
        "fish",
        "fisherman",
    ],

    "Mining": [
        "mining",
        "mine ores",
        "mining simulator",
    ],

    "Factory": [
        "factory",
        "factory simulator",
        "factory game",
    ],

    "City Builder": [
        "city builder",
        "build a city",
        "city building",
    ],

    "House Building": [
        "house building",
        "build a house",
        "build houses",
    ],

    "Flight Simulation": [
        "flight simulator",
        "flight simulation",
        "airplane simulator",
        "pilot simulator",
    ],

    "Driving Simulation": [
        "driving simulator",
        "driving simulation",
    ],

    "Job Simulation": [
        "job simulator",
        "job simulation",
        "work simulator",
    ],

    "Business": [
        "business",
        "business game",
        "run a business",
    ],

    "Trading": [
        "trading",
        "trade items",
        "trade with players",
    ],

    "Economy": [
        "economy",
        "economic",
        "player economy",
    ],

    "Market": [
        "market",
        "marketplace",
        "auction house",
    ],

    "Shop Management": [
        "shop management",
        "manage a shop",
        "run a shop",
    ],

    "Restaurant Management": [
        "restaurant management",
        "manage a restaurant",
        "run a restaurant",
    ],

    "Factory Management": [
        "factory management",
        "manage a factory",
    ],

    "Property": [
        "property",
        "real estate",
        "buy houses",
        "own property",
    ],

    "Collecting": [
        "collecting",
        "collect items",
        "collect everything",
    ],

    "Auction": [
        "auction",
        "auctioning",
        "bid on",
    ],

    "Trading Cards": [
        "trading cards",
        "collectible cards",
        "card trading",
    ],

    # ------------------------------------------------------------------
    # COMPETITIVE
    # ------------------------------------------------------------------

    "Ranked": [
        "ranked",
        "ranked mode",
        "competitive ranking",
    ],

    "Leaderboards": [
        "leaderboard",
        "leaderboards",
        "top players",
    ],

    "Tournament": [
        "tournament",
        "tournaments",
    ],

    "Esports": [
        "esports",
        "e-sports",
        "esport",
    ],

    # ------------------------------------------------------------------
    # SHOOTERS
    # ------------------------------------------------------------------

    "Tactical Shooter": [
        "tactical shooter",
        "tactical fps",
        "tactical combat",
    ],

    "Hero Shooter": [
        "hero shooter",
        "hero-based shooter",
        "hero based shooter",
    ],

    "Military Shooter": [
        "military shooter",
        "war shooter",
        "army shooter",
    ],

    "Zombie Shooter": [
        "zombie shooter",
        "zombie gun",
        "shoot zombies",
    ],

    "Sniper": [
        "sniper",
        "sniping",
    ],

    "Gun Game": [
        "gun game",
        "gunfight",
        "gun fight",
    ],

    "Team Deathmatch": [
        "team deathmatch",
        "team death match",
        "tdm",
    ],

    "Capture the Flag": [
        "capture the flag",
        "ctf",
    ],

    "Extraction": [
        "extraction",
        "extract",
        "extract from",
    ],

    # ------------------------------------------------------------------
    # SPORTS
    # ------------------------------------------------------------------

    "Football": [
        "football",
        "american football",
    ],

    "Basketball": [
        "basketball",
    ],

    "Soccer": [
        "soccer",
        "football simulator",
    ],

    "Baseball": [
        "baseball",
    ],

    "Volleyball": [
        "volleyball",
    ],

    "Tennis": [
        "tennis",
    ],

    "Hockey": [
        "hockey",
    ],

    "Golf": [
        "golf",
    ],

    "Boxing": [
        "boxing",
        "boxer",
    ],

    "Wrestling": [
        "wrestling",
        "wrestler",
    ],

    "Skateboarding": [
        "skateboard",
        "skateboarding",
    ],

    "Surfing": [
        "surfing",
        "surf",
    ],

    "Swimming": [
        "swimming",
        "swim",
    ],

    "Track & Field": [
        "track and field",
        "track & field",
        "athletics",
    ],

    # ------------------------------------------------------------------
    # RACING
    # ------------------------------------------------------------------

    "Street Racing": [
        "street racing",
        "street race",
    ],

    "Racing Sim": [
        "racing simulator",
        "racing simulation",
        "racing sim",
    ],

    "Arcade Racing": [
        "arcade racing",
        "arcade racer",
    ],

    "Kart Racing": [
        "kart racing",
        "kart racer",
        "go kart",
    ],

    "Drag Racing": [
        "drag racing",
        "drag race",
    ],

    "Drift": [
        "drift",
        "drifting",
    ],

    "Motorcycle Racing": [
        "motorcycle racing",
        "motorbike racing",
        "bike racing",
    ],

    "Boat Racing": [
        "boat racing",
        "boat race",
    ],

    "Air Racing": [
        "air racing",
        "air race",
        "plane racing",
    ],

    "Obstacle Racing": [
        "obstacle racing",
        "obstacle race",
    ],

    # ------------------------------------------------------------------
    # STRATEGY
    # ------------------------------------------------------------------

    "RTS": [
        "real time strategy",
        "real-time strategy",
        "rts",
    ],

    "Turn-Based Strategy": [
        "turn based strategy",
        "turn-based strategy",
    ],

    "4X": [
        "4x strategy",
        "4x game",
        "explore expand exploit exterminate",
    ],

    "Resource Management": [
        "resource management",
        "manage resources",
        "gather resources",
    ],

    "Tactical": [
        "tactical",
        "tactics",
    ],

    "Deck Building": [
        "deck building",
        "deckbuilder",
        "build your deck",
    ],

    "Auto Battler": [
        "auto battler",
        "autobattler",
        "auto battle",
    ],

    # ------------------------------------------------------------------
    # PUZZLES
    # ------------------------------------------------------------------

    "Logic": [
        "logic puzzle",
        "logic game",
    ],

    "Word Puzzle": [
        "word puzzle",
        "word game",
        "guess the word",
    ],

    "Trivia": [
        "trivia",
        "quiz",
        "quiz game",
    ],

    "Escape Room": [
        "escape room",
        "escape-room",
    ],

    "Matching": [
        "matching game",
        "match three",
        "match 3",
    ],

    "Physics Puzzle": [
        "physics puzzle",
        "physics-based puzzle",
    ],

    "Memory": [
        "memory game",
        "memory puzzle",
    ],

    "Maze": [
        "maze",
        "mazes",
    ],

    "Riddles": [
        "riddle",
        "riddles",
    ],

    "Detective": [
        "detective",
        "detectives",
        "investigator",
    ],

    "Brain Teaser": [
        "brain teaser",
        "brain teaser game",
    ],

    # ------------------------------------------------------------------
    # COLLECTION / PROGRESSION
    # ------------------------------------------------------------------

    "Collectathon": [
        "collectathon",
        "collect everything",
        "collect them all",
    ],

    "Pets": [
        "pets",
        "pet",
        "pet collection",
    ],

    "Eggs": [
        "eggs",
        "egg hatching",
        "hatch eggs",
    ],

    "Limited Items": [
        "limited items",
        "limited item",
        "limiteds",
    ],

    "Cosmetics": [
        "cosmetics",
        "cosmetic items",
        "skins",
    ],

    "Badges": [
        "badges",
        "badge hunting",
    ],

    "Achievements": [
        "achievements",
        "achievement",
    ],

    "Discoveries": [
        "discoveries",
        "discover items",
        "discover secrets",
    ],

    "Upgrades": [
        "upgrades",
        "upgrade",
    ],

    "Prestige": [
        "prestige",
        "prestiging",
    ],

    "Rebirth": [
        "rebirth",
        "rebirths",
        "rebirth system",
    ],

    "Unlockables": [
        "unlockables",
        "unlock items",
        "unlock characters",
    ],

    "Rare Items": [
        "rare items",
        "rare item",
        "rare drops",
    ],

    # ------------------------------------------------------------------
    # BUILDING / CREATION
    # ------------------------------------------------------------------

    "Building": [
        "building",
        "build",
        "builder",
    ],

    "Construction": [
        "construction",
        "construct",
    ],

    "Designing": [
        "design",
        "designing",
        "designer",
    ],

    "Interior Design": [
        "interior design",
        "decorate your house",
        "decorate your home",
    ],

    "Fashion Design": [
        "fashion design",
        "design outfits",
        "design clothes",
    ],

    "Vehicle Building": [
        "build vehicles",
        "vehicle building",
        "build a car",
    ],

    "World Building": [
        "world building",
        "build a world",
        "create a world",
    ],

    "Level Creation": [
        "level creation",
        "create levels",
        "level editor",
    ],

    "Sandbox Creation": [
        "sandbox creation",
        "create anything",
        "creation sandbox",
    ],

    "Art": [
        "art",
        "artist",
        "drawing",
        "draw",
    ],

    "Music": [
        "music",
        "musical",
        "piano",
        "instrument",
    ],

    "Animation": [
        "animation",
        "animate",
        "animating",
    ],

    # ------------------------------------------------------------------
    # SETTINGS / THEMES
    # ------------------------------------------------------------------

    "Modern": [
        "modern",
        "modern city",
    ],

    "Medieval": [
        "medieval",
        "middle ages",
        "medieval kingdom",
    ],

    "Historical": [
        "historical",
        "history",
        "historical era",
    ],

    "Futuristic": [
        "futuristic",
        "future",
        "future city",
    ],

    "Cyberpunk": [
        "cyberpunk",
        "cyber punk",
    ],

    "Post-Apocalyptic": [
        "post-apocalyptic",
        "post apocalyptic",
        "apocalypse",
        "apocalyptic",
    ],

    "Western": [
        "western",
        "cowboy",
        "wild west",
    ],

    "Pirate": [
        "pirate",
        "pirates",
        "pirate ship",
    ],

    "Underwater": [
        "underwater",
        "under water",
        "ocean",
        "sea",
    ],

    "Space": [
        "space",
        "spaceship",
        "galaxy",
        "planet",
        "astronaut",
    ],

    "Magic": [
        "magic",
        "magical",
        "spell",
        "wizard",
        "witch",
    ],

    "Ninja": [
        "ninja",
        "shinobi",
    ],

    "Samurai": [
        "samurai",
        "katana",
    ],

    # ------------------------------------------------------------------
    # VIBE / DISCOVERY
    # ------------------------------------------------------------------

    "Chill": [
        "chill",
        "chill game",
        "laid back",
    ],

    "Relaxing": [
        "relaxing",
        "relax",
        "peaceful",
        "cozy",
    ],

    "Funny": [
        "funny",
        "comedy",
        "hilarious",
        "joke",
    ],

    "Chaotic": [
        "chaotic",
        "chaos",
        "mayhem",
    ],

    "Immersive": [
        "immersive",
        "immersive world",
    ],

    "Story-Driven": [
        "story driven",
        "story-driven",
        "narrative driven",
        "narrative-driven",
    ],

    "Replayable": [
        "replayable",
        "replay value",
        "play again",
    ],

    "Short Sessions": [
        "short sessions",
        "quick rounds",
        "quick games",
        "5 minute",
        "10 minute",
    ],

    "Long Sessions": [
        "long sessions",
        "hours of gameplay",
        "play for hours",
    ],

    "Family-Friendly": [
        "family friendly",
        "family-friendly",
        "safe for kids",
    ],

    "Beginner-Friendly": [
        "beginner friendly",
        "beginner-friendly",
        "new players",
        "easy to learn",
    ],

    "Solo Friendly": [
        "solo friendly",
        "solo-friendly",
        "play solo",
    ],

    "Friend Group": [
        "friend group",
        "group of friends",
        "friends",
    ],

    "Good With Friends": [
        "good with friends",
        "play with friends",
        "friends can play",
    ],

    "Quick Play": [
        "quick play",
        "quick game",
        "quick round",
        "quick match",
    ],

    "Challenging": [
        "challenging",
        "difficult",
        "hard",
        "challenge",
    ],

    "High Skill Ceiling": [
        "high skill ceiling",
        "skill ceiling",
        "master",
        "mastery",
    ],

    "Controller Friendly": [
        "controller",
        "gamepad",
        "controller support",
    ],

    "Mobile Friendly": [
        "mobile",
        "mobile friendly",
        "phone",
        "tablet",
    ],

    "Low-End Friendly": [
        "low end",
        "low-end",
        "low spec",
        "low specs",
        "weak pc",
    ],
}


# ======================================================================
# TEXT HELPERS
# ======================================================================

def normalize_text(text):
    """
    Normalize text so keyword matching is more reliable.
    """

    if not text:
        return ""

    text = str(text).lower()

    text = text.replace(
        "&",
        " and "
    )

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def keyword_matches(text, keyword):
    """
    Safer keyword matching.

    Short terms like 'rp' or 'vc' should not accidentally match
    random words.
    """

    keyword = normalize_text(keyword)

    if not keyword:
        return False

    if len(keyword) <= 3:
        return re.search(
            r"\b" + re.escape(keyword) + r"\b",
            text
        ) is not None

    return keyword in text


# ======================================================================
# CATEGORY DETECTION
# ======================================================================

def detect_categories(game):
    """
    Determine BFYP categories from:
      - Roblox genre
      - game name
      - game description
      - Roblox metadata

    Only categories from VALID_CATEGORIES can be returned.
    """

    categories = set()

    name = normalize_text(
        game.get("name", "")
    )

    description = normalize_text(
        game.get("description", "")
    )

    genre = game.get("genre")

    combined_text = (
        name
        + " "
        + name
        + " "
        + description
    )

    # --------------------------------------------------------------
    # Roblox's own genre
    # --------------------------------------------------------------

    if genre in GENRE_TO_CATEGORIES:

        for category in GENRE_TO_CATEGORIES[genre]:

            if category in VALID_CATEGORY_SET:
                categories.add(category)

    # --------------------------------------------------------------
    # Keyword detection
    # --------------------------------------------------------------

    for category, keywords in CATEGORY_KEYWORDS.items():

        if category not in VALID_CATEGORY_SET:
            continue

        for keyword in keywords:

            if keyword_matches(
                combined_text,
                keyword
            ):

                categories.add(category)
                break

    # --------------------------------------------------------------
    # Name-based stronger signals
    # --------------------------------------------------------------

    # Obby
    if "obby" in name:

        categories.add("Obby")

    # Anime
    if "anime" in name:

        categories.add("Anime")

    # Horror
    if "horror" in name:

        categories.add("Horror")

    # Simulator
    if (
        "simulator" in name
        or "simulation" in name
    ):

        categories.add("Simulation")

    # Tycoon
    if "tycoon" in name:

        categories.add("Tycoon")

    # RPG
    if "rpg" in name:

        categories.add("RPG")

    # Racing
    if (
        "racing" in name
        or "race" in name
    ):

        categories.add("Racing")

    # --------------------------------------------------------------
    # Special combinations
    # --------------------------------------------------------------

    if (
        "horror" in combined_text
        and (
            "survive" in combined_text
            or "survival" in combined_text
        )
    ):

        categories.add("Survival Horror")

    if (
        "horror" in combined_text
        and (
            "escape" in combined_text
        )
    ):

        categories.add("Escape Horror")

    if (
        "horror" in combined_text
        and (
            "jumpscare" in combined_text
            or "jump scare" in combined_text
        )
    ):

        categories.add("Jumpscare")

    if (
        "anime" in combined_text
        and (
            "fight" in combined_text
            or "battle" in combined_text
            or "combat" in combined_text
        )
    ):

        categories.add("Fighting")
        categories.add("Action")

    if (
        "anime" in combined_text
        and "rpg" in combined_text
    ):

        categories.add("Anime")
        categories.add("RPG")
        categories.add("Action RPG")

    if (
        "tower defense" in combined_text
    ):

        categories.add("Tower Defense")
        categories.add("Strategy")

    if (
        "roleplay" in combined_text
        or "role-play" in combined_text
    ):

        categories.add("Roleplay")

    # --------------------------------------------------------------
    # Remove invalid categories
    # --------------------------------------------------------------

    categories = {
        category
        for category in categories
        if category in VALID_CATEGORY_SET
    }

    return sort_categories(categories)


def sort_categories(categories):
    """
    Keep category output in the same general order as VALID_CATEGORIES.
    """

    order = {
        category: index
        for index, category
        in enumerate(VALID_CATEGORIES)
    }

    return sorted(
        categories,
        key=lambda category: order.get(
            category,
            999999
        )
    )


# ======================================================================
# HTTP
# ======================================================================

def get_json(url, params=None):
    """
    Download JSON and retry temporary failures.
    """

    if params:

        separator = (
            "&"
            if "?" in url
            else "?"
        )

        url = (
            url
            + separator
            + urllib.parse.urlencode(
                params
            )
        )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            with urllib.request.urlopen(
                request,
                timeout=30
            ) as response:

                return json.load(
                    response
                )

        except urllib.error.HTTPError as error:

            if (
                error.code == 429
                or error.code >= 500
            ):

                retry_after = (
                    error.headers.get(
                        "Retry-After"
                    )
                )

                if (
                    retry_after
                    and retry_after.isdigit()
                ):

                    wait = int(
                        retry_after
                    )

                else:

                    wait = 2 ** attempt

                print(
                    f"  HTTP {error.code}. "
                    f"Waiting {wait}s "
                    f"(try {attempt}/{MAX_RETRIES})"
                )

                time.sleep(wait)

                continue

            print(
                f"  HTTP {error.code}: {url}"
            )

            return None

        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:

            print(
                f"  Network problem: "
                f"{error} "
                f"(try {attempt}/{MAX_RETRIES})"
            )

            time.sleep(
                2 ** attempt
            )

    return None


# ======================================================================
# GENERAL HELPERS
# ======================================================================

def chunks(items, size):

    for start in range(
        0,
        len(items),
        size
    ):

        yield items[
            start:start + size
        ]


def recursive_find_universe_ids(value):
    """
    Recursively search discovery responses for Universe IDs.
    """

    found = set()

    if isinstance(
        value,
        dict
    ):

        for key, item in value.items():

            normalized = (
                str(key)
                .lower()
                .replace("-", "")
                .replace("_", "")
            )

            if normalized == "universeid":

                if isinstance(
                    item,
                    int
                ):

                    found.add(item)

                elif (
                    isinstance(item, str)
                    and item.isdigit()
                ):

                    found.add(
                        int(item)
                    )

            else:

                found.update(
                    recursive_find_universe_ids(
                        item
                    )
                )

    elif isinstance(
        value,
        list
    ):

        for item in value:

            found.update(
                recursive_find_universe_ids(
                    item
                )
            )

    return found


# ======================================================================
# SEARCH DISCOVERY
# ======================================================================

def discover_via_search():

    universe_ids = set()

    print(
        "\n=============================="
    )

    print(
        "ROBLOX SEARCH DISCOVERY"
    )

    print(
        "=============================="
    )

    for number, term in enumerate(
        SEARCH_TERMS,
        start=1
    ):

        if len(universe_ids) >= MAX_DISCOVERED_GAMES:
            break

        print(
            f"[{number}/{len(SEARCH_TERMS)}] "
            f"Searching: {term!r}"
        )

        payload = get_json(
            SEARCH_URL,
            {
                "searchQuery": term,
                "pageType": "all",
                "sessionId": SESSION_ID,
            },
        )

        time.sleep(
            PAUSE_SECONDS
        )

        if not payload:

            print(
                "  No response."
            )

            continue

        found = (
            recursive_find_universe_ids(
                payload
            )
        )

        found = set(
            list(found)[
                :MAX_RESULTS_PER_SEARCH
            ]
        )

        before = len(
            universe_ids
        )

        universe_ids.update(
            found
        )

        added = (
            len(universe_ids)
            - before
        )

        print(
            f"  Found {len(found)} IDs "
            f"({added} new, "
            f"{len(universe_ids)} total)"
        )

    return universe_ids


# ======================================================================
# EXPLORE DISCOVERY
# ======================================================================

def discover_via_explore():

    universe_ids = set()

    print(
        "\n=============================="
    )

    print(
        "ROBLOX EXPLORE DISCOVERY"
    )

    print(
        "=============================="
    )

    payload = get_json(
        EXPLORE_SORTS_URL,
        {
            "sessionId": SESSION_ID,
            "device": "computer",
            "country": "all",
        },
    )

    time.sleep(
        PAUSE_SECONDS
    )

    if not payload:

        print(
            "Could not retrieve Explore sorts."
        )

        return universe_ids

    sorts = []

    if isinstance(
        payload,
        dict
    ):

        possible_sorts = (
            payload.get(
                "sorts",
                []
            )
        )

        if isinstance(
            possible_sorts,
            list
        ):

            sorts = possible_sorts

    print(
        f"Found {len(sorts)} Explore sorts."
    )

    for number, sort in enumerate(
        sorts,
        start=1
    ):

        if len(universe_ids) >= MAX_DISCOVERED_GAMES:
            break

        if not isinstance(
            sort,
            dict
        ):

            continue

        sort_id = (
            sort.get("sortId")
            or sort.get("token")
            or sort.get("id")
        )

        sort_name = (
            sort.get("sortDisplayName")
            or sort.get("name")
            or str(sort_id)
        )

        if not sort_id:
            continue

        print(
            f"[{number}/{len(sorts)}] "
            f"Explore sort: {sort_name}"
        )

        content = get_json(
            EXPLORE_SORT_CONTENT_URL,
            {
                "sessionId": SESSION_ID,
                "sortId": sort_id,
                "device": "computer",
                "country": "all",
                "maxRows": MAX_RESULTS_PER_SORT,
            },
        )

        time.sleep(
            PAUSE_SECONDS
        )

        if not content:

            print(
                "  No content."
            )

            continue

        found = (
            recursive_find_universe_ids(
                content
            )
        )

        found = set(
            list(found)[
                :MAX_RESULTS_PER_SORT
            ]
        )

        before = len(
            universe_ids
        )

        universe_ids.update(
            found
        )

        added = (
            len(universe_ids)
            - before
        )

        print(
            f"  Found {len(found)} IDs "
            f"({added} new, "
            f"{len(universe_ids)} total)"
        )

    return universe_ids


# ======================================================================
# PLACE -> UNIVERSE
# ======================================================================

def resolve_place_id(place_id):

    data = get_json(
        PLACE_TO_UNIVERSE_URL.format(
            place_id=place_id
        )
    )

    time.sleep(
        PAUSE_SECONDS
    )

    if (
        data
        and isinstance(
            data.get("universeId"),
            int
        )
    ):

        return data["universeId"]

    print(
        f"  Could not find a universe "
        f"for place {place_id}"
    )

    return None


# ======================================================================
# GAME DETAILS
# ======================================================================

def fetch_games(universe_ids):

    payload = get_json(
        GAMES_URL,
        {
            "universeIds": ",".join(
                map(
                    str,
                    universe_ids
                )
            )
        },
    )

    time.sleep(
        PAUSE_SECONDS
    )

    if not payload:
        return {}

    return {
        item["id"]: item
        for item in payload.get(
            "data",
            []
        )
        if "id" in item
    }


def fetch_votes(universe_ids):

    payload = get_json(
        VOTES_URL,
        {
            "universeIds": ",".join(
                map(
                    str,
                    universe_ids
                )
            )
        },
    )

    time.sleep(
        PAUSE_SECONDS
    )

    if not payload:
        return {}

    return {
        item["id"]: (
            item.get(
                "upVotes",
                0
            ),
            item.get(
                "downVotes",
                0
            ),
        )
        for item in payload.get(
            "data",
            []
        )
        if "id" in item
    }


def fetch_icons(universe_ids):

    payload = get_json(
        ICONS_URL,
        {
            "universeIds": ",".join(
                map(
                    str,
                    universe_ids
                )
            ),
            "size": "256x256",
            "format": "Png",
            "isCircular": "false",
        },
    )

    time.sleep(
        PAUSE_SECONDS
    )

    if not payload:
        return {}

    return {
        item["targetId"]: item.get(
            "imageUrl"
        )
        for item in payload.get(
            "data",
            []
        )
        if (
            item.get("state")
            == "Completed"
            and item.get("targetId")
            is not None
        )
    }


# ======================================================================
# DATE HELPERS
# ======================================================================

def to_unix(iso_text):

    if not iso_text:
        return None

    try:

        cleaned = re.sub(
            r"\.\d+",
            "",
            iso_text
        ).replace(
            "Z",
            "+00:00"
        )

        return int(
            datetime.fromisoformat(
                cleaned
            ).timestamp()
        )

    except ValueError:

        return None


# ======================================================================
# BUILD GAME RECORD
# ======================================================================

def build_record(
    game,
    votes,
    icon_url
):

    up, down = votes

    total = up + down

    like_ratio = (
        round(
            up / total,
            3
        )
        if total
        else None
    )

    creator = (
        game.get("creator")
        or {}
    )

    genre = game.get(
        "genre"
    )

    categories = detect_categories(
        game
    )

    return {

        "UniverseId": game["id"],

        "PlaceId": game.get(
            "rootPlaceId"
        ),

        "Name": game.get(
            "name",
            ""
        ),

        "Description": (
            game.get(
                "description"
            )
            or ""
        )[:1000],

        "CreatorId": creator.get(
            "id"
        ),

        "CreatorName": creator.get(
            "name"
        ),

        "CreatorType": creator.get(
            "type"
        ),

        "Thumbnail": icon_url,

        "Categories": categories,

        "RobloxGenre": genre,

        "Playing": game.get(
            "playing",
            0
        ),

        "Visits": game.get(
            "visits",
            0
        ),

        "Favorites": game.get(
            "favoritedCount",
            0
        ),

        "RobloxLikeRatio": like_ratio,

        "CreatedAt": to_unix(
            game.get(
                "created"
            )
        ),

        "UpdatedAt": to_unix(
            game.get(
                "updated"
            )
        ),

        "FetchedAt": int(
            time.time()
        ),
    }


# ======================================================================
# CATALOG-LEVEL CATEGORY CALCULATIONS
#
# These categories depend on OTHER games in the catalog.
# They should not be assigned simply because a keyword appears.
# ======================================================================

def apply_catalog_categories(records):

    if not records:
        return records

    # --------------------------------------------------------------
    # Gather values
    # --------------------------------------------------------------

    playing_values = sorted(
        [
            int(
                record.get(
                    "Playing",
                    0
                ) or 0
            )
            for record in records
        ]
    )

    visits_values = sorted(
        [
            int(
                record.get(
                    "Visits",
                    0
                ) or 0
            )
            for record in records
        ]
    )

    favorites_values = sorted(
        [
            int(
                record.get(
                    "Favorites",
                    0
                ) or 0
            )
            for record in records
        ]
    )

    def percentile(
        values,
        percentage
    ):

        if not values:
            return 0

        index = int(
            len(values)
            * percentage
        )

        index = min(
            index,
            len(values) - 1
        )

        return values[index]

    # --------------------------------------------------------------
    # Thresholds
    # --------------------------------------------------------------

    popular_playing = percentile(
        playing_values,
        0.90
    )

    trending_playing = percentile(
        playing_values,
        0.75
    )

    large_community_playing = percentile(
        playing_values,
        0.75
    )

    small_community_playing = percentile(
        playing_values,
        0.25
    )

    popular_visits = percentile(
        visits_values,
        0.90
    )

    hidden_gem_playing = percentile(
        playing_values,
        0.50
    )

    hidden_gem_visits = percentile(
        visits_values,
        0.50
    )

    # --------------------------------------------------------------
    # Assign calculated categories
    # --------------------------------------------------------------

    current_time = time.time()

    for record in records:

        categories = set(
            record.get(
                "Categories",
                []
            )
        )

        playing = int(
            record.get(
                "Playing",
                0
            ) or 0
        )

        visits = int(
            record.get(
                "Visits",
                0
            ) or 0
        )

        favorites = int(
            record.get(
                "Favorites",
                0
            ) or 0
        )

        created_at = record.get(
            "CreatedAt"
        )

        # ----------------------------------------------------------
        # Popular
        # ----------------------------------------------------------

        if (
            playing >= popular_playing
            or visits >= popular_visits
        ):

            categories.add(
                "Popular"
            )

        # ----------------------------------------------------------
        # Trending
        #
        # This is currently a relative popularity approximation.
        # Later BFYP can calculate a much better trend score using
        # multiple crawler snapshots.
        # ----------------------------------------------------------

        if (
            playing >= trending_playing
            and playing > 0
        ):

            categories.add(
                "Trending"
            )

        if (
            playing >= large_community_playing
        ):

            categories.add(
                "Large Community"
            )

        # ----------------------------------------------------------
        # Small Community
        # ----------------------------------------------------------

        if (
            playing <= small_community_playing
        ):

            categories.add(
                "Small Community"
            )

        # ----------------------------------------------------------
        # Hidden Gem
        #
        # We don't call every low-player game a hidden gem.
        # It needs some engagement signal.
        # ----------------------------------------------------------

        if (
            playing <= hidden_gem_playing
            and visits <= hidden_gem_visits
            and favorites > 0
        ):

            categories.add(
                "Hidden Gem"
            )

        # ----------------------------------------------------------
        # New Release
        #
        # Games released within approximately 30 days.
        # ----------------------------------------------------------

        if created_at:

            age_seconds = (
                current_time
                - created_at
            )

            if age_seconds <= (
                30 * 24 * 60 * 60
            ):

                categories.add(
                    "New Release"
                )

        # ----------------------------------------------------------
        # Popularity signals
        # ----------------------------------------------------------

        if visits > 10_000_000:

            categories.add(
                "Popular"
            )

        # ----------------------------------------------------------
        # Validate
        # ----------------------------------------------------------

        categories = {
            category
            for category in categories
            if category in VALID_CATEGORY_SET
        }

        record["Categories"] = sort_categories(
            categories
        )

    return records


# ======================================================================
# SEED FILE
# ======================================================================

def read_seed_ids():

    """
    seed_ids.txt supports:

        123456789

    Universe ID.

    Or:

        p:123456789

    Place ID.

    Lines beginning with # are comments.
    """

    if not SEED_FILE.exists():

        print(
            "seed_ids.txt was not found."
        )

        print(
            "Automatic discovery will still run."
        )

        return [], []

    universe_ids = []
    place_ids = []

    for line in SEED_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.split(
            "#",
            1
        )[0].strip()

        if not line:
            continue

        if line.lower().startswith(
            "p:"
        ):

            value = line[
                2:
            ].strip()

            if value.isdigit():

                place_ids.append(
                    int(value)
                )

        elif line.isdigit():

            universe_ids.append(
                int(line)
            )

        else:

            print(
                f"Skipping line I don't "
                f"understand: {line!r}"
            )

    return (
        universe_ids,
        place_ids
    )


# ======================================================================
# MAIN
# ======================================================================

def main():

    print(
        "=========================================="
    )

    print(
        " BFYP CATALOG CRAWLER"
    )

    print(
        " Automatic Roblox Game Discovery"
    )

    print(
        "=========================================="
    )

    print(
        f"\nBFYP category vocabulary: "
        f"{len(VALID_CATEGORIES)} categories"
    )

    # --------------------------------------------------------------
    # 1. Read manual seeds
    # --------------------------------------------------------------

    seed_universe_ids, place_ids = (
        read_seed_ids()
    )

    universe_ids = set(
        seed_universe_ids
    )

    print(
        f"Manual seeds: "
        f"{len(seed_universe_ids)} universe IDs, "
        f"{len(place_ids)} place IDs"
    )

    # --------------------------------------------------------------
    # 2. Resolve Place IDs
    # --------------------------------------------------------------

    for place_id in place_ids:

        universe_id = resolve_place_id(
            place_id
        )

        if universe_id:

            universe_ids.add(
                universe_id
            )

    # --------------------------------------------------------------
    # 3. Search discovery
    # --------------------------------------------------------------

    if USE_SEARCH_DISCOVERY:

        discovered_search = (
            discover_via_search()
        )

        universe_ids.update(
            discovered_search
        )

        print(
            f"\nSearch discovery added "
            f"{len(discovered_search)} IDs."
        )

    # --------------------------------------------------------------
    # 4. Explore discovery
    # --------------------------------------------------------------

    if USE_EXPLORE_DISCOVERY:

        discovered_explore = (
            discover_via_explore()
        )

        universe_ids.update(
            discovered_explore
        )

        print(
            f"\nExplore discovery added "
            f"{len(discovered_explore)} IDs."
        )

    # --------------------------------------------------------------
    # 5. Limit catalog size for this run
    # --------------------------------------------------------------

    universe_ids = list(
        universe_ids
    )

    if (
        len(universe_ids)
        > MAX_DISCOVERED_GAMES
    ):

        universe_ids = universe_ids[
            :MAX_DISCOVERED_GAMES
        ]

    print(
        "\n=========================================="
    )

    print(
        f"Total unique games discovered: "
        f"{len(universe_ids)}"
    )

    print(
        "=========================================="
    )

    if not universe_ids:

        raise SystemExit(
            "\nNo games were discovered."
        )

    # --------------------------------------------------------------
    # 6. Fetch detailed data
    # --------------------------------------------------------------

    records = []

    batches = list(
        chunks(
            universe_ids,
            BATCH_SIZE
        )
    )

    for batch_number, batch in enumerate(
        batches,
        start=1
    ):

        print(
            f"\nDetailed batch "
            f"{batch_number}/{len(batches)}: "
            f"{len(batch)} games"
        )

        games = fetch_games(
            batch
        )

        votes = fetch_votes(
            batch
        )

        icons = fetch_icons(
            batch
        )

        for universe_id in batch:

            game = games.get(
                universe_id
            )

            if game is None:

                print(
                    f"  No info for "
                    f"{universe_id} "
                    f"(private, removed, "
                    f"or invalid) - skipped"
                )

                continue

            record = build_record(
                game,
                votes.get(
                    universe_id,
                    (0, 0)
                ),
                icons.get(
                    universe_id
                ),
            )

            records.append(
                record
            )

            print(
                f"  + {record['Name']} "
                f"[{len(record['Categories'])} tags]"
            )

    # --------------------------------------------------------------
    # 7. Calculate catalog-level categories
    # --------------------------------------------------------------

    print(
        "\nCalculating catalog-level tags..."
    )

    records = apply_catalog_categories(
        records
    )

    # --------------------------------------------------------------
    # 8. Final validation
    # --------------------------------------------------------------

    for record in records:

        record["Categories"] = [
            category
            for category in record.get(
                "Categories",
                []
            )
            if category in VALID_CATEGORY_SET
        ]

        record["Categories"] = sort_categories(
            record["Categories"]
        )

    # --------------------------------------------------------------
    # 9. Build catalog
    # --------------------------------------------------------------

    catalog = {

        "GeneratedAt": int(
            time.time()
        ),

        "Count": len(
            records
        ),

        "CategoryCount": len(
            VALID_CATEGORIES
        ),

        "Games": records,
    }

    # --------------------------------------------------------------
    # 10. Save
    # --------------------------------------------------------------

    OUTPUT_FILE.write_text(
        json.dumps(
            catalog,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # --------------------------------------------------------------
    # 11. Summary
    # --------------------------------------------------------------

    print(
        "\n=========================================="
    )

    print(
        " DONE"
    )

    print(
        "=========================================="
    )

    print(
        f"Saved {len(records)} games "
        f"to {OUTPUT_FILE}"
    )

    print(
        f"BFYP categories available: "
        f"{len(VALID_CATEGORIES)}"
    )

    print(
        "\nFirst 10 games:"
    )

    for record in records[:10]:

        categories = ", ".join(
            record.get(
                "Categories",
                []
            )[:8]
        )

        print(
            f"\n  - {record['Name']}"
        )

        print(
            f"    Playing: "
            f"{record['Playing']:,}"
        )

        print(
            f"    Categories: "
            f"{categories}"
        )

    if not records:

        print(
            "\nNo games were saved."
        )

        print(
            "Check the output above for errors."
        )


# ======================================================================
# START
# ======================================================================

if __name__ == "__main__":
    main()
