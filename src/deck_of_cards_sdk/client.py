"""Client for the Deck of Cards API (https://deckofcardsapi.com/)."""

from collections.abc import Iterable
from types import TracebackType
from typing import Literal, Self

from deck_of_cards_sdk.exceptions import InvalidArgumentError
from deck_of_cards_sdk.models import (
    Card,
    Deck,
    DrawResult,
    PileDrawResult,
    PileListing,
    PileResult,
    parse_deck,
    parse_draw,
    parse_pile_draw,
    parse_pile_listing,
    parse_pile_result,
)
from deck_of_cards_sdk.transport import HttpTransport, QueryParams
from deck_of_cards_sdk.validation import (
    validate_card_codes,
    validate_count,
    validate_deck_id,
    validate_pile_name,
)

PilePosition = Literal["top", "bottom", "random"]

_PILE_DRAW_ROUTES: dict[str, str] = {
    "top": "draw/",
    "bottom": "draw/bottom/",
    "random": "draw/random/",
}


class DeckOfCardsClient:
    """Typed operations for the Deck of Cards API.

    Every argument is validated before a request is sent, so invalid input
    raises :class:`InvalidArgumentError` without calling the API.

    The client records which cards it has drawn from each deck and which pile
    each one is in, because the API reports success for a card that was
    never drawn without placing it, and silently moves a card that is
    already in another pile (OBS-05). :meth:`add_to_pile` checks this record
    first (DEC-06), so only cards drawn through this client can be added to
    piles.
    """

    def __init__(self, transport: HttpTransport | None = None) -> None:
        """Create a client.

        Args:
            transport: an existing transport, for example one using a mock
                HTTP client in tests. The caller keeps ownership of it, so
                :meth:`close` does not close it.
        """
        self._owns_transport = transport is None
        self._transport = transport if transport is not None else HttpTransport()
        self._record = _CardRecord()

    def create_deck(
        self,
        *,
        shuffled: bool = True,
        deck_count: int = 1,
        cards: Iterable[str] | None = None,
        jokers_enabled: bool = False,
    ) -> Deck:
        """Create a new deck.

        A shuffled deck uses ``deck/new/shuffle/`` with ``deck_count``
        (API-01), and ``cards`` creates a partial deck (API-05). An
        unshuffled deck uses ``deck/new/`` and may include Jokers (API-04).
        Only these documented combinations are allowed.

        Raises:
            InvalidArgumentError: if an argument is invalid, or the
                combination is not documented.
        """
        count = validate_count(deck_count)
        if shuffled:
            if jokers_enabled:
                raise InvalidArgumentError(
                    "jokers_enabled is only documented for an unshuffled deck; "
                    "create one with shuffled=False, then call shuffle_deck"
                )
            params: dict[str, str | int] = {"deck_count": count}
            if cards is not None:
                params["cards"] = ",".join(validate_card_codes(cards))
            return parse_deck(self._transport.get_json("deck/new/shuffle/", params))

        if count != 1 or cards is not None:
            raise InvalidArgumentError(
                "deck_count and cards are only documented for a shuffled deck"
            )
        params = {"jokers_enabled": "true"} if jokers_enabled else {}
        return parse_deck(self._transport.get_json("deck/new/", params))

    def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult:
        """Draw ``count`` cards from the top of the deck (API-02)."""
        path = f"deck/{validate_deck_id(deck_id)}/draw/"
        params = {"count": validate_count(count)}
        result = parse_draw(self._transport.get_json(path, params))
        self._record.drawn(result.deck_id, result.cards)
        return result

    def shuffle_deck(self, deck_id: str, *, remaining_only: bool = False) -> Deck:
        """Reshuffle a deck (API-03).

        With ``remaining_only=True``, only the cards still in the main stack
        are shuffled; drawn cards and cards in piles are left alone. Otherwise
        every card, including those in piles, returns to the deck (OBS-05).
        """
        path = f"deck/{validate_deck_id(deck_id)}/shuffle/"
        params: QueryParams = {"remaining": "true"} if remaining_only else {}
        deck = parse_deck(self._transport.get_json(path, params))
        if not remaining_only:
            self._record.forget(deck.deck_id)
        return deck

    def add_to_pile(
        self, deck_id: str, pile_name: str, cards: Iterable[str]
    ) -> PileResult:
        """Add drawn cards to a pile, creating the pile if it is new (API-07).

        Pile operations do not work with decks made from several decks.

        Raises:
            InvalidArgumentError: if an argument is invalid, or a card has not
                been drawn through this client, is already in a pile, or is
                listed more than once (DEC-06).
        """
        path = _pile_path(deck_id, pile_name, "add/")
        codes = validate_card_codes(cards)
        self._record.check_add(deck_id, codes)
        result = parse_pile_result(
            self._transport.get_json(path, {"cards": ",".join(codes)})
        )
        self._record.added(deck_id, pile_name, codes)
        return result

    def shuffle_pile(self, deck_id: str, pile_name: str) -> PileResult:
        """Shuffle the cards in a pile (API-08)."""
        path = _pile_path(deck_id, pile_name, "shuffle/")
        return parse_pile_result(self._transport.get_json(path))

    def list_pile(self, deck_id: str, pile_name: str) -> PileListing:
        """List the cards in a pile (API-09)."""
        name = validate_pile_name(pile_name)
        path = _pile_path(deck_id, name, "list/")
        return parse_pile_listing(self._transport.get_json(path), name)

    def draw_from_pile(
        self,
        deck_id: str,
        pile_name: str,
        *,
        count: int | None = None,
        cards: Iterable[str] | None = None,
        position: PilePosition = "top",
    ) -> PileDrawResult:
        """Draw cards from a pile (API-10).

        Draws from the top by default, as the pile is a stack. ``position``
        can be ``"bottom"`` or ``"random"``, which accept ``count`` only.
        Specific ``cards`` can be drawn only from the top route. With
        neither ``count`` nor ``cards``, the API draws one card.

        Raises:
            InvalidArgumentError: if an argument is invalid, or the
                combination is not documented.
        """
        if position not in _PILE_DRAW_ROUTES:
            raise InvalidArgumentError(
                f"position must be 'top', 'bottom' or 'random', got {position!r}"
            )
        if count is not None and cards is not None:
            raise InvalidArgumentError("give count or cards, not both")
        if cards is not None and position != "top":
            raise InvalidArgumentError(
                "cards are only documented for drawing from the top of a pile"
            )
        path = _pile_path(deck_id, pile_name, _PILE_DRAW_ROUTES[position])
        params: dict[str, str | int] = {}
        if count is not None:
            params["count"] = validate_count(count)
        if cards is not None:
            params["cards"] = ",".join(validate_card_codes(cards))
        result = parse_pile_draw(self._transport.get_json(path, params))
        self._record.drawn_from_pile(result.deck_id, result.cards)
        return result

    def return_cards(
        self,
        deck_id: str,
        *,
        pile_name: str | None = None,
        cards: Iterable[str] | None = None,
    ) -> PileResult:
        """Return cards to the main deck (API-11).

        Without ``pile_name``, drawn cards are returned and cards in piles are
        left alone (OBS-05); with it, cards in that pile are. ``cards`` limits
        the return to those cards.
        """
        if pile_name is None:
            path = f"deck/{validate_deck_id(deck_id)}/return/"
        else:
            path = _pile_path(deck_id, pile_name, "return/")
        codes = validate_card_codes(cards) if cards is not None else None
        params: QueryParams = {"cards": ",".join(codes)} if codes is not None else {}
        result = parse_pile_result(self._transport.get_json(path, params))
        self._record.returned(deck_id, pile_name, codes)
        return result

    def close(self) -> None:
        """Close the transport, if this client created it."""
        if self._owns_transport:
            self._transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _pile_path(deck_id: str, pile_name: str, action: str) -> str:
    return (
        f"deck/{validate_deck_id(deck_id)}/pile/{validate_pile_name(pile_name)}/"
        f"{action}"
    )


class _CardRecord:
    """The cards a client has drawn from each deck, and the pile each is in.

    A card is either held (drawn and not in a pile) or in exactly one pile.
    Decks are keyed by the deck ID in each response, so drawing from ``new``
    is recorded against the deck the API created.
    """

    def __init__(self) -> None:
        self._held: dict[str, set[str]] = {}
        self._pile_of: dict[str, dict[str, str]] = {}

    def check_add(self, deck_id: str, codes: tuple[str, ...]) -> None:
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
