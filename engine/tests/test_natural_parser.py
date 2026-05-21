"""Tests for the natural language game parser.

Covers all game categories the parser should handle:
grid placement, flanking, nim, matching/shedding, collecting,
comparing, trick-taking, dice placement, tile placement, and race.
"""

from engine.parser.natural import parse_natural


# --- Grid Placement ---

def test_basic_grid_placement():
    gdl = parse_natural("Two players take turns placing stones on a 5x5 grid. Get 4 in a row to win. If the board is full, it's a draw.")
    assert gdl["board"]["type"] == "grid"
    assert gdl["board"]["grid"]["rows"] == 5
    assert gdl["board"]["grid"]["cols"] == 5
    assert len(gdl["rules"]) >= 1
    assert any("place" in r["action"] for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])
    assert any(c["type"] == "draw" for c in gdl["end_conditions"])


def test_3x3_grid():
    gdl = parse_natural("Two players place marks on a 3x3 grid. 3 in a row wins. Full board is a draw.")
    assert gdl["board"]["grid"]["rows"] == 3
    assert gdl["board"]["grid"]["cols"] == 3


def test_large_grid():
    gdl = parse_natural("Two players take turns on a 9x9 grid. First to get 5 in a row wins.")
    assert gdl["board"]["grid"]["rows"] == 9
    assert gdl["board"]["grid"]["cols"] == 9


# --- Flanking/Reversi ---

def test_flanking_surround():
    gdl = parse_natural("Two players place stones on an 8x8 grid. Surround opponent stones to flip them to your color. Most stones when the board is full wins.")
    assert gdl["board"]["type"] == "grid"
    assert any("flank" in str(r.get("conditions", "")) or "flip" in str(r.get("effects", "")) for r in gdl["rules"])


def test_flanking_reversi():
    gdl = parse_natural("Play Reversi on an 8x8 board. Place a disc to outflank opponent discs. Flanked discs flip to your color.")
    assert any("flip" in str(r.get("effects", "")) for r in gdl["rules"])


# --- Nim-like ---

def test_nim_piles():
    gdl = parse_natural("Three piles of stones (3, 5, 7). Players take turns removing any number of stones from one pile. The player who takes the last stone wins.")
    assert gdl["board"]["type"] == "track"
    assert any("remove" in r["action"] for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


# --- Card: Matching/Shedding ---

def test_matching_card_game():
    gdl = parse_natural("Two players are dealt 7 cards. Play a card matching the top card by suit or rank. If you cannot match, draw from the deck. First to empty their hand wins.")
    assert gdl["board"]["type"] == "card_zones"
    rules = [r["name"] for r in gdl["rules"]]
    assert "play_card" in rules
    assert "draw_card" in rules


def test_shedding_get_rid():
    gdl = parse_natural("Deal 5 cards each. Match the discard pile by suit or rank. Get rid of all your cards to win.")
    assert gdl["board"]["type"] == "card_zones"
    assert any(r["name"] == "play_card" for r in gdl["rules"])


# --- Card: Collecting ---

def test_collecting_ask():
    gdl = parse_natural("Two players are dealt 5 cards. Ask your opponent for a rank you hold. If they have it, they give you all cards of that rank. If not, draw from the deck. Collect sets of 4 to score. Most sets wins.")
    assert gdl["board"]["type"] == "card_zones"
    assert any(r["name"] == "ask_for_rank" for r in gdl["rules"])


def test_collecting_go_fish():
    gdl = parse_natural("Play Go Fish with 7 cards each. Ask for ranks, collect books of 4. Player with most books wins.")
    assert any(r["name"] == "ask_for_rank" for r in gdl["rules"])


# --- Card: Comparing ---

def test_comparing_higher_rank():
    gdl = parse_natural("Two players are each dealt 5 cards. Players take turns playing one card. The higher rank wins the round and scores a point. After all cards are played, the player with more points wins.")
    assert gdl["board"]["type"] == "card_zones"
    assert any(r["name"] == "play_card" for r in gdl["rules"])
    assert any("compare" in str(c.get("condition", "")) or "score" in str(c.get("score", "")) for c in gdl["end_conditions"])


def test_comparing_war():
    gdl = parse_natural("Split the deck evenly. Both players flip their top card. Higher card wins both cards. First to collect all cards wins.")
    assert any(r["name"] == "battle" for r in gdl["rules"])


# --- Card: Trick-taking ---

def test_trick_taking_follow_suit():
    gdl = parse_natural("Deal 13 cards each. Players play one card per trick. Follow the lead suit if you can. Highest card of the lead suit wins the trick. Avoid taking hearts. Fewest points wins.")
    assert gdl["board"]["type"] == "card_zones"
    assert any(r["name"] == "play_card" for r in gdl["rules"])
    zones = [z["name"] for z in gdl["board"]["zones"]]
    assert "trick" in zones
    assert any("hearts" in str(c.get("condition", "")) or "score" in str(c.get("score", "")) for c in gdl["end_conditions"])


def test_trick_taking_simple():
    gdl = parse_natural("Two players play cards in tricks. You must follow suit. The highest card wins the trick.")
    assert any(r["name"] == "play_card" for r in gdl["rules"])
    zones = [z["name"] for z in gdl["board"]["zones"]]
    assert "trick" in zones


# --- Dice Placement ---

def test_dice_placement():
    gdl = parse_natural("Two players take turns rolling a die and placing a piece on a 5x5 grid. The number rolled determines which row you must place in. First to get 3 in a row wins.")
    assert gdl["board"]["type"] == "grid"
    assert any(r.get("chance") for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


# --- Tile Placement ---

def test_l_tile_placement():
    gdl = parse_natural("Two players take turns placing L-shaped tiles on a 6x6 grid. Each tile covers exactly 3 squares in an L shape. A player wins by completely filling a row or column. If no more tiles can be placed, the player who placed more tiles wins.")
    assert gdl["board"]["type"] == "grid"
    assert gdl["board"].get("_tile_shape") == "L"
    assert gdl["board"].get("_tile_size") == 3
    assert any(r["name"] == "place_tile" for r in gdl["rules"])


def test_domino_placement():
    gdl = parse_natural("Two players place domino tiles on a 4x4 grid. Each domino covers 2 squares. Most tiles placed wins.")
    assert gdl["board"].get("_tile_shape") is not None
    assert any(r["name"] == "place_tile" for r in gdl["rules"])


# --- Edge Cases ---

def test_no_crash_on_empty():
    gdl = parse_natural("")
    assert gdl is not None


def test_no_crash_on_nonsense():
    gdl = parse_natural("The quick brown fox jumps over the lazy dog.")
    assert gdl is not None


def test_understood_tracking():
    gdl = parse_natural("Two players take turns placing stones on a 5x5 grid. 4 in a row wins. Full board is a draw.")
    info = gdl["_parse_info"]
    assert "5x5 grid" in str(info["understood"])
    assert "win condition" in str(info["understood"])


# --- Movement/Capture ---

def test_movement_basic():
    gdl = parse_natural("Two players place pieces on a 6x6 grid. Move your piece one square at a time to an adjacent empty space. Capture all opponent pieces to win.")
    assert any("move" in r["action"] for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


def test_movement_with_jump():
    gdl = parse_natural("Two players have 12 pieces each on an 8x8 grid. Move diagonally one square. Jump over opponent pieces to capture them. Capture all opponent pieces to win.")
    rules = [r["name"] for r in gdl["rules"]]
    assert any("move" in name for name in rules)
    assert any("jump" in name for name in rules)


def test_movement_slide():
    gdl = parse_natural("Slide your piece to any adjacent empty space on the 5x5 board. The player who cannot move loses.")
    assert any("move" in r["action"] for r in gdl["rules"])


# --- Sowing/Mancala ---

def test_sowing_basic():
    gdl = parse_natural("Two players have 6 pits each with 4 stones. Pick up all stones from one of your pits and distribute them one per pit clockwise. Most stones in your store wins.")
    assert any("sow" in r["action"] for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


def test_sowing_mancala():
    gdl = parse_natural("Play Mancala. Pick up seeds from a pit and sow them counter-clockwise. Landing in your store gives an extra turn. Most seeds wins.")
    assert any("sow" in r["action"] for r in gdl["rules"])


# --- Directional Movement ---

def test_movement_forward():
    gdl = parse_natural("Two players have pieces on a 6x6 board. Move your pieces forward one space per turn. First to reach the other side wins.")
    assert any("move" in r["action"] for r in gdl["rules"])
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


def test_movement_advance():
    gdl = parse_natural("6x6 grid. Players advance their tokens toward the opposite end. First to cross the board wins.")
    assert any("move" in r["action"] for r in gdl["rules"])


# --- Capture Games ---

def test_capture_jump():
    gdl = parse_natural("8x8 board. Move pieces diagonally. Jump over an opponent's piece to capture it. Capture all opponent pieces to win.")
    assert gdl["board"]["type"] == "grid"
    rules = gdl["rules"]
    assert any("jump" in r["name"] or "capture" in r["name"] for r in rules)
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


def test_capture_eliminate():
    gdl = parse_natural("6x6 grid. Players take turns moving pieces one space. If you land on an opponent piece, eliminate it. Last player with pieces wins.")
    rules = gdl["rules"]
    assert any("move" in r["action"] or "capture" in r.get("name", "") for r in rules)


# --- Multi-Die Race ---

def test_race_two_dice():
    gdl = parse_natural("Roll two dice and move that many spaces on a track of 30 spaces. First to reach the end wins.")
    assert gdl["board"]["type"] == "track"
    rules = gdl["rules"]
    # Should have a race/roll rule
    assert any("roll" in r["name"] or "race" in r.get("name", "") for r in rules)


def test_race_landing_bump():
    gdl = parse_natural("Roll a die and move forward on a 20-space track. If you land on an opponent, send them back to start. First to finish wins.")
    assert gdl["board"]["type"] == "track"
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


# --- Territory / Area Control ---

def test_territory_most_pieces():
    gdl = parse_natural("Two players place stones on a 5x5 grid. When the board is full, the player with the most stones wins.")
    assert any(c["type"] == "win" for c in gdl["end_conditions"])
    assert any("count_pieces" in str(c.get("score", "")) for c in gdl["end_conditions"])


def test_territory_control():
    gdl = parse_natural("7x7 board. Place markers. The player who controls more territory at the end wins.")
    assert any(c["type"] == "win" for c in gdl["end_conditions"])


def test_no_false_betting():
    """'between' should not trigger 'betting' detection."""
    gdl = parse_natural("Place stones on a grid. Surround opponent stones between two of yours to flip them.")
    assert "betting" not in str(gdl["_parse_info"]["not_understood"])
