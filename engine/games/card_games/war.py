"""War card game implementation.

The simplest card game: deal the deck evenly, both players flip
their top card, higher rank wins both cards. Repeat until one
player has all the cards.

War (tie-breaking): when cards match, each player places 3 cards
face-down and flips a 4th. Higher 4th card wins all cards in play.
"""

from __future__ import annotations
from typing import Optional
import random

from engine.gdl.cards import (
    Card, CardZone, CardGameState, create_standard_deck, compare_cards
)


def create_war_game(seed: Optional[int] = None) -> CardGameState:
    """Create a new War game state."""
    if seed is not None:
        random.seed(seed)

    state = CardGameState()

    # Create zones
    deck = CardZone("deck", visible_to="none", ordered=True)
    hand_p1 = CardZone("hand_p1", owner="player1", visible_to="none", ordered=True)
    hand_p2 = CardZone("hand_p2", owner="player2", visible_to="none", ordered=True)
    table = CardZone("table", visible_to="all")
    won_p1 = CardZone("won_p1", owner="player1", visible_to="all")
    won_p2 = CardZone("won_p2", owner="player2", visible_to="all")

    state.add_zone(deck)
    state.add_zone(hand_p1)
    state.add_zone(hand_p2)
    state.add_zone(table)
    state.add_zone(won_p1)
    state.add_zone(won_p2)

    # Create and shuffle deck
    cards = create_standard_deck()
    random.shuffle(cards)
    for card in cards:
        deck.add(card)

    # Deal evenly
    state.deal("deck", "hand_p1", 26)
    state.deal("deck", "hand_p2", 26)

    return state


def play_round(state: CardGameState) -> dict:
    """Play one round of War.

    Returns info about what happened:
      - cards played by each player
      - who won the round
      - if war occurred
    """
    hand_p1 = state.get_zone("hand_p1")
    hand_p2 = state.get_zone("hand_p2")
    table = state.get_zone("table")

    # Check for game over
    if hand_p1.is_empty:
        return {"game_over": True, "winner": "player2"}
    if hand_p2.is_empty:
        return {"game_over": True, "winner": "player1"}

    # Both flip top card
    card_p1 = hand_p1.draw()
    card_p2 = hand_p2.draw()
    table.add(card_p1)
    table.add(card_p2)

    result = {
        "game_over": False,
        "p1_card": card_p1,
        "p2_card": card_p2,
        "war": False,
        "winner": None,
        "cards_won": 0,
    }

    cmp = compare_cards(card_p1, card_p2)

    if cmp > 0:
        # Player 1 wins this round
        _collect_table(state, "player1")
        result["winner"] = "player1"
        result["cards_won"] = table.size
    elif cmp < 0:
        # Player 2 wins this round
        _collect_table(state, "player2")
        result["winner"] = "player2"
        result["cards_won"] = table.size
    else:
        # War! Tie-breaking
        result["war"] = True
        war_result = _resolve_war(state)
        result["winner"] = war_result["winner"]
        result["cards_won"] = war_result["cards_won"]

    return result


def _resolve_war(state: CardGameState) -> dict:
    """Resolve a war (tie). Each player places 3 face-down, flips a 4th."""
    hand_p1 = state.get_zone("hand_p1")
    hand_p2 = state.get_zone("hand_p2")
    table = state.get_zone("table")

    # Place 3 face-down each (or as many as available)
    for _ in range(3):
        if not hand_p1.is_empty:
            table.add(hand_p1.draw())
        if not hand_p2.is_empty:
            table.add(hand_p2.draw())

    # Flip a 4th
    if hand_p1.is_empty:
        _collect_table(state, "player2")
        return {"winner": "player2", "cards_won": table.size}
    if hand_p2.is_empty:
        _collect_table(state, "player1")
        return {"winner": "player1", "cards_won": table.size}

    card_p1 = hand_p1.draw()
    card_p2 = hand_p2.draw()
    table.add(card_p1)
    table.add(card_p2)

    cmp = compare_cards(card_p1, card_p2)
    if cmp > 0:
        _collect_table(state, "player1")
        return {"winner": "player1", "cards_won": table.size}
    elif cmp < 0:
        _collect_table(state, "player2")
        return {"winner": "player2", "cards_won": table.size}
    else:
        # Another tie — recurse
        return _resolve_war(state)


def _collect_table(state: CardGameState, winner: str):
    """Move all cards from table to winner's hand (bottom)."""
    table = state.get_zone("table")
    hand = state.get_zone(f"hand_{winner[:2]}_{winner[-1]}" if "player" not in winner
                          else f"hand_p{winner[-1]}")
    cards = list(table.cards)
    random.shuffle(cards)  # Shuffle won cards before adding to bottom
    table.cards.clear()
    for card in cards:
        hand.add(card, to_top=False)


def play_full_game(seed: Optional[int] = None, max_rounds: int = 500) -> dict:
    """Play a full game of War and return the result."""
    state = create_war_game(seed)
    rounds = []

    for i in range(max_rounds):
        result = play_round(state)
        rounds.append(result)

        if result["game_over"]:
            return {
                "winner": result["winner"],
                "rounds": len(rounds),
                "final_p1_cards": state.get_zone("hand_p1").size,
                "final_p2_cards": state.get_zone("hand_p2").size,
            }

    # Game didn't finish — whoever has more cards wins
    p1_count = state.get_zone("hand_p1").size
    p2_count = state.get_zone("hand_p2").size
    winner = "player1" if p1_count > p2_count else "player2" if p2_count > p1_count else "draw"

    return {
        "winner": winner,
        "rounds": max_rounds,
        "final_p1_cards": p1_count,
        "final_p2_cards": p2_count,
        "truncated": True,
    }
