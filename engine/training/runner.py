"""Game runner for training and evaluation."""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from engine.engine import GameEngine
from engine.gdl.state import GameState, Move, GameResult


@dataclass
class GameRecord:
    """Record of a single game."""
    game_number: int
    winner: Optional[str]
    result_type: str
    num_moves: int
    duration_ms: float


@dataclass
class RunResults:
    """Aggregate results from a run of games."""
    game_name: str
    player1_type: str
    player2_type: str
    total_games: int
    player1_wins: int = 0
    player2_wins: int = 0
    draws: int = 0
    total_moves: int = 0
    total_duration_ms: float = 0
    games: list = field(default_factory=list)

    @property
    def player1_win_rate(self) -> float:
        return self.player1_wins / self.total_games if self.total_games else 0

    @property
    def player2_win_rate(self) -> float:
        return self.player2_wins / self.total_games if self.total_games else 0

    @property
    def draw_rate(self) -> float:
        return self.draws / self.total_games if self.total_games else 0

    @property
    def avg_game_length(self) -> float:
        return self.total_moves / self.total_games if self.total_games else 0

    def summary(self) -> str:
        return (
            f"{self.game_name}: {self.player1_type} vs {self.player2_type}\n"
            f"  Games: {self.total_games}\n"
            f"  P1 wins: {self.player1_wins} ({self.player1_win_rate:.0%})\n"
            f"  P2 wins: {self.player2_wins} ({self.player2_win_rate:.0%})\n"
            f"  Draws:   {self.draws} ({self.draw_rate:.0%})\n"
            f"  Avg moves: {self.avg_game_length:.1f}\n"
            f"  Total time: {self.total_duration_ms:.0f}ms"
        )

    def to_dict(self) -> dict:
        return {
            "game_name": self.game_name,
            "player1_type": self.player1_type,
            "player2_type": self.player2_type,
            "total_games": self.total_games,
            "player1_wins": self.player1_wins,
            "player2_wins": self.player2_wins,
            "draws": self.draws,
            "player1_win_rate": self.player1_win_rate,
            "avg_game_length": self.avg_game_length,
            "total_duration_ms": self.total_duration_ms,
        }


class GameRunner:
    """Run games between two players and collect results."""

    def __init__(self, engine: GameEngine, max_moves: int = 200):
        self.engine = engine
        self.max_moves = max_moves

    def run(self, player1, player2, num_games: int,
            player1_name: str = "player1",
            player2_name: str = "player2") -> RunResults:
        """Run num_games games and return results."""
        results = RunResults(
            game_name=self.engine.meta["name"],
            player1_type=player1_name,
            player2_type=player2_name,
            total_games=num_games,
        )

        for i in range(num_games):
            record = self._play_game(player1, player2, i + 1)
            results.games.append(record)
            results.total_moves += record.num_moves
            results.total_duration_ms += record.duration_ms

            if record.winner == "player1":
                results.player1_wins += 1
            elif record.winner == "player2":
                results.player2_wins += 1
            else:
                results.draws += 1

        return results

    def _play_game(self, player1, player2, game_number: int) -> GameRecord:
        """Play a single game and return the record."""
        start = time.monotonic()
        state = self.engine.initial_state()
        num_moves = 0

        for _ in range(self.max_moves):
            result = self.engine.check_terminal(state)
            if result:
                duration = (time.monotonic() - start) * 1000
                return GameRecord(
                    game_number=game_number,
                    winner=result.winner,
                    result_type=result.result_type,
                    num_moves=num_moves,
                    duration_ms=duration,
                )

            if state.current_player == "player1":
                move = player1.choose_move(state)
            else:
                move = player2.choose_move(state)

            if move is None:
                break

            state = self.engine.apply_move(state, move)
            num_moves += 1

        # Max moves reached or no move available
        result = self.engine.check_terminal(state)
        duration = (time.monotonic() - start) * 1000
        return GameRecord(
            game_number=game_number,
            winner=result.winner if result else None,
            result_type=result.result_type if result else "incomplete",
            num_moves=num_moves,
            duration_ms=duration,
        )


def run_benchmark(game_path: str, num_games: int = 100, depth: int = 6):
    """Run a benchmark: reasoner vs random opponent."""
    from engine.training.opponents import RandomOpponent, ReasonerOpponent

    engine = GameEngine.from_file(game_path)
    runner = GameRunner(engine)

    player1 = ReasonerOpponent(engine, max_depth=depth)
    player2 = RandomOpponent(engine)

    results = runner.run(player1, player2, num_games,
                        player1_name=f"reasoner(depth={depth})",
                        player2_name="random")
    return results


if __name__ == "__main__":
    import sys
    import os

    games_dir = os.path.join(os.path.dirname(__file__), "..", "games", "examples")

    game_name = sys.argv[1] if len(sys.argv) > 1 else "tictactoe"
    num_games = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    game_path = os.path.join(games_dir, f"{game_name}.json")
    results = run_benchmark(game_path, num_games, depth)
    print(results.summary())
