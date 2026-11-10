"""The record behind the client's pile-add guard (DEC-06).

The API reports success for a card that was never drawn without placing it,
and silently moves a card that is already in another pile (OBS-05), so the
client keeps its own record and checks each add against it first.
"""

from collections.abc import Iterable

from deck_of_cards_sdk.exceptions import InvalidArgumentError
from deck_of_cards_sdk.models import Card


class CardRecord:
    """The cards a client has drawn from each deck, and the pile each is in.

    A card is either held (drawn and not in a pile) or in exactly one pile.
    Decks are keyed by the deck ID in each response, so drawing from ``new``
    is recorded against the deck the API created. Pile operations do not work
    with decks made from several decks, so each card code is one card.
    """

    def __init__(self) -> None:
        self._held: dict[str, set[str]] = {}
        self._pile_of: dict[str, dict[str, str]] = {}

    def check_add(self, deck_id: str, codes: tuple[str, ...]) -> None:
        """Check that ``codes`` can be added to a pile.

        Raises:
            InvalidArgumentError: if a card is listed twice, is already in a
                pile, or has not been drawn from ``deck_id`` by this client.
        """
        held = self._held.get(deck_id, set())
        pile_of = self._pile_of.get(deck_id, {})
        seen: set[str] = set()
        for code in codes:
            if code in seen:
                raise InvalidArgumentError(f"card {code} is listed more than once")
            seen.add(code)
            if code in pile_of:
                raise InvalidArgumentError(
                    f"card {code} is already in pile {pile_of[code]!r}; "
                    "draw it from that pile first"
                )
            if code not in held:
                raise InvalidArgumentError(
                    f"card {code} has not been drawn from deck {deck_id} by this client"
                )

    def drawn(self, deck_id: str, cards: Iterable[Card]) -> None:
        self._held.setdefault(deck_id, set()).update(card.code for card in cards)

    def added(self, deck_id: str, pile_name: str, codes: Iterable[str]) -> None:
        held = self._held.setdefault(deck_id, set())
        pile_of = self._pile_of.setdefault(deck_id, {})
        for code in codes:
            held.discard(code)
            pile_of[code] = pile_name

    def drawn_from_pile(self, deck_id: str, cards: tuple[Card, ...]) -> None:
        pile_of = self._pile_of.get(deck_id, {})
        for card in cards:
            pile_of.pop(card.code, None)
        self.drawn(deck_id, cards)

    def returned(
        self, deck_id: str, pile_name: str | None, codes: Iterable[str] | None
    ) -> None:
        if pile_name is None:
            held = self._held.get(deck_id, set())
            if codes is None:
                held.clear()
            else:
                held.difference_update(codes)
            return
        pile_of = self._pile_of.get(deck_id, {})
        returned = [
            code
            for code, pile in pile_of.items()
            if pile == pile_name and (codes is None or code in codes)
        ]
        for code in returned:
            del pile_of[code]

    def forget(self, deck_id: str) -> None:
        self._held.pop(deck_id, None)
        self._pile_of.pop(deck_id, None)
