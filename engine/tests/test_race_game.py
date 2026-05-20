"""End-to-end tests for race games parsed from natural language."""

import pytest
from engine.parser.natural import parse_natural
from engine.engine import GameEngine
from engine.gdl.board import TrackSpace
from engine.gdl.state import Move, Piece, setup_initial_state


# --- Parser tests ---

class TestRaceParser:
    def test_basic_race_parses_track(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        assert gdl["board"]["type"] == "track"
        assert gdl["board"]["track"]["length"] == 20

    def test_race_with_space_number(self):
        gdl = parse_natural(
            "Roll dice, move forward. Land on an opponent's space to send them "
            "back to start. First to space 30 wins."
        )
        assert gdl["board"]["type"] == "track"
        assert gdl["board"]["track"]["length"] == 30

    def test_race_has_roll_and_move_rule(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        assert len(gdl["rules"]) >= 1
        rule = gdl["rules"][0]
        assert rule["name"] == "roll_and_move"
        assert rule["action"] == "chance"
        assert any("roll_and_move" in e for e in rule["effects"])

    def test_race_has_win_condition(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        assert any(ec["type"] == "win" for ec in gdl["end_conditions"])

    def test_race_has_setup(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        assert any(a["action"] == "race_setup" for a in gdl["setup"])

    def test_race_has_token_pieces(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        assert any(p["name"] == "token" for p in gdl["pieces"])

    def test_bump_race_detection(self):
        gdl = parse_natural(
            "Roll dice, move forward. Land on an opponent's space to send them "
            "back to start. First to space 30 wins."
        )
        rule = gdl["rules"][0]
        assert "roll_and_move_bump" in rule["effects"][0]

    def test_race_has_state_vars(self):
        gdl = parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )
        var_names = [v["name"] for v in gdl["state_vars"]]
        assert "last_play" in var_names

    def test_race_name_inference(self):
        gdl = parse_natural(
            "Two players race along a 10-space track. Roll and move. First to the end wins."
        )
        assert "Race" in gdl["meta"]["name"]


# --- Engine tests ---

class TestRaceEngine:
    @pytest.fixture
    def gdl(self):
        return parse_natural(
            "Two players roll a die and move their piece along a 20-space track. "
            "First to reach the end wins."
        )

    @pytest.fixture
    def engine(self, gdl):
        return GameEngine(gdl)

    @pytest.fixture
    def state(self, engine):
        return engine.initial_state()

    def test_initial_state_tokens_at_start(self, state):
        pieces_at_0 = state.get_pieces(TrackSpace(0))
        assert len(pieces_at_0) == 2
        owners = {p.owner for p in pieces_at_0}
        assert owners == {"player1", "player2"}

    def test_six_legal_moves(self, engine, state):
        moves = engine.legal_moves(state)
        assert len(moves) == 6
        rolls = sorted(m.params["roll"] for m in moves)
        assert rolls == [1, 2, 3, 4, 5, 6]

    def test_basic_move(self, engine, state):
        move = Move("roll_and_move", {"roll": 4})
        s2 = engine.apply_move(state, move)
        # Player 1 should be at space 4
        found = False
        for space, piece in s2.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 4
                found = True
                break
        assert found, "Player 1 token not found"

    def test_turn_alternates(self, engine, state):
        s2 = engine.apply_move(state, Move("roll_and_move", {"roll": 1}))
        assert s2.current_player == "player2"

    def test_not_terminal_initially(self, engine, state):
        assert engine.check_terminal(state) is None

    def test_reaching_end_wins(self, engine, state):
        # Move player 1 near the end (space 18), then roll 1 to reach 19 (last space of 20)
        s = state.copy()
        token = Piece("token", "player1")
        s.remove_piece(TrackSpace(0), token)
        s.add_piece(TrackSpace(18), token)

        s2 = engine.apply_move(s, Move("roll_and_move", {"roll": 1}))
        result = engine.check_terminal(s2)
        assert result is not None
        assert result.winner == "player1"

    def test_overshoot_caps_at_end(self, engine, state):
        s = state.copy()
        token = Piece("token", "player1")
        s.remove_piece(TrackSpace(0), token)
        s.add_piece(TrackSpace(17), token)

        s2 = engine.apply_move(s, Move("roll_and_move", {"roll": 6}))
        # Should be capped at space 19 (length 20, 0-indexed)
        for space, piece in s2.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 19
                break

    def test_play_to_completion(self, engine, state):
        """Play a full game and verify it terminates."""
        s = state
        max_turns = 200
        for turn in range(max_turns):
            result = engine.check_terminal(s)
            if result is not None:
                assert result.winner in ("player1", "player2")
                return
            moves = engine.legal_moves(s)
            assert len(moves) > 0, f"No legal moves on turn {turn}"
            # Always pick max roll to ensure game ends
            best_move = max(moves, key=lambda m: m.params["roll"])
            s = engine.apply_move(s, best_move)
        pytest.fail("Game did not terminate within 200 turns")


class TestBumpRaceEngine:
    @pytest.fixture
    def gdl(self):
        return parse_natural(
            "Roll dice, move forward. Land on an opponent's space to send them "
            "back to start. First to space 30 wins."
        )

    @pytest.fixture
    def engine(self, gdl):
        return GameEngine(gdl)

    @pytest.fixture
    def state(self, engine):
        return engine.initial_state()

    def test_bump_opponent(self, engine, state):
        # Move p1 to space 3
        s = engine.apply_move(state, Move("roll_and_move", {"roll": 3}))
        # p2 turn, move to space 3 (should bump p1 back to 0)
        s = engine.apply_move(s, Move("roll_and_move", {"roll": 3}))
        # Check p1 is back at 0
        for space, piece in s.all_pieces():
            if piece.owner == "player1" and piece.name == "token":
                assert space.index == 0, f"Expected p1 at 0 (bumped), got {space.index}"
                break
        # Check p2 is at 3
        for space, piece in s.all_pieces():
            if piece.owner == "player2" and piece.name == "token":
                assert space.index == 3
                break

    def test_bump_race_track_length(self, state):
        assert state.board.length == 30
