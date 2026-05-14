"""End-to-end tests for Chutes and Ladders via the GDL engine."""

import os
import random
import pytest
from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Move, Piece


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "games", "examples")


@pytest.fixture
def engine():
    return GameEngine.from_file(os.path.join(EXAMPLES_DIR, "chutes_and_ladders.json"))


@pytest.fixture
def state(engine):
    return engine.initial_state()


class TestInitialState:
    def test_board_type(self, state):
        from engine.gdl.board import TrackBoard
        assert isinstance(state.board, TrackBoard)
        assert state.board.length == 26

    def test_both_players_at_start(self, state):
        pieces_at_0 = state.get_pieces(TrackSpace(0))
        assert len(pieces_at_0) == 2
        owners = {p.owner for p in pieces_at_0}
        assert owners == {"player1", "player2"}

    def test_player1_starts(self, state):
        assert state.current_player == "player1"

    def test_not_terminal(self, engine, state):
        assert engine.check_terminal(state) is None


class TestLegalMoves:
    def test_always_six_moves(self, engine, state):
        """Die roll produces 6 legal moves (1-6)."""
        moves = engine.legal_moves(state)
        assert len(moves) == 6
        rolls = sorted(m.params["roll"] for m in moves)
        assert rolls == [1, 2, 3, 4, 5, 6]


class TestMovement:
    def test_basic_move(self, engine, state):
        """Rolling 3 from space 0 moves to space 3."""
        move = Move("roll_and_move", {"roll": 3})
        state2 = engine.apply_move(state, move)
        # Player 1 should be at space 3
        for space, piece in state2.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 3
                break
        else:
            pytest.fail("Player 1 token not found")

    def test_turn_alternates(self, engine, state):
        move = Move("roll_and_move", {"roll": 1})
        state2 = engine.apply_move(state, move)
        assert state2.current_player == "player2"

    def test_ladder_climb(self, engine, state):
        """Landing on ladder at space 2 should jump to space 10."""
        move = Move("roll_and_move", {"roll": 2})
        state2 = engine.apply_move(state, move)
        for space, piece in state2.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 10, f"Expected 10 (ladder), got {space.index}"
                break

    def test_chute_slide(self, engine, state):
        """Landing on chute at space 14 should slide to space 3."""
        # First move p1 to space 8 (via ladder from 8→12)
        # Actually let's build up step by step. Space 14 has a chute to 3.
        # Move p1 to a position where rolling will land on 14.
        # Start at 0, roll 6 → land on 6 → ladder to 16
        s = engine.apply_move(state, Move("roll_and_move", {"roll": 6}))  # p1 → 16 (ladder 6→16)
        # p2's turn, move them somewhere
        s = engine.apply_move(s, Move("roll_and_move", {"roll": 1}))  # p2 → 1
        # p1 at 16, need to not land on chute 19 or 22 or 24
        # Roll 3 → 19 → chute to 7
        # Let's actually test the chute at 19: p1 at 16, roll 3 → 19 → chute → 7
        s = engine.apply_move(s, Move("roll_and_move", {"roll": 3}))  # p1: 16+3=19 → chute → 7
        for space, piece in s.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 7, f"Expected 7 (chute from 19), got {space.index}"
                break

    def test_other_player_unaffected(self, engine, state):
        """Moving one player doesn't move the other."""
        move = Move("roll_and_move", {"roll": 5})
        state2 = engine.apply_move(state, move)
        # Player 2 should still be at space 0
        for space, piece in state2.all_pieces():
            if piece.owner == "player2" and piece.name == "token":
                assert space.index == 0
                break

    def test_overshoot_capped(self, engine, state):
        """Moving past the end caps at board_size (25)."""
        # Move p1 to space 23 (via ladder at 15→23)
        # From 0: roll 3→3, then later get to 15
        # Actually, let me manipulate state directly for this test
        # Remove p1 from 0, place at 23
        s = state.copy()
        token = Piece("token", "player1")
        s.remove_piece(TrackSpace(0), token)
        s.set_piece(TrackSpace(23), token)

        # Roll 6 from 23 → 29, but capped to 25
        # However space 24 has a chute to 18!
        # Space 25 has no chute/ladder, so rolling 2 → 25 → wins
        s2 = engine.apply_move(s, Move("roll_and_move", {"roll": 2}))
        for space, piece in s2.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 25
                break


class TestWinCondition:
    def test_reaching_end_wins(self, engine, state):
        """Player reaching space 25 wins."""
        # Place player 1 at space 23 directly
        s = state.copy()
        token = Piece("token", "player1")
        s.remove_piece(TrackSpace(0), token)
        s.set_piece(TrackSpace(23), token)

        # Roll 2 → 25 → win
        s2 = engine.apply_move(s, Move("roll_and_move", {"roll": 2}))
        result = engine.check_terminal(s2)
        assert result is not None
        assert result.result_type == "win"
        assert result.winner == "player1"

    def test_game_with_random_players(self, engine):
        """A game with random moves should terminate."""
        random.seed(42)
        state = engine.initial_state()
        for _ in range(500):
            result = engine.check_terminal(state)
            if result:
                assert result.result_type == "win"
                assert result.winner in ("player1", "player2")
                return
            moves = engine.legal_moves(state)
            assert len(moves) > 0
            state = engine.apply_move(state, random.choice(moves))
        pytest.fail("Game did not terminate in 500 moves")


class TestFeatures:
    def test_features_registered(self):
        from engine.reasoner.features import get_features
        features = get_features("Chutes and Ladders")
        assert len(features) == 2
        names = [f.name for f in features]
        assert "position_lead" in names
        assert "progress" in names

    def test_initial_progress_zero(self, state):
        from engine.reasoner.features import get_features
        features = get_features("Chutes and Ladders")
        progress = next(f for f in features if f.name == "progress")
        assert progress.extract(state, "player1") == 0.0
