"""Tests for Card parsing (API-06, API-13, OBS-01, DEC-02)."""

import dataclasses

import pytest

from deck_of_cards_sdk.models import Card, parse_card


def card_data(code: str, value: str, suit: str) -> dict[str, object]:
    return {
        "code": code,
        "value": value,
        "suit": suit,
        "image": f"https://deckofcardsapi.com/static/img/{code}.png",
    }


def test_parses_a_standard_card() -> None:
    card = parse_card(card_data("6H", "6", "HEARTS"))

    assert card == Card(
        code="6H",
        value="6",
        suit="HEARTS",
        image="https://deckofcardsapi.com/static/img/6H.png",
    )
    assert card.rank == "6"
    assert not card.is_king


def test_zero_code_is_ten() -> None:
    card = parse_card(card_data("0H", "10", "HEARTS"))

    assert card.rank == "0"
    assert card.value == "10"


@pytest.mark.parametrize(
    ("code", "value", "suit"),
    [
        ("AS", "ACE", "SPADES"),
        ("JD", "JACK", "DIAMONDS"),
        ("QC", "QUEEN", "CLUBS"),
        ("KH", "KING", "HEARTS"),
    ],
)
def test_parses_named_ranks(code: str, value: str, suit: str) -> None:
    assert parse_card(card_data(code, value, suit)).value == value


@pytest.mark.parametrize("code", ["KS", "KD", "KC", "KH"])
def test_every_king_is_a_king(code: str) -> None:
    suit = {"S": "SPADES", "D": "DIAMONDS", "C": "CLUBS", "H": "HEARTS"}[code[1]]

    assert parse_card(card_data(code, "KING", suit)).is_king


@pytest.mark.parametrize(("code", "suit"), [("X1", "BLACK"), ("X2", "RED")])
def test_undocumented_joker_codes_are_rejected(code: str, suit: str) -> None:
    with pytest.raises(ValueError, match="unknown card code"):
        parse_card(card_data(code, "JOKER", suit))


def test_lower_case_code_is_normalised() -> None:
    assert parse_card(card_data("ks", "KING", "SPADES")).code == "KS"


def test_extra_fields_are_ignored() -> None:
    data = card_data("5S", "5", "SPADES")
    data["images"] = {"svg": "5S.svg", "png": "5S.png"}

    card = parse_card(data)

    assert card.code == "5S"


@pytest.mark.parametrize("field", ["code", "value", "suit", "image"])
def test_missing_field_is_rejected(field: str) -> None:
    data = card_data("5S", "5", "SPADES")
    del data[field]

    with pytest.raises(ValueError, match="missing"):
        parse_card(data)


@pytest.mark.parametrize("field", ["code", "value", "suit", "image"])
@pytest.mark.parametrize("bad_value", [None, 5, True, ["5S"]])
def test_non_string_field_is_rejected(field: str, bad_value: object) -> None:
    data = card_data("5S", "5", "SPADES")
    data[field] = bad_value

    with pytest.raises(ValueError, match="must be a string"):
        parse_card(data)


@pytest.mark.parametrize("code", ["", "K", "1S", "KX", "KSS", "X3", "XX"])
def test_unknown_code_is_rejected(code: str) -> None:
    with pytest.raises(ValueError, match="unknown card code"):
        parse_card(card_data(code, "KING", "SPADES"))


@pytest.mark.parametrize(
    ("code", "value", "suit"),
    [
        ("5S", "5", "HEARTS"),
        ("KS", "QUEEN", "SPADES"),
        ("0H", "0", "HEARTS"),
    ],
)
def test_value_or_suit_not_matching_code_is_rejected(
    code: str, value: str, suit: str
) -> None:
    with pytest.raises(ValueError, match="expected"):
        parse_card(card_data(code, value, suit))


def test_card_is_immutable() -> None:
    card = parse_card(card_data("5S", "5", "SPADES"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        card.code = "6S"  # type: ignore[misc]
