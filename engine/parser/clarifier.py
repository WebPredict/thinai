"""Game description clarification system.

Analyzes parsed GDL and the original English text to detect
ambiguities, missing details, and potential issues. Produces
structured clarification questions for the user, and can apply
their answers back into the GDL.
"""

from __future__ import annotations

import copy
import re
from typing import Optional


def find_clarifications(gdl: dict, original_text: str) -> list[dict]:
    """Analyze parsed GDL and original text to find missing/ambiguous details.

    Returns a list of clarification questions, each with:
    - id: unique string identifier
    - question: human-readable question
    - type: "missing" | "ambiguous" | "confirm"
    - field: which GDL field this affects
    - default: what we'll assume if they don't answer
    - options: list of possible answers (for multiple choice)
    """
    questions: list[dict] = []
    text_lower = original_text.lower()

    board = gdl.get("board", {})
    meta = gdl.get("meta", {})
    end_conditions = gdl.get("end_conditions", [])
    rules = gdl.get("rules", [])
    setup = gdl.get("setup", [])

    board_type = board.get("type", "")
    is_grid = board_type == "grid"
    is_card = board_type == "card_zones"

    has_win = any(ec.get("type") == "win" for ec in end_conditions)
    has_draw = any(ec.get("type") == "draw" for ec in end_conditions)

    grid = board.get("grid", {})
    rows = grid.get("rows", 0)
    cols = grid.get("cols", 0)

    # ------------------------------------------------------------------
    # 1. No win condition at all
    # ------------------------------------------------------------------
    if not end_conditions:
        questions.append({
            "id": "no_win_condition",
            "question": "How does a player win?",
            "type": "missing",
            "field": "end_conditions",
            "default": None,
            "options": [],
        })

    # ------------------------------------------------------------------
    # 2. Missing draw condition (grid game with win but no draw)
    # ------------------------------------------------------------------
    if is_grid and has_win and not has_draw:
        questions.append({
            "id": "missing_draw",
            "question": "What happens if the board fills up with no winner?",
            "type": "missing",
            "field": "end_conditions",
            "default": "It's a draw",
            "options": ["It's a draw", "Keep playing"],
        })

    # ------------------------------------------------------------------
    # 3. Missing board size (grid game, no dimensions in original text)
    # ------------------------------------------------------------------
    if is_grid and not _text_mentions_grid_size(text_lower):
        questions.append({
            "id": "missing_board_size",
            "question": "What size should the board be?",
            "type": "missing",
            "field": "board.grid",
            "default": "5x5",
            "options": ["3x3", "5x5", "8x8"],
        })

    # ------------------------------------------------------------------
    # 4. Missing hand size (card game, no deal count in text)
    # ------------------------------------------------------------------
    if is_card and not _has_deal_count(setup, text_lower):
        questions.append({
            "id": "missing_hand_size",
            "question": "How many cards should each player start with?",
            "type": "missing",
            "field": "setup",
            "default": "7",
            "options": ["5", "7", "10", "13"],
        })

    # ------------------------------------------------------------------
    # 5. Ambiguous win direction (points/score but unclear higher/lower)
    # ------------------------------------------------------------------
    if _mentions_points(text_lower) and not _win_direction_clear(text_lower, end_conditions):
        questions.append({
            "id": "ambiguous_win_direction",
            "question": "Does the player with MORE points win, or FEWER?",
            "type": "ambiguous",
            "field": "end_conditions",
            "default": "More points wins",
            "options": ["More points wins", "Fewer points wins"],
        })

    # ------------------------------------------------------------------
    # 6. Missing tie rule (card compare game, no mention of ties)
    # ------------------------------------------------------------------
    if is_card and _is_compare_game(text_lower, rules) and not _mentions_ties(text_lower):
        questions.append({
            "id": "missing_tie_rule",
            "question": "What happens when both cards are the same rank?",
            "type": "missing",
            "field": "rules",
            "default": "No points awarded",
            "options": ["No points awarded", "Both score a point", "Play again"],
        })

    # ------------------------------------------------------------------
    # 7. Large board warning
    # ------------------------------------------------------------------
    if is_grid and rows > 10 and cols > 10:
        smaller = min(rows, cols, 10)
        questions.append({
            "id": "large_board_warning",
            "question": f"A {rows}x{cols} board will be slow to search. "
                        f"Use {smaller}x{smaller} instead?",
            "type": "confirm",
            "field": "board.grid",
            "default": f"{smaller}x{smaller}",
            "options": [f"Yes, use {smaller}x{smaller}", f"No, keep {rows}x{cols}"],
        })

    # ------------------------------------------------------------------
    # 8. Turn order unclear (mentions extra/bonus turn but alternating)
    # ------------------------------------------------------------------
    if (_mentions_extra_turn(text_lower)
            and meta.get("turn_order") == "alternating"):
        questions.append({
            "id": "turn_order_unclear",
            "question": "Should a player sometimes get extra turns?",
            "type": "ambiguous",
            "field": "meta.turn_order",
            "default": "No, always alternate",
            "options": ["Yes, when...", "No, always alternate"],
        })

    # ------------------------------------------------------------------
    # 9. Number of players > 2
    # ------------------------------------------------------------------
    if meta.get("players", 2) > 2:
        questions.append({
            "id": "player_count",
            "question": "ThinAI currently supports 2 players. Use 2 players?",
            "type": "confirm",
            "field": "meta.players",
            "default": "Yes",
            "options": ["Yes", "No"],
        })

    # ------------------------------------------------------------------
    # 10. Piece movement unclear
    # ------------------------------------------------------------------
    if _mentions_moving(text_lower) and not _movement_specified(text_lower, rules):
        questions.append({
            "id": "piece_movement_unclear",
            "question": "How do pieces move?",
            "type": "ambiguous",
            "field": "rules",
            "default": "One square in any direction",
            "options": [
                "One square in any direction",
                "Diagonally only",
                "Any distance in a line",
            ],
        })

    # ------------------------------------------------------------------
    # 11. Single color for both players' pieces
    # ------------------------------------------------------------------
    cosmetics = gdl.get("_cosmetics", {})
    has_p1_color = "player1_color" in cosmetics
    has_p2_color = "player2_color" in cosmetics
    if is_grid and has_p1_color and not has_p2_color:
        # Only one color mentioned — both players look the same
        questions.append({
            "id": "single_piece_color",
            "question": "You mentioned one color for pieces. What color should the other player's pieces be?",
            "type": "missing",
            "field": "_cosmetics.player2_color",
            "default": "Automatic (contrasting color)",
            "options": [
                "Automatic (contrasting color)",
                "Red", "Blue", "Green", "Black", "White", "Purple",
            ],
        })

    return questions


# ======================================================================
# Helper predicates
# ======================================================================

def _text_mentions_grid_size(text: str) -> bool:
    """Check if the original text explicitly mentions a grid/board size."""
    if re.search(r'\d+\s*[x\xd7]\s*\d+', text):
        return True
    if re.search(r'\d+\s*rows?\s*(?:and|,)\s*\d+\s*col', text):
        return True
    if re.search(r'\d+\s*col\w*\s*(?:and|,)\s*\d+\s*rows?', text):
        return True
    return False


def _has_deal_count(setup: list[dict], text: str) -> bool:
    """Check if a deal count is explicitly specified."""
    # Check if the text explicitly mentions dealing N cards
    if re.search(r'deal\w*\s+\d+\s+cards?', text):
        return True
    if re.search(r'\d+\s+cards?\s+(?:each|per|to each)', text):
        return True
    return False


def _mentions_points(text: str) -> bool:
    """Check if text mentions points or scoring."""
    return bool(re.search(r'\b(?:points?|scores?|scoring)\b', text))


def _win_direction_clear(text: str, end_conditions: list[dict]) -> bool:
    """Check if the text or end_conditions clarify higher vs lower wins."""
    # Explicit higher/more wins
    if re.search(r'\b(?:most|more|highest|maximum)\s+(?:points?|scores?)\s+wins?', text):
        return True
    # Explicit lower/fewer wins
    if re.search(r'\b(?:fewest|fewer|lowest|least|minimum)\s+(?:points?|scores?)\s+wins?', text):
        return True
    # Check end conditions for score direction hints
    for ec in end_conditions:
        cond_str = str(ec)
        if 'avoid' in cond_str or 'fewest' in cond_str or 'least' in cond_str:
            return True
        if 'most' in cond_str or 'more' in cond_str:
            return True
    return False


def _is_compare_game(text: str, rules: list[dict]) -> bool:
    """Check if this is a card-compare game (War-like)."""
    if any(w in text for w in ['compare', 'higher rank', 'higher card',
                                'flip', 'war', 'battle']):
        return True
    for rule in rules:
        if rule.get("action") == "chance" and 'war' in rule.get("name", ""):
            return True
        if 'compare' in str(rule.get("effects", [])):
            return True
    return False


def _mentions_ties(text: str) -> bool:
    """Check if the text addresses what happens on ties."""
    return bool(re.search(r'\b(?:tie|ties|tied|same rank|equal rank|same value|draw|war)\b', text))


def _mentions_extra_turn(text: str) -> bool:
    """Check if the text mentions extra/bonus turns."""
    return bool(re.search(r'\b(?:extra turn|bonus turn|another turn|go again)\b', text))


def _mentions_moving(text: str) -> bool:
    """Check if the text mentions moving pieces (not placing)."""
    return bool(re.search(r'\b(?:move|moves|moving|slide|slides|step)\b', text))


def _movement_specified(text: str, rules: list[dict]) -> bool:
    """Check if movement direction/distance is specified."""
    # Text specifies direction or distance
    if re.search(r'\b(?:diagonal(?:ly)?|orthogonal(?:ly)?|any direction|'
                 r'one square|one space|adjacent|forward|backward|'
                 r'any distance|up to \d+)\b', text):
        return True
    # Rules already include move params with meaningful selectors
    for rule in rules:
        if rule.get("action") == "move":
            for p in rule.get("params", []):
                sel = p.get("select", "")
                if sel in ("adjacent_empty", "jump_targets", "diagonal_empty"):
                    return True
    return False


# ======================================================================
# Apply clarifications
# ======================================================================

def apply_clarification(gdl: dict, clarification_id: str, answer: str) -> dict:
    """Apply a user's answer to modify the GDL.

    Returns a new GDL dict with the modification applied.
    """
    gdl = copy.deepcopy(gdl)

    if clarification_id == "missing_draw":
        if answer == "It's a draw":
            gdl["end_conditions"].append({
                "type": "draw",
                "condition": "count(spaces[piece_at(s) == empty]) == 0",
            })
        # "Keep playing" means no draw condition needed — leave as-is

    elif clarification_id == "missing_board_size":
        match = re.match(r"(\d+)x(\d+)", answer)
        if match:
            rows, cols = int(match.group(1)), int(match.group(2))
            gdl["board"]["grid"]["rows"] = rows
            gdl["board"]["grid"]["cols"] = cols
            # Update any column-range params in rules
            for rule in gdl.get("rules", []):
                for param in rule.get("params", []):
                    if param.get("name") == "column":
                        param["select"] = f"int_range(0, {cols - 1})"

    elif clarification_id == "missing_hand_size":
        count = int(answer) if answer.isdigit() else 7
        for action in gdl.get("setup", []):
            if action.get("action") == "deal":
                action["count"] = count

    elif clarification_id == "ambiguous_win_direction":
        # Tag end conditions with score direction
        for ec in gdl.get("end_conditions", []):
            if ec.get("type") == "win" and "score" in ec:
                if answer == "Fewer points wins":
                    ec["score_order"] = "ascending"
                else:
                    ec["score_order"] = "descending"

    elif clarification_id == "missing_tie_rule":
        # Add a tie-handling state var
        state_vars = gdl.setdefault("state_vars", [])
        if answer == "No points awarded":
            state_vars.append({
                "name": "tie_rule", "type": "string",
                "scope": "global", "initial": "no_points",
            })
        elif answer == "Both score a point":
            state_vars.append({
                "name": "tie_rule", "type": "string",
                "scope": "global", "initial": "both_score",
            })
        elif answer == "Play again":
            state_vars.append({
                "name": "tie_rule", "type": "string",
                "scope": "global", "initial": "replay",
            })

    elif clarification_id == "large_board_warning":
        if answer.startswith("Yes"):
            size_match = re.search(r"(\d+)x(\d+)", answer)
            if size_match:
                gdl["board"]["grid"]["rows"] = int(size_match.group(1))
                gdl["board"]["grid"]["cols"] = int(size_match.group(2))

    elif clarification_id == "turn_order_unclear":
        if answer.startswith("Yes"):
            gdl["meta"]["turn_order"] = "conditional"
        else:
            gdl["meta"]["turn_order"] = "alternating"

    elif clarification_id == "player_count":
        if answer == "Yes":
            gdl["meta"]["players"] = 2

    elif clarification_id == "piece_movement_unclear":
        # Update or add movement rule
        move_rules = [r for r in gdl.get("rules", []) if r.get("action") == "move"]
        if answer == "One square in any direction":
            selector = "adjacent_empty"
        elif answer == "Diagonally only":
            selector = "diagonal_empty"
        elif answer == "Any distance in a line":
            selector = "line_empty"
        else:
            selector = "adjacent_empty"

        if move_rules:
            for rule in move_rules:
                for param in rule.get("params", []):
                    if param.get("name") == "to":
                        param["select"] = selector
        else:
            # Add a basic move rule
            piece_name = gdl["pieces"][0]["name"] if gdl.get("pieces") else "piece"
            gdl["rules"].append({
                "name": f"move_{piece_name}",
                "action": "move",
                "params": [
                    {"name": "from", "select": "own_pieces"},
                    {"name": "to", "select": selector},
                ],
                "conditions": [],
                "effects": [f"move_piece(from, to)"],
            })

    elif clarification_id == "no_win_condition":
        # Can't auto-apply since we don't know the condition, but store
        # the answer as a raw end condition string for downstream processing
        if answer:
            gdl["end_conditions"].append({
                "type": "win",
                "player": "current_player",
                "condition": answer,
                "_user_provided": True,
            })

    return gdl


# ======================================================================
# Main: test with sample game descriptions
# ======================================================================

if __name__ == "__main__":
    import json

    def _print_clarifications(label: str, questions: list[dict]):
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
        if not questions:
            print("  (no clarifications needed)")
        for q in questions:
            print(f"\n  [{q['id']}] ({q['type']})")
            print(f"  Q: {q['question']}")
            if q["options"]:
                print(f"  Options: {q['options']}")
            if q["default"] is not None:
                print(f"  Default: {q['default']}")
            print(f"  Field: {q['field']}")

    # ----- Test 1: Grid game missing draw condition -----
    gdl_no_draw = {
        "meta": {"name": "Connect Marks", "players": 2, "turn_order": "alternating", "version": "1.0"},
        "board": {"type": "grid", "grid": {"rows": 5, "cols": 5, "topology": "rect8"}},
        "pieces": [{"name": "mark", "owner": "each", "display": "X/O"}],
        "state_vars": [],
        "setup": [],
        "rules": [{"name": "place_mark", "action": "place",
                    "params": [{"name": "target", "select": "empty_space"}],
                    "conditions": ["piece_at(target) == empty"],
                    "effects": ["place mark(current_player) at target"]}],
        "end_conditions": [
            {"type": "win", "player": "current_player",
             "condition": "any d in directions: line_length(last_placed, d, current_player) >= 4"},
        ],
    }
    text_no_draw = "Two players take turns placing marks on a 5x5 grid. Get 4 in a row to win."
    qs = find_clarifications(gdl_no_draw, text_no_draw)
    _print_clarifications("Test 1: Grid game missing draw condition", qs)
    assert any(q["id"] == "missing_draw" for q in qs), "Should detect missing draw"
    assert not any(q["id"] == "missing_board_size" for q in qs), "Should NOT flag board size (5x5 in text)"

    # Apply the draw clarification
    updated = apply_clarification(gdl_no_draw, "missing_draw", "It's a draw")
    assert any(ec["type"] == "draw" for ec in updated["end_conditions"]), "Draw condition should be added"
    print("\n  -> Applied 'It's a draw': draw condition added successfully")

    # ----- Test 2: Grid game with no board size in text -----
    gdl_no_size = {
        "meta": {"name": "Grid Game", "players": 2, "turn_order": "alternating", "version": "1.0"},
        "board": {"type": "grid", "grid": {"rows": 3, "cols": 3, "topology": "rect8"}},
        "pieces": [{"name": "mark", "owner": "each", "display": "X/O"}],
        "state_vars": [],
        "setup": [],
        "rules": [{"name": "place_mark", "action": "place",
                    "params": [{"name": "target", "select": "empty_space"}],
                    "conditions": ["piece_at(target) == empty"],
                    "effects": ["place mark(current_player) at target"]}],
        "end_conditions": [
            {"type": "win", "player": "current_player",
             "condition": "any d in directions: line_length(last_placed, d, current_player) >= 3"},
        ],
    }
    text_no_size = "Players take turns placing marks on a board. Get 3 in a row to win."
    qs = find_clarifications(gdl_no_size, text_no_size)
    _print_clarifications("Test 2: Grid game with no board size", qs)
    assert any(q["id"] == "missing_board_size" for q in qs), "Should detect missing board size"
    assert any(q["id"] == "missing_draw" for q in qs), "Should also detect missing draw"

    # Apply the board size clarification
    updated = apply_clarification(gdl_no_size, "missing_board_size", "8x8")
    assert updated["board"]["grid"]["rows"] == 8, "Rows should be updated"
    assert updated["board"]["grid"]["cols"] == 8, "Cols should be updated"
    print("\n  -> Applied '8x8': board updated to 8x8 successfully")

    # ----- Test 3: Card game with no hand size specified -----
    gdl_card = {
        "meta": {"name": "Card Battle", "players": 2, "turn_order": "alternating", "version": "1.0"},
        "board": {
            "type": "card_zones",
            "zones": [
                {"name": "deck", "visible_to": "none", "ordered": True},
                {"name": "hand_p1", "owner": "player1", "visible_to": "owner", "ordered": False},
                {"name": "hand_p2", "owner": "player2", "visible_to": "owner", "ordered": False},
                {"name": "table", "visible_to": "all"},
            ],
        },
        "pieces": [],
        "state_vars": [
            {"name": "p1_score", "type": "int", "scope": "global", "initial": 0},
            {"name": "p2_score", "type": "int", "scope": "global", "initial": 0},
        ],
        "setup": [
            {"action": "shuffle", "zone": "deck"},
            {"action": "deal", "from": "deck", "to": "hand_p1", "count": 5},
            {"action": "deal", "from": "deck", "to": "hand_p2", "count": 5},
        ],
        "rules": [{"name": "play_card", "action": "play",
                    "params": [{"name": "card_id", "select": "gin_rummy_hand"}],
                    "conditions": [], "effects": ["compare_play(card_id)"]}],
        "end_conditions": [
            {"type": "win", "player": "player_by_score",
             "condition": "compare_game_over()",
             "score": "compare_score(current_player)"},
        ],
        "cards": {"deck": "standard52", "deck_zone": "deck"},
    }
    text_card = "Each player flips a card from their hand. The higher rank wins the round and scores a point. Play until all cards are gone."
    qs = find_clarifications(gdl_card, text_card)
    _print_clarifications("Test 3: Card game with no hand size", qs)
    assert any(q["id"] == "missing_hand_size" for q in qs), "Should detect missing hand size"
    assert any(q["id"] == "missing_tie_rule" for q in qs), "Should detect missing tie rule"

    # Apply hand size
    updated = apply_clarification(gdl_card, "missing_hand_size", "10")
    for action in updated["setup"]:
        if action.get("action") == "deal":
            assert action["count"] == 10, "Deal count should be 10"
    print("\n  -> Applied '10': deal count updated to 10 successfully")

    # ----- Test 4: Complete game (should return no clarifications) -----
    gdl_complete = {
        "meta": {"name": "Tic-Tac-Toe", "players": 2, "turn_order": "alternating", "version": "1.0"},
        "board": {"type": "grid", "grid": {"rows": 3, "cols": 3, "topology": "rect8"}},
        "pieces": [{"name": "mark", "owner": "each", "display": "X/O"}],
        "state_vars": [],
        "setup": [],
        "rules": [{"name": "place_mark", "action": "place",
                    "params": [{"name": "target", "select": "empty_space"}],
                    "conditions": ["piece_at(target) == empty"],
                    "effects": ["place mark(current_player) at target"]}],
        "end_conditions": [
            {"type": "win", "player": "current_player",
             "condition": "any d in directions: line_length(last_placed, d, current_player) >= 3"},
            {"type": "draw", "condition": "count(spaces[piece_at(s) == empty]) == 0"},
        ],
    }
    text_complete = "Two players take turns on a 3x3 grid placing marks. Get 3 in a row to win. If the board is full it's a draw."
    qs = find_clarifications(gdl_complete, text_complete)
    _print_clarifications("Test 4: Complete game (Tic-Tac-Toe)", qs)
    assert len(qs) == 0, f"Complete game should have 0 clarifications, got {len(qs)}"

    # ----- Test 5: Large board warning -----
    gdl_large = copy.deepcopy(gdl_complete)
    gdl_large["board"]["grid"]["rows"] = 15
    gdl_large["board"]["grid"]["cols"] = 15
    text_large = "Two players on a 15x15 grid. Get 5 in a row to win. Board full is a draw."
    qs = find_clarifications(gdl_large, text_large)
    _print_clarifications("Test 5: Large board warning", qs)
    assert any(q["id"] == "large_board_warning" for q in qs), "Should warn about large board"

    # ----- Test 6: Multiple players -----
    gdl_multi = copy.deepcopy(gdl_complete)
    gdl_multi["meta"]["players"] = 4
    text_multi = "Four players take turns on a 3x3 grid. Get 3 in a row to win. Board full is a draw."
    qs = find_clarifications(gdl_multi, text_multi)
    _print_clarifications("Test 6: 4-player game", qs)
    assert any(q["id"] == "player_count" for q in qs), "Should flag >2 players"

    updated = apply_clarification(gdl_multi, "player_count", "Yes")
    assert updated["meta"]["players"] == 2, "Should reduce to 2 players"
    print("\n  -> Applied 'Yes': player count set to 2 successfully")

    # ----- Test 7: Movement unclear -----
    gdl_move = {
        "meta": {"name": "Move Game", "players": 2, "turn_order": "alternating", "version": "1.0"},
        "board": {"type": "grid", "grid": {"rows": 8, "cols": 8, "topology": "rect8"}},
        "pieces": [{"name": "pawn", "owner": "each", "display": "P"}],
        "state_vars": [],
        "setup": [],
        "rules": [],
        "end_conditions": [
            {"type": "win", "player": "current_player", "condition": "reached_last_row()"},
            {"type": "draw", "condition": "no_legal_moves()"},
        ],
    }
    text_move = "Players move their pawns on an 8x8 board. First to reach the other side wins."
    qs = find_clarifications(gdl_move, text_move)
    _print_clarifications("Test 7: Movement unclear", qs)
    assert any(q["id"] == "piece_movement_unclear" for q in qs), "Should flag unclear movement"

    updated = apply_clarification(gdl_move, "piece_movement_unclear", "Diagonally only")
    move_rules = [r for r in updated["rules"] if r.get("action") == "move"]
    assert len(move_rules) == 1, "Should add a move rule"
    assert move_rules[0]["params"][1]["select"] == "diagonal_empty"
    print("\n  -> Applied 'Diagonally only': move rule added with diagonal_empty selector")

    # ----- Test 8: Extra turn mentioned but turn order is alternating -----
    gdl_extra = copy.deepcopy(gdl_complete)
    text_extra = "Two players on a 3x3 grid. Place marks. If you get 3 in a row you win. Board full is a draw. A player gets an extra turn if they complete a pair."
    qs = find_clarifications(gdl_extra, text_extra)
    _print_clarifications("Test 8: Extra turn mentioned but alternating", qs)
    assert any(q["id"] == "turn_order_unclear" for q in qs), "Should flag extra turn ambiguity"

    print(f"\n{'='*60}")
    print("  All tests passed!")
    print(f"{'='*60}")
