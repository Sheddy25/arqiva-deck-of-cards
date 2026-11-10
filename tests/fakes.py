"""A fake card client for game tests."""

from collections.abc import Iterable
from types import MappingProxyType

from deck_of_cards_sdk import Deck, DrawResult, PileResult
from tests.cards import make_card

DECK_ID = "fakedeck01"


class FakeCardClient:
    """Deals cards in a fixed order and records every call.

    Satisfies :class:`card_game.ports.CardClient`. Unlike the SDK client, it
    does not guard ``add_to_pile`` (DEC-06).
    """

    def __init__(self, sequence: Iterable[str]) -> None:
        self._cards = [make_card(code) for code in sequence]
        self.calls: list[tuple[object, ...]] = []
        self.piles: dict[str, list[str]] = {}

    def create_deck(
        self, *, shuffled: bool = True, jokers_enabled: bool = False
    ) -> Deck:
        self.calls.append(("create_deck", shuffled, jokers_enabled))
        return Deck(DECK_ID, shuffled, len(self._cards))

    def shuffle_deck(self, deck_id: str) -> Deck:
        self.calls.append(("shuffle_deck", deck_id))
        return Deck(deck_id, True, len(self._cards))

    def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult:
        self.calls.append(("draw_cards", deck_id, count))
        drawn, self._cards = self._cards[:count], self._cards[count:]
        return DrawResult(deck_id, tuple(drawn), len(self._cards))

    def add_to_pile(
        self, deck_id: str, pile_name: str, cards: Iterable[str]
    ) -> PileResult:
        codes = list(cards)
        self.calls.append(("add_to_pile", deck_id, pile_name, codes))
        self.piles.setdefault(pile_name, []).extend(codes)
        counts = {name: len(pile) for name, pile in self.piles.items()}
        return PileResult(deck_id, len(self._cards), MappingProxyType(counts))
