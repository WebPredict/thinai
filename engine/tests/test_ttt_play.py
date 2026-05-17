"""AI competency tests for Tic-Tac-Toe threat detection.

Verifies the Reasoner (with EffortAllocator) makes obvious correct moves:
blocking threats, taking wins, and preferring the center.
"""

from engine.engine import GameEngine
from engine.reasoner.reasoner import Reasoner
from engine.metacognition.effort import EffortAllocator


def _setup_ttt():
    return GameEngine.from_file("engine/games/examples/tictactoe.json")


def _play_moves(eng, positions):
    """Play a sequence of moves given as (row, col) tuples."""
    state = eng.initial_state()
    for r, c in positions:
        moves = eng.legal_moves(state)
        move = next(m for m in moves
                    if m.params["target"].row == r and m.params["target"].col == c)
        state = eng.apply_move(state, move)
    return state


def _ai_choice(eng, state, max_depth=6):
    allocator = EffortAllocator()
    reasoner = Reasoner(eng, max_depth=max_depth, effort_allocator=allocator)
    move = reasoner.choose_move(state)
    target = move.params["target"]
    return (target.row, target.col), reasoner.last_depth_used


def test_takes_winning_move():
    """P1 has two in a row on row 0, should complete it."""
    eng = _setup_ttt()
    # P1: (0,0), P2: (1,0), P1: (0,1), P2: (1,1)
    # Now P1's turn — (0,2) wins immediately.
    state = _play_moves(eng, [(0, 0), (1, 0), (0, 1), (1, 1)])
    choice, depth = _ai_choice(eng, state)
    assert choice == (0, 2), f"AI should win at (0,2), chose {choice}"


def test_blocks_opponent_win():
    """P2 must block P1's two-in-a-row threat."""
    eng = _setup_ttt()
    # P1: (0,0), P2: (2,2), P1: (0,1)
    # Now P2 must block (0,2) or P1 wins next turn.
    state = _play_moves(eng, [(0, 0), (2, 2), (0, 1)])
    choice, depth = _ai_choice(eng, state)
    assert choice == (0, 2), f"AI should block at (0,2), chose {choice}"


def test_takes_only_winning_move_on_full_board():
    """On a nearly-full board, P1 must take the one winning square.

    Board (P1 to move, 1 empty cell):
      P1 | P2 | P1
      P2 | P1 | P2
      P2 | .  | P1
    Only (2,1) is empty. P1 doesn't complete a line there but it's the
    only legal move. More importantly, this confirms the AI functions
    correctly on a nearly-full board without errors.

    Better: a board where the last move IS the winning move.
      P1 | P2 | P1
      P2 | P1 | P2
      P2 | P1 | .
    P1 plays (2,2) — completes the diagonal (0,0)-(1,1)-(2,2).
    """
    eng = _setup_ttt()
    # Moves: P1(0,0), P2(0,1), P1(1,1), P2(1,0), P1(0,2), P2(2,0), P1(2,1), P2(1,2)
    # Board: P1 P2 P1 / P2 P1 P2 / P2 P1 .  -> P1's turn, (2,2) wins diagonal
    state = _play_moves(eng, [
        (0, 0), (0, 1), (1, 1), (1, 0),
        (0, 2), (2, 0), (2, 1), (1, 2)
    ])
    choice, depth = _ai_choice(eng, state)
    assert choice == (2, 2), f"AI should win at (2,2), chose {choice}"


def test_takes_win_over_block():
    """When the AI can win immediately, it should win rather than block.

    Board (P2 to move):
      P1 | P1 | .
      .  | P2 | .
      P2 | .  | P2
    P2 has (1,1) and (2,0) and (2,2). P1 threatens (0,2).
    But P2 can win immediately at (2,1) completing row 2!
    AI should take the win rather than blocking.
    5 moves played (P2's turn).
    """
    eng = _setup_ttt()
    # P1: (0,0), P2: (1,1), P1: (0,1), P2: (2,0), P1: ? we need P2's turn with 5 moves
    # 5 moves = P1 made 3, P2 made 2. P2's turn.
    # Wait, 5 moves means P2's turn (P1:3, P2:2). Let me check:
    # move 1: P1, move 2: P2, move 3: P1, move 4: P2, move 5: P1 -> P2's turn
    # P1: (0,0), P2: (2,0), P1: (0,1), P2: (2,2), P1: (1,0)
    # Board: P1 P1 . / P1 . . / P2 . P2
    # P2 has (2,0) and (2,2), can win at (2,1)!
    # P1 has (0,0), (0,1), (1,0) — threatens (0,2) for row AND (2,0) for col
    # but (2,0) is taken by P2.
    state = _play_moves(eng, [(0, 0), (2, 0), (0, 1), (2, 2), (1, 0)])
    choice, depth = _ai_choice(eng, state)
    assert choice == (2, 1), f"AI should win at (2,1), chose {choice}"
