"""Tests for the game engine over a fake client (CH-03 to CH-08, CH-13,
INT-01 to INT-04, INT-07, DEC-02)."""

from collections.abc import Sequence

import pytest

from card_game.engine import GameEngine
from card_game.models import GameResult
from card_game.rules import PileRule, should_start_new_pile
from deck_of_cards_sdk import Card, DeckOfCardsClient
from tests.fakes import DECK_ID, FakeCardClient

PACK_ORDER = [rank + suit for suit in "SDCH" for rank in "A234567890JQK"]
JOKER_CODES = ["X1", "X2"]


def deck(*first: str, last: Sequence[str] = (), jokers: bool = False) -> list[str]:
    """A full deck in pack order, with ``first`` moved to the start and
    ``last`` to the end."""
    chosen = {*first, *last}
    pack = PACK_ORDER + (JOKER_CODES if jokers else [])
    return [*first, *(code for code in pack if code not in chosen), *last]


def play(
    sequence: Sequence[str],
    rule: PileRule = should_start_new_pile,
    *,
    jokers: bool = False,
) -> tuple[GameResult, FakeCardClient]:
    client = FakeCardClient(sequence)
    return GameEngine(client, rule, jokers=jokers).run(), client


def summary(result: GameResult) -> list[tuple[str, str, str, int]]:
    return [(p.name, p.bottom.code, p.top.code, p.count) for p in result.piles]


def test_a_full_game_in_pack_order() -> None:
    result, _ = play(PACK_ORDER)

    assert summary(result) == [
        ("discard_1", "AS", "QS", 12),
        ("discard_2", "KS", "QD", 13),
        ("discard_3", "KD", "QC", 13),
        ("discard_4", "KC", "QH", 13),
        ("discard_5", "KH", "KH", 1),
    ]
    assert result.deck_id == DECK_ID
    assert result.total_discarded == 52
    assert result.cards_remaining == 0
    assert result.binned == ()


def test_the_local_piles_match_the_piles_added_through_the_api() -> None:
    result, client = play(PACK_ORDER)

    assert client.piles == {
        pile.name: [card.code for card in pile.cards] for pile in result.piles
    }


def test_a_standard_shuffled_deck_is_created() -> None:
    _, client = play(PACK_ORDER)

    assert client.calls[0] == ("create_deck", True, False)


def test_cards_are_drawn_and_added_one_at_a_time() -> None:
    _, client = play(PACK_ORDER)

    assert [call[0] for call in client.calls] == ["create_deck"] + [
        "draw_cards",
        "add_to_pile",
    ] * 52
    draws = [call for call in client.calls if call[0] == "draw_cards"]
    adds = [call for call in client.calls if call[0] == "add_to_pile"]
    assert all(call == ("draw_cards", DECK_ID, 1) for call in draws)
    assert all(len(call[3]) == 1 for call in adds)  # type: ignore[arg-type]


def test_a_king_drawn_first_starts_the_first_pile() -> None:
    result, _ = play(deck("KH"))

    assert summary(result)[0][:2] == ("discard_1", "KH")
    assert len(result.piles) == 4


def test_cards_before_the_first_king_go_in_the_first_pile() -> None:
    result, _ = play(deck("2S", "3S", "KH"))

    assert summary(result)[0] == ("discard_1", "2S", "3S", 2)
    assert summary(result)[1][:2] == ("discard_2", "KH")


def test_a_king_drawn_last_is_alone_in_the_last_pile() -> None:
    result, _ = play(deck(last=["KS"]))

    assert summary(result)[-1] == ("discard_5", "KS", "KS", 1)


def test_consecutive_kings_each_start_a_pile() -> None:
    result, _ = play(deck("KS", "KH", "KD", "KC"))

    assert summary(result)[:3] == [
        ("discard_1", "KS", "KS", 1),
        ("discard_2", "KH", "KH", 1),
        ("discard_3", "KD", "KD", 1),
    ]
    assert summary(result)[3][:2] == ("discard_4", "KC")
    assert result.piles[3].count == 49


def test_an_ace_rule_moves_the_pile_boundaries() -> None:
    def ace_rule(card: Card) -> bool:
        return card.rank == "A"

    result, _ = play(PACK_ORDER, ace_rule)

    assert summary(result) == [
        ("discard_1", "AS", "KS", 13),
        ("discard_2", "AD", "KD", 13),
        ("discard_3", "AC", "KC", 13),
        ("discard_4", "AH", "KH", 13),
    ]


def test_a_game_with_jokers_bins_them() -> None:
    result, client = play(deck("X1", last=["X2"], jokers=True), jokers=True)

    assert client.calls[:2] == [
        ("create_deck", False, True),
        ("shuffle_deck", DECK_ID),
    ]
    assert [card.code for card in result.binned] == ["X1", "X2"]
    assert summary(result)[0][:2] == ("discard_1", "AS")
    assert result.total_discarded == 52
    assert sum(call[0] == "draw_cards" for call in client.calls) == 54
    assert all(not card.is_joker for pile in result.piles for card in pile.cards)


def test_a_joker_between_kings_does_not_start_or_join_a_pile() -> None:
    result, _ = play(deck("KS", "X2", "KH", jokers=True), jokers=True)

    assert summary(result)[0] == ("discard_1", "KS", "KS", 1)
    assert summary(result)[1][:2] == ("discard_2", "KH")


def test_a_new_binning_rule_needs_no_other_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("card_game.engine.should_bin_card", lambda c: c.rank == "2")

    result, _ = play(PACK_ORDER)

    assert [card.code for card in result.binned] == ["2S", "2D", "2C", "2H"]
    assert result.total_discarded == 48


def test_the_sdk_client_can_drive_the_engine() -> None:
    with DeckOfCardsClient() as client:
        engine = GameEngine(client)

    assert isinstance(engine, GameEngine)
