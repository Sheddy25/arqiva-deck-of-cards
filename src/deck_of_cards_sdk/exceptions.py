"""Errors raised by the Deck of Cards SDK.

Every error is a :class:`DeckOfCardsError`, so callers can catch them all
with one ``except`` clause.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deck_of_cards_sdk.models import DrawResult


class DeckOfCardsError(Exception):
    """Base class for every error raised by the SDK."""


class InvalidArgumentError(DeckOfCardsError):
    """An argument was invalid, so no request was sent."""


class TransportError(DeckOfCardsError):
    """No HTTP response was received."""


class RequestTimeoutError(TransportError):
    """The request timed out."""


class ConnectionFailedError(TransportError):
    """The connection to the API failed."""


class HttpStatusError(DeckOfCardsError):
    """The API responded with a non-2xx HTTP status."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class ResponseFormatError(DeckOfCardsError):
    """The response was not valid JSON or had unexpected fields or types."""


class ApiError(DeckOfCardsError):
    """The API returned ``"success": false``.

    ``body`` is the response's JSON object, kept out of the message.
    """

    def __init__(self, message: str, body: Mapping[str, object] | None = None) -> None:
        super().__init__(message)
        self.body = body


class IncompleteDrawError(ApiError):
    """A draw asked for more cards than remained (OBS-04).

    The API still draws the cards that were left. They are in ``result``, and
    the client has recorded them, so they can be added to piles.
    """

    def __init__(self, message: str, result: "DrawResult") -> None:
        super().__init__(message)
        self.result = result
