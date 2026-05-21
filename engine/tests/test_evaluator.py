"""Tests for the learnable evaluator and feature extraction."""

import os
import pytest
from engine.gdl.state import GameState, Piece
from engine.gdl.board import GridBoard, GridSpace, TrackBoard, TrackSpace
from engine.reasoner.evaluator import LearnableEval
from engine.reasoner.features import (
    get_features, TTT_FEATURES, C4_FEATURES, MANCALA_FEATURES, REVERSI_FEATURES,
    _ttt_center_control, _ttt_corner_count, _ttt_threats,
    _c4_center_column, _c4_three_in_row,
    _mancala_store_lead, _mancala_extra_turn_opportunities,
    _reversi_corner_count, _reversi_disc_count, _reversi_x_square_penalty,
)


# --- Feature extraction tests ---

class TestTTTFeatures:
    def _make_state(self):
        return GameState(GridBoard(3, 3))

    def test_center_control_empty(self):
        state = self._make_state()
        assert _ttt_center_control(state, "player1") == 0.0

    def test_center_control_owned(self):
        state = self._make_state()
        state.set_piece(GridSpace(1, 1), Piece("mark", "player1"))
        assert _ttt_center_control(state, "player1") == 1.0
        assert _ttt_center_control(state, "player2") == -1.0

    def test_corner_count(self):
        state = self._make_state()
        state.set_piece(GridSpace(0, 0), Piece("mark", "player1"))
        state.set_piece(GridSpace(2, 2), Piece("mark", "player1"))
        state.set_piece(GridSpace(0, 2), Piece("mark", "player2"))
        # P1 has 2 corners, P2 has 1. Score for P1: (2-1)/4 = 0.25
        assert _ttt_corner_count(state, "player1") == 0.25
        assert _ttt_corner_count(state, "player2") == -0.25

    def test_threats_winning_move(self):
        state = self._make_state()
        state.set_piece(GridSpace(0, 0), Piece("mark", "player1"))
        state.set_piece(GridSpace(0, 1), Piece("mark", "player1"))
        # P1 has a threat at (0, 2) for horizontal win
        threats = _ttt_threats(state, "player1")
        assert threats > 0


class TestC4Features:
    def _make_state(self):
        return GameState(GridBoard(6, 7))

    def test_center_column_empty(self):
        state = self._make_state()
        assert _c4_center_column(state, "player1") == 0.0

    def test_center_column_advantage(self):
        state = self._make_state()
        state.set_piece(GridSpace(5, 3), Piece("disc", "player1"))
        val = _c4_center_column(state, "player1")
        assert val > 0

    def test_three_in_row(self):
        state = self._make_state()
        for c in range(3):
            state.set_piece(GridSpace(5, c), Piece("disc", "player1"))
        val = _c4_three_in_row(state, "player1")
        assert val > 0


class TestMancalaFeatures:
    def _make_state(self):
        state = GameState(TrackBoard(14, loop=True))
        # Standard setup: 4 stones per pit
        for i in range(6):
            for _ in range(4):
                state.add_piece(TrackSpace(i), Piece("stone", None))
        for i in range(7, 13):
            for _ in range(4):
                state.add_piece(TrackSpace(i), Piece("stone", None))
        return state

    def test_store_lead_initial(self):
        state = self._make_state()
        assert _mancala_store_lead(state, "player1") == 0.0

    def test_store_lead_advantage(self):
        state = self._make_state()
        for _ in range(5):
            state.add_piece(TrackSpace(6), Piece("stone", None))
        val = _mancala_store_lead(state, "player1")
        assert val > 0

    def test_extra_turn_opportunities(self):
        state = GameState(TrackBoard(14, loop=True))
        # Put exactly 6 stones in pit 0 → lands on store (index 6)
        for _ in range(6):
            state.add_piece(TrackSpace(0), Piece("stone", None))
        val = _mancala_extra_turn_opportunities(state, "player1")
        assert val > 0


class TestReversiFeatures:
    def _make_state(self):
        state = GameState(GridBoard(8, 8))
        # Standard reversi opening
        state.set_piece(GridSpace(3, 3), Piece("disc", "player1"))
        state.set_piece(GridSpace(3, 4), Piece("disc", "player2"))
        state.set_piece(GridSpace(4, 3), Piece("disc", "player2"))
        state.set_piece(GridSpace(4, 4), Piece("disc", "player1"))
        return state

    def test_disc_count_equal(self):
        state = self._make_state()
        assert _reversi_disc_count(state, "player1") == 0.0

    def test_corner_count_empty(self):
        state = self._make_state()
        assert _reversi_corner_count(state, "player1") == 0.0

    def test_corner_count_advantage(self):
        state = self._make_state()
        state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        assert _reversi_corner_count(state, "player1") == 0.25

    def test_x_square_penalty(self):
        state = self._make_state()
        # Own X-square (1,1) with empty corner (0,0) — bad
        state.set_piece(GridSpace(1, 1), Piece("disc", "player1"))
        val = _reversi_x_square_penalty(state, "player1")
        assert val < 0  # Penalty for owning X-square near empty corner


# --- LearnableEval tests ---

class TestLearnableEval:
    def test_create_with_defaults(self):
        ev = LearnableEval("Reversi")
        assert len(ev.features) == 5
        assert len(ev.weights) == 5
        assert ev.generation == 0

    def test_create_with_gdl_auto_features(self):
        """Games without L0 features should auto-generate from GDL."""
        import json
        from pathlib import Path
        gdl = json.loads(Path("engine/games/examples/tictactoe.json").read_text())
        ev = LearnableEval("Tic-Tac-Toe", gdl=gdl)
        assert len(ev.features) >= 4  # auto-features generate several
        assert len(ev.weights) == len(ev.features)

    def test_unknown_game_raises(self):
        with pytest.raises(ValueError):
            LearnableEval("Unknown Game")

    def test_zero_weights_near_zero_eval(self):
        ev = LearnableEval("Reversi", weights=[0, 0, 0, 0, 0])
        state = GameState(GridBoard(8, 8))
        assert ev(state, "player1") == 0.0

    def test_eval_changes_with_state(self):
        ev = LearnableEval("Reversi", weights=[1.0, 0.5, 0.3, 0.2, 0.1])
        state = GameState(GridBoard(8, 8))
        score_empty = ev(state, "player1")

        state.set_piece(GridSpace(0, 0), Piece("disc", "player1"))
        score_corner = ev(state, "player1")
        # Owning a corner should change score
        assert score_corner != score_empty

    def test_update_weights_win(self):
        ev = LearnableEval("Reversi", weights=[0, 0, 0, 0, 0], learning_rate=0.5)
        trace = [
            {"features": [1.0, 0.5, 0.0, 0.0, 0.0], "move_index": 4, "total_moves": 5},
        ]
        ev.update_weights(trace, outcome=1.0)
        assert ev.weights[0] > 0
        assert ev.weights[1] > 0
        assert ev.generation == 1

    def test_update_weights_loss(self):
        ev = LearnableEval("Reversi", weights=[0.5, 0.5, 0.5, 0.5, 0.5], learning_rate=0.5)
        trace = [
            {"features": [1.0, 0.5, 0.0, 0.0, 0.0], "move_index": 4, "total_moves": 5},
        ]
        ev.update_weights(trace, outcome=-1.0)
        assert ev.weights[0] < 0.5

    def test_history_recorded(self):
        ev = LearnableEval("Reversi", weights=[0, 0, 0, 0, 0])
        trace = [{"features": [1.0, 0.0, 0.0, 0.0, 0.0], "move_index": 0, "total_moves": 1}]
        ev.update_weights(trace, 1.0)
        ev.update_weights(trace, -1.0)
        assert len(ev.history) == 2
        assert ev.history[0]["generation"] == 1
        assert ev.history[1]["generation"] == 2

    def test_extract_features(self):
        ev = LearnableEval("Reversi")
        state = GameState(GridBoard(8, 8))
        feats = ev.extract_features(state, "player1")
        assert len(feats) == 5
        assert all(isinstance(f, float) for f in feats)

    def test_weight_summary(self):
        ev = LearnableEval("Reversi", weights=[0.8, -0.2, 0.5, 0.1, 0.0])
        summary = ev.weight_summary()
        assert len(summary) == 5
        assert summary[0]["weight"] == 0.8

    def test_serialization_roundtrip(self):
        ev = LearnableEval("Reversi", weights=[0.1, 0.2, 0.3, 0.4, 0.5])
        ev.generation = 10
        data = ev.to_dict()
        ev2 = LearnableEval.from_dict(data)
        assert ev2.weights == ev.weights
        assert ev2.generation == 10
        assert ev2.game_name == "Reversi"

    def test_feature_registry(self):
        assert len(get_features("Tic-Tac-Toe")) == 4
        assert len(get_features("Connect Four")) == 4
        assert len(get_features("Mancala (Kalah)")) == 5
        assert len(get_features("Reversi")) == 5
        assert len(get_features("Unknown")) == 0
