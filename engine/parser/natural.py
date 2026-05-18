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
    is_card = board.get("type") == "card_zones"
    pieces = _extract_pieces(text_lower, board)
    rules = _extract_rules(text_lower, board, pieces)
    end_conditions = _extract_end_conditions(text_lower, board, rules)
    setup = _extract_setup(text_lower, board, pieces)
    turn_order = _extract_turn_order(text_lower)
    state_vars = _extract_state_vars(text_lower, board)

    # Infer game name from first few words or board type
    name = _infer_name(text, board)

    # Track what we understood vs didn't
    understood = []
    not_understood = []

    if players != 2 or 'player' in text_lower:
        understood.append(f"{players} players")
    else:
        understood.append("2 players (assumed)")

    if board.get("type") == "card_zones":
        zone_names = [z["name"] for z in board.get("zones", [])]
        understood.append(f"card game with zones: {', '.join(zone_names)}")
    elif board.get("type") == "grid" and any(w in text_lower for w in ['grid', 'board', 'x']):
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
        'rent': 'rent/payment',
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
    }

    # Add card-specific fields
    if is_card:
        deck_zone = "pond" if any(z["name"] == "pond" for z in board.get("zones", [])) else "deck"
        gdl["cards"] = {"deck": "standard52", "deck_zone": deck_zone}

    gdl["_parse_info"] = {
        "understood": understood,
        "not_understood": not_understood,
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


def _is_card_game(text: str) -> bool:
    """Detect if the description is about a card game."""
    card_signals = ['card', 'cards', 'deal', 'hand', 'deck', 'suit', 'rank',
                    'hearts', 'spades', 'clubs', 'diamonds', 'draw pile',
                    'discard', 'shuffle', 'ace', 'king', 'queen', 'jack']
    count = sum(1 for s in card_signals if s in text)
    return count >= 2  # need at least 2 card-related words


def _extract_board(text: str) -> dict:
    """Extract board structure from text."""
    # Card game detection — check before grid/track
    if _is_card_game(text):
        return _extract_card_board(text)

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


def _extract_card_board(text: str) -> dict:
    """Extract card zone board structure from a card game description."""
    zones = [
        {"name": "deck", "visible_to": "none", "ordered": True},
        {"name": "hand_p1", "owner": "player1", "visible_to": "owner", "ordered": False},
        {"name": "hand_p2", "owner": "player2", "visible_to": "owner", "ordered": False},
    ]

    # Detect discard pile
    if any(w in text for w in ['discard', 'play a card', 'play card', 'match', 'pile']):
        zones.append({"name": "discard", "visible_to": "all", "ordered": True})

    # Detect draw pile / pond
    if any(w in text for w in ['draw pile', 'pond', 'go fish', 'draw from']):
        # Rename deck to pond for fishing games
        zones[0]["name"] = "pond"

    # Detect set/score zones (for collecting games like Go Fish)
    if any(w in text for w in ['set', 'sets', 'collect', 'book', 'books', 'group']):
        zones.append({"name": "sets_p1", "owner": "player1", "visible_to": "all"})
        zones.append({"name": "sets_p2", "owner": "player2", "visible_to": "all"})

    # Detect table/play area
    if any(w in text for w in ['table', 'flip', 'face up', 'face-up']):
        zones.append({"name": "table", "visible_to": "all"})

    return {
        "type": "card_zones",
        "zones": zones,
    }


def _extract_pieces(text: str, board: dict) -> list[dict]:
    """Extract piece definitions."""
    # Card games don't use pieces — cards are in zones
    if board.get("type") == "card_zones":
        return []

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

    # Card game rules
    if board.get("type") == "card_zones":
        return _extract_card_rules(text, board)

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

    # Card game end conditions
    if board.get("type") == "card_zones":
        return _extract_card_end_conditions(text, board)

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

    # Card game setup
    if board.get("type") == "card_zones":
        deck_zone = "pond" if any(z["name"] == "pond" for z in board.get("zones", [])) else "deck"

        # Shuffle deck
        setup.append({"action": "shuffle", "zone": deck_zone})

        # Deal cards — look for "deal N cards"
        deal_match = re.search(r'deal\w*\s+(\d+)\s+cards?', text)
        if not deal_match:
            deal_match = re.search(r'(\d+)\s+cards?\s+(?:each|per|to each)', text)
        if not deal_match:
            # Common defaults
            if 'go fish' in text:
                deal_count = 7
            elif 'crazy eight' in text or 'uno' in text:
                deal_count = 7
            else:
                deal_count = 5  # reasonable default
        else:
            deal_count = int(deal_match.group(1))

        setup.append({"action": "deal", "from": deck_zone, "to": "hand_p1", "count": deal_count})
        setup.append({"action": "deal", "from": deck_zone, "to": "hand_p2", "count": deal_count})

        # If there's a discard pile, flip one card to start it
        has_discard = any(z["name"] == "discard" for z in board.get("zones", []))
        if has_discard and any(w in text for w in ['flip', 'turn over', 'face up', 'start', 'discard']):
            setup.append({"action": "reveal", "from": deck_zone, "to": "discard", "count": 1})

        return setup

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
    if 'flank' in text_lower or ('flip' in text_lower and 'card' not in text_lower):
        return "Custom Reversi"

    # Card game names
    if _is_card_game(text_lower):
        if 'go fish' in text_lower:
            return "Custom Go Fish"
        if 'crazy eight' in text_lower:
            return "Custom Crazy Eights"
        if 'war' in text_lower:
            return "Custom War"
        if 'ask' in text_lower and ('rank' in text_lower or 'card' in text_lower):
            return "Custom Fishing Game"
        if 'set' in text_lower or 'collect' in text_lower:
            return "Custom Collection Game"
        if 'match' in text_lower and ('suit' in text_lower or 'rank' in text_lower):
            return "Custom Card Match"
        if 'wild' in text_lower or 'eight' in text_lower:
            return "Custom Crazy Eights"
        return "Custom Card Game"

    return "Custom Game"


def _extract_card_end_conditions(text: str, board: dict) -> list[dict]:
    """Extract end conditions for card games."""
    conditions = []

    # "empty hand wins" / "first to play all cards"
    if any(w in text for w in ['empty hand', 'no cards left', 'all cards', 'first to play all',
                                'gets rid of all']):
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": "crazy_eights_hand_empty(current_player)",
        })

    # "most sets wins" / "most books"
    if any(w in text for w in ['most sets', 'most books', 'most groups', 'most collected']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "go_fish_game_over()",
            "score": "count_sets(current_player)",
        })

    # Go Fish style: all sets complete or can't continue
    if 'go fish' in text or ('set' in text and 'collect' in text):
        if not conditions:
            conditions.append({
                "type": "win",
                "player": "player_by_score",
                "condition": "go_fish_game_over()",
                "score": "count_sets(current_player)",
            })

    # War style: opponent has no cards
    if any(w in text for w in ['all cards', 'all 52', 'no cards']):
        if 'war' in text or 'flip' in text or 'higher' in text:
            conditions.append({
                "type": "win", "player": "player1",
                "condition": 'zone_empty("hand_p2")',
            })
            conditions.append({
                "type": "win", "player": "player2",
                "condition": 'zone_empty("hand_p1")',
            })

    # Score/points based: "most points wins" / "more points wins"
    if any(w in text for w in ['more points', 'most points', 'scores a point',
                                'higher rank wins']):
        conditions = [{
            "type": "win",
            "player": "player_by_score",
            "condition": "compare_game_over()",
            "score": "compare_score(current_player)",
        }]
        return conditions

    # Fallback: deck runs out, fewer cards wins
    if not conditions:
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "crazy_eights_deck_empty()",
            "score": "crazy_eights_score(current_player)",
        })

    return conditions


def _extract_card_rules(text: str, board: dict) -> list[dict]:
    """Extract rules for a card game from natural language."""
    rules = []

    # Go Fish style: ask for a rank
    if any(w in text for w in ['ask', 'do you have', 'go fish', 'request']):
        rules.append({
            "name": "ask_for_rank",
            "action": "ask",
            "params": [{"name": "rank", "select": "card_rank"}],
            "conditions": ["has_rank_in_hand(current_player, rank)"],
            "effects": ["go_fish_ask(rank)"],
        })
        return rules

    # Crazy Eights / Uno style: match suit or rank
    if any(w in text for w in ['match', 'same suit', 'same rank', 'play a card',
                                'matching', 'crazy eight', 'uno']):
        rules.append({
            "name": "play_card",
            "action": "play",
            "params": [{"name": "card_id", "select": "crazy_eights_playable"}],
            "conditions": [],
            "effects": ["crazy_eights_play(card_id)"],
        })
        rules.append({
            "name": "draw_card",
            "action": "draw",
            "params": [],
            "conditions": ["crazy_eights_must_draw()"],
            "effects": ["crazy_eights_draw()"],
        })
        return rules

    # War style: both flip cards
    if any(w in text for w in ['flip', 'war', 'compare cards']):
        rules.append({
            "name": "battle",
            "action": "chance",
            "chance": True,
            "params": [],
            "conditions": [],
            "effects": ["war_battle()"],
        })
        return rules

    # Compare/score style: play a card, higher rank wins, score points
    if any(w in text for w in ['higher rank', 'higher card', 'wins the round',
                                'scores a point', 'play one card', 'playing one card']):
        # Add a table/trick zone if not present
        zones = board.get("zones", [])
        zone_names = [z["name"] for z in zones]
        if "trick" not in zone_names:
            zones.append({"name": "trick", "visible_to": "all", "ordered": True})
        if "taken_p1" not in zone_names:
            zones.append({"name": "taken_p1", "owner": "player1", "visible_to": "all", "ordered": False})
        if "taken_p2" not in zone_names:
            zones.append({"name": "taken_p2", "owner": "player2", "visible_to": "all", "ordered": False})
        board["zones"] = zones

        rules.append({
            "name": "play_card",
            "action": "play",
            "params": [{"name": "card_id", "select": "gin_rummy_hand"}],
            "conditions": [],
            "effects": ["compare_play(card_id)"],
        })
        return rules

    # Generic: draw a card (fallback for unrecognized card games)
    rules.append({
        "name": "draw_card",
        "action": "draw",
        "params": [],
        "conditions": [],
        "effects": ["card_move(deck, hand_p1, 1)"],
    })
    return rules


def _extract_state_vars(text: str, board: dict) -> list[dict]:
    """Extract state variables needed for the game."""
    state_vars = []

    if board.get("type") == "card_zones":
        # Go Fish needs extra_turn tracking
        if any(w in text for w in ['ask', 'go fish', 'extra turn', 'another turn']):
            state_vars.extend([
                {"name": "last_ask_rank", "type": "string", "scope": "global", "initial": ""},
                {"name": "last_ask_player", "type": "string", "scope": "global", "initial": ""},
                {"name": "last_result", "type": "string", "scope": "global", "initial": ""},
                {"name": "extra_turn", "type": "bool", "scope": "global", "initial": False},
            ])

        # Crazy Eights needs active suit tracking
        if any(w in text for w in ['match', 'wild', 'crazy eight', 'suit']):
            state_vars.extend([
                {"name": "active_suit", "type": "string", "scope": "global", "initial": ""},
                {"name": "last_play", "type": "string", "scope": "global", "initial": ""},
                {"name": "last_action", "type": "string", "scope": "global", "initial": ""},
            ])

        # Compare/score games need score and play tracking
        if any(w in text for w in ['higher rank', 'higher card', 'scores a point',
                                    'play one card', 'playing one card']):
            state_vars.extend([
                {"name": "p1_score", "type": "int", "scope": "global", "initial": 0},
                {"name": "p2_score", "type": "int", "scope": "global", "initial": 0},
                {"name": "last_play", "type": "string", "scope": "global", "initial": ""},
                {"name": "last_action", "type": "string", "scope": "global", "initial": ""},
            ])

    return state_vars
