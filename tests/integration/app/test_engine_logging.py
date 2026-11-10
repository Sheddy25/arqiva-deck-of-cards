"""Tests for the transactions a game logs (CH-09, INT-06)."""

import logging
from collections import Counter

import pytest

from card_game.engine import GameEngine, GameInterruptedError, GameInvariantError
from deck_of_cards_sdk import RequestTimeoutError
from tests.cards import PACK_ORDER
from tests.fakes import DECK_ID, FakeCardClient

ENGINE_LOGGER = "card_game.engine"


def logged(caplog: pytest.LogCaptureFixture) -> list[tuple[str, dict[str, object]]]:
    """The events logged by the engine, with their context."""
    return [
        (vars(record)["event"], vars(record)["context"])
        for record in caplog.records
        if record.name == ENGINE_LOGGER
    ]


@pytest.fixture(autouse=True)
def _capture_debug(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, ENGINE_LOGGER)


def test_a_full_game_logs_every_transaction(caplog: pytest.LogCaptureFixture) -> None:
    GameEngine(FakeCardClient(PACK_ORDER)).run()

    counts = Counter(event for event, _ in logged(caplog))
    assert counts == {
        "operation.started": 1 + 52 + 52,
        "deck.created": 1,
        "card.drawn": 52,
        "card.discarded": 52,
        "pile.created": 5,
        "game.completed": 1,
    }
    sequences = [vars(record)["sequence"] for record in caplog.records]
    assert sequences == list(range(1, len(sequences) + 1))


def test_each_attempt_is_logged_before_its_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    GameEngine(FakeCardClient(PACK_ORDER)).run()

    assert logged(caplog)[:7] == [
        ("operation.started", {"operation": "create deck", "jokers": False}),
        (
            "deck.created",
            {"deck_id": DECK_ID, "shuffled": True, "remaining": 52},
        ),
        ("operation.started", {"operation": "draw", "deck_id": DECK_ID}),
        ("card.drawn", {"deck_id": DECK_ID, "card": "AS", "remaining": 51}),
        (
            "operation.started",
            {
                "operation": "add to pile",
                "deck_id": DECK_ID,
                "pile": "discard_1",
                "card": "AS",
            },
        ),
        ("pile.created", {"deck_id": DECK_ID, "pile": "discard_1"}),
        (
            "card.discarded",
            {
                "deck_id": DECK_ID,
                "pile": "discard_1",
                "card": "AS",
                "pile_count": 1,
                "remaining": 51,
            },
        ),
    ]
    assert logged(caplog)[-1] == (
        "game.completed",
        {"deck_id": DECK_ID, "piles": 5, "discarded": 52, "binned": 0, "remaining": 0},
    )


def test_a_joker_game_logs_the_shuffle_and_each_joker_binned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    GameEngine(FakeCardClient(["X1", *PACK_ORDER, "X2"]), jokers=True).run()

    events = logged(caplog)
    assert ("deck.shuffled", {"deck_id": DECK_ID, "remaining": 54}) in events
    binned = [context for event, context in events if event == "card.binned"]
    assert binned == [
        {"deck_id": DECK_ID, "card": "X1"},
        {"deck_id": DECK_ID, "card": "X2"},
    ]


def test_a_failure_is_logged_and_the_game_is_not_completed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    timeout = RequestTimeoutError("timed out")
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 2): timeout})

    with pytest.raises(GameInterruptedError):
        GameEngine(client).run()

    assert logged(caplog)[-2:] == [
        (
            "operation.failed",
            {
                "operation": "add to pile",
                "outcome": "unknown",
                "error": "RequestTimeoutError",
                "reason": "timed out",
                "deck_id": DECK_ID,
                "pile": "discard_1",
            },
        ),
        (
            "game.interrupted",
            {
                "deck_id": DECK_ID,
                "outcome": "unknown",
                "piles": 1,
                "discarded": 1,
                "binned": 0,
                "unplaced": ["2S"],
            },
        ),
    ]
    assert all(event != "game.completed" for event, _ in logged(caplog))


def test_a_failed_completion_check_is_logged(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise GameInvariantError("the game broke its rules: example")

    monkeypatch.setattr("card_game.engine.check_invariants", broken)

    with pytest.raises(GameInvariantError):
        GameEngine(FakeCardClient(PACK_ORDER)).run()

    assert logged(caplog)[-1] == (
        "operation.failed",
        {
            "operation": "completion check",
            "reason": "the game broke its rules: example",
        },
    )


def test_log_messages_never_name_a_card(caplog: pytest.LogCaptureFixture) -> None:
    GameEngine(FakeCardClient(PACK_ORDER)).run()

    for message in caplog.messages:
        assert not any(f"={code}" in message for code in PACK_ORDER), message
