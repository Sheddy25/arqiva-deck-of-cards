"""Typed models for data returned by the Deck of Cards API."""

from collections.abc import Mapping
from dataclasses import dataclass

from deck_of_cards_sdk.exceptions import ResponseFormatError
from deck_of_cards_sdk.validation import RANK_VALUES, SUIT_NAMES, is_card_code


@dataclass(frozen=True)
class Card:
    """A playing card as returned by the API.

    Codes are a rank followed by a suit, with ``0`` for ten (API-06). Only
    these documented codes are supported, so Jokers are not (DEC-02).
    """

    code: str
    value: str
    suit: str
    image: str

    @property
    def rank(self) -> str:
        """The rank character of the code, for example ``"K"`` for ``"KS"``."""
        return self.code[0]

    @property
    def is_king(self) -> bool:
        """Whether this card is a King of any suit."""
        return self.rank == "K"


def parse_card(data: Mapping[str, object]) -> Card:
    """Build a :class:`Card` from a card object in an API response.

    The code is upper-cased because the API treats codes case-insensitively
    (API-06). Fields other than ``code``, ``value``, ``suit`` and ``image``,
    such as ``images``, are ignored.

    Raises:
        ResponseFormatError: if a required field is missing or not a string,
            the code is not a documented card code, or the value and suit do
            not match the code.
    """
    code = _require_str(data, "code").upper()
    value = _require_str(data, "value")
    suit = _require_str(data, "suit")
    image = _require_str(data, "image")

    if not is_card_code(code):
        raise ResponseFormatError(f"unknown card code {code!r}")
    expected_value, expected_suit = RANK_VALUES[code[0]], SUIT_NAMES[code[1]]
    if (value, suit) != (expected_value, expected_suit):
        raise ResponseFormatError(
            f"card {code!r} has value {value!r} and suit {suit!r}; "
            f"expected {expected_value!r} and {expected_suit!r}"
        )
    return Card(code=code, value=value, suit=suit, image=image)


def _require_str(data: Mapping[str, object], field: str) -> str:
    if field not in data:
        raise ResponseFormatError(f"card is missing the {field!r} field")
    value = data[field]
    if not isinstance(value, str):
        raise ResponseFormatError(
            f"card field {field!r} must be a string, not {type(value).__name__}"
        )
    return value
