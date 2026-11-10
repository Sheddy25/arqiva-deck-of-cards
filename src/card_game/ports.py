"""The client operations the game engine needs.

``DeckOfCardsClient`` satisfies this protocol, and tests use a fake that does
too, without inheriting from the SDK client.
"""

from collections.abc import Iterable
from typing import Protocol

from deck_of_cards_sdk import Deck, DrawResult, PileResult


class CardClient(Protocol):
    """Creates and shuffles a deck, draws cards and adds them to piles."""

    def create_deck(
        self, *, shuffled: bool = True, jokers_enabled: bool = False
    ) -> Deck: ...

    def shuffle_deck(self, deck_id: str) -> Deck: ...

    def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult: ...

    def add_to_pile(
        self, deck_id: str, pile_name: str, cards: Iterable[str]
    ) -> PileResult: ...
