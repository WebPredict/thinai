"""AI competency tests for Mancala (Kalah).

Verifies the Reasoner (with EffortAllocator) makes obvious correct moves:
taking extra turns and making captures when possible.
"""

from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Piece
from engine.reasoner.reasoner import Reasoner
from engine.metacognition.effort import EffortAllocator


def _setup_mancala():
    return GameEngine.from_file("engine/games/examples/mancala.json")


def _ai_choice(eng, state, max_depth=6):
    allocator = EffortAllocator()
    reasoner = Reasoner(eng, max_depth=max_depth, effort_allocator=allocator)
    move = reasoner.choose_move(state)
    pit = move.params["pit"]
    return pit.index, reasoner.last_depth_used


def _find_pit_move(eng, state, pit_index):
    """Find the legal move for picking a specific pit."""
    moves = eng.legal_moves(state)
    for m in moves:
        pit = m.params.get("pit")
        if pit is not None and pit.index == pit_index:
            return m
    raise ValueError(f"No legal move for pit {pit_index}. Legal: {moves}")


def _set_pits(eng, pit_counts, current_player="player1"):
    """Create a Mancala state with specific pit stone counts.

    pit_counts: list of 14 ints (pits 0-5 = P1, 6 = P1 store,
                pits 7-12 = P2, 13 = P2 store).
    """
    state = eng.initial_state()
    # Clear all spaces
    for i in range(14):
        space = TrackSpace(i)
        state.pieces.pop(space, None)
    # Fill to desired counts
    for i, count in enumerate(pit_counts):
        if count > 0:
            space = TrackSpace(i)
            state.pieces[space] = [Piece("stone", None) for _ in range(count)]
    state.current_player = current_player
    state.state_vars["last_pit_is_store"] = False
    state.state_vars["last_pit_index"] = -1
    return state


def test_takes_extra_turn_when_it_leads_to_win():
    """AI should sow from a pit that gives an extra turn when it leads to
    winning the endgame.

    Set up a near-endgame where P1 has pits [0, 0, 0, 0, 0, 1] and store=23.
    P2 has pits [0, 0, 0, 0, 0, 1] and store=23.
    P1 sows pit 5 (1 stone) -> lands in store (index 6), gets extra turn,
    but P1 has no more stones so the game ends. P1 store = 24.
    Actually both have 1 stone — if P1 picks pit 5, the stone goes to store,
    P1 gets extra turn, no more pits, game ends with P1 at 24 vs P2 at 24. Draw.

    Better: P1 store=25, P2 store=22. If P1 sows pit 5 into store = 26 total,
    game ends. P2 remaining stones (1) go to P2 store = 23. P1 wins 26-23.
    """
    eng = _setup_mancala()
    # P1 pits: [0,0,0,0,0,1], P1 store: 25
    # P2 pits: [0,0,0,0,0,1], P2 store: 21
    state = _set_pits(eng, [0, 0, 0, 0, 0, 1,  25,  0, 0, 0, 0, 0, 1, 21])
    pit, depth = _ai_choice(eng, state)
    assert pit == 5, (
        f"AI should sow pit 5 to score into store and win, chose pit {pit}"
    )


def test_captures_when_landing_on_empty_own_pit():
    """AI should sow into an empty own-side pit to capture opponent's stones.

    Set up: P1 pit 0 has 1 stone, P1 pit 1 is empty, opponent pit 11
    (opposite of pit 1) has 6 stones. Sowing from pit 0 lands on pit 1
    (empty, own side) — captures opponent's 6 stones from pit 11.
    """
    eng = _setup_mancala()
    # P1 pits: [1, 0, 0, 0, 0, 1], P1 store: 0
    # P2 pits: [0, 0, 0, 0, 6, 0], P2 store: 0
    # Pit 11 (opposite of pit 1) = index 11 = P2's 5th pit
    # Sowing from pit 0 (1 stone) -> lands on pit 1 (empty, own side)
    # -> captures pit 11's 6 stones
    state = _set_pits(eng, [1, 0, 0, 0, 0, 1,  0,  0, 0, 0, 0, 6, 0, 0])
    pit, depth = _ai_choice(eng, state)
    assert pit == 0, (
        f"AI should sow from pit 0 to capture 6 stones, chose pit {pit}"
    )


def test_only_legal_move_chosen():
    """When only one pit has stones, AI must choose it.

    This is a basic sanity check that the AI picks the only available move.
    """
    eng = _setup_mancala()
    # P1 has stones only in pit 3, everything else empty on P1 side.
    # P2 has some stones to prevent game-end.
    state = _set_pits(eng, [0, 0, 0, 2, 0, 0,  10,  4, 4, 4, 4, 4, 4, 10])
    pit, depth = _ai_choice(eng, state)
    assert pit == 3, (
        f"AI should sow from pit 3 (the only pit with stones), chose pit {pit}"
    )
