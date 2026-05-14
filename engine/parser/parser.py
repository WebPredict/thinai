"""Constrained English to GDL parser.

Takes a constrained-English game description and produces a
GDL JSON specification that the engine can execute.
"""

from __future__ import annotations
from typing import Optional

from engine.parser.tokenizer import tokenize, get_section
from engine.parser import templates


def parse(text: str) -> dict:
    """Parse a constrained-English game description into GDL JSON."""
    sections = tokenize(text)

    # Meta
    game_section = get_section(sections, "GAME")
    game_name = templates.parse_game_name(game_section.content) if game_section else "Unknown"

    players_section = get_section(sections, "PLAYERS")
    player_info = templates.parse_players(players_section.content) if players_section else {"players": 2, "turn_order": "alternating"}

    meta = {
        "name": game_name,
        "players": player_info["players"],
        "turn_order": player_info["turn_order"],
        "version": "1.0",
    }

    # Board
    board_section = get_section(sections, "BOARD")
    board = templates.parse_board(board_section.content) if board_section else {"type": "grid", "grid": {"rows": 3, "cols": 3}}

    # Pieces
    pieces_section = get_section(sections, "PIECES")
    pieces = templates.parse_pieces(pieces_section.content) if pieces_section else []

    # Setup
    setup_section = get_section(sections, "SETUP")
    setup = templates.parse_setup(setup_section.content, board) if setup_section else []

    # Special (parse before moves since it may affect meta)
    special_section = get_section(sections, "SPECIAL")
    special_result = {}
    if special_section:
        special_result = templates.parse_special(special_section.content, meta)
        if "turn_rule" in special_result:
            meta["turn_rule"] = special_result["turn_rule"]

    # Moves
    moves_section = get_section(sections, "MOVES")
    moves_content = moves_section.content if moves_section else ""
    # Include special section content for move pattern detection
    if special_section:
        moves_content += "\n" + special_section.content
    rules = templates.parse_moves(moves_content, board, pieces)

    # Win conditions
    win_section = get_section(sections, "WIN")
    # Pass move content to win parser for context
    win_content = win_section.content if win_section else ""
    if moves_section:
        win_content = win_section.content + "\n[moves_context:" + moves_section.content + "]" if win_section else ""
    end_conditions = templates.parse_win(win_section.content, board) if win_section else []

    # Draw conditions
    draw_section = get_section(sections, "DRAW")
    if draw_section:
        end_conditions.extend(templates.parse_draw(draw_section.content))

    # Build GDL
    gdl = {
        "meta": meta,
        "board": board,
        "pieces": pieces,
        "state_vars": [],
        "setup": setup,
        "rules": rules,
        "end_conditions": end_conditions,
    }

    return gdl
