"""
Game object recognition vocabulary for ThinAI's natural-language parser.

Provides a comprehensive mapping of game-related words to categories and
display properties, plus functions for recognizing objects in free text.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Master vocabulary (~150 canonical entries)
# ---------------------------------------------------------------------------

GAME_OBJECTS: dict[str, dict] = {
    # ── Game Pieces (~40) ──────────────────────────────────────────────
    "stone":   {"category": "piece", "display": "circle",  "color": "default"},
    "disc":    {"category": "piece", "display": "circle",  "color": "default"},
    "disk":    {"category": "piece", "display": "circle",  "color": "default"},
    "chip":    {"category": "piece", "display": "circle",  "color": "default"},
    "marker":  {"category": "piece", "display": "circle",  "color": "default"},
    "peg":     {"category": "piece", "display": "circle",  "color": "default"},
    "bead":    {"category": "piece", "display": "circle",  "color": "default"},
    "token":   {"category": "piece", "display": "circle",  "color": "default"},
    "counter": {"category": "piece", "display": "circle",  "color": "default"},
    "checker": {"category": "piece", "display": "checker", "color": "default"},
    "piece":   {"category": "piece", "display": "circle",  "color": "default"},
    "man":     {"category": "piece", "display": "circle",  "color": "default"},
    "meeple":  {"category": "piece", "display": "meeple",  "color": "default"},
    "pawn":    {"category": "chess", "display": "pawn",    "color": "default"},
    "rook":    {"category": "chess", "display": "rook",    "color": "default"},
    "knight":  {"category": "chess", "display": "knight",  "color": "default"},
    "bishop":  {"category": "chess", "display": "bishop",  "color": "default"},
    "queen":   {"category": "chess", "display": "queen",   "color": "default"},
    "king":    {"category": "chess", "display": "king",    "color": "default"},
    "domino":  {"category": "piece", "display": "domino",  "color": "default"},
    "tile":    {"category": "piece", "display": "square",  "color": "default"},
    "die":     {"category": "piece", "display": "die",     "color": "default"},
    "dice":    {"category": "piece", "display": "die",     "color": "default"},
    "marble":  {"category": "piece", "display": "circle",  "color": "default"},
    "ball":    {"category": "piece", "display": "circle",  "color": "default"},
    "block":   {"category": "piece", "display": "square",  "color": "default"},
    "cube":    {"category": "piece", "display": "square",  "color": "default"},
    "pin":     {"category": "piece", "display": "circle",  "color": "default"},
    "cap":     {"category": "piece", "display": "circle",  "color": "default"},
    "ring":    {"category": "piece", "display": "ring",    "color": "default"},
    "figurine": {"category": "piece", "display": "meeple", "color": "default"},
    "miniature": {"category": "piece", "display": "meeple", "color": "default"},
    "mini":    {"category": "piece", "display": "meeple",  "color": "default"},
    "standee": {"category": "piece", "display": "meeple",  "color": "default"},
    "chit":    {"category": "piece", "display": "square",  "color": "default"},
    "stick":   {"category": "piece", "display": "stick",   "color": "default"},
    "rod":     {"category": "piece", "display": "stick",   "color": "default"},
    "spinner": {"category": "piece", "display": "circle",  "color": "default"},
    "wheel":   {"category": "piece", "display": "circle",  "color": "default"},
    "brick":   {"category": "piece", "display": "square",  "color": "default"},

    # ── Abstract Symbols (~15) ─────────────────────────────────────────
    "cross":    {"category": "symbol", "display": "cross",    "color": "default"},
    "circle":   {"category": "symbol", "display": "circle",   "color": "default"},
    "square":   {"category": "symbol", "display": "square",   "color": "default"},
    "triangle": {"category": "symbol", "display": "triangle", "color": "default"},
    "star":     {"category": "symbol", "display": "star",     "color": "default"},
    "diamond":  {"category": "symbol", "display": "diamond",  "color": "default"},
    "heart":    {"category": "symbol", "display": "heart",    "color": "default"},
    "dot":      {"category": "symbol", "display": "circle",   "color": "default"},
    "orb":      {"category": "symbol", "display": "circle",   "color": "default"},
    "gem":      {"category": "symbol", "display": "diamond",  "color": "default"},
    "crystal":  {"category": "symbol", "display": "diamond",  "color": "default"},
    "coin":     {"category": "symbol", "display": "coin",     "color": "gold"},
    "medal":    {"category": "symbol", "display": "circle",   "color": "gold"},
    "trophy":   {"category": "symbol", "display": "trophy",   "color": "gold"},

    # ── Military / Combat (~15) ────────────────────────────────────────
    "soldier":  {"category": "military", "display": "soldier",  "color": "default"},
    "warrior":  {"category": "military", "display": "soldier",  "color": "default"},
    "archer":   {"category": "military", "display": "archer",   "color": "default"},
    "cavalry":  {"category": "military", "display": "knight",   "color": "default"},
    "ship":     {"category": "military", "display": "ship",     "color": "default"},
    "cannon":   {"category": "military", "display": "cannon",   "color": "default"},
    "tank":     {"category": "military", "display": "tank",     "color": "default"},
    "flag":     {"category": "military", "display": "flag",     "color": "default"},
    "shield":   {"category": "military", "display": "shield",   "color": "default"},
    "sword":    {"category": "military", "display": "sword",    "color": "default"},
    "spear":    {"category": "military", "display": "spear",    "color": "default"},
    "bow":      {"category": "military", "display": "bow",      "color": "default"},
    "army":     {"category": "military", "display": "soldier",  "color": "default"},
    "general":  {"category": "military", "display": "soldier",  "color": "gold"},
    "fortress": {"category": "military", "display": "castle",   "color": "default"},

    # ── Nature (~15) ───────────────────────────────────────────────────
    "tree":     {"category": "nature", "display": "tree",     "color": "green"},
    "mountain": {"category": "nature", "display": "mountain", "color": "gray"},
    "rock":     {"category": "nature", "display": "circle",   "color": "gray"},
    "flower":   {"category": "nature", "display": "flower",   "color": "default"},
    "seed":     {"category": "nature", "display": "circle",   "color": "brown"},
    "leaf":     {"category": "nature", "display": "leaf",     "color": "green"},
    "water":    {"category": "nature", "display": "water",    "color": "blue"},
    "fire":     {"category": "nature", "display": "fire",     "color": "red"},
    "sun":      {"category": "nature", "display": "sun",      "color": "gold"},
    "moon":     {"category": "nature", "display": "moon",     "color": "silver"},
    "animal":   {"category": "nature", "display": "meeple",   "color": "default"},
    "bird":     {"category": "nature", "display": "bird",     "color": "default"},
    "fish":     {"category": "nature", "display": "fish",     "color": "blue"},
    "snake":    {"category": "nature", "display": "snake",    "color": "green"},
    "dragon":   {"category": "nature", "display": "dragon",   "color": "red"},

    # ── People / Characters (~15) ─────────────────────────────────────
    "player":   {"category": "character", "display": "meeple",  "color": "default"},
    "wizard":   {"category": "character", "display": "wizard",  "color": "purple"},
    "thief":    {"category": "character", "display": "meeple",  "color": "black"},
    "farmer":   {"category": "character", "display": "meeple",  "color": "brown"},
    "merchant": {"category": "character", "display": "meeple",  "color": "gold"},
    "pirate":   {"category": "character", "display": "meeple",  "color": "default"},
    "ninja":    {"category": "character", "display": "meeple",  "color": "black"},
    "ghost":    {"category": "character", "display": "ghost",   "color": "white"},
    "skeleton": {"category": "character", "display": "meeple",  "color": "white"},
    "goblin":   {"category": "character", "display": "meeple",  "color": "green"},
    "troll":    {"category": "character", "display": "meeple",  "color": "green"},
    "hero":     {"category": "character", "display": "meeple",  "color": "gold"},
    "villain":  {"category": "character", "display": "meeple",  "color": "red"},
    "guard":    {"category": "character", "display": "soldier", "color": "default"},
    "scout":    {"category": "character", "display": "meeple",  "color": "default"},

    # ── Resources (~15) ────────────────────────────────────────────────
    "gold":     {"category": "resource", "display": "coin",     "color": "gold"},
    "silver":   {"category": "resource", "display": "coin",     "color": "silver"},
    "wood":     {"category": "resource", "display": "square",   "color": "brown"},
    "ore":      {"category": "resource", "display": "diamond",  "color": "gray"},
    "wool":     {"category": "resource", "display": "circle",   "color": "white"},
    "wheat":    {"category": "resource", "display": "wheat",    "color": "gold"},
    "food":     {"category": "resource", "display": "circle",   "color": "green"},
    "money":    {"category": "resource", "display": "coin",     "color": "gold"},
    "treasure": {"category": "resource", "display": "chest",    "color": "gold"},
    "key":      {"category": "resource", "display": "key",      "color": "gold"},
    "chest":    {"category": "resource", "display": "chest",    "color": "brown"},
    "potion":   {"category": "resource", "display": "potion",   "color": "purple"},
    "scroll":   {"category": "resource", "display": "scroll",   "color": "default"},
    "crown":    {"category": "resource", "display": "crown",    "color": "gold"},

    # ── Board Elements (~10) ──────────────────────────────────────────
    "wall":    {"category": "board", "display": "wall",   "color": "gray"},
    "bridge":  {"category": "board", "display": "bridge", "color": "brown"},
    "path":    {"category": "board", "display": "path",   "color": "default"},
    "door":    {"category": "board", "display": "door",   "color": "brown"},
    "gate":    {"category": "board", "display": "gate",   "color": "gray"},
    "tower":   {"category": "board", "display": "tower",  "color": "gray"},
    "castle":  {"category": "board", "display": "castle", "color": "gray"},
    "house":   {"category": "board", "display": "house",  "color": "default"},
    "village": {"category": "board", "display": "house",  "color": "default"},
    "city":    {"category": "board", "display": "castle", "color": "default"},

    # ── Animals (~25) ──────────────────────────────────────────────────
    "horse":      {"category": "nature", "display": "horse",      "color": "brown"},
    "wolf":       {"category": "nature", "display": "wolf",       "color": "gray"},
    "bear":       {"category": "nature", "display": "bear",       "color": "brown"},
    "cat":        {"category": "nature", "display": "cat",        "color": "default"},
    "dog":        {"category": "nature", "display": "dog",        "color": "brown"},
    "rabbit":     {"category": "nature", "display": "rabbit",     "color": "white"},
    "lion":       {"category": "nature", "display": "lion",       "color": "gold"},
    "tiger":      {"category": "nature", "display": "tiger",      "color": "gold"},
    "elephant":   {"category": "nature", "display": "elephant",   "color": "gray"},
    "eagle":      {"category": "nature", "display": "eagle",      "color": "brown"},
    "fox":        {"category": "nature", "display": "fox",        "color": "brown"},
    "deer":       {"category": "nature", "display": "deer",       "color": "brown"},
    "owl":        {"category": "nature", "display": "owl",        "color": "brown"},
    "shark":      {"category": "nature", "display": "shark",      "color": "gray"},
    "dolphin":    {"category": "nature", "display": "dolphin",    "color": "blue"},
    "frog":       {"category": "nature", "display": "frog",       "color": "green"},
    "mouse":      {"category": "nature", "display": "mouse",      "color": "gray"},
    "monkey":     {"category": "nature", "display": "monkey",     "color": "brown"},
    "penguin":    {"category": "nature", "display": "penguin",    "color": "black"},
    "bee":        {"category": "nature", "display": "bee",        "color": "gold"},
    "ant":        {"category": "nature", "display": "ant",        "color": "black"},
    "spider":     {"category": "nature", "display": "spider",     "color": "black"},
    "crab":       {"category": "nature", "display": "crab",       "color": "red"},
    "whale":      {"category": "nature", "display": "whale",      "color": "blue"},
    "turtle":     {"category": "nature", "display": "turtle",     "color": "green"},

    # ── Fantasy/RPG (~18) ─────────────────────────────────────────────
    "elf":        {"category": "character", "display": "elf",       "color": "green"},
    "dwarf":      {"category": "character", "display": "dwarf",     "color": "brown"},
    "orc":        {"category": "character", "display": "orc",       "color": "green"},
    "mage":       {"category": "character", "display": "mage",      "color": "blue"},
    "cleric":     {"category": "character", "display": "cleric",    "color": "white"},
    "paladin":    {"category": "character", "display": "paladin",   "color": "gold"},
    "ranger":     {"category": "character", "display": "ranger",    "color": "green"},
    "barbarian":  {"category": "character", "display": "barbarian", "color": "brown"},
    "demon":      {"category": "character", "display": "demon",     "color": "red"},
    "angel":      {"category": "character", "display": "angel",     "color": "white"},
    "unicorn":    {"category": "character", "display": "unicorn",   "color": "white"},
    "phoenix":    {"category": "character", "display": "phoenix",   "color": "red"},
    "ogre":       {"category": "character", "display": "ogre",      "color": "green"},
    "vampire":    {"category": "character", "display": "vampire",   "color": "red"},
    "werewolf":   {"category": "character", "display": "werewolf",  "color": "gray"},
    "golem":      {"category": "character", "display": "golem",     "color": "gray"},
    "fairy":      {"category": "character", "display": "fairy",     "color": "purple"},
    "imp":        {"category": "character", "display": "imp",       "color": "red"},

    # ── Vehicles (~10) ─────────────────────────────────────────────────
    "car":        {"category": "vehicle", "display": "car",        "color": "default"},
    "truck":      {"category": "vehicle", "display": "truck",      "color": "default"},
    "plane":      {"category": "vehicle", "display": "plane",      "color": "default"},
    "helicopter": {"category": "vehicle", "display": "helicopter", "color": "default"},
    "boat":       {"category": "vehicle", "display": "boat",       "color": "blue"},
    "submarine":  {"category": "vehicle", "display": "submarine",  "color": "gray"},
    "rocket":     {"category": "vehicle", "display": "rocket",     "color": "red"},
    "train":      {"category": "vehicle", "display": "train",      "color": "default"},
    "bicycle":    {"category": "vehicle", "display": "bicycle",    "color": "default"},
    "motorcycle": {"category": "vehicle", "display": "motorcycle", "color": "default"},

    # ── Sports/Toys (~8) ──────────────────────────────────────────────
    "goal":       {"category": "board",  "display": "goal",    "color": "default"},
    "net":        {"category": "board",  "display": "net",     "color": "default"},
    "hoop":       {"category": "board",  "display": "hoop",    "color": "default"},
    "bat":        {"category": "piece",  "display": "bat",     "color": "brown"},
    "racket":     {"category": "piece",  "display": "racket",  "color": "default"},
    "arrow":      {"category": "military", "display": "arrow", "color": "default"},
    "target":     {"category": "board",  "display": "target",  "color": "red"},

    # ── Food (~10) ────────────────────────────────────────────────────
    "apple":      {"category": "resource", "display": "apple",    "color": "red"},
    "bread":      {"category": "resource", "display": "bread",    "color": "brown"},
    "cake":       {"category": "resource", "display": "cake",     "color": "default"},
    "pie":        {"category": "resource", "display": "pie",      "color": "brown"},
    "candy":      {"category": "resource", "display": "candy",    "color": "default"},
    "cookie":     {"category": "resource", "display": "cookie",   "color": "brown"},
    "mushroom":   {"category": "resource", "display": "mushroom", "color": "brown"},
    "berry":      {"category": "resource", "display": "berry",    "color": "red"},
    "carrot":     {"category": "resource", "display": "carrot",   "color": "default"},
    "corn":       {"category": "resource", "display": "corn",     "color": "gold"},

    # ── Space/Sci-fi (~10) ────────────────────────────────────────────
    "planet":     {"category": "nature", "display": "planet",    "color": "blue"},
    "alien":      {"category": "nature", "display": "alien",     "color": "green"},
    "robot":      {"category": "nature", "display": "robot",     "color": "gray"},
    "asteroid":   {"category": "nature", "display": "asteroid",  "color": "gray"},
    "satellite":  {"category": "nature", "display": "satellite", "color": "gray"},
    "laser":      {"category": "nature", "display": "laser",     "color": "red"},
    "spaceship":  {"category": "nature", "display": "spaceship", "color": "gray"},
    "meteor":     {"category": "nature", "display": "meteor",    "color": "red"},
    "ufo":        {"category": "nature", "display": "ufo",       "color": "green"},
    "comet":      {"category": "nature", "display": "comet",     "color": "blue"},

    # ── Weather/Elements (~8) ─────────────────────────────────────────
    "lightning":  {"category": "nature", "display": "lightning", "color": "gold"},
    "ice":        {"category": "nature", "display": "ice",       "color": "blue"},
    "cloud":      {"category": "nature", "display": "cloud",     "color": "white"},
    "rain":       {"category": "nature", "display": "rain",      "color": "blue"},
    "wind":       {"category": "nature", "display": "wind",      "color": "default"},
    "storm":      {"category": "nature", "display": "storm",     "color": "gray"},
    "lava":       {"category": "nature", "display": "lava",      "color": "red"},
    "thunder":    {"category": "nature", "display": "thunder",   "color": "gold"},

    # ── Buildings (~10) ───────────────────────────────────────────────
    "temple":     {"category": "board", "display": "temple",     "color": "gold"},
    "church":     {"category": "board", "display": "church",     "color": "white"},
    "pyramid":    {"category": "board", "display": "pyramid",    "color": "gold"},
    "lighthouse": {"category": "board", "display": "lighthouse", "color": "white"},
    "barn":       {"category": "board", "display": "barn",       "color": "red"},
    "factory":    {"category": "board", "display": "factory",    "color": "gray"},
    "mine":       {"category": "board", "display": "mine",       "color": "brown"},
    "well":       {"category": "board", "display": "well",       "color": "gray"},
    "windmill":   {"category": "board", "display": "windmill",   "color": "default"},
    "tent":       {"category": "board", "display": "tent",       "color": "brown"},

    # ── Tools (~12) ───────────────────────────────────────────────────
    "hammer":     {"category": "resource", "display": "hammer",  "color": "brown"},
    "axe":        {"category": "resource", "display": "axe",     "color": "gray"},
    "pickaxe":    {"category": "resource", "display": "pickaxe", "color": "gray"},
    "shovel":     {"category": "resource", "display": "shovel",  "color": "brown"},
    "rope":       {"category": "resource", "display": "rope",    "color": "brown"},
    "ladder":     {"category": "resource", "display": "ladder",  "color": "brown"},
    "bell":       {"category": "resource", "display": "bell",    "color": "gold"},
    "book":       {"category": "resource", "display": "book",    "color": "brown"},
    "candle":     {"category": "resource", "display": "candle",  "color": "gold"},
    "lantern":    {"category": "resource", "display": "lantern", "color": "gold"},
    "compass":    {"category": "resource", "display": "compass", "color": "default"},
    "map":        {"category": "resource", "display": "map",     "color": "brown"},

    # ── Card-related (~10) ─────────────────────────────────────────────
    "card":  {"category": "card", "display": "card", "color": "default"},
    "hand":  {"category": "card", "display": "card", "color": "default"},
    "deck":  {"category": "card", "display": "card", "color": "default"},
    "pile":  {"category": "card", "display": "card", "color": "default"},
    "suit":  {"category": "card", "display": "card", "color": "default"},
    "rank":  {"category": "card", "display": "card", "color": "default"},
    "ace":   {"category": "card", "display": "card", "color": "default"},
    "jack":  {"category": "card", "display": "card", "color": "default"},
    "joker": {"category": "card", "display": "card", "color": "default"},
}

# ---------------------------------------------------------------------------
# Plural / synonym aliases  (all point back to a canonical entry)
# ---------------------------------------------------------------------------

_PLURAL_RULES: dict[str, str] = {}


def _add_alias(alias: str, canonical: str) -> None:
    """Register *alias* as pointing to the same entry as *canonical*."""
    if canonical in GAME_OBJECTS:
        _PLURAL_RULES[alias] = canonical


# --- regular plurals (just append "s") ---
_REGULAR_PLURALS = [
    "stone", "disc", "disk", "chip", "marker", "peg", "bead", "token",
    "counter", "checker", "piece", "meeple", "pawn", "rook", "knight",
    "bishop", "domino", "tile", "marble", "ball", "block", "cube",
    "pin", "cap", "figurine", "miniature", "standee", "chit", "stick",
    "rod", "spinner", "wheel",
    "cross", "circle", "square", "triangle", "star", "diamond", "heart",
    "dot", "ring", "orb", "gem", "crystal", "coin", "medal",
    "soldier", "warrior", "archer", "ship", "cannon", "tank", "flag",
    "shield", "sword", "spear", "general",
    "tree", "mountain", "rock", "flower", "seed", "leaf", "dragon",
    "animal", "bird", "snake",
    "wizard", "farmer", "merchant", "pirate", "ninja", "ghost",
    "skeleton", "goblin", "troll", "guard", "scout",
    "scroll", "crown", "potion", "key", "chest",
    "wall", "bridge", "path", "door", "gate", "tower", "castle",
    "house", "village", "card", "deck", "pile",
    # Animals
    "horse", "wolf", "bear", "cat", "dog", "rabbit", "lion", "tiger",
    "elephant", "eagle", "fox", "owl", "shark", "dolphin", "frog",
    "monkey", "penguin", "bee", "ant", "spider", "crab", "whale", "turtle",
    # Fantasy/RPG
    "elf", "dwarf", "orc", "mage", "cleric", "paladin", "ranger",
    "barbarian", "demon", "angel", "unicorn", "ogre", "vampire",
    "werewolf", "golem", "imp",
    # Vehicles
    "car", "truck", "plane", "helicopter", "boat", "submarine",
    "rocket", "train", "bicycle", "motorcycle",
    # Sports/Toys
    "goal", "net", "hoop", "bat", "racket", "arrow", "target",
    # Food
    "apple", "bread", "cake", "pie", "cookie", "mushroom", "carrot",
    # Space/Sci-fi
    "planet", "alien", "robot", "asteroid", "satellite", "laser",
    "spaceship", "meteor", "comet",
    # Weather/Elements
    "cloud", "storm",
    # Buildings
    "temple", "church", "pyramid", "lighthouse", "barn", "tent",
    # Tools
    "hammer", "axe", "pickaxe", "shovel", "rope", "ladder", "bell",
    "book", "candle", "lantern", "compass",
]
for _w in _REGULAR_PLURALS:
    _add_alias(_w + "s", _w)

# --- irregular plurals ---
_add_alias("men", "man")
_add_alias("queens", "queen")
_add_alias("kings", "king")
_add_alias("dice", "die")       # also a direct entry
_add_alias("armies", "army")
_add_alias("fortresses", "fortress")
_add_alias("fishes", "fish")
_add_alias("trophies", "trophy")
_add_alias("leaves", "leaf")
_add_alias("wools", "wool")
_add_alias("heroes", "hero")
_add_alias("villains", "villain")
_add_alias("villains", "villain")
_add_alias("thieves", "thief")
_add_alias("cities", "city")
_add_alias("aces", "ace")
_add_alias("jacks", "jack")
_add_alias("jokers", "joker")
_add_alias("hands", "hand")
_add_alias("suits", "suit")
_add_alias("ranks", "rank")
_add_alias("bricks", "brick")
_add_alias("minis", "mini")

# Irregular plurals for new entries
_add_alias("wolves", "wolf")
# "deer" is both singular and plural — already a canonical entry
_add_alias("mice", "mouse")
_add_alias("monkeys", "monkey")
_add_alias("foxes", "fox")
_add_alias("elves", "elf")
_add_alias("dwarves", "dwarf")
_add_alias("phoenixes", "phoenix")
_add_alias("fairies", "fairy")
_add_alias("berries", "berry")
_add_alias("candies", "candy")
_add_alias("factories", "factory")
_add_alias("mines", "mine")
_add_alias("wells", "well")
_add_alias("windmills", "windmill")
_add_alias("axes", "axe")
_add_alias("pickaxes", "pickaxe")
_add_alias("books", "book")
_add_alias("maps", "map")
_add_alias("ufos", "ufo")
_add_alias("pies", "pie")
_add_alias("corns", "corn")

# --- common synonyms ---
_add_alias("stones", "stone")
_add_alias("x", "cross")        # tic-tac-toe X
_add_alias("o", "circle")       # tic-tac-toe O
_add_alias("nought", "circle")
_add_alias("noughts", "circle")
# "boat" and "horse" are now canonical entries (vehicle/nature).
# Keep "boats" and "horses" as regular plurals (added below).
_add_alias("fort", "fortress")
_add_alias("forts", "fortress")
_add_alias("troop", "soldier")
_add_alias("troops", "soldier")
_add_alias("infantry", "soldier")
_add_alias("unit", "soldier")
_add_alias("units", "soldier")
_add_alias("gem", "gem")
_add_alias("gems", "gem")
_add_alias("jewel", "gem")
_add_alias("jewels", "gem")
_add_alias("currency", "money")
_add_alias("cash", "money")
_add_alias("lumber", "wood")
_add_alias("timber", "wood")
_add_alias("grain", "wheat")
_add_alias("grains", "wheat")
_add_alias("crops", "wheat")
_add_alias("resource", "gold")   # generic fallback
_add_alias("resources", "gold")
_add_alias("loot", "treasure")
_add_alias("hoard", "treasure")
_add_alias("flask", "potion")
_add_alias("flasks", "potion")
_add_alias("elixir", "potion")
_add_alias("dagger", "sword")
_add_alias("daggers", "sword")
_add_alias("blade", "sword")
_add_alias("blades", "sword")
_add_alias("lance", "spear")
_add_alias("lances", "spear")
_add_alias("pike", "spear")
_add_alias("pikes", "spear")
_add_alias("keep", "castle")
_add_alias("citadel", "castle")
_add_alias("town", "village")
_add_alias("towns", "village")
_add_alias("settlement", "village")
_add_alias("settlements", "village")
_add_alias("hut", "house")
_add_alias("huts", "house")
_add_alias("cabin", "house")
_add_alias("cabins", "house")

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

# Compile a single merged lookup: canonical entries + aliases
_LOOKUP: dict[str, dict] = {}
_LOOKUP.update(GAME_OBJECTS)
for _alias, _canon in _PLURAL_RULES.items():
    if _alias not in _LOOKUP and _canon in GAME_OBJECTS:
        _LOOKUP[_alias] = {**GAME_OBJECTS[_canon], "_canonical": _canon}


def recognize_object(word: str) -> Optional[dict]:
    """Look up a single word and return its object info, or None.

    Case-insensitive.  Returns a *copy* so callers can mutate safely.
    The returned dict always includes a ``"word"`` key with the canonical
    form of the matched term.
    """
    key = word.strip().lower()
    entry = _LOOKUP.get(key)
    if entry is None:
        return None
    result = dict(entry)
    result["word"] = result.pop("_canonical", key)
    return result


# Pre-compiled pattern: match any known word at a word boundary.
# Sorted longest-first so "checker" matches before "check".
_ALL_KEYS = sorted(_LOOKUP.keys(), key=len, reverse=True)
_WORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _ALL_KEYS) + r")\b",
    re.IGNORECASE,
)


def extract_objects(text: str) -> list[dict]:
    """Scan *text* and return all recognized game objects.

    Each match is a dict with ``word``, ``category``, ``display``, ``color``,
    and ``position`` (character offset in *text*).  Matches are returned in
    order of appearance; duplicates are included.
    """
    results: list[dict] = []
    for m in _WORD_PATTERN.finditer(text):
        info = recognize_object(m.group(0))
        if info is not None:
            info["position"] = m.start()
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# Convenience: category summary
# ---------------------------------------------------------------------------

def category_summary() -> dict[str, int]:
    """Return a count of canonical entries per category."""
    counts: dict[str, int] = {}
    for entry in GAME_OBJECTS.values():
        cat = entry["category"]
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Self-test / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("ThinAI Game Object Vocabulary  --  self-test")
    print("=" * 60)

    # --- 1. recognize_object tests ---
    test_words = [
        "stone", "Pawn", "QUEEN", "knights", "soldiers",
        "trees", "coin", "castle", "card", "nonexistent",
        "horse", "fort", "troops", "blade", "grain",
    ]
    print("\n--- recognize_object tests ---")
    for w in test_words:
        result = recognize_object(w)
        if result:
            print(f"  {w:15s} -> {result['word']:10s}  "
                  f"cat={result['category']:10s}  "
                  f"display={result['display']}")
        else:
            print(f"  {w:15s} -> (not found)")

    # --- 2. extract_objects on sample descriptions ---
    samples = [
        "Each player starts with 5 stones and 2 pawns on the board.",
        "Place a knight, a bishop, and the queen on the back rank.",
        "The thief steals gold coins from the merchant's chest.",
        "Build a castle with walls and a tower to protect your king.",
        "Draw a card from the deck. If it is a star, gain a gem.",
        "Soldiers march across the bridge toward the enemy fortress.",
    ]
    print("\n--- extract_objects tests ---")
    for desc in samples:
        objs = extract_objects(desc)
        names = [o["word"] for o in objs]
        print(f"\n  \"{desc}\"")
        print(f"    found {len(objs)}: {names}")

    # --- 3. Stats ---
    cats = category_summary()
    total_canonical = len(GAME_OBJECTS)
    total_with_aliases = len(_LOOKUP)
    print("\n--- vocabulary stats ---")
    print(f"  Canonical entries : {total_canonical}")
    print(f"  Including aliases : {total_with_aliases}")
    print(f"  Categories        : {len(cats)}")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:12s} : {n}")
    print()
