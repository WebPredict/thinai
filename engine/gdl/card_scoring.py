"""Generic card combination scoring for ThinAI.

Reusable primitives for scoring card combinations — subsets summing to
a target, rank-based pairs, cross-suit runs with multiplicity, flushes,
and sequential play patterns (pegging-style).

Used by: Cribbage, and available to any card game needing combination scoring.
Complements melds.py which handles same-suit runs and same-rank sets.
"""

from __future__ import annotations
from collections import Counter
from itertools import combinations
from typing import Optional

from engine.gdl.cards import Card, RANK_VALUES


# === Rank value maps (games can pass their own) ===

# Standard: A=14, 2=2, ..., K=13
STANDARD_RANK_VALUES = dict(RANK_VALUES)

# Cribbage peg values: A=1, face cards=10
CRIBBAGE_PEG_VALUES = {
    "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10,
}

# Cribbage rank order (for runs): A=1, 2=2, ..., K=13
CRIBBAGE_RANK_ORDER = {
    "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13,
}


def find_subsets_summing_to(cards: list[Card], target: int,
                            rank_values: Optional[dict] = None) -> list[list[Card]]:
    """Find all card subsets (size 2-5) whose rank values sum to target.

    Args:
        cards: Cards to search through (typically 4-5 cards).
        target: Target sum (e.g., 15 for Cribbage).
        rank_values: Rank-to-value mapping. Defaults to standard (A=14).

    Returns:
        List of card lists, each summing to target.
    """
    values = rank_values or STANDARD_RANK_VALUES
    results = []
    for size in range(2, len(cards) + 1):
        for combo in combinations(cards, size):
            if sum(values.get(c.rank, 0) for c in combo) == target:
                results.append(list(combo))
    return results


def count_rank_pairs(cards: list[Card]) -> int:
    """Count same-rank pairs. Each pair = 2 points.

    For N cards of the same rank, there are N*(N-1)/2 pairs.
    E.g., three 5s = 3 pairs = 6 points.

    Returns:
        Total pair points (count_of_pairs * 2).
    """
    ranks = Counter(c.rank for c in cards)
    return sum((n * (n - 1) // 2) * 2 for n in ranks.values())


def count_rank_run_points(cards: list[Card], min_size: int = 3,
                          rank_order: Optional[dict] = None) -> int:
    """Score cross-suit runs with multiplicity.

    Groups cards by rank, finds maximal consecutive rank sequences of
    min_size or longer, and scores: run_length * product_of_group_sizes.

    Examples (Cribbage rank order):
        [3, 4, 5]       -> 3 (one run of 3)
        [3, 3, 4, 5]    -> 6 (two runs of 3: each 3 pairs with 4-5)
        [3, 3, 4, 4, 5] -> 12 (four runs of 3: 2*2*1)
        [3, 4, 5, 6]    -> 4 (one run of 4)

    Args:
        cards: Cards to evaluate.
        min_size: Minimum run length (default 3).
        rank_order: Rank-to-order mapping for sequencing. Defaults to standard.

    Returns:
        Total run points.
    """
    order = rank_order or STANDARD_RANK_VALUES
    # Group cards by their rank order value
    by_order: dict[int, int] = Counter()
    for c in cards:
        val = order.get(c.rank, 0)
        if val > 0:
            by_order[val] += 1

    if len(by_order) < min_size:
        return 0

    sorted_vals = sorted(by_order.keys())
    total_points = 0

    # Find all maximal consecutive sequences
    i = 0
    while i < len(sorted_vals):
        # Start a new potential run
        run_start = i
        j = i + 1
        while j < len(sorted_vals) and sorted_vals[j] == sorted_vals[j - 1] + 1:
            j += 1
        run_length = j - run_start

        if run_length >= min_size:
            # Find the longest sub-runs of at least min_size
            # For Cribbage, we want the maximal run, not sub-runs
            # Multiplicity = product of group sizes in the run
            multiplicity = 1
            for k in range(run_start, j):
                multiplicity *= by_order[sorted_vals[k]]
            total_points += run_length * multiplicity

        i = j if run_length > 1 else i + 1

    return total_points


def count_flush(cards: list[Card], min_count: int = 4) -> int:
    """Count cards of the same suit if at least min_count match.

    Args:
        cards: Cards to check.
        min_count: Minimum same-suit cards required (default 4).

    Returns:
        Count of matching suit cards, or 0 if below min_count.
    """
    if not cards:
        return 0
    suits = Counter(c.suit for c in cards)
    best_count = max(suits.values())
    return best_count if best_count >= min_count else 0


def sequential_play_pairs(play_history_ranks: list[str]) -> int:
    """Score pairs from the end of a sequential play history.

    In pegging-style play, only consecutive matching ranks count.
    [7, 7] = 2 pts (pair), [7, 7, 7] = 6 pts (triple), [7, 7, 7, 7] = 12 pts.
    [7, 3, 7] = 0 (the 3 breaks the sequence).

    Args:
        play_history_ranks: Ordered list of ranks as played.

    Returns:
        Pair points (0, 2, 6, or 12).
    """
    if len(play_history_ranks) < 2:
        return 0

    last_rank = play_history_ranks[-1]
    match_count = 1
    for i in range(len(play_history_ranks) - 2, -1, -1):
        if play_history_ranks[i] == last_rank:
            match_count += 1
        else:
            break

    # nC2 * 2 for the matching cards
    return (match_count * (match_count - 1) // 2) * 2


def sequential_play_run(play_history_ranks: list[str], min_size: int = 3,
                        rank_order: Optional[dict] = None) -> int:
    """Find the longest run ending at the last played card.

    Checks suffixes of the play history: takes the last N ranks, sorts them,
    and checks if they form a consecutive sequence (no gaps, no duplicates).
    Returns the longest such run length.

    Args:
        play_history_ranks: Ordered list of ranks as played.
        min_size: Minimum run length (default 3).
        rank_order: Rank-to-order mapping. Defaults to standard.

    Returns:
        Length of the longest valid run, or 0 if none found.
    """
    order = rank_order or STANDARD_RANK_VALUES
    n = len(play_history_ranks)
    if n < min_size:
        return 0

    best = 0
    # Check suffixes from longest to shortest
    for length in range(min(n, 7), min_size - 1, -1):
        suffix = play_history_ranks[-length:]
        values = [order.get(r, 0) for r in suffix]
        # Must have no duplicate values and form a consecutive sequence
        if len(set(values)) != length:
            continue
        sorted_vals = sorted(values)
        if sorted_vals[-1] - sorted_vals[0] == length - 1:
            best = length
            break  # Found longest, stop

    return best
