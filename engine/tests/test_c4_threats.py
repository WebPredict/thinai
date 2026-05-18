"""Regression tests for Connect Four threat detection.

Ensures the AI blocks obvious threats and takes winning moves.
The 500→5000 node budget change (for board games) restored depth 4
which is needed to see 1-move threats in Connect Four.
"""

from engine.engine import GameEngine
from engine.reasoner.reasoner import Reasoner
from engine.metacognition.effort import EffortAllocator


def _setup_c4():
    return GameEngine.from_file("engine/games/examples/connect_four.json")


def _play_columns(eng, cols):
    """Play a sequence of column moves, alternating players."""
    state = eng.initial_state()
    for col in cols:
        moves = eng.legal_moves(state)
        col_moves = {m.params["column"]: m for m in moves}
        assert col in col_moves, f"Column {col} not legal"
        state = eng.apply_move(state, col_moves[col])
    return state


def _ai_choice(eng, state):
    """Get the AI's chosen column with effort allocator."""
    allocator = EffortAllocator()
    reasoner = Reasoner(eng, max_depth=6, effort_allocator=allocator)
    move = reasoner.choose_move(state)
    return move.params.get("column"), reasoner.last_depth_used


def test_blocks_vertical_threat():
    """AI must block a vertical 3-in-a-row (single open end)."""
    eng = _setup_c4()
    # p1 stacks col 3 three times, p2 plays elsewhere
    state = _play_columns(eng, [3, 0, 3, 1, 3])
    col, depth = _ai_choice(eng, state)
    assert col == 3, f"AI should block vertical at col 3, chose col {col}"


def test_takes_winning_move():
    """AI must take an immediate winning move."""
    eng = _setup_c4()
    # p2 builds 3 vertical in col 3
    state = _play_columns(eng, [0, 3, 1, 3, 0, 3])
    # p1 wastes a move
    moves = eng.legal_moves(state)
    col_moves = {m.params["column"]: m for m in moves}
    state = eng.apply_move(state, col_moves[1])
    # p2 can win at col 3
    col, depth = _ai_choice(eng, state)
    assert col == 3, f"AI should win at col 3, chose col {col}"


def test_effort_allocator_depth_for_c4():
    """Effort allocator must give at least depth 4 for Connect Four."""
    eng = _setup_c4()
    state = eng.initial_state()
    allocator = EffortAllocator()
    decision = allocator.recommend(state, eng)
    assert decision.depth >= 4, f"C4 needs at least depth 4, got {decision.depth}"


def test_card_games_stay_within_budget():
    """Card games should stay within 1500 node budget."""
    eng = GameEngine.from_file("engine/games/examples/uno.json")
    state = eng.initial_state()
    allocator = EffortAllocator()
    decision = allocator.recommend(state, eng)
    assert decision.max_nodes <= 1500, f"Card games should be within 1500 nodes, got {decision.max_nodes}"
