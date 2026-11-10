"""The game's rules (CH-07, CH-08, CH-13, DEC-02).

Every rule the game applies to a drawn card lives here. To model a new rule,
change one of these functions, or give the engine a different ``PileRule``.
"""

from collections.abc import Callable

from deck_of_cards_sdk import Card

PileRule = Callable[[Card], bool]
"""Decides, from a drawn card, whether that card starts a new discard pile."""


def should_start_new_pile(card: Card) -> bool:
    """Return whether ``card`` starts a new discard pile: it is a King.

    The card becomes the first card, the bottom, of the new pile (CH-07,
    CH-08).
    """
    return card.is_king


def should_bin_card(card: Card) -> bool:
    """Return whether ``card`` is binned instead of placed in a pile: it is a
    Joker (DEC-02)."""
    return card.is_joker
