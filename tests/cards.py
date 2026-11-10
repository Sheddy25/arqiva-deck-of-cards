"""Cards for game tests."""

from deck_of_cards_sdk import Card
from deck_of_cards_sdk.validation import (
    JOKER_SUITS,
    JOKER_VALUE,
    RANK_VALUES,
    SUIT_NAMES,
)

PACK_ORDER = [rank + suit for suit in "SDCH" for rank in "A234567890JQK"]
"""A new pack's order: spades, diamonds, clubs, hearts, each Ace to King."""


def make_card(code: str) -> Card:
    """Return the card the API would send for ``code``, such as "KH" or "X1"."""
    if code in JOKER_SUITS:
        value, suit = JOKER_VALUE, JOKER_SUITS[code]
    else:
        value, suit = RANK_VALUES[code[0]], SUIT_NAMES[code[1]]
    return Card(code, value, suit, f"https://deckofcardsapi.com/static/img/{code}.png")
