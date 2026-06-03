"""Generic meld system for card games.

Provides reusable meld detection, validation, and scoring for any card game
that uses sets (same rank) or runs (sequential same suit). Supports wild cards.

Used by: Canasta, Gin Rummy (future), and any novel game mentioning melds.
"""

from __future__ import annotations
from collections import defaultdict
from typing import Optional

from engine.gdl.cards import Card, RANK_VALUES


# Card point values for scoring (Canasta-style, configurable per game)
DEFAULT_CARD_VALUES = {
    "3": 5, "4": 5, "5": 5, "6": 5, "7": 5,
    "8": 10, "9": 10, "10": 10, "J": 10, "Q": 10, "K": 10,
    "A": 20, "2": 20, "Joker": 50,
}


def find_sets(cards: list[Card], min_size: int = 3,
              wild_ranks: Optional[list[str]] = None) -> list[list[Card]]:
    """Find all valid sets (groups of same rank) from cards.

    Args:
        cards: list of Card objects
        min_size: minimum cards per set (default 3)
        wild_ranks: ranks that act as wild (e.g., ["2", "Joker"])

    Returns:
        List of card groups, each a list of Cards forming a valid set.
    """
    wild_ranks = set(wild_ranks or [])
    wilds = [c for c in cards if c.rank in wild_ranks]
    naturals = [c for c in cards if c.rank not in wild_ranks]

    # Group naturals by rank
    by_rank = defaultdict(list)
    for c in naturals:
        by_rank[c.rank].append(c)

    sets = []
    wilds_used = 0
    available_wilds = list(wilds)

    for rank, group in by_rank.items():
        if len(group) >= min_size:
            # Pure natural set
            sets.append(group[:])
        elif len(group) >= 2 and available_wilds and len(group) + len(available_wilds) >= min_size:
            # Set with wild cards (naturals must outnumber wilds)
            needed = min_size - len(group)
            if needed <= len(available_wilds) and len(group) > needed:
                meld = group[:] + available_wilds[:needed]
                sets.append(meld)
                available_wilds = available_wilds[needed:]

    return sets


def find_runs(cards: list[Card], min_size: int = 3,
              wild_ranks: Optional[list[str]] = None,
              same_suit: bool = True,
              rank_values: Optional[dict] = None) -> list[list[Card]]:
    """Find all valid runs (sequential cards) from cards.

    Args:
        cards: list of Card objects
        min_size: minimum cards per run (default 3)
        wild_ranks: ranks that act as wild (e.g., ["2", "Joker"])
        same_suit: if True (default), runs must be same suit.
            If False, runs can span suits (e.g., Cribbage).
        rank_values: custom rank-to-value mapping. Defaults to RANK_VALUES.

    Returns:
        List of card groups, each forming a valid run.
    """
    wild_ranks = set(wild_ranks or [])
    rv = rank_values or RANK_VALUES
    naturals = [c for c in cards if c.rank not in wild_ranks]

    if same_suit:
        # Group by suit, find runs within each suit
        by_suit = defaultdict(list)
        for c in naturals:
            by_suit[c.suit].append(c)
        groups = list(by_suit.values())
    else:
        # All cards in one group (cross-suit runs)
        groups = [naturals] if naturals else []

    runs = []
    for group_cards in groups:
        sorted_cards = sorted(group_cards, key=lambda c: rv.get(c.rank, 0))

        # Find consecutive sequences
        i = 0
        while i < len(sorted_cards):
            run = [sorted_cards[i]]
            j = i + 1
            while j < len(sorted_cards):
                prev_val = rv.get(run[-1].rank, 0)
                curr_val = rv.get(sorted_cards[j].rank, 0)
                if curr_val == prev_val + 1:
                    run.append(sorted_cards[j])
                    j += 1
                else:
                    break
            if len(run) >= min_size:
                runs.append(run)
            i = j if j > i + 1 else i + 1

    return runs


def find_all_melds(cards: list[Card], allow_sets: bool = True,
                   allow_runs: bool = True, min_size: int = 3,
                   wild_ranks: Optional[list[str]] = None) -> list[list[Card]]:
    """Find all valid melds (sets and/or runs) from cards.

    Returns all possible melds — may overlap (same card in multiple melds).
    Use best_melds() to get optimal non-overlapping selection.
    """
    melds = []
    if allow_sets:
        melds.extend(find_sets(cards, min_size, wild_ranks))
    if allow_runs:
        melds.extend(find_runs(cards, min_size, wild_ranks))
    return melds


def is_valid_meld(cards: list[Card], wild_ranks: Optional[list[str]] = None,
                  min_size: int = 3) -> bool:
    """Check if a group of cards forms a valid meld."""
    if len(cards) < min_size:
        return False

    wild_ranks = set(wild_ranks or [])
    naturals = [c for c in cards if c.rank not in wild_ranks]
    wilds = [c for c in cards if c.rank in wild_ranks]

    if not naturals:
        return False  # can't have all-wild meld

    # Naturals must outnumber wilds
    if len(wilds) >= len(naturals):
        return False

    # Check if it's a valid set (all naturals same rank)
    natural_ranks = set(c.rank for c in naturals)
    if len(natural_ranks) == 1:
        return True

    # Check if it's a valid run (sequential same suit)
    natural_suits = set(c.suit for c in naturals)
    if len(natural_suits) == 1:
        values = sorted(RANK_VALUES.get(c.rank, 0) for c in naturals)
        for i in range(1, len(values)):
            if values[i] != values[i-1] + 1:
                return False
        return True

    return False


def best_melds(cards: list[Card], allow_sets: bool = True,
               allow_runs: bool = True, min_size: int = 3,
               wild_ranks: Optional[list[str]] = None) -> list[list[Card]]:
    """Find optimal non-overlapping melds that minimize deadwood.

    Uses greedy selection — not guaranteed optimal but fast and good enough.
    """
    all_melds = find_all_melds(cards, allow_sets, allow_runs, min_size, wild_ranks)

    # Sort by size descending (bigger melds = more cards used)
    all_melds.sort(key=len, reverse=True)

    used_ids = set()
    selected = []

    for meld in all_melds:
        meld_ids = {c.id for c in meld}
        if not meld_ids & used_ids:
            selected.append(meld)
            used_ids |= meld_ids

    return selected


def deadwood_value(cards: list[Card], melds: list[list[Card]],
                   card_values: Optional[dict] = None) -> int:
    """Calculate the point value of unmelded cards (deadwood)."""
    values = card_values or DEFAULT_CARD_VALUES
    melded_ids = set()
    for meld in melds:
        for c in meld:
            melded_ids.add(c.id)

    total = 0
    for c in cards:
        if c.id not in melded_ids:
            total += values.get(c.rank, 0)
    return total


def meld_score(meld: list[Card], card_values: Optional[dict] = None,
               bonuses: Optional[dict] = None) -> int:
    """Calculate the score for a single meld.

    Args:
        meld: list of cards in the meld
        card_values: per-rank point values
        bonuses: dict of bonus rules, e.g. {7: 300, "natural_7": 500}
    """
    values = card_values or DEFAULT_CARD_VALUES
    bonuses = bonuses or {}

    # Base: sum of card values
    total = sum(values.get(c.rank, 0) for c in meld)

    # Bonuses for meld size
    size = len(meld)
    if size in bonuses:
        total += bonuses[size]

    # Canasta bonuses (7+ cards)
    if size >= 7:
        has_wild = any(c.rank in ("2", "Joker") for c in meld)
        if "natural_7" in bonuses and not has_wild:
            total += bonuses["natural_7"]
        elif "mixed_7" in bonuses and has_wild:
            total += bonuses["mixed_7"]

    return total


def can_add_to_meld(card: Card, meld: list[Card],
                    wild_ranks: Optional[list[str]] = None) -> bool:
    """Check if a card can be added to an existing meld."""
    wild_ranks = set(wild_ranks or [])

    # Wild cards can always be added (if naturals still outnumber)
    if card.rank in wild_ranks:
        naturals = sum(1 for c in meld if c.rank not in wild_ranks)
        wilds = sum(1 for c in meld if c.rank in wild_ranks) + 1
        return naturals > wilds

    # For sets: card must match the meld's rank
    natural_ranks = set(c.rank for c in meld if c.rank not in wild_ranks)
    if len(natural_ranks) == 1 and card.rank in natural_ranks:
        return True

    # For runs: card must extend the sequence in same suit
    natural_suits = set(c.suit for c in meld if c.rank not in wild_ranks)
    if len(natural_suits) == 1 and card.suit in natural_suits:
        values = sorted(RANK_VALUES.get(c.rank, 0) for c in meld if c.rank not in wild_ranks)
        card_val = RANK_VALUES.get(card.rank, 0)
        if card_val == values[0] - 1 or card_val == values[-1] + 1:
            return True

    return False
