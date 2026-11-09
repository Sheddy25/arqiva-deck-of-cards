"""Tests for argument and response-field validation (API-06, API-09, OBS-03,
DEC-02)."""

import pytest

from deck_of_cards_sdk.exceptions import InvalidArgumentError, ResponseFormatError
from deck_of_cards_sdk.validation import (
    is_card_code,
    parse_int_field,
    validate_card_codes,
    validate_count,
    validate_deck_id,
    validate_pile_name,
)


@pytest.mark.parametrize("code", ["AS", "0H", "KD", "9C", "qh", "jS"])
def test_documented_codes_are_card_codes(code: str) -> None:
    assert is_card_code(code)


@pytest.mark.parametrize("code", ["", "A", "1S", "10H", "KX", "KSS", "X1", "X2"])
def test_other_codes_are_not_card_codes(code: str) -> None:
    assert not is_card_code(code)


@pytest.mark.parametrize("deck_id", ["3p40paa87x90", "ABC123", "a"])
def test_valid_deck_id_is_returned(deck_id: str) -> None:
    assert validate_deck_id(deck_id) == deck_id


@pytest.mark.parametrize(
    "deck_id", ["", " ", "abc 123", "abc/123", "../x", "abc?x=1", "abc\n", None, 42]
)
def test_invalid_deck_id_is_rejected(deck_id: object) -> None:
    with pytest.raises(InvalidArgumentError, match="deck ID"):
        validate_deck_id(deck_id)


@pytest.mark.parametrize("count", [1, 2, 52])
def test_valid_count_is_returned(count: int) -> None:
    assert validate_count(count) == count


@pytest.mark.parametrize("count", [0, -1, True, False, 1.0, "1", None])
def test_invalid_count_is_rejected(count: object) -> None:
    with pytest.raises(InvalidArgumentError, match="count"):
        validate_count(count)


@pytest.mark.parametrize("name", ["discard_1", "player-2", "Pile3"])
def test_valid_pile_name_is_returned(name: str) -> None:
    assert validate_pile_name(name) == name


@pytest.mark.parametrize(
    "name", ["", "discard 1", "discard/1", "pile?x", "pile\n", None, 1]
)
def test_invalid_pile_name_is_rejected(name: object) -> None:
    with pytest.raises(InvalidArgumentError, match="pile name"):
        validate_pile_name(name)


def test_card_codes_are_returned_upper_cased() -> None:
    assert validate_card_codes(["as", "0H", "Kd"]) == ("AS", "0H", "KD")


def test_card_codes_accept_any_iterable() -> None:
    assert validate_card_codes(code for code in ["AS", "2S"]) == ("AS", "2S")


def test_empty_card_codes_are_rejected() -> None:
    with pytest.raises(InvalidArgumentError, match="at least one"):
        validate_card_codes([])


def test_single_string_of_card_codes_is_rejected() -> None:
    with pytest.raises(InvalidArgumentError, match="must be a list"):
        validate_card_codes("AS,2S")


@pytest.mark.parametrize(
    "codes", [["AS", "1S"], ["X1"], ["AS", ""], ["AS", None], ["AS,2S"]]
)
def test_invalid_card_code_is_rejected(codes: list[object]) -> None:
    with pytest.raises(InvalidArgumentError, match="invalid card codes"):
        validate_card_codes(codes)  # type: ignore[arg-type]


@pytest.mark.parametrize(("value", "expected"), [(0, 0), (52, 52), ("42", 42)])
def test_int_field_accepts_numbers_and_decimal_strings(
    value: object, expected: int
) -> None:
    assert parse_int_field(value, "remaining") == expected


@pytest.mark.parametrize(
    "value", [-1, "-1", "4x", "", " 4", "4.0", 4.0, True, None, "٤"]
)
def test_int_field_rejects_other_values(value: object) -> None:
    with pytest.raises(ResponseFormatError, match="'remaining'"):
        parse_int_field(value, "remaining")
