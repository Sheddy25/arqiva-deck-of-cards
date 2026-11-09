"""Typed models for data returned by the Deck of Cards API."""

from collections.abc import Mapping
from dataclasses import dataclass

from deck_of_cards_sdk.exceptions import ResponseFormatError
from deck_of_cards_sdk.validation import (
    JOKER_SUITS,
    JOKER_VALUE,
    RANK_VALUES,
    SUIT_NAMES,
    is_card_code,
    parse_int_field,
)


@dataclass(frozen=True)
class Card:
    """A playing card as returned by the API.

    Standard codes are a rank followed by a suit, with ``0`` for ten
    (API-06). Jokers use the codes ``X1`` and ``X2`` (OBS-02, DEC-02).
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

    @property
    def is_joker(self) -> bool:
        """Whether this card is one of the two Jokers."""
        return self.code in JOKER_SUITS


def parse_card(data: Mapping[str, object]) -> Card:
    """Build a :class:`Card` from a card object in an API response.

    The code is upper-cased because the API treats codes case-insensitively
    (API-06). Fields other than ``code``, ``value``, ``suit`` and ``image``,
    such as ``images``, are ignored.

    Raises:
        ResponseFormatError: if a required field is missing or not a string,
            the code is not a card code, or the value and suit do not match
            the code.
    """
    code = _require_str(data, "code").upper()
    value = _require_str(data, "value")
    suit = _require_str(data, "suit")
    image = _require_str(data, "image")

    if not is_card_code(code):
        raise ResponseFormatError(f"unknown card code {code!r}")
    expected_value, expected_suit = _expected_value_and_suit(code)
    if (value, suit) != (expected_value, expected_suit):
        raise ResponseFormatError(
            f"card {code!r} has value {value!r} and suit {suit!r}; "
            f"expected {expected_value!r} and {expected_suit!r}"
        )
    return Card(code=code, value=value, suit=suit, image=image)


@dataclass(frozen=True)
class Deck:
    """A deck's state after it is created or reshuffled (API-01, API-03,
    API-04, API-05)."""

    deck_id: str
    shuffled: bool
    remaining: int


@dataclass(frozen=True)
class DrawResult:
    """The cards drawn from a deck and how many remain (API-02)."""

    deck_id: str
    cards: tuple[Card, ...]
    remaining: int


def parse_deck(data: Mapping[str, object]) -> Deck:
    """Build a :class:`Deck` from a create or reshuffle response.

    Raises:
        ResponseFormatError: if ``deck_id``, ``shuffled`` or ``remaining`` is
            missing or has the wrong type.
    """
    shuffled = data.get("shuffled")
    if not isinstance(shuffled, bool):
        raise ResponseFormatError(
            f"deck field 'shuffled' must be true or false, got {shuffled!r}"
        )
    return Deck(
        deck_id=_require_str(data, "deck_id", "deck"),
        shuffled=shuffled,
        remaining=parse_int_field(data.get("remaining"), "remaining"),
    )


def parse_draw(data: Mapping[str, object]) -> DrawResult:
    """Build a :class:`DrawResult` from a draw response.

    ``remaining`` may be a number or a decimal string (OBS-03).

    Raises:
        ResponseFormatError: if ``deck_id``, ``cards`` or ``remaining`` is
            missing or has the wrong type, or any card is invalid.
    """
    cards = data.get("cards")
    if not isinstance(cards, list):
        raise ResponseFormatError(f"draw field 'cards' must be a list, got {cards!r}")
    return DrawResult(
        deck_id=_require_str(data, "deck_id", "draw"),
        cards=tuple(_parse_card_item(item) for item in cards),
        remaining=parse_int_field(data.get("remaining"), "remaining"),
    )


def _parse_card_item(item: object) -> Card:
    if not isinstance(item, Mapping):
        raise ResponseFormatError(
            f"each card must be a JSON object, not {type(item).__name__}"
        )
    return parse_card(item)


def _expected_value_and_suit(code: str) -> tuple[str, str]:
    if code in JOKER_SUITS:
        return JOKER_VALUE, JOKER_SUITS[code]
    return RANK_VALUES[code[0]], SUIT_NAMES[code[1]]


def _require_str(data: Mapping[str, object], field: str, what: str = "card") -> str:
    if field not in data:
        raise ResponseFormatError(f"{what} is missing the {field!r} field")
    value = data[field]
    if not isinstance(value, str):
        raise ResponseFormatError(
            f"{what} field {field!r} must be a string, not {type(value).__name__}"
        )
    return value
