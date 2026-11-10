"""Tests for the game rules (CH-07, CH-08, CH-13, DEC-02)."""

import pytest

from card_game.rules import PileRule, should_bin_card, should_start_new_pile
from deck_of_cards_sdk import Card
from tests.cards import make_card

KINGS = ["KS", "KD", "KC", "KH"]
OTHER_RANKS = ["AS", "2D", "9C", "0H", "JS", "QD"]
JOKERS = ["X1", "X2"]


@pytest.mark.parametrize("code", KINGS)
def test_a_king_starts_a_new_pile(code: str) -> None:
    assert should_start_new_pile(make_card(code))


@pytest.mark.parametrize("code", OTHER_RANKS + JOKERS)
def test_other_cards_do_not_start_a_new_pile(code: str) -> None:
    assert not should_start_new_pile(make_card(code))


@pytest.mark.parametrize("code", JOKERS)
def test_a_joker_is_binned(code: str) -> None:
    assert should_bin_card(make_card(code))


@pytest.mark.parametrize("code", KINGS + OTHER_RANKS)
def test_other_cards_are_not_binned(code: str) -> None:
    assert not should_bin_card(make_card(code))


def test_a_different_rule_can_replace_the_king_rule() -> None:
    def ace_rule(card: Card) -> bool:
        return card.rank == "A"

    rules: list[PileRule] = [should_start_new_pile, ace_rule]

    assert [rule(make_card("AS")) for rule in rules] == [False, True]
    assert [rule(make_card("KS")) for rule in rules] == [True, False]
