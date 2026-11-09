"""Checks for SDK arguments and for numbers in API responses.

Argument checks raise :class:`InvalidArgumentError` before any request is
sent. Response checks raise :class:`ResponseFormatError`.
"""

import re
from collections.abc import Iterable

from deck_of_cards_sdk.exceptions import InvalidArgumentError, ResponseFormatError

# Code rank -> API value name (API-06, OBS-01). The rank "0" is ten.
RANK_VALUES = {
    "A": "ACE",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "0": "10",
    "J": "JACK",
    "Q": "QUEEN",
    "K": "KING",
}

# Code suit -> API suit name (API-06, OBS-01).
SUIT_NAMES = {"S": "SPADES", "D": "DIAMONDS", "C": "CLUBS", "H": "HEARTS"}

_DECK_ID = re.compile(r"[A-Za-z0-9]+")
_PILE_NAME = re.compile(r"[A-Za-z0-9_-]+")
_DECIMAL = re.compile(r"[0-9]+")


def is_card_code(code: str) -> bool:
    """Whether ``code`` is a documented card code, ignoring case.

    Codes are a rank followed by a suit, with ``0`` for ten (API-06). The
    Joker codes are undocumented, so they are not card codes here (DEC-02).
    """
    code = code.upper()
    return len(code) == 2 and code[0] in RANK_VALUES and code[1] in SUIT_NAMES


def validate_deck_id(deck_id: object) -> str:
    """Return ``deck_id`` if it is non-empty letters and digits only."""
    if not isinstance(deck_id, str) or not _DECK_ID.fullmatch(deck_id):
        raise InvalidArgumentError(
            f"deck ID must be letters and digits only, got {deck_id!r}"
        )
    return deck_id


def validate_count(count: object) -> int:
    """Return ``count`` if it is a whole number of at least 1."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise InvalidArgumentError(
            f"count must be a whole number of at least 1, got {count!r}"
        )
    return count


def validate_pile_name(name: object) -> str:
    """Return ``name`` if it is non-empty letters, digits, ``_`` and ``-``."""
    if not isinstance(name, str) or not _PILE_NAME.fullmatch(name):
        raise InvalidArgumentError(
            f"pile name must be letters, digits, '_' and '-' only, got {name!r}"
        )
    return name


def validate_card_codes(codes: Iterable[str]) -> tuple[str, ...]:
    """Return the card codes upper-cased, if there is at least one and all
    are documented codes (API-06, DEC-02).

    A single string such as ``"AS,2S"`` is rejected, because iterating it
    would give single characters.
    """
    if isinstance(codes, str):
        raise InvalidArgumentError(
            f"card codes must be a list such as ['AS', '2S'], got {codes!r}"
        )
    items = tuple(codes)
    if not items:
        raise InvalidArgumentError("at least one card code is required")
    invalid = [code for code in items if not _is_code_string(code)]
    if invalid:
        raise InvalidArgumentError(f"invalid card codes: {invalid!r}")
    return tuple(code.upper() for code in items)


def parse_int_field(value: object, field: str) -> int:
    """Return a non-negative whole number from an API response field.

    The API sends some numbers as JSON numbers and others as strings such as
    ``"42"``, so both are accepted (API-09, OBS-03).
    """
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and _DECIMAL.fullmatch(value):
        return int(value)
    raise ResponseFormatError(
        f"field {field!r} must be a non-negative whole number, got {value!r}"
    )


def _is_code_string(code: object) -> bool:
    return isinstance(code, str) and is_card_code(code)
