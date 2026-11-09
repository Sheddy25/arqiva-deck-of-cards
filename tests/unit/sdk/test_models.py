"""Tests for card, deck and draw parsing (API-06, API-13, OBS-01 to OBS-03,
DEC-02)."""

import dataclasses

import pytest

from deck_of_cards_sdk.exceptions import ResponseFormatError
from deck_of_cards_sdk.models import (
    Card,
    Deck,
    DrawResult,
    parse_card,
    parse_deck,
    parse_draw,
    parse_pile_draw,
    parse_pile_listing,
    parse_pile_result,
)


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
    assert not card.is_joker


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
def test_parses_jokers(code: str, suit: str) -> None:
    card = parse_card(card_data(code, "JOKER", suit))

    assert card.is_joker
    assert not card.is_king


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

    with pytest.raises(ResponseFormatError, match="missing"):
        parse_card(data)


@pytest.mark.parametrize("field", ["code", "value", "suit", "image"])
@pytest.mark.parametrize("bad_value", [None, 5, True, ["5S"]])
def test_non_string_field_is_rejected(field: str, bad_value: object) -> None:
    data = card_data("5S", "5", "SPADES")
    data[field] = bad_value

    with pytest.raises(ResponseFormatError, match="must be a string"):
        parse_card(data)


@pytest.mark.parametrize("code", ["", "K", "1S", "KX", "KSS", "X3", "XX"])
def test_unknown_code_is_rejected(code: str) -> None:
    with pytest.raises(ResponseFormatError, match="unknown card code"):
        parse_card(card_data(code, "KING", "SPADES"))


@pytest.mark.parametrize(
    ("code", "value", "suit"),
    [
        ("5S", "5", "HEARTS"),
        ("KS", "QUEEN", "SPADES"),
        ("0H", "0", "HEARTS"),
        ("X1", "JOKER", "RED"),
        ("X2", "KING", "RED"),
    ],
)
def test_value_or_suit_not_matching_code_is_rejected(
    code: str, value: str, suit: str
) -> None:
    with pytest.raises(ResponseFormatError, match="expected"):
        parse_card(card_data(code, value, suit))


def test_card_is_immutable() -> None:
    card = parse_card(card_data("5S", "5", "SPADES"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        card.code = "6S"  # type: ignore[misc]


def deck_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "success": True,
        "deck_id": "abc123",
        "shuffled": True,
        "remaining": 52,
    }
    data.update(overrides)
    return data


def draw_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "success": True,
        "deck_id": "abc123",
        "cards": [card_data("6H", "6", "HEARTS")],
        "remaining": 51,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(("remaining", "expected"), [(52, 52), ("42", 42), (0, 0)])
def test_parses_a_deck(remaining: object, expected: int) -> None:
    deck = parse_deck(deck_data(remaining=remaining))

    assert deck == Deck(deck_id="abc123", shuffled=True, remaining=expected)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"deck_id": None}, "'deck_id'"),
        ({"deck_id": 123}, "'deck_id'"),
        ({"shuffled": None}, "'shuffled'"),
        ({"shuffled": "true"}, "'shuffled'"),
        ({"remaining": None}, "'remaining'"),
        ({"remaining": -1}, "'remaining'"),
    ],
)
def test_invalid_deck_is_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ResponseFormatError, match=message):
        parse_deck(deck_data(**overrides))


def test_parses_a_draw() -> None:
    result = parse_draw(draw_data())

    assert result == DrawResult(
        deck_id="abc123",
        cards=(parse_card(card_data("6H", "6", "HEARTS")),),
        remaining=51,
    )


def test_parses_a_draw_with_no_cards() -> None:
    assert parse_draw(draw_data(cards=[], remaining=0)).cards == ()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"deck_id": None}, "'deck_id'"),
        ({"cards": None}, "'cards'"),
        ({"cards": {"code": "6H"}}, "'cards'"),
        ({"cards": ["6H"]}, "JSON object"),
        ({"cards": [card_data("6H", "7", "HEARTS")]}, "expected"),
        ({"remaining": "4x"}, "'remaining'"),
    ],
)
def test_invalid_draw_is_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ResponseFormatError, match=message):
        parse_draw(draw_data(**overrides))


@pytest.mark.parametrize(
    "piles",
    [
        None,
        ["discard"],
        {"discard": 2},
        {"discard": {"remaining": "x"}},
        {"discard": {}},
    ],
)
def test_invalid_pile_counts_are_rejected(piles: object) -> None:
    data = {"deck_id": "abc123", "remaining": 50, "piles": piles}

    with pytest.raises(ResponseFormatError):
        parse_pile_result(data)


def test_pile_result_without_piles_has_no_counts() -> None:
    assert parse_pile_result({"deck_id": "abc123", "remaining": 52}).piles == {}


@pytest.mark.parametrize(
    "data",
    [
        {"piles": {}},
        {"deck_id": "abc123", "piles": {}},
        {"deck_id": "abc123", "cards": "AS", "piles": {}},
    ],
)
def test_invalid_pile_draw_is_rejected(data: dict[str, object]) -> None:
    with pytest.raises(ResponseFormatError):
        parse_pile_draw(data)


@pytest.mark.parametrize(
    "pile",
    [
        "discard",
        {"remaining": 1, "cards": "AS"},
        {"remaining": 1, "cards": [card_data("AS", "ACE", "HEARTS")]},
    ],
)
def test_invalid_pile_listing_is_rejected(pile: object) -> None:
    data = {"deck_id": "abc123", "remaining": 0, "piles": {"discard": pile}}

    with pytest.raises(ResponseFormatError):
        parse_pile_listing(data, "discard")


def test_pile_listing_without_cards_is_empty() -> None:
    data = {"deck_id": "abc123", "remaining": 0, "piles": {"discard": {"remaining": 0}}}

    assert parse_pile_listing(data, "discard").cards == ()
