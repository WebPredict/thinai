"""End-to-end tests for Nim via the GDL engine."""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Move


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "nim.json"))


@pytest.fixture
def state(engine):
    return engine.initial_state()


class TestInitialState:
    def test_board_type(self, state):
        from engine.gdl.board import TrackBoard
        assert isinstance(state.board, TrackBoard)
        assert state.board.length == 3
        assert state.board.loop is False

    def test_pile_sizes(self, state):
        """Piles start at 3, 4, 5 stones."""
        assert state.count_pieces_at(TrackSpace(0)) == 3
        assert state.count_pieces_at(TrackSpace(1)) == 4
        assert state.count_pieces_at(TrackSpace(2)) == 5

    def test_player1_starts(self, state):
        assert state.current_player == "player1"

    def test_not_terminal(self, engine, state):
        assert engine.check_terminal(state) is None


class TestLegalMoves:
    def test_initial_move_count(self, engine, state):
        """Should have 3+4+5=12 legal moves (each pile * each valid amount)."""
        moves = engine.legal_moves(state)
        assert len(moves) == 12

    def test_move_from_pile_0(self, engine, state):
        """Pile 0 has 3 stones, so amounts 1, 2, 3 are legal."""
        moves = engine.legal_moves(state)
        pile0_moves = [m for m in moves if m.params["pile"] == TrackSpace(0)]
        amounts = sorted(m.params["amount"] for m in pile0_moves)
        assert amounts == [1, 2, 3]

    def test_move_from_pile_2(self, engine, state):
        """Pile 2 has 5 stones, so amounts 1-5 are legal."""
        moves = engine.legal_moves(state)
        pile2_moves = [m for m in moves if m.params["pile"] == TrackSpace(2)]
        amounts = sorted(m.params["amount"] for m in pile2_moves)
        assert amounts == [1, 2, 3, 4, 5]

    def test_empty_pile_no_moves(self, engine, state):
        """After emptying a pile, no moves from it."""
        # Take all 3 from pile 0
        move = Move("take_stones", {"pile": TrackSpace(0), "amount": 3})
        state2 = engine.apply_move(state, move)
        moves = engine.legal_moves(state2)
        pile0_moves = [m for m in moves if m.params["pile"] == TrackSpace(0)]
        assert len(pile0_moves) == 0


class TestGameplay:
    def test_take_reduces_pile(self, engine, state):
        """Taking 2 from pile 1 (4 stones) leaves 2."""
        move = Move("take_stones", {"pile": TrackSpace(1), "amount": 2})
        state2 = engine.apply_move(state, move)
        assert state2.count_pieces_at(TrackSpace(1)) == 2

    def test_turn_alternates(self, engine, state):
        move = Move("take_stones", {"pile": TrackSpace(0), "amount": 1})
        state2 = engine.apply_move(state, move)
        assert state2.current_player == "player2"

    def test_other_piles_unchanged(self, engine, state):
        """Taking from one pile doesn't affect others."""
        move = Move("take_stones", {"pile": TrackSpace(0), "amount": 2})
        state2 = engine.apply_move(state, move)
        assert state2.count_pieces_at(TrackSpace(1)) == 4
        assert state2.count_pieces_at(TrackSpace(2)) == 5

    def test_take_all_from_pile(self, engine, state):
        """Can take all stones from a pile."""
        move = Move("take_stones", {"pile": TrackSpace(2), "amount": 5})
        state2 = engine.apply_move(state, move)
        assert state2.count_pieces_at(TrackSpace(2)) == 0

    def test_win_by_taking_last(self, engine, state):
        """Player who takes the last stone wins."""
        # Clear pile 0 and 1 (leave pile 2 with 1 stone for player1 to take)
        s = state
        s = engine.apply_move(s, Move("take_stones", {"pile": TrackSpace(0), "amount": 3}))  # p1
        s = engine.apply_move(s, Move("take_stones", {"pile": TrackSpace(1), "amount": 4}))  # p2
        s = engine.apply_move(s, Move("take_stones", {"pile": TrackSpace(2), "amount": 4}))  # p1, leaves 1
        s = engine.apply_move(s, Move("take_stones", {"pile": TrackSpace(2), "amount": 1}))  # p2 takes last

        result = engine.check_terminal(s)
        assert result is not None
        assert result.result_type == "win"
        assert result.winner == "player2"

    def test_game_with_random_players(self, engine):
        """A game with random moves should terminate."""
        random.seed(42)
        state = engine.initial_state()
        for _ in range(100):
            result = engine.check_terminal(state)
            if result:
                assert result.result_type == "win"
                assert result.winner in ("player1", "player2")
                return
            moves = engine.legal_moves(state)
            assert len(moves) > 0
            state = engine.apply_move(state, random.choice(moves))
        pytest.fail("Game did not terminate in 100 moves")


class TestNimFeatures:
    def test_features_registered(self):
        from engine.reasoner.features import get_features
        features = get_features("Nim")
        assert len(features) == 3  # xor_position removed (was cheating)
        names = [f.name for f in features]
        assert "total_stones" in names
        assert "pile_balance" in names
        assert "single_pile_count" in names

    def test_total_stones_initial(self, state):
        from engine.reasoner.features import get_features
        features = get_features("Nim")
        total_feat = next(f for f in features if f.name == "total_stones")
        val = total_feat.extract(state, "player1")
        assert val == 1.0  # 12/12 = 1.0
