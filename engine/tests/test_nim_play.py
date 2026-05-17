"""AI competency tests for Nim.

Verifies the Reasoner (with EffortAllocator) makes correct moves in
positions with known optimal strategy. In Nim, the winning strategy
is based on XOR (nim-sum) of pile sizes.
"""

from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Move, Piece
from engine.reasoner.reasoner import Reasoner
from engine.metacognition.effort import EffortAllocator


def _setup_nim():
    return GameEngine.from_file("engine/games/examples/nim.json")


def _ai_choice(eng, state, max_depth=6):
    allocator = EffortAllocator()
    reasoner = Reasoner(eng, max_depth=max_depth, effort_allocator=allocator)
    move = reasoner.choose_move(state)
    pile = move.params["pile"]
    amount = move.params["amount"]
    return pile.index, amount, reasoner.last_depth_used


def _set_piles(eng, pile_sizes):
    """Create a Nim state with specific pile sizes."""
    state = eng.initial_state()
    # Clear all piles
    for i in range(3):
        space = TrackSpace(i)
        state.pieces.pop(space, None)
    # Fill to desired sizes
    for i, count in enumerate(pile_sizes):
        space = TrackSpace(i)
        if count > 0:
            state.pieces[space] = [Piece("stone", None) for _ in range(count)]
    return state


def test_takes_last_stone_to_win():
    """When only one pile remains with stones, take them all to win."""
    eng = _setup_nim()
    # Piles: [0, 0, 3] — take all 3 from pile 2 to win.
    state = _set_piles(eng, [0, 0, 3])
    pile, amount, depth = _ai_choice(eng, state)
    assert pile == 2 and amount == 3, (
        f"AI should take all 3 from pile 2 to win, chose pile {pile} amount {amount}"
    )


def test_takes_all_from_single_remaining_pile():
    """When one pile has 1 stone, take it to win."""
    eng = _setup_nim()
    state = _set_piles(eng, [0, 1, 0])
    pile, amount, depth = _ai_choice(eng, state)
    assert pile == 1 and amount == 1, (
        f"AI should take 1 from pile 1 to win, chose pile {pile} amount {amount}"
    )


def test_leaves_opponent_in_losing_position():
    """From piles [1, 1, 0], take from one pile to leave opponent with [0, 1, 0].

    Optimal: take 1 from pile 0, leaving [0, 1, 0]. Opponent must take
    the last stone? No — in normal play, taking the last stone wins.
    So [1, 1, 0] with your turn: take both from one pile? No, then
    opponent takes the other and wins. The correct play is to take 1
    from either pile, leaving [0, 1, 0] or [1, 0, 0] — opponent wins
    by taking last. Actually [1, 1, 0] is a losing position (nim-sum = 0).

    Better test: [1, 2, 0]. Nim-sum = 3. Take 1 from pile 1 → [1, 1, 0]
    (nim-sum = 0, opponent in losing position).
    """
    eng = _setup_nim()
    state = _set_piles(eng, [1, 2, 0])
    pile, amount, depth = _ai_choice(eng, state)
    # After the move, check that nim-sum is 0 (losing for opponent)
    new_piles = [1, 2, 0]
    new_piles[pile] -= amount
    nim_sum = new_piles[0] ^ new_piles[1] ^ new_piles[2]
    assert nim_sum == 0, (
        f"AI should leave opponent with nim-sum 0, but chose pile {pile} "
        f"amount {amount} leaving piles {new_piles} (nim-sum {nim_sum})"
    )
