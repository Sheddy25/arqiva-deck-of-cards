"""Tests for the transaction log and its JSON Lines formatter (CH-09, INT-06)."""

import json
import logging

import pytest

from card_game.events import (
    ConsoleFormatter,
    Event,
    JsonLinesFormatter,
    TransactionLog,
)

LOGGER = "tests.events"


def test_card_game_library_has_a_null_handler() -> None:
    handlers = logging.getLogger("card_game").handlers

    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)


def records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER]


def test_each_event_is_numbered_in_order(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)
    log = TransactionLog(logging.getLogger(LOGGER))

    log.record(Event.DECK_CREATED, deck_id="abc123", remaining=52)
    log.record(Event.CARD_DRAWN, deck_id="abc123", card="KH", remaining=51)

    logged = [vars(record) for record in records(caplog)]
    assert [r["event"] for r in logged] == ["deck.created", "card.drawn"]
    assert [r["sequence"] for r in logged] == [1, 2]
    assert logged[1]["context"] == {
        "deck_id": "abc123",
        "card": "KH",
        "remaining": 51,
    }


def test_the_message_keeps_cards_face_down(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)
    log = TransactionLog(logging.getLogger(LOGGER))

    log.record(Event.CARD_DRAWN, deck_id="abc123", card="KH", remaining=51)
    log.record(Event.GAME_INTERRUPTED, outcome="unknown", unplaced=["KH"])

    assert caplog.messages == [
        "#1 card.drawn deck_id=abc123 remaining=51",
        "#2 game.interrupted outcome=unknown",
    ]


def test_empty_context_values_are_dropped(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)

    TransactionLog(logging.getLogger(LOGGER)).record(
        Event.OPERATION_FAILED, operation="draw", pile=None
    )

    assert caplog.messages == ["#1 operation.failed operation=draw"]
    assert vars(records(caplog)[0])["context"] == {"operation": "draw"}


@pytest.mark.parametrize(
    ("event", "level"),
    [
        (Event.OPERATION_STARTED, logging.DEBUG),
        (Event.CARD_DISCARDED, logging.INFO),
        (Event.GAME_COMPLETED, logging.INFO),
        (Event.OPERATION_FAILED, logging.ERROR),
        (Event.GAME_INTERRUPTED, logging.ERROR),
    ],
)
def test_events_are_logged_at_their_level(
    caplog: pytest.LogCaptureFixture, event: Event, level: int
) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)

    TransactionLog(logging.getLogger(LOGGER)).record(event)

    assert records(caplog)[0].levelno == level


def test_the_console_formatter_shows_cards_only_when_asked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)
    log = TransactionLog(logging.getLogger(LOGGER))
    log.record(Event.CARD_DRAWN, deck_id="abc123", card="KH")
    log.record(Event.GAME_INTERRUPTED, unplaced=["KH", "2S"])
    drawn, interrupted = records(caplog)

    assert ConsoleFormatter().format(drawn) == "INFO #1 card.drawn deck_id=abc123"
    assert ConsoleFormatter(show_cards=True).format(drawn) == (
        "INFO #1 card.drawn deck_id=abc123 card=KH"
    )
    assert ConsoleFormatter(show_cards=True).format(interrupted) == (
        "ERROR #2 game.interrupted unplaced=KH,2S"
    )


def test_the_json_formatter_writes_one_object_with_the_cards(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, LOGGER)
    log = TransactionLog(logging.getLogger(LOGGER))
    log.record(Event.CARD_DISCARDED, pile="discard_2", card="0H", pile_count=3)

    line = JsonLinesFormatter().format(records(caplog)[0])

    assert "\n" not in line
    entry = json.loads(line)
    assert entry.pop("time").endswith("+00:00")
    assert entry == {
        "level": "INFO",
        "sequence": 1,
        "event": "card.discarded",
        "pile": "discard_2",
        "card": "0H",
        "pile_count": 3,
    }


def test_the_json_formatter_writes_other_records_as_messages() -> None:
    record = logging.LogRecord(
        LOGGER, logging.WARNING, __file__, 1, "%s", ("hi",), None
    )

    entry = json.loads(JsonLinesFormatter().format(record))

    assert entry["level"] == "WARNING"
    assert entry["message"] == "hi"
    assert "event" not in entry
