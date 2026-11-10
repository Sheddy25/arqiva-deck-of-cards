"""Command-line demonstration of the discard game (CH-03, CH-06, CH-10, INT-05).

Run ``card-game`` or ``python -m card_game``. Cards are dealt face down: the
progress lines never name a card, and only the final report shows the bottom
and top card of each pile.

Exit codes: 0 when the game completes, 1 when it is interrupted or fails its
completion checks, 2 for invalid options, and 130 when cancelled.
"""

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TextIO

from card_game.engine import GameEngine, GameInterruptedError, GameInvariantError
from card_game.events import ConsoleFormatter, Event, JsonLinesFormatter
from card_game.models import DiscardPile, GameResult
from card_game.ports import CardClient
from deck_of_cards_sdk import CARD_BACK_IMAGE, Card, DeckOfCardsClient

ClientFactory = Callable[[], AbstractContextManager[CardClient]]

_GAME_LOGGER = "card_game"


def main(
    argv: Sequence[str] | None = None,
    client_factory: ClientFactory = DeckOfCardsClient,
) -> int:
    """Play one game and print its report.

    Args:
        argv: the command-line options; ``sys.argv[1:]`` by default.
        client_factory: makes the client for the game, as a context manager
            that closes it afterwards.

    Returns:
        The exit code.
    """
    args = _parse_args(argv)
    out = sys.stdout
    try:
        handlers = _make_handlers(args, out)
    except OSError as error:
        print(f"error: cannot open the log file: {error}", file=sys.stderr)
        return 1

    logger = logging.getLogger(_GAME_LOGGER)
    level = logger.level
    propagate = logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for handler in handlers:
        logger.addHandler(handler)
    try:
        return _play(client_factory, args.jokers, out)
    finally:
        for handler in handlers:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(level)
        logger.propagate = propagate


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="card-game",
        description=(
            "Deal a shuffled deck one card at a time into face-down discard "
            "piles, starting a new pile at each King, then report each pile."
        ),
    )
    parser.add_argument(
        "--jokers",
        action="store_true",
        help="include the two Jokers, which are binned when drawn",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="log every transaction to standard error, showing the cards",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        metavar="PATH",
        help="append every transaction to PATH as JSON Lines",
    )
    return parser.parse_args(argv)


def _make_handlers(args: argparse.Namespace, out: TextIO) -> list[logging.Handler]:
    handlers: list[logging.Handler] = [_ProgressHandler(out)]
    if args.verbose:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(ConsoleFormatter(show_cards=True))
        handlers.append(console)
    if args.log_file is not None:
        audit = logging.FileHandler(args.log_file, encoding="utf-8")
        audit.setFormatter(JsonLinesFormatter())
        handlers.append(audit)
    return handlers


def _play(client_factory: ClientFactory, jokers: bool, out: TextIO) -> int:
    print(f"Cards are dealt face down (card back: {CARD_BACK_IMAGE}).", file=out)
    try:
        with client_factory() as client:
            result = GameEngine(client, jokers=jokers).run()
    except GameInterruptedError as error:
        print(f"error: {error}", file=sys.stderr)
        if error.piles:
            print("\nPiles confirmed before the game stopped:", file=out)
            print(_pile_table(error.piles), file=out)
        return 1
    except GameInvariantError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Game cancelled.", file=sys.stderr)
        return 130
    _print_report(result, out)
    return 0


def _print_report(result: GameResult, out: TextIO) -> None:
    print(f"\nGame complete: {len(result.piles)} piles.", file=out)
    print(_pile_table(result.piles), file=out)
    print(f"\nTotal discarded: {result.total_discarded}", file=out)
    print(f"Cards remaining: {result.cards_remaining}", file=out)
    if result.binned:
        print(f"Cards binned: {len(result.binned)} ({_names(result.binned)})", file=out)


def _pile_table(piles: Sequence[DiscardPile]) -> str:
    rows = [("Pile", "Bottom card", "Top card", "Cards")]
    rows += [(p.name, p.bottom.name, p.top.name, str(p.count)) for p in piles]
    widths = [max(len(row[column]) for row in rows) for column in range(4)]
    lines = [
        f"{name:<{widths[0]}}  {bottom:<{widths[1]}}  "
        f"{top:<{widths[2]}}  {count:>{widths[3]}}"
        for name, bottom, top, count in rows
    ]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _names(cards: Sequence[Card]) -> str:
    return ", ".join(card.name for card in cards)


class _ProgressHandler(logging.Handler):
    """Shows the game's progress from its transaction events, keeping every
    card face down."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__(logging.INFO)
        self._stream = stream
        self._deck_size: object = "?"
        self._drawn = 0
        self._new_pile = False

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "event", None)
        context: dict[str, object] = getattr(record, "context", {})
        if event == Event.DECK_CREATED:
            self._deck_size = context.get("remaining")
            self._write(
                f"Created deck {context.get('deck_id')} with {self._deck_size} cards."
            )
        elif event == Event.DECK_SHUFFLED:
            self._write(f"Shuffled deck {context.get('deck_id')}.")
        elif event == Event.CARD_DRAWN:
            self._drawn += 1
        elif event == Event.PILE_CREATED:
            self._new_pile = True
        elif event == Event.CARD_DISCARDED:
            marker = "face down, new pile" if self._new_pile else "face down"
            self._write(f"{self._card()} -> {context.get('pile')} [{marker}]")
            self._new_pile = False
        elif event == Event.CARD_BINNED:
            self._write(f"{self._card()} -> binned (Joker)")

    def _card(self) -> str:
        width = len(str(self._deck_size))
        return f"Card {self._drawn:>{width}}/{self._deck_size}"

    def _write(self, line: str) -> None:
        self._stream.write(line + "\n")
