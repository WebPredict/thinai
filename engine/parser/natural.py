"""Natural language parser for game descriptions.

Converts plain English game descriptions into GDL specifications
without requiring section keywords (GAME:, BOARD:, etc.).

Uses pattern matching and keyword extraction to identify:
- Board structure (grid size, track length)
- Pieces (what players place/move)
- Move rules (place, drop, take, move)
- Win conditions (N in a row, most pieces, last piece)
- Draw conditions (board full, no moves)
- Turn structure (alternating, conditional)
"""

from __future__ import annotations
import re
from typing import Optional


def parse_natural(text: str) -> dict:
    """Parse a plain English game description into GDL JSON.

    Examples:
      "Two players take turns placing stones on a 5x5 grid.
       A player wins by getting 4 in a row. If the board is
       full with no winner, it's a draw."

      "Three piles of stones (3, 5, 7). Players take turns
       removing any number of stones from one pile. The player
       who takes the last stone wins."
    """
    text_lower = text.lower()
    sentences = _split_sentences(text)

    # Extract game components
    players = _extract_players(text_lower)
    board = _extract_board(text_lower)
    pieces = _extract_pieces(text_lower, board)
    rules = _extract_rules(text_lower, board, pieces)
    end_conditions = _extract_end_conditions(text_lower, board, rules)
    setup = _extract_setup(text_lower, board, pieces)
    turn_order = _extract_turn_order(text_lower)
    state_vars = []

    # Infer game name from first few words or board type
    name = _infer_name(text, board)

    # Track what we understood vs didn't
    understood = []
    not_understood = []

    if players != 2 or 'player' in text_lower:
        understood.append(f"{players} players")
    else:
        understood.append("2 players (assumed)")

    if board.get("type") == "grid" and any(w in text_lower for w in ['grid', 'board', 'x']):
        g = board.get("grid", {})
        understood.append(f"{g.get('rows')}x{g.get('cols')} grid")
    elif board.get("type") == "track" and any(w in text_lower for w in ['pile', 'track']):
        understood.append(f"{board['track']['length']}-space track")
    else:
        not_understood.append("board structure (defaulted to 3x3 grid)")

    if rules:
        understood.append(f"move type: {rules[0]['action']}")
    else:
        not_understood.append("how players make moves")

    if end_conditions:
        types = [c['type'] for c in end_conditions]
        if 'win' in types:
            understood.append("win condition")
        if 'draw' in types:
            understood.append("draw condition")
    else:
        not_understood.append("win/draw conditions")

    # Check for unrecognized verbs/concepts
    unknown_concepts = []
    concept_keywords = {
        'buy': 'buying/purchasing', 'sell': 'selling', 'money': 'currency/money',
        'rent': 'rent/payment', 'card': 'cards (coming in Phase 5)',
        'hand': 'card hands (coming in Phase 5)', 'deal': 'dealing cards (coming in Phase 5)',
        'dice': 'dice rolling', 'bet': 'betting', 'bid': 'bidding',
        'trade': 'trading', 'build': 'building', 'upgrade': 'upgrading',
        'move from': 'moving pieces between spaces', 'capture': 'capturing pieces',
    }
    for keyword, label in concept_keywords.items():
        if keyword in text_lower and label not in str(understood):
            unknown_concepts.append(label)

    if unknown_concepts:
        not_understood.extend(unknown_concepts)

    gdl = {
        "meta": {
            "name": name,
            "players": players,
            "turn_order": turn_order,
            "version": "1.0",
        },
        "board": board,
        "pieces": pieces,
        "state_vars": state_vars,
        "setup": setup,
        "rules": rules,
        "end_conditions": end_conditions,
        "_parse_info": {
            "understood": understood,
            "not_understood": not_understood,
        },
    }

    return gdl


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Split on period, exclamation, or question mark followed by space/newline
    parts = re.split(r'[.!?]+\s*', text)
    return [s.strip() for s in parts if s.strip()]


def _extract_players(text: str) -> int:
    """Extract number of players."""
    match = re.search(r'(\d+)\s+players?', text)
    if match:
        return int(match.group(1))
    if 'two players' in text or 'two-player' in text:
        return 2
    if 'three players' in text:
        return 3
    return 2  # default


def _extract_board(text: str) -> dict:
    """Extract board structure from text."""
    # NxM grid
    grid_match = re.search(r'(\d+)\s*[x×]\s*(\d+)\s*(?:grid|board)', text)
    if grid_match:
        rows, cols = int(grid_match.group(1)), int(grid_match.group(2))
        return {
            "type": "grid",
            "grid": {"rows": rows, "cols": cols, "topology": "rect8"},
        }

    # "N rows and M columns" or "M columns and N rows"
    rc_match = re.search(r'(\d+)\s*rows?\s*(?:and|,)\s*(\d+)\s*col', text)
    if rc_match:
        return {
            "type": "grid",
            "grid": {"rows": int(rc_match.group(1)), "cols": int(rc_match.group(2)), "topology": "rect8"},
        }
    cr_match = re.search(r'(\d+)\s*col\w*\s*(?:and|,)\s*(\d+)\s*rows?', text)
    if cr_match:
        return {
            "type": "grid",
            "grid": {"rows": int(cr_match.group(2)), "cols": int(cr_match.group(1)), "topology": "rect8"},
        }

    # Piles pattern (Nim-style)
    piles_match = re.search(r'(\d+)\s+piles?\s+(?:of\s+)?(?:stones?|objects?|tokens?)', text)
    if piles_match:
        num_piles = int(piles_match.group(1))
        return {
            "type": "track",
            "track": {"length": num_piles, "loop": False},
        }

    # "piles of stones (3, 5, 7)" — extract pile count from numbers
    piles_nums = re.search(r'piles?\s*(?:of\s+\w+\s*)?\(([^)]+)\)', text)
    if piles_nums:
        nums = re.findall(r'\d+', piles_nums.group(1))
        return {
            "type": "track",
            "track": {"length": len(nums), "loop": False},
            "_pile_sizes": [int(n) for n in nums],
        }

    # "N-space track"
    track_match = re.search(r'(\d+)[- ]?space\s+track', text)
    if track_match:
        return {
            "type": "track",
            "track": {"length": int(track_match.group(1)), "loop": False},
        }

    # Default: 3x3 grid
    if 'grid' in text or 'board' in text:
        return {
            "type": "grid",
            "grid": {"rows": 3, "cols": 3, "topology": "rect8"},
        }

    # If we find nothing specific, assume a small grid
    return {
        "type": "grid",
        "grid": {"rows": 3, "cols": 3, "topology": "rect8"},
    }


def _extract_pieces(text: str, board: dict) -> list[dict]:
    """Extract piece definitions."""
    pieces = []

    # "placing stones/marks/discs/pieces"
    place_match = re.search(r'plac(?:e|ing)\s+(\w+?)s?\s+', text)
    if place_match:
        name = place_match.group(1)
        if name in ('a', 'an', 'the', 'their', 'your'):
            # Skip articles, look for the next word
            place_match2 = re.search(r'plac(?:e|ing)\s+(?:a|an|the|their)\s+(\w+?)s?\s+', text)
            if place_match2:
                name = place_match2.group(1)
            else:
                name = 'mark'
        pieces.append({
            "name": name,
            "owner": "each",
            "display": name,
        })
        return pieces

    # "stones" in pile/Nim context
    if board.get("type") == "track":
        stone_match = re.search(r'(?:piles?\s+of\s+)?(\w+?)s?\s*\(', text)
        if stone_match and stone_match.group(1) not in ('pile', 'player'):
            name = stone_match.group(1)
        else:
            name = 'stone'
        pieces.append({
            "name": name,
            "owner": "none",
            "display": name,
        })
        return pieces

    # Default: marks
    pieces.append({
        "name": "mark",
        "owner": "each",
        "display": "X/O",
    })
    return pieces


def _extract_rules(text: str, board: dict, pieces: list) -> list[dict]:
    """Extract move rules from text."""
    rules = []
    piece_name = pieces[0]["name"] if pieces else "mark"

    # Gravity/column drop (Connect Four style)
    if ('drop' in text or 'falls' in text or 'column' in text) and board.get("type") == "grid":
        cols = board.get("grid", {}).get("cols", 7)
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

    # Nim-style: take/remove from pile
    if ('take' in text or 'remov' in text) and board.get("type") == "track":
        num_piles = board.get("track", {}).get("length", 3)
        # Determine max take amount
        max_take = 0
        pile_sizes = board.get("_pile_sizes", [])
        if pile_sizes:
            max_take = max(pile_sizes)
        else:
            max_match = re.search(r'(?:up to|at most|max(?:imum)?)\s+(\d+)', text)
            if max_match:
                max_take = int(max_match.group(1))
        if max_take == 0:
            # "any number" or not specified — use a reasonable max
            max_take = max(pile_sizes) if pile_sizes else 10

        rules.append({
            "name": f"take_{piece_name}s",
            "action": "remove",
            "params": [
                {"name": "pile", "select": "space"},
                {"name": "amount", "select": f"int_range(1, {max_take})"},
            ],
            "conditions": [
                f"count(pieces_at(pile)) >= amount",
            ],
            "effects": [
                f"remove_n(pile, amount)",
            ],
        })
        return rules

    # Flanking/Reversi style
    if 'flank' in text or 'sandwich' in text or 'flip' in text:
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

    # Default: simple placement on empty space (TTT style)
    if board.get("type") == "grid":
        rules.append({
            "name": f"place_{piece_name}",
            "action": "place",
            "params": [{"name": "target", "select": "empty_space"}],
            "conditions": ["piece_at(target) == empty"],
            "effects": [f"place {piece_name}(current_player) at target"],
        })
        return rules

    return rules


def _extract_end_conditions(text: str, board: dict, rules: list) -> list[dict]:
    """Extract win/draw conditions."""
    conditions = []

    # "N in a row" / "N in a line"
    row_match = re.search(r'(\d+)\s+in\s+a\s+(?:row|line|straight)', text)
    if row_match:
        n = int(row_match.group(1))
        # Determine the target variable based on move type
        has_column = any('column' in str(r.get('params', '')) for r in rules)
        target_var = "_target" if has_column else "last_placed"
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": f"any d in directions: line_length({target_var}, d, current_player) >= {n}",
        })

    # "last stone/piece wins" (Nim-style)
    if 'last' in text and ('win' in text or 'loses' in text):
        is_misere = 'loses' in text or 'last.*loses' in text
        if board.get("type") == "track":
            conditions.append({
                "type": "win",
                "player": "current_player" if not is_misere else "opponent",
                "condition": "all s in spaces: count(pieces_at(s)) == 0",
            })

    # "most pieces/discs/stones wins"
    if 'most' in text and 'win' in text:
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "has_legal_move(player1) == false and has_legal_move(player2) == false",
            "score": "count(pieces[owner == current_player])",
        })

    # Draw: "board is full" / "all squares filled" / "no winner"
    if ('full' in text or 'filled' in text or 'no winner' in text) and 'draw' in text:
        conditions.append({
            "type": "draw",
            "condition": "count(spaces[piece_at(s) == empty]) == 0",
        })

    # If we found a "N in a row" win but no draw, add a board-full draw
    if any(c["type"] == "win" for c in conditions) and not any(c["type"] == "draw" for c in conditions):
        if board.get("type") == "grid":
            conditions.append({
                "type": "draw",
                "condition": "count(spaces[piece_at(s) == empty]) == 0",
            })

    return conditions


def _extract_setup(text: str, board: dict, pieces: list) -> list[dict]:
    """Extract initial setup."""
    setup = []

    # Nim-style: fill piles with specific counts
    pile_sizes = board.get("_pile_sizes", [])
    if pile_sizes and board.get("type") == "track":
        piece_name = pieces[0]["name"] if pieces else "stone"
        for i, count in enumerate(pile_sizes):
            setup.append({
                "action": "fill",
                "piece": piece_name,
                "at": f"index == {i}",
                "count": count,
            })

    # General: "starts empty" or no setup mentioned for grids
    # (default for grid games is empty board, no setup needed)

    return setup


def _extract_turn_order(text: str) -> str:
    """Extract turn order from text."""
    if 'pass' in text or 'skip' in text:
        return "conditional"
    if 'extra turn' in text or 'another turn' in text:
        return "conditional"
    return "alternating"


def _infer_name(text: str, board: dict) -> str:
    """Infer a game name from the description."""
    # Look for a quoted name
    quote_match = re.search(r'["\']([^"\']+)["\']', text)
    if quote_match:
        return quote_match.group(1)

    # Look for "called X" or "named X"
    called_match = re.search(r'(?:called|named)\s+(\w+(?:\s+\w+)?)', text, re.IGNORECASE)
    if called_match:
        return called_match.group(1).title()

    # Infer from game type
    text_lower = text.lower()
    if 'pile' in text_lower and ('take' in text_lower or 'remov' in text_lower):
        return "Custom Nim"
    if 'in a row' in text_lower:
        n = re.search(r'(\d+)\s+in\s+a\s+row', text_lower)
        grid = re.search(r'(\d+)\s*x\s*(\d+)', text_lower)
        if n and grid:
            return f"{n.group(1)}-in-a-Row ({grid.group(1)}x{grid.group(2)})"
        elif n:
            return f"{n.group(1)}-in-a-Row"
    if 'flank' in text_lower or 'flip' in text_lower:
        return "Custom Reversi"

    return "Custom Game"
