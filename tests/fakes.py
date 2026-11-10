"""A fake card client for game tests."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from deck_of_cards_sdk import Deck, DeckOfCardsError, DrawResult, PileResult
from tests.cards import make_card

DECK_ID = "fakedeck01"


class FakeCardClient:
    """Deals cards in a fixed order and records every call.

    Satisfies :class:`card_game.ports.CardClient`. Unlike the SDK client, it
    does not guard ``add_to_pile`` (DEC-06).

    Args:
        sequence: the codes of the cards to deal, in order.
        fail: errors to raise, keyed by method name and call number from 1.
            A failing call is recorded but changes nothing.
        deal: how many cards a draw returns, keyed by draw number from 1,
            in place of the count asked for.
    """

    def __init__(
        self,
        sequence: Iterable[str],
        *,
        fail: Mapping[tuple[str, int], DeckOfCardsError] | None = None,
        deal: Mapping[int, int] | None = None,
    ) -> None:
        self._cards = [make_card(code) for code in sequence]
        self._fail = dict(fail or {})
        self._deal = dict(deal or {})
        self.calls: list[tuple[object, ...]] = []
        self.piles: dict[str, list[str]] = {}

    def create_deck(
        self, *, shuffled: bool = True, jokers_enabled: bool = False
    ) -> Deck:
        self._record("create_deck", shuffled, jokers_enabled)
        return Deck(DECK_ID, shuffled, len(self._cards))

    def shuffle_deck(self, deck_id: str) -> Deck:
        self._record("shuffle_deck", deck_id)
        return Deck(deck_id, True, len(self._cards))

    def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult:
        number = self._record("draw_cards", deck_id, count)
        count = self._deal.get(number, count)
        drawn, self._cards = self._cards[:count], self._cards[count:]
        return DrawResult(deck_id, tuple(drawn), len(self._cards))

    def add_to_pile(
        self, deck_id: str, pile_name: str, cards: Iterable[str]
    ) -> PileResult:
        codes = list(cards)
        self._record("add_to_pile", deck_id, pile_name, codes)
        self.piles.setdefault(pile_name, []).extend(codes)
        counts = {name: len(pile) for name, pile in self.piles.items()}
        return PileResult(deck_id, len(self._cards), MappingProxyType(counts))

    def _record(self, method: str, *args: object) -> int:
        """Record a call, raise its planned error, and return its number."""
        self.calls.append((method, *args))
        number = sum(call[0] == method for call in self.calls)
        if (method, number) in self._fail:
            raise self._fail[method, number]
        return number
