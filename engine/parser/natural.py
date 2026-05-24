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
    text = text.lower()
    sentences = _split_sentences(text)

    # Extract game components
    players = _extract_players(text)
    board = _extract_board(text)
    is_card = board.get("type") == "card_zones"
    pieces = _extract_pieces(text, board)
    rules = _extract_rules(text, board, pieces)
    end_conditions = _extract_end_conditions(text, board, rules)
    setup = _extract_setup(text, board, pieces)
    turn_order = _extract_turn_order(text)
    state_vars = _extract_state_vars(text, board)
    cosmetics = _extract_cosmetics(text)

    # Infer game name from first few words or board type
    name = _infer_name(text, board)

    # Track what we understood vs didn't
    understood = []
    not_understood = []

    if players != 2 or 'player' in text:
        understood.append(f"{players} players")
    else:
        understood.append("2 players (assumed)")

    if board.get("type") == "card_zones":
        zone_names = [z["name"] for z in board.get("zones", [])]
        understood.append(f"card game with zones: {', '.join(zone_names)}")
    elif board.get("type") == "grid" and any(w in text for w in ['grid', 'board', 'x']):
        g = board.get("grid", {})
        understood.append(f"{g.get('rows')}x{g.get('cols')} grid")
    elif board.get("type") == "track" and any(w in text for w in ['pile', 'track', 'race',
                                                                          'reach the end', 'move forward',
                                                                          'move along', 'first to reach']):
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
        'move from': 'moving pieces between spaces',
    }
    for keyword, label in concept_keywords.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text) and label not in str(understood):
            unknown_concepts.append(label)

    if unknown_concepts:
        not_understood.extend(unknown_concepts)

    # Choice race games need conditional turns (roll then choose)
    has_race_choice = any(r.get("name") == "move_forward" for r in rules)
    if has_race_choice:
        turn_order = "conditional"

    meta = {
        "name": name,
        "players": players,
        "turn_order": turn_order,
        "version": "1.0",
    }
    if has_race_choice:
        meta["turn_rule"] = "if race_turn_done(): next_player else: same_player"

    # Flanking/Reversi games or "pass when no moves": skip stuck player
    is_flanking = any(r.get("name", "").startswith("place") and
                      any("flip" in str(e) or "flank" in str(e) for e in r.get("effects", []))
                      for r in rules)
    has_pass_keywords = any(w in text for w in ['pass your turn', 'skip your turn',
                                                 'no legal move', 'cannot move',
                                                 "can't move", 'no valid move',
                                                 'pass if'])
    if (is_flanking or has_pass_keywords) and not has_race_choice:
        meta["turn_order"] = "conditional"
        meta["turn_rule"] = "if has_legal_move(next_player): next_player else: same_player"

    # Jump chain: movement+capture games get same-player turn on chain jumps
    has_jump_capture = any(
        any(p.get("select") == "grid_moves" for p in r.get("params", []))
        for r in rules
    ) and any(w in text for w in ['jump', 'capture', 'hop'])
    if has_jump_capture and not has_race_choice:
        meta["turn_order"] = "conditional"
        meta["turn_rule"] = "if jump_chain_active(): same_player else: next_player"

    # Extra turn / go again: result-triggered same-player turn
    has_extra_turn = any(w in text for w in ['extra turn', 'another turn', 'go again',
                                              'take another turn', 'gets another',
                                              'plays again', 'bonus turn'])
    if has_extra_turn and not has_race_choice and not is_flanking:
        meta["turn_order"] = "conditional"
        meta["turn_rule"] = "if extra_turn: same_player else: next_player"

    gdl = {
        "meta": meta,
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
        # Detect deck type from description
        deck_type = "standard52"
        if any(w in text for w in ['uno', 'skip', 'reverse', 'draw two', 'wild card']):
            deck_type = "uno"
        elif re.search(r'(?:4|four)\s+colors?', text) and re.search(r'(?:number|numb)\w*\s+(?:0|1).*(?:9|10)', text):
            deck_type = "uno"  # 4 colors with numbered cards = Uno-style
        gdl["cards"] = {"deck": deck_type, "deck_zone": deck_zone}

    if cosmetics:
        gdl["_cosmetics"] = cosmetics

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

    # Race / track detection: "first to space N", "reach space N", "first to reach the end"
    race_keywords = ['race', 'finish line', 'reach the end', 'move forward',
                     'move along', 'first to reach', 'first to the end']
    if any(w in text for w in race_keywords):
        # Try to extract track length from "space N" / "N spaces" / "space N wins"
        space_n = re.search(r'(?:space|position)\s+(\d+)', text)
        n_spaces = re.search(r'(\d+)\s+spaces?', text)
        if space_n:
            length = int(space_n.group(1))
        elif n_spaces:
            length = int(n_spaces.group(1))
        else:
            length = 20  # default race track length
        return {
            "type": "track",
            "track": {"length": length, "loop": False},
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

    # "placing stones/marks/discs/pieces" — skip color adjectives and articles
    _SKIP_WORDS = {'a', 'an', 'the', 'their', 'your', 'red', 'blue', 'green',
                   'yellow', 'orange', 'purple', 'pink', 'black', 'white',
                   'gold', 'silver', 'brown', 'dark', 'light', 'colored'}
    place_match = re.search(r'plac(?:e|ing)\s+((?:\w+\s+){0,3}\w+?)s?\s+(?:on|in|at)', text)
    if place_match:
        words = place_match.group(1).split()
        # Take the last non-skip word as the piece name
        name = 'mark'
        for w in reversed(words):
            if w.lower().rstrip('s') not in _SKIP_WORDS:
                name = w.lower().rstrip('s')
                break
        pieces.append({
            "name": name,
            "owner": "each",
            "display": name,
        })
        return pieces

    # Race / track-with-tokens context
    if board.get("type") == "track":
        race_keywords = ['race', 'finish line', 'reach the end', 'first to reach',
                         'first to the end', 'move forward', 'move along']
        is_race = (any(w in text for w in race_keywords)
                   or re.search(r'roll\b.*\bmove\b', text))
        if is_race:
            pieces.append({
                "name": "token",
                "owner": "each",
                "display": "token",
            })
            return pieces

        # Nim/pile context
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

    # Tile/L-shape/multi-cell placement (check before gravity since "column" may appear in win condition)
    if any(w in text for w in ['tile', 'l-shape', 'l shape', 'domino', 'covers', 'tetris']):
        tile_size = 3
        if 'domino' in text:
            tile_size = 2
        elif re.search(r'covers?\s+(\d+)', text):
            tile_size = int(re.search(r'covers?\s+(\d+)', text).group(1))
        shape = "L" if any(w in text for w in ['l-shape', 'l shape', 'l-shaped']) else "line"
        board["_tile_shape"] = shape
        board["_tile_size"] = tile_size
        rules.append({
            "name": "place_tile",
            "action": "place",
            "params": [{"name": "tile_id", "select": "tile_placements"}],
            "conditions": [],
            "effects": ["place_tile(tile_id)"],
        })
        return rules

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
    if any(w in text for w in ['flank', 'sandwich', 'flip', 'surround to capture',
                                'surround to flip', 'trap between', 'reversi', 'othello',
                                'outflank', 'enclose']):
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

    # Movement/Capture: move pieces from one space to another (grid games only — track games use race rules)
    if board.get("type") != "track" and any(w in text for w in ['move your piece', 'move one square', 'move a piece',
                                'slide', 'step forward', 'jump over',
                                'move diagonally', 'move orthogonally',
                                'move to an adjacent', 'moves one space',
                                'advance', 'retreat', 'move forward', 'move backward',
                                'move toward', 'move across', 'move pieces',
                                'move one space', 'move two spaces',
                                'reach the other side', 'reach the opposite']):
        # Determine movement direction
        is_diagonal = 'diagonal' in text
        is_orthogonal = 'orthogonal' in text or 'straight' in text
        is_forward = 'forward' in text or 'advance' in text or 'toward' in text

        if is_diagonal:
            move_dirs = "diagonal"
        elif is_orthogonal:
            move_dirs = "orthogonal"
        else:
            move_dirs = "all"

        # Use generic grid movement engine
        rules.append({
            "name": f"move_{piece_name}",
            "action": "move",
            "params": [{"name": "move_id", "select": "grid_moves"}],
            "conditions": [],
            "effects": ["grid_move_execute(move_id)"],
        })

        # Store movement config in board for state_vars initialization
        board["_move_directions"] = move_dirs
        board["_forward_only"] = is_forward
        board["_needs_piece_setup"] = True
        return rules

    # Sowing/Mancala: pick up and distribute tokens
    if any(w in text for w in ['sow', 'distribute', 'drop one in each',
                                'pick up stones', 'pick up all', 'mancala',
                                'drop one per', 'counter-clockwise',
                                'clockwise', 'pick up seeds']):
        num_pits = 6  # default
        pit_match = re.search(r'(\d+)\s*pits?', text)
        if pit_match:
            num_pits = int(pit_match.group(1))

        # Use track board if not already set
        if board.get("type") != "track":
            board["type"] = "track"
            board["track"] = {"length": (num_pits + 1) * 2, "loop": True}

        rules.append({
            "name": "sow",
            "action": "sow",
            "params": [{"name": "pit", "select": "current_player_pits"}],
            "conditions": ["count(pieces_at(pit)) > 0"],
            "effects": ["sow_from(pit)"],
        })
        return rules

    # Dice + placement: roll a die, place in constrained position
    if ('roll' in text or 'die' in text or 'dice' in text) and board.get("type") == "grid":
        rules.append({
            "name": "roll_and_place",
            "action": "chance",
            "chance": True,
            "params": [],
            "conditions": [],
            "effects": ["dice_place()"],
        })
        return rules

    # Race: roll dice, move piece forward on a track
    race_keywords = ['race', 'finish line', 'reach the end', 'move forward',
                     'move along', 'first to reach', 'first to the end']
    is_race = (any(w in text for w in race_keywords)
               or re.search(r'roll\b.*\bmove\b', text))
    if is_race and board.get("type") == "track":
        has_bump = any(w in text for w in ['send them back', 'send back',
                                           'back to start', 'bump',
                                           "opponent's space",
                                           "opponent space",
                                           'land on an opponent',
                                           'land on opponent',
                                           'landing on an opponent',
                                           'landing on opponent'])
        # Detect number of dice
        num_dice = 1
        dice_match = re.search(r'(?:roll|throw)\s+(?:two|2)\s+(?:dice|die)', text)
        if dice_match:
            num_dice = 2
        dice_match3 = re.search(r'(?:roll|throw)\s+(?:three|3)\s+(?:dice|die)', text)
        if dice_match3:
            num_dice = 3
        max_roll = 6 * num_dice
        has_choice = any(w in text for w in ['forward or backward', 'backward or forward',
                                              'choose to move', 'move forward or backward',
                                              'either direction'])

        if has_choice:
            # Two-phase: roll (chance), then choose direction (strategy)
            rules.append({
                "name": "roll_dice",
                "action": "chance",
                "chance": True,
                "params": [],
                "conditions": ["race_can_roll()"],
                "effects": ["race_roll()"],
            })
            rules.append({
                "name": "move_forward",
                "action": "move",
                "params": [],
                "conditions": ["race_can_move()"],
                "effects": ["race_move_forward()"],
            })
            rules.append({
                "name": "move_backward",
                "action": "move",
                "params": [],
                "conditions": ["race_can_move()"],
                "effects": ["race_move_backward()"],
            })
        else:
            effect_fn = "roll_and_move_bump(roll)" if has_bump else "roll_and_move(roll)"
            rules.append({
                "name": "roll_and_move",
                "action": "chance",
                "chance": True,
                "params": [{"name": "roll", "select": f"int_range({num_dice}, {max_roll})"}],
                "conditions": [],
                "effects": [effect_fn],
            })
        return rules

    # Capture-based games: detect standalone capture mechanics for grid games
    capture_keywords = ['capture', 'captured', 'capturing', 'take opponent',
                        'remove opponent', 'eliminate', 'eliminated',
                        'eat opponent', 'knock out', 'knocked out']
    has_capture = any(w in text for w in capture_keywords)
    if has_capture and board.get("type") == "grid" and not rules:
        # Movement + capture game — use generic grid movement
        is_diagonal = 'diagonal' in text
        move_dirs = "diagonal" if is_diagonal else "all"

        rules.append({
            "name": f"move_{piece_name}",
            "action": "move",
            "params": [{"name": "move_id", "select": "grid_moves"}],
            "conditions": [],
            "effects": ["grid_move_execute(move_id)"],
        })
        board["_move_directions"] = move_dirs
        board["_forward_only"] = False
        board["_needs_piece_setup"] = True
        return rules

    # Default: simple placement on empty space (TTT style)
    if board.get("type") == "grid":
        # Detect piece inventory: "each player has N pieces/stones"
        piece_limit = None
        inv_match = re.search(r'each player (?:has|gets|starts with)\s+(\d+)', text)
        if not inv_match:
            inv_match = re.search(r'(\d+)\s+(?:pieces?|stones?|marks?)\s+(?:each|per)', text)
        if inv_match:
            piece_limit = int(inv_match.group(1))
            board["_piece_limit"] = piece_limit

        conditions = ["piece_at(target) == empty"]
        if piece_limit:
            conditions.append(f"pieces_placed(current_player) < {piece_limit}")

        rules.append({
            "name": f"place_{piece_name}",
            "action": "place",
            "params": [{"name": "target", "select": "empty_space"}],
            "conditions": conditions,
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

    # "capture all opponent pieces" / "no pieces left"
    # Exclude flanking games — "cannot move" means pass, not capture-all
    is_flanking_game = any(w in text for w in ['flip', 'flank', 'sandwich', 'surround', 'reversi', 'othello'])
    capture_all_keywords = ['capture all', 'no pieces left', 'eliminate all',
                            'remove all opponent', 'last piece', 'no remaining',
                            'all opponent pieces', 'take all']
    if not is_flanking_game:
        capture_all_keywords.extend(["opponent can't move", 'cannot move'])
    if any(w in text for w in capture_all_keywords):
        # Use checkers end condition if game uses checkers engine
        # Use grid_no_moves for generic movement games, checkers for checkers
        has_grid_moves = any(
            any(p.get("select") == "grid_moves" for p in r.get("params", []))
            for r in rules)
        has_checkers = any(
            any(p.get("select") == "checkers_moves" for p in r.get("params", []))
            for r in rules)
        if has_grid_moves:
            conditions.append({
                "type": "win",
                "player": "current_player",
                "condition": "grid_no_moves()",
            })
        elif has_checkers:
            conditions.append({
                "type": "win",
                "player": "current_player",
                "condition": "checkers_opponent_has_no_moves()",
            })
        else:
            conditions.append({
                "type": "win",
                "player": "current_player",
                "condition": "opponent_has_no_pieces_or_moves(current_player)",
            })

    # Territory / area control: most pieces or most controlled area wins
    if any(w in text for w in ['most territory', 'most area', 'control more',
                                'controls more', 'most pieces on the board',
                                'most stones on the board', 'majority',
                                'most pieces wins', 'most stones wins',
                                'most marks wins', 'dominates']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "board_full() or no_legal_moves()",
            "score": "count_pieces(current_player)",
        })

    # "closer to center" / positional scoring
    if any(w in text for w in ['closer to the center', 'nearest to center',
                                'most central']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "board_full() or no_legal_moves()",
            "score": "center_proximity_score(current_player)",
        })

    # Sowing: most stones in store wins (only for track/mancala boards)
    if board.get("type") == "track" and any(w in text for w in ['most stones', 'most seeds', 'most in store',
                                'most in your store', 'mancala']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "one_side_empty()",
            "score": "store_count(current_player)",
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

    # Race: first to reach the end / finish line
    race_keywords = ['race', 'finish line', 'reach the end', 'first to reach',
                     'first to the end', 'first to space', 'move forward',
                     'move along']
    is_race = any(w in text for w in race_keywords) or re.search(r'roll\b.*\bmove\b', text)
    if is_race and board.get("type") == "track":
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": "race_won(current_player)",
        })

    # Movement: reach the other/opposite side wins
    if any(w in text for w in ['reach the other side', 'reach the opposite', 'reach opponent',
                                'cross the board', 'get to the other end']):
        if board.get("type") == "grid":
            rows = board.get("grid", {}).get("rows", 8)
            conditions.append({
                "type": "win",
                "player": "current_player",
                "condition": f"piece_on_row(current_player, {rows - 1})" if 'player1' != 'current_player' else f"piece_on_row(current_player, 0)",
                "_comment": "First player to get a piece to opponent's back row wins",
            })

    # "filling a row/column wins"
    if any(w in text for w in ['fill a row', 'filling a row', 'complete a row',
                                'fill a column', 'filling a column', 'complete a column',
                                'fills a row', 'fills a column']):
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": "row_or_col_filled(current_player)",
        })

    # "most pieces/tiles/discs/stones wins" or "placed more tiles wins"
    if ('most' in text or 'more' in text) and 'win' in text:
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "no_legal_moves()",
            "score": "count_my_pieces(current_player)",
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

    # Flanking/Reversi game — 4 pieces in center
    is_flanking = any("flip" in str(r.get("effects", [])) or "flank" in str(r.get("effects", []))
                      for r in board.get("_rules_ref", []))  # check via board ref
    # Detect from text
    if any(w in text for w in ['flip', 'flank', 'sandwich', 'surround', 'reversi', 'othello']):
        is_flanking = True
    if is_flanking and board.get("type") == "grid":
        rows = board.get("grid", {}).get("rows", 8)
        cols = board.get("grid", {}).get("cols", 8)
        cr, cc = rows // 2, cols // 2
        piece_name = "piece"
        for p in pieces:
            if p.get("name"):
                piece_name = p["name"]
                break
        # Center 4 pieces in alternating pattern
        setup.append({"action": "place", "piece": f"{piece_name}(player1)", "at": f"space_at({cr-1}, {cc-1})"})
        setup.append({"action": "place", "piece": f"{piece_name}(player2)", "at": f"space_at({cr-1}, {cc})"})
        setup.append({"action": "place", "piece": f"{piece_name}(player2)", "at": f"space_at({cr}, {cc-1})"})
        setup.append({"action": "place", "piece": f"{piece_name}(player1)", "at": f"space_at({cr}, {cc})"})
        return setup

    # Movement/capture game — place pieces in starting rows
    if board.get("_needs_piece_setup"):
        rows = board.get("grid", {}).get("rows", 8)
        cols = board.get("grid", {}).get("cols", 8)
        piece_name = "piece"
        for p in pieces:
            if p.get("name"):
                piece_name = p["name"]
                break

        # Check for specific row count in description
        word_nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
        row_match = re.search(r'(?:first|starting)\s+(\d+)\s+rows?', text)
        if not row_match:
            word_match = re.search(r'(?:first|starting)\s+(one|two|three|four|five)\s+rows?', text)
            if word_match:
                class FakeMatch:
                    def __init__(self, v): self._v = v
                    def group(self, _): return str(self._v)
                row_match = FakeMatch(word_nums[word_match.group(1)])
        if row_match:
            fill_rows = int(row_match.group(1))
        elif re.search(r'(\d+)\s+pieces?\s+each', text):
            piece_count = int(re.search(r'(\d+)\s+pieces?\s+each', text).group(1))
            fill_rows = max(1, (piece_count + cols - 1) // cols)  # rows needed
        else:
            fill_rows = min(2, rows // 3)

        # Detect dark square placement
        dark_only = any(w in text for w in ['dark square', 'black square', 'checkerboard',
                                             'alternate square', 'alternating square'])

        for r in range(rows - fill_rows, rows):
            for c in range(cols):
                if dark_only and (r + c) % 2 == 0:
                    continue  # skip light squares
                setup.append({"action": "place", "piece": f"{piece_name}(player1)", "at": f"space_at({r}, {c})"})
        for r in range(fill_rows):
            for c in range(cols):
                if dark_only and (r + c) % 2 == 0:
                    continue
                setup.append({"action": "place", "piece": f"{piece_name}(player2)", "at": f"space_at({r}, {c})"})
        return setup

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
        # Always flip for matching/shedding games (they need a card to match against)
        has_discard = any(z["name"] == "discard" for z in board.get("zones", []))
        is_matching = any(w in text for w in ['match', 'matching', 'crazy eight', 'uno',
                                               'same suit', 'same rank', 'play a card'])
        if has_discard and (is_matching or any(w in text for w in ['flip', 'turn over', 'face up', 'start', 'discard'])):
            setup.append({"action": "reveal", "from": deck_zone, "to": "discard", "count": 1})

        return setup

    # Race game setup: place tokens for each player at start
    race_keywords = ['race', 'finish line', 'reach the end', 'first to reach',
                     'first to the end', 'move forward', 'move along']
    is_race = (any(w in text for w in race_keywords)
               or re.search(r'roll\b.*\bmove\b', text))
    if is_race and board.get("type") == "track":
        setup.append({"action": "race_setup"})
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
    text = text.lower()
    if 'pile' in text and ('take' in text or 'remov' in text):
        return "Custom Nim"
    if 'in a row' in text:
        n = re.search(r'(\d+)\s+in\s+a\s+row', text)
        grid = re.search(r'(\d+)\s*x\s*(\d+)', text)
        if n and grid:
            return f"{n.group(1)}-in-a-Row ({grid.group(1)}x{grid.group(2)})"
        elif n:
            return f"{n.group(1)}-in-a-Row"
    if 'flank' in text or ('flip' in text and 'card' not in text):
        return "Custom Reversi"

    race_keywords = ['race', 'finish line', 'reach the end', 'first to reach',
                     'first to the end', 'move forward', 'move along']
    if any(w in text for w in race_keywords) or re.search(r'roll\b.*\bmove\b', text):
        return "Custom Race"

    # Card game names
    if _is_card_game(text):
        if 'go fish' in text:
            return "Custom Go Fish"
        if 'crazy eight' in text:
            return "Custom Crazy Eights"
        if 'war' in text:
            return "Custom War"
        if 'ask' in text and ('rank' in text or 'card' in text):
            return "Custom Fishing Game"
        if 'set' in text or 'collect' in text:
            return "Custom Collection Game"
        if 'match' in text and ('suit' in text or 'rank' in text):
            return "Custom Card Match"
        if 'wild' in text or 'eight' in text:
            return "Custom Crazy Eights"
        return "Custom Card Game"

    return "Custom Game"


def _extract_card_end_conditions(text: str, board: dict) -> list[dict]:
    """Extract end conditions for card games."""
    conditions = []

    # "empty hand wins" / "first to play all cards" / "get rid of all"
    if any(w in text for w in ['empty hand', 'no cards left', 'first to play all',
                                'gets rid of all', 'empty your hand', 'shed all',
                                'get rid of']):
        conditions.append({
            "type": "win",
            "player": "current_player",
            "condition": "crazy_eights_hand_empty(current_player)",
        })

    # Trick-taking: lowest points / avoid points / fewest points
    if any(w in text for w in ['avoid points', 'fewest points', 'lowest points',
                                'least points', 'avoid hearts', 'avoid taking']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "hearts_game_over()",
            "score": "hearts_score(current_player)",
        })
        return conditions

    # Trick-taking: most tricks wins
    if any(w in text for w in ['most tricks', 'win the most tricks', 'wins more tricks']):
        conditions.append({
            "type": "win",
            "player": "player_by_score",
            "condition": "hearts_game_over()",
            "score": "hearts_score(current_player)",
        })
        return conditions

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

    # 1. Collecting/Go Fish style: ask for a rank, collect sets
    if any(w in text for w in ['ask', 'do you have', 'go fish', 'request',
                                'collect set', 'book of', 'set of 4', 'sets of']):
        rules.append({
            "name": "ask_for_rank",
            "action": "ask",
            "params": [{"name": "rank", "select": "card_rank"}],
            "conditions": ["has_rank_in_hand(current_player, rank)"],
            "effects": ["go_fish_ask(rank)"],
        })
        return rules

    # 2. Matching/Shedding: play matching card, empty hand wins
    # Detect card special powers
    card_effects = {}
    if re.search(r'\b8s?\b.*wild|wild.*\b8s?\b|eight.*wild|wild.*eight', text):
        card_effects["wild_rank"] = "8"
    if 'wild' in text and 'wild' not in str(card_effects):
        card_effects["has_wild"] = True
    if any(w in text for w in ['skip', 'skip card', 'miss a turn']):
        card_effects["has_skip"] = True
    if any(w in text for w in ['reverse', 'reverses', 'change direction']):
        card_effects["has_reverse"] = True
    if re.search(r'draw\s+(?:two|2|four|4)', text):
        card_effects["has_draw_penalty"] = True

    if any(w in text for w in ['match', 'same suit', 'same rank', 'matching',
                                'play a card that matches', 'play a matching',
                                'crazy eight', 'uno', 'empty hand', 'get rid of',
                                'shed', 'discard matching']):
        # Use Uno engine if Uno-style effects detected, otherwise Crazy Eights
        use_uno = card_effects.get("has_skip") or card_effects.get("has_reverse") or \
                  card_effects.get("has_draw_penalty") or 'uno' in text
        selector = "uno_playable" if use_uno else "crazy_eights_playable"
        effect = "uno_play(card_id)" if use_uno else "crazy_eights_play(card_id)"
        draw_cond = "uno_must_draw()" if use_uno else "crazy_eights_must_draw()"
        draw_effect = "uno_draw()" if use_uno else "crazy_eights_draw()"

        rules.append({
            "name": "play_card",
            "action": "play",
            "params": [{"name": "card_id", "select": selector}],
            "conditions": [],
            "effects": [effect],
        })
        rules.append({
            "name": "draw_card",
            "action": "draw",
            "params": [],
            "conditions": [draw_cond],
            "effects": [draw_effect],
        })
        if card_effects:
            board["_card_effects"] = card_effects
        return rules

    # 3. Trick-taking: play cards in tricks, follow suit, highest wins
    if any(w in text for w in ['trick', 'follow suit', 'trump', 'lead',
                                'wins the trick', 'take the trick',
                                'avoid points', 'avoid hearts']):
        # Add trick zone if not present
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
            "params": [{"name": "card_id", "select": "hearts_playable"}],
            "conditions": [],
            "effects": ["hearts_play(card_id)"],
        })
        return rules

    # 4. War style: both flip cards
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

    # Movement game config
    if board.get("_move_directions") or board.get("_needs_piece_setup"):
        # Detect promotion keywords
        has_promotion = any(w in text for w in ['king', 'crowned', 'promoted', 'promotion',
                                                 'becomes a king', 'reaches the back',
                                                 'reaches the opposite', 'last row'])
        state_vars.extend([
            {"name": "_move_directions", "type": "string", "scope": "global",
             "initial": board.get("_move_directions", "all")},
            {"name": "_forward_only", "type": "bool", "scope": "global",
             "initial": board.get("_forward_only", False)},
            {"name": "_promotion_enabled", "type": "bool", "scope": "global",
             "initial": has_promotion},
            {"name": "last_play", "type": "string", "scope": "global", "initial": ""},
            {"name": "last_action", "type": "string", "scope": "global", "initial": ""},
        ])

    # Race game state vars
    race_keywords = ['race', 'finish line', 'reach the end', 'first to reach',
                     'first to the end', 'move forward', 'move along']
    is_race = (any(w in text for w in race_keywords)
               or re.search(r'roll\b.*\bmove\b', text))
    if is_race and board.get("type") == "track":
        has_choice = any(w in text for w in ['forward or backward', 'backward or forward',
                                              'choose to move', 'either direction'])
        state_vars.extend([
            {"name": "last_play", "type": "string", "scope": "global", "initial": ""},
            {"name": "last_action", "type": "string", "scope": "global", "initial": ""},
        ])
        if has_choice:
            state_vars.extend([
                {"name": "race_phase", "type": "string", "scope": "global", "initial": "roll"},
                {"name": "race_roll", "type": "int", "scope": "global", "initial": 0},
            ])
        return state_vars

    # Extra turn state var for any game mentioning bonus/extra turns
    if any(w in text for w in ['extra turn', 'another turn', 'go again', 'plays again', 'bonus turn']):
        if not any(sv["name"] == "extra_turn" for sv in state_vars):
            state_vars.append({"name": "extra_turn", "type": "bool", "scope": "global", "initial": False})

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


def _extract_cosmetics(text: str) -> dict:
    """Extract visual/cosmetic preferences from text."""
    cosmetics = {}

    COLOR_MAP = {
        'red': '#c83030', 'blue': '#2060d0', 'green': '#20a040',
        'yellow': '#d4a020', 'orange': '#d08020', 'purple': '#8040c0',
        'pink': '#d060a0', 'black': '#222222', 'white': '#f0e8d8',
        'gold': '#d4a656', 'silver': '#a0a0a8', 'brown': '#8B4513',
        'cyan': '#20c0c0', 'crimson': '#dc143c', 'navy': '#1a1a6e',
    }

    # Find colors mentioned with pieces/players
    # "red and blue pieces" / "red vs green" / "player 1 is red"
    piece_colors = []
    for color, hex_val in COLOR_MAP.items():
        if re.search(r'\b' + color + r'\b', text):
            piece_colors.append({"name": color, "hex": hex_val})

    if len(piece_colors) >= 2:
        cosmetics["player1_color"] = piece_colors[0]["hex"]
        cosmetics["player2_color"] = piece_colors[1]["hex"]
    elif len(piece_colors) == 1:
        cosmetics["player1_color"] = piece_colors[0]["hex"]

    # Board color: "on a green board" / "blue board" / "wooden board"
    # Try multiple patterns to catch "wooden 6x6 board" etc.
    board_match = re.search(r'(wooden|wood|dark|light|white|' + '|'.join(COLOR_MAP.keys()) + r')\s+(?:\d+\s*[x×]\s*\d+\s+)?(?:board|grid|field)', text)
    if board_match:
        word = board_match.group(1)
        if word in COLOR_MAP:
            cosmetics["board_color"] = COLOR_MAP[word]
        elif word in ('wooden', 'wood'):
            cosmetics["board_color"] = '#a0784a'
            cosmetics["board_style"] = 'wood'
        elif word in ('dark'):
            cosmetics["board_color"] = '#1a1a1a'
        elif word in ('light', 'white'):
            cosmetics["board_color"] = '#e8e0d0'

    # Board pattern: checkerboard/chessboard
    if any(w in text for w in ['checkerboard', 'chessboard', 'checkered',
                                'alternating squares', 'chess board',
                                'checker board']):
        cosmetics["board_pattern"] = "checkerboard"

    return cosmetics
