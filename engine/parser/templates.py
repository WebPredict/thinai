"""Pattern templates for constrained English parsing.

Each template matches a pattern in the English text and produces
the corresponding GDL fragment.
"""

from __future__ import annotations
import re
from typing import Optional


def parse_game_name(content: str) -> str:
    """Extract game name from GAME section."""
    return content.strip().split("\n")[0].strip()


def parse_players(content: str) -> dict:
    """Parse PLAYERS section → meta fields."""
    content = content.strip().lower()
    # "2, alternating turns"
    # "2, alternating turns (with extra turn rule)"
    # "2, alternating turns (player may pass if no legal move)"
    match = re.match(r"(\d+)", content)
    players = int(match.group(1)) if match else 2

    turn_order = "alternating"
    if "pass" in content or "no legal move" in content:
        turn_order = "conditional"
    elif "extra turn" in content:
        turn_order = "conditional"

    return {"players": players, "turn_order": turn_order}


def parse_board(content: str) -> dict:
    """Parse BOARD section → board spec."""
    content = content.strip()
    first_line = content.split("\n")[0].lower()

    # "{N}x{M} grid"
    grid_match = re.search(r"(\d+)\s*x\s*(\d+)\s*grid", first_line)
    if grid_match:
        rows, cols = int(grid_match.group(1)), int(grid_match.group(2))
        # Check for explicit "rows" / "columns" clarification
        detail_match = re.search(r"(\d+)\s*rows?,\s*(\d+)\s*col", content.lower())
        if detail_match:
            rows, cols = int(detail_match.group(1)), int(detail_match.group(2))
        return {
            "type": "grid",
            "grid": {"rows": rows, "cols": cols, "topology": "rect8"},
        }

    # "{N}-space track"
    track_match = re.search(r"(\d+)[- ]space\s*track", first_line)
    if track_match:
        length = int(track_match.group(1))
        loop = "loop" in content.lower() or "circular" in content.lower()
        board = {
            "type": "track",
            "track": {"length": length, "loop": loop},
        }
        # Parse regions from remaining lines
        regions = _parse_regions(content)
        if regions:
            board["regions"] = regions
        return board

    raise ValueError(f"Cannot parse board description: {content}")


def _parse_regions(content: str) -> list[dict]:
    """Parse region definitions from board content."""
    regions = []
    for line in content.split("\n")[1:]:
        line = line.strip()
        if not line:
            continue
        # "Spaces 0-5 are player 1's pits."
        match = re.match(
            r"spaces?\s+(\d+)(?:-(\d+))?\s+(?:is|are)\s+player\s+(\d+)'s\s+(\w+)",
            line, re.IGNORECASE
        )
        if match:
            start = int(match.group(1))
            end = int(match.group(2)) if match.group(2) else start
            player_num = match.group(3)
            name = match.group(4).lower()
            region_name = f"{name}_p{player_num}"
            if start == end:
                spaces = f"index == {start}"
            else:
                spaces = f"index >= {start} and index <= {end}"
            regions.append({
                "name": region_name,
                "spaces": spaces,
                "owner": f"player{player_num}",
            })
    return regions


def parse_pieces(content: str) -> list[dict]:
    """Parse PIECES section → piece definitions."""
    content = content.strip().lower()
    pieces = []

    # "each player has a mark (X or O)"
    each_match = re.search(r"each player has (?:a |an )?(\w+)", content)
    if each_match:
        name = each_match.group(1)
        display = name
        # Look for display hint in parens
        paren_match = re.search(r"\(([^)]+)\)", content)
        if paren_match:
            display = paren_match.group(1)
        pieces.append({
            "name": name,
            "owner": "each",
            "display": display,
        })
        # Check for properties
        if "flippable" in content:
            pieces[-1]["properties"] = {
                "flippable": {"type": "bool", "default": True}
            }
        return pieces

    # "stones (no owner)" / "stones (shared)"
    unowned_match = re.search(r"(\w+)s?\s*\((?:no owner|shared|unowned)\)", content)
    if unowned_match:
        pieces.append({
            "name": unowned_match.group(1),
            "owner": "none",
            "display": unowned_match.group(1),
        })
        return pieces

    # "each player has discs"
    discs_match = re.search(r"each player has (\w+)", content)
    if discs_match:
        pieces.append({
            "name": discs_match.group(1).rstrip("s"),
            "owner": "each",
            "display": discs_match.group(1),
        })
        return pieces

    return pieces


def parse_setup(content: str, board_spec: dict) -> list[dict]:
    """Parse SETUP section → setup actions."""
    content = content.strip().lower()
    actions = []

    if "empty" in content and ("board" in content or "starts" in content):
        return []  # "board starts empty"

    # "Place 4 stones in each pit (not in stores)."
    fill_match = re.search(r"place\s+(\d+)\s+(\w+)s?\s+in\s+each\s+(\w+)", content)
    if fill_match:
        count = int(fill_match.group(1))
        piece = fill_match.group(2)
        region_type = fill_match.group(3)
        # Find matching regions in board spec
        for region in board_spec.get("regions", []):
            if region_type in region["name"]:
                actions.append({
                    "action": "fill",
                    "piece": piece,
                    "at": region["spaces"],
                    "count": count,
                })
        return actions

    # "Place player 1's disc at (3,3) and (4,4)."
    for line in content.split("\n"):
        place_match = re.findall(
            r"place\s+player\s+(\d+)'s\s+(\w+)\s+at\s+([\d\s,()and]+)",
            line, re.IGNORECASE
        )
        for match in place_match:
            player = f"player{match[0]}"
            piece_name = match[1]
            coords_str = match[2]
            # Extract coordinate pairs
            coord_pairs = re.findall(r"\((\d+)\s*,\s*(\d+)\)", coords_str)
            for r, c in coord_pairs:
                actions.append({
                    "action": "place",
                    "piece": f"{piece_name}({player})",
                    "at": f"space_at({r}, {c})",
                })

    return actions


def parse_moves(content: str, board_spec: dict, pieces: list) -> list[dict]:
    """Parse MOVES section → rule definitions."""
    content_lower = content.strip().lower()
    rules = []

    # Detect gravity (connect four pattern)
    has_gravity = "drop" in content_lower or "lowest" in content_lower or "falls" in content_lower
    has_column = "column" in content_lower

    if has_column and has_gravity:
        # Connect Four style: choose column, disc drops
        cols = board_spec.get("grid", {}).get("cols", 7)
        piece_name = pieces[0]["name"] if pieces else "disc"
        rules.append({
            "name": f"drop_{piece_name}",
            "action": "place",
            "params": [{"name": "column", "select": f"int_range(0, {cols - 1})"}],
            "conditions": ["piece_at(space_at(0, column)) == empty"],
            "effects": [
                f"set _target = space_at(lowest_empty_row(column), column)",
                f"place {piece_name}(current_player) at _target",
            ],
        })
        return rules

    # Detect simple placement (tic-tac-toe pattern)
    if "place" in content_lower and "empty" in content_lower:
        piece_name = pieces[0]["name"] if pieces else "mark"
        rules.append({
            "name": f"place_{piece_name}",
            "action": "place",
            "params": [{"name": "target", "select": "empty_space"}],
            "conditions": ["piece_at(target) == empty"],
            "effects": [f"place {piece_name}(current_player) at target"],
        })
        return rules

    # Detect flank-based placement (Reversi pattern)
    if "flank" in content_lower:
        piece_name = pieces[0]["name"] if pieces else "disc"
        rules.append({
            "name": f"place_{piece_name}",
            "action": "place",
            "params": [{"name": "target", "select": "empty_space"}],
            "conditions": [
                "piece_at(target) == empty",
                "any d in directions: flanks(target, d, current_player)",
            ],
            "effects": [
                f"place {piece_name}(current_player) at target",
                f"for d in directions[flanks(target, d, current_player)]: flip_line(target, d, current_player)",
            ],
        })
        return rules

    return rules


def parse_win(content: str, board_spec: dict) -> list[dict]:
    """Parse WIN section → end conditions."""
    content_lower = content.strip().lower()
    conditions = []

    # "N in a row" pattern
    row_match = re.search(r"(\d+)\s+(?:of their \w+ )?in a (?:row|line)", content_lower)
    if row_match:
        n = int(row_match.group(1))
        # Determine what variable references the last move
        target_var = "_target" if "drop" in content_lower or "column" in content_lower else "last_placed"
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": f"any d in directions: line_length({target_var}, d, current_player) >= {n}",
        })

    # "more discs/stones wins" pattern
    if "more" in content_lower and "win" in content_lower:
        piece_match = re.search(r"more\s+(\w+)", content_lower)
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "has_legal_move(player1) == false and has_legal_move(player2) == false",
            "score": "count(pieces[owner == current_player])",
        })

    # "neither player can move" pattern
    if "neither" in content_lower and ("move" in content_lower or "play" in content_lower):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "has_legal_move(player1) == false and has_legal_move(player2) == false",
            "score": "count(pieces[owner == current_player])",
        })

    return conditions


def parse_draw(content: str) -> list[dict]:
    """Parse DRAW section → draw end conditions."""
    content_lower = content.strip().lower()
    conditions = []

    # "board is full" / "no winner"
    if "full" in content_lower:
        conditions.append({
            "type": "draw",
            "condition": "count(spaces[piece_at(s) == empty]) == 0",
        })

    # "equal discs/stones"
    if "equal" in content_lower:
        conditions.append({
            "type": "draw",
            "condition": "has_legal_move(player1) == false and has_legal_move(player2) == false and count(pieces[owner == player1]) == count(pieces[owner == player2])",
        })

    return conditions


def parse_special(content: str, meta: dict) -> dict:
    """Parse SPECIAL section → extra rules and turn modifications."""
    content_lower = content.strip().lower()
    result = {}

    # "flipped" / "flip" → already handled in MOVES for Reversi
    # "another turn" / "extra turn"
    if "another turn" in content_lower or "extra turn" in content_lower:
        meta["turn_order"] = "conditional"

    # "pass" / "no legal move"
    if "pass" in content_lower or "no legal move" in content_lower:
        meta["turn_order"] = "conditional"
        result["turn_rule"] = "if has_legal_move(next_player): next_player else: same_player"

    return result
