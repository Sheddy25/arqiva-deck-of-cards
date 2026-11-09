"""Client for the Deck of Cards API (https://deckofcardsapi.com/)."""

from collections.abc import Iterable
from types import TracebackType
from typing import Self

from deck_of_cards_sdk.exceptions import InvalidArgumentError
from deck_of_cards_sdk.models import Deck, DrawResult, parse_deck, parse_draw
from deck_of_cards_sdk.transport import HttpTransport, QueryParams
from deck_of_cards_sdk.validation import (
    validate_card_codes,
    validate_count,
    validate_deck_id,
)


class DeckOfCardsClient:
    """Typed operations for the Deck of Cards API.

    Every argument is validated before a request is sent, so invalid input
    raises :class:`InvalidArgumentError` without calling the API.
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
        return parse_draw(self._transport.get_json(path, params))

    def shuffle_deck(self, deck_id: str, *, remaining_only: bool = False) -> Deck:
        """Reshuffle a deck (API-03).

        With ``remaining_only=True``, only the cards still in the main stack
        are shuffled; drawn cards and cards in piles are left alone.
        """
        path = f"deck/{validate_deck_id(deck_id)}/shuffle/"
        params: QueryParams = {"remaining": "true"} if remaining_only else {}
        return parse_deck(self._transport.get_json(path, params))

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
