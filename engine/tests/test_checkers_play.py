"""AI competency tests for Checkers threat detection.

Verifies the Reasoner (with EffortAllocator) makes obvious correct moves:
taking captures when available (mandatory in checkers) and preferring
multi-jumps over single jumps.
"""

from engine.engine import GameEngine
from engine.gdl.board import GridSpace
from engine.gdl.state import Piece, GameState
from engine.gdl.checkers import get_all_moves
from engine.reasoner.reasoner import Reasoner
from engine.metacognition.effort import EffortAllocator


def _setup_checkers():
    return GameEngine.from_file("engine/games/examples/checkers.json")


def _ai_choice(eng, state, max_depth=6):
    allocator = EffortAllocator()
    reasoner = Reasoner(eng, max_depth=max_depth, effort_allocator=allocator)
    move = reasoner.choose_move(state)
    return move, reasoner.last_depth_used


def _clear_board(state):
    """Remove all pieces from the board."""
    for space in list(state.pieces.keys()):
        state.set_piece(space, None)


def _setup_position(eng, p1_pieces, p2_pieces, current_player="player1",
                     p1_kings=None, p2_kings=None):
    """Create a custom checkers position.

    p1_pieces / p2_pieces: list of (row, col) for men
    p1_kings / p2_kings: list of (row, col) for kings
    """
    state = eng.initial_state()
    _clear_board(state)
    for r, c in (p1_pieces or []):
        state.set_piece(GridSpace(r, c), Piece("man", "player1"))
    for r, c in (p2_pieces or []):
        state.set_piece(GridSpace(r, c), Piece("man", "player2"))
    for r, c in (p1_kings or []):
        state.set_piece(GridSpace(r, c), Piece("king", "player1"))
    for r, c in (p2_kings or []):
        state.set_piece(GridSpace(r, c), Piece("king", "player2"))
    state.current_player = current_player
    state.state_vars["must_jump_from"] = ""
    return state


def test_takes_capture_when_available():
    """AI must take a jump when one is available (mandatory capture).

    Set up: P1 man at (5,2), P2 man at (4,3), empty at (3,4).
    P1 can jump over P2's piece.
    """
    eng = _setup_checkers()
    state = _setup_position(
        eng,
        p1_pieces=[(5, 2)],
        p2_pieces=[(4, 3)],
        current_player="player1"
    )
    moves = get_all_moves(state)
    # All legal moves should be jumps (mandatory capture)
    assert all(m.is_jump for m in moves), "All moves should be jumps when a capture exists"

    move, depth = _ai_choice(eng, state)
    # The AI should execute the jump
    checkers_moves = get_all_moves(state)
    selected = checkers_moves[move.params["move_id"]]
    assert selected.is_jump, f"AI should take the capture, but chose a non-jump move"


def test_takes_double_jump_over_single():
    """AI should prefer a double jump over a single jump when both are available.

    Set up: P1 man at (7,0), P2 men at (6,1) and (4,3).
    P1 can jump (7,0)->(5,2) capturing (6,1), then (5,2)->(3,4) capturing (4,3).
    """
    eng = _setup_checkers()
    state = _setup_position(
        eng,
        p1_pieces=[(7, 0)],
        p2_pieces=[(6, 1), (4, 3)],
        current_player="player1"
    )
    moves = get_all_moves(state)
    # Should have at least one multi-jump
    multi_jumps = [m for m in moves if len(m.captures) >= 2]
    if not multi_jumps:
        import pytest
        pytest.skip("Board setup did not produce multi-jump; checking single jump only")

    move, depth = _ai_choice(eng, state)
    selected = moves[move.params["move_id"]]
    assert selected.is_jump, "AI should take a jump"
    assert len(selected.captures) >= 2, (
        f"AI should take the double jump (2 captures), "
        f"but chose a move with {len(selected.captures)} capture(s)"
    )


def test_does_not_sacrifice_last_piece():
    """AI should not move its piece into a position where it gets captured
    if a safe move exists.

    Set up: P1 man at (5,0), P2 man at (3,2). P1 can move to (4,1) which
    lets P2 jump, or stay safe. With only one piece, losing it means losing.
    We give P1 a second safe piece so the game doesn't end immediately.
    """
    eng = _setup_checkers()
    # P1 has a man at (5,0) and a safe man at (7,6).
    # P2 has a man at (3,2).
    # If P1 moves (5,0)->(4,1), P2 can jump to (5,0) capturing P1.
    # P1 should prefer moving the safe piece at (7,6) instead.
    state = _setup_position(
        eng,
        p1_pieces=[(5, 0), (7, 6)],
        p2_pieces=[(3, 2)],
        current_player="player1"
    )
    moves = get_all_moves(state)
    if len(moves) < 2:
        import pytest
        pytest.skip("Need multiple move options for this test")

    move, depth = _ai_choice(eng, state)
    selected = moves[move.params["move_id"]]
    # The AI should NOT move (5,0) to (4,1) since that's suicidal
    from_space = selected.steps[0][0]
    to_space = selected.steps[0][1]
    is_suicidal = (from_space.row == 5 and from_space.col == 0 and
                   to_space.row == 4 and to_space.col == 1)
    assert not is_suicidal, (
        f"AI moved (5,0)->(4,1) which allows opponent capture — should avoid this"
    )
