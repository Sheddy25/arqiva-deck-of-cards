"""Tests for the completion checks on a finished game."""

import dataclasses

import pytest

from card_game.engine import GameInvariantError, check_invariants
from card_game.models import DiscardPile, GameResult
from card_game.rules import PileRule, should_start_new_pile
from deck_of_cards_sdk import Card
from tests.cards import PACK_ORDER, make_card


def finished_game() -> tuple[GameResult, list[Card]]:
    """A correct game: the pack drawn in order, a new pile at each King."""
    drawn = [make_card(code) for code in PACK_ORDER]
    piles: list[DiscardPile] = []
    for card in drawn:
        if not piles or card.is_king:
            piles.append(DiscardPile(f"discard_{len(piles) + 1}", (card,)))
        else:
            piles[-1] = piles[-1].with_card(card)
    return GameResult("abc123", tuple(piles), cards_remaining=0), drawn


def check(
    result: GameResult,
    drawn: list[Card],
    *,
    deck_size: int = 52,
    rule: PileRule = should_start_new_pile,
    jokers: bool = False,
) -> None:
    check_invariants(result, drawn, deck_size=deck_size, rule=rule, jokers=jokers)


def test_a_correct_game_passes() -> None:
    check(*finished_game())


def test_a_correct_game_with_jokers_passes() -> None:
    result, drawn = finished_game()
    jokers = (make_card("X1"), make_card("X2"))

    check(
        dataclasses.replace(result, binned=jokers),
        [jokers[0], *drawn, jokers[1]],
        deck_size=54,
        jokers=True,
    )


def test_a_correct_game_binning_other_cards_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("card_game.engine.should_bin_card", lambda c: c.is_king)
    result, drawn = finished_game()
    kings = tuple(card for card in drawn if card.is_king)
    piles = (DiscardPile("discard_1", tuple(c for c in drawn if not c.is_king)),)

    check(dataclasses.replace(result, piles=piles, binned=kings), drawn)


def test_a_deck_of_the_wrong_size_fails() -> None:
    with pytest.raises(GameInvariantError, match="deck held 54 cards, not 52"):
        check(*finished_game(), deck_size=54)


def test_jokers_missing_from_a_joker_game_fails() -> None:
    with pytest.raises(GameInvariantError, match="not one standard pack"):
        check(*finished_game(), jokers=True)


def test_missing_draws_fail() -> None:
    result, drawn = finished_game()

    with pytest.raises(GameInvariantError, match="51 cards were drawn"):
        check(result, drawn[:-1])


def test_a_card_drawn_twice_fails() -> None:
    result, drawn = finished_game()

    with pytest.raises(GameInvariantError, match="drawn more than once"):
        check(result, [*drawn[:-1], drawn[0]])


def test_cards_out_of_draw_order_fail() -> None:
    result, drawn = finished_game()
    first, *rest = result.piles
    swapped = (first.cards[0], first.cards[2], first.cards[1], *first.cards[3:])
    piles = (dataclasses.replace(first, cards=swapped), *rest)

    with pytest.raises(GameInvariantError, match="in draw order"):
        check(dataclasses.replace(result, piles=piles), drawn)


def test_a_binned_card_that_was_not_drawn_fails() -> None:
    result, drawn = finished_game()

    with pytest.raises(GameInvariantError, match="binned cards are not"):
        check(dataclasses.replace(result, binned=(make_card("X1"),)), drawn)


def test_cards_left_in_the_deck_fail() -> None:
    result, drawn = finished_game()

    with pytest.raises(GameInvariantError, match="reports 1 cards remaining"):
        check(dataclasses.replace(result, cards_remaining=1), drawn)


def test_misnamed_piles_fail() -> None:
    result, drawn = finished_game()
    first, second, *rest = result.piles
    piles = (first, dataclasses.replace(second, name="discard_9"), *rest)

    with pytest.raises(GameInvariantError, match="not named discard_1 upwards"):
        check(dataclasses.replace(result, piles=piles), drawn)


def test_piles_that_do_not_follow_the_rule_fail() -> None:
    def ace_rule(card: Card) -> bool:
        return card.rank == "A"

    with pytest.raises(GameInvariantError) as error:
        check(*finished_game(), rule=ace_rule)

    assert "discard_2 does not start with a card matching the rule" in str(error.value)
    assert "discard_2 holds a card matching the rule above its bottom" in str(
        error.value
    )
