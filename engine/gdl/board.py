"""Board models for ThinAI GDL.

Boards are spatial structures that hold pieces. Each board type
provides space enumeration, adjacency, and direction information.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# Direction vectors for grid topologies
RECT4_DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # E, S, W, N
RECT8_DIRS = [
    (-1, 0), (-1, 1), (0, 1), (1, 1),   # N, NE, E, SE
    (1, 0), (1, -1), (0, -1), (-1, -1),  # S, SW, W, NW
]


@dataclass(frozen=True)
class GridSpace:
    """A position on a grid board."""
    row: int
    col: int

    def __repr__(self):
        return f"({self.row},{self.col})"


@dataclass(frozen=True)
class TrackSpace:
    """A position on a track board."""
    index: int

    def __repr__(self):
        return f"[{self.index}]"


class GridBoard:
    """A rectangular grid board with configurable topology."""

    def __init__(self, rows: int, cols: int, topology: str = "rect8"):
        self.rows = rows
        self.cols = cols
        self.topology = topology
        if topology == "rect4":
            self.direction_vectors = RECT4_DIRS
        elif topology == "rect8":
            self.direction_vectors = RECT8_DIRS
        else:
            raise ValueError(f"Unsupported grid topology: {topology}")

        self._spaces = tuple(
            GridSpace(r, c) for r in range(rows) for c in range(cols)
        )

    @property
    def spaces(self) -> tuple[GridSpace, ...]:
        return self._spaces

    def space_at(self, row: int, col: int) -> Optional[GridSpace]:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return GridSpace(row, col)
        return None

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    def neighbors(self, space: GridSpace) -> list[GridSpace]:
        result = []
        for dr, dc in self.direction_vectors:
            nr, nc = space.row + dr, space.col + dc
            if self.in_bounds(nr, nc):
                result.append(GridSpace(nr, nc))
        return result

    def directions(self) -> list[tuple[int, int]]:
        return list(self.direction_vectors)

    @classmethod
    def from_gdl(cls, board_spec: dict) -> "GridBoard":
        grid = board_spec["grid"]
        return cls(
            rows=grid["rows"],
            cols=grid["cols"],
            topology=grid.get("topology", "rect8"),
        )


class TrackBoard:
    """A linear or circular track board."""

    def __init__(self, length: int, loop: bool = False):
        self.length = length
        self.loop = loop
        self._spaces = tuple(TrackSpace(i) for i in range(length))

    @property
    def spaces(self) -> tuple[TrackSpace, ...]:
        return self._spaces

    def space_at(self, index: int) -> Optional[TrackSpace]:
        if self.loop:
            return TrackSpace(index % self.length)
        if 0 <= index < self.length:
            return TrackSpace(index)
        return None

    def next_space(self, space: TrackSpace) -> Optional[TrackSpace]:
        return self.space_at(space.index + 1)

    def prev_space(self, space: TrackSpace) -> Optional[TrackSpace]:
        return self.space_at(space.index - 1)

    @classmethod
    def from_gdl(cls, board_spec: dict) -> "TrackBoard":
        track = board_spec["track"]
        return cls(
            length=track["length"],
            loop=track.get("loop", False),
        )


def create_board(board_spec: dict):
    """Create the appropriate board type from a GDL board specification."""
    board_type = board_spec["type"]
    if board_type == "grid":
        return GridBoard.from_gdl(board_spec)
    elif board_type == "track":
        return TrackBoard.from_gdl(board_spec)
    else:
        raise ValueError(f"Unsupported board type: {board_type}")
