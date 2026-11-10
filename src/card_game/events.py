"""Transaction logging for the game (CH-09, INT-06).

Each game action is logged as an :class:`Event` with a sequence number and
context such as the deck ID, pile and cards remaining. Card codes are kept in
the record's ``context`` but left out of its message, so a plain console log
keeps the cards face down; :class:`JsonLinesFormatter` writes them to an
audit file.
"""

import json
import logging
from datetime import UTC, datetime
from enum import StrEnum


class Event(StrEnum):
    """The transactions a game logs."""

    OPERATION_STARTED = "operation.started"
    DECK_CREATED = "deck.created"
    DECK_SHUFFLED = "deck.shuffled"
    CARD_DRAWN = "card.drawn"
    PILE_CREATED = "pile.created"
    CARD_DISCARDED = "card.discarded"
    CARD_BINNED = "card.binned"
    OPERATION_FAILED = "operation.failed"
    GAME_COMPLETED = "game.completed"
    GAME_INTERRUPTED = "game.interrupted"


CARD_FIELDS = frozenset({"card", "unplaced"})
"""Context fields that name cards, which a plain console log must not show."""

_LEVELS = {
    Event.OPERATION_STARTED: logging.DEBUG,
    Event.OPERATION_FAILED: logging.ERROR,
    Event.GAME_INTERRUPTED: logging.ERROR,
}


class TransactionLog:
    """Logs the transactions of one game, numbering them from 1."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._sequence = 0

    def record(self, event: Event, **context: object) -> None:
        """Log ``event`` with its context.

        The record carries ``event``, ``sequence`` and ``context`` as extra
        attributes for formatters. Context values of ``None`` are dropped.
        """
        self._sequence += 1
        context = {key: value for key, value in context.items() if value is not None}
        shown = " ".join(
            f"{key}={value}" for key, value in context.items() if key not in CARD_FIELDS
        )
        message = f"#{self._sequence} {event}" + (f" {shown}" if shown else "")
        self._logger.log(
            _LEVELS.get(event, logging.INFO),
            message,
            extra={
                "event": str(event),
                "sequence": self._sequence,
                "context": context,
            },
        )


class JsonLinesFormatter(logging.Formatter):
    """Formats each record as one JSON object, for an audit file.

    Transaction records give their time, level, sequence, event and full
    context, including card codes. Other records give their message.
    """

    def format(self, record: logging.LogRecord) -> str:
        time = datetime.fromtimestamp(record.created, UTC).isoformat()
        entry: dict[str, object] = {"time": time, "level": record.levelname}
        event = getattr(record, "event", None)
        if event is None:
            entry["message"] = record.getMessage()
        else:
            entry["sequence"] = getattr(record, "sequence", None)
            entry["event"] = event
            entry.update(getattr(record, "context", {}))
        return json.dumps(entry, default=str)
