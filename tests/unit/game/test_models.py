"""Tests for the discard pile and game result (CH-10, INT-04)."""

import dataclasses

import pytest

from card_game.models import DiscardPile, GameResult
from tests.cards import make_card


def test_a_pile_with_one_card_has_it_as_top_and_bottom() -> None:
    pile = DiscardPile("discard_1", [make_card("KH")])

    assert pile.bottom == pile.top == make_card("KH")
    assert pile.count == 1


def test_the_first_card_placed_is_the_bottom_and_the_last_is_the_top() -> None:
    pile = DiscardPile("discard_1", [make_card("KH")])

    pile.add(make_card("5S"))
    pile.add(make_card("0D"))

    assert pile.bottom == make_card("KH")
    assert pile.top == make_card("0D")
    assert pile.count == 3
    assert [card.code for card in pile.cards] == ["KH", "5S", "0D"]


def test_a_pile_cannot_be_empty() -> None:
    with pytest.raises(ValueError, match="'discard_1' must start with a card"):
        DiscardPile("discard_1", [])


def test_a_pile_keeps_its_own_list() -> None:
    cards = [make_card("KH")]
    pile = DiscardPile("discard_1", cards)

    pile.add(make_card("5S"))

    assert cards == [make_card("KH")]


def test_total_discarded_counts_the_cards_in_every_pile() -> None:
    first = DiscardPile("discard_1", [make_card("2S"), make_card("3S")])
    second = DiscardPile("discard_2", [make_card("KH")])

    result = GameResult("abc123", (first, second), cards_remaining=0)

    assert result.total_discarded == 3
    assert result.binned == ()


def test_binned_jokers_are_not_counted_as_discarded() -> None:
    pile = DiscardPile("discard_1", [make_card("KH")])

    result = GameResult("abc123", (pile,), cards_remaining=0, binned=(make_card("X1"),))

    assert result.total_discarded == 1
    assert result.binned == (make_card("X1"),)


def test_a_game_result_is_immutable() -> None:
    result = GameResult("abc123", (), cards_remaining=0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.cards_remaining = 1  # type: ignore[misc]
