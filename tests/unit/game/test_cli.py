"""Tests for the command-line app over a fake client (CH-03, CH-06, CH-09,
CH-10, INT-05, DEC-02)."""

import contextlib
import inspect
import io
import json
import logging
import runpy
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from card_game.cli import main
from card_game.engine import GameInvariantError
from deck_of_cards_sdk import CARD_BACK_IMAGE, DeckOfCardsClient, RequestTimeoutError
from tests.cards import PACK_ORDER, make_card
from tests.fakes import DECK_ID, FakeCardClient

Factory = Callable[[], AbstractContextManager[FakeCardClient]]


def factory(client: FakeCardClient) -> Factory:
    return lambda: contextlib.nullcontext(client)


def closing_factory(client: FakeCardClient, closed: list[str]) -> Factory:
    """A factory whose client records in ``closed`` when it is closed."""

    @contextlib.contextmanager
    def tracked() -> Iterator[FakeCardClient]:
        try:
            yield client
        finally:
            closed.append("closed")

    return tracked


def cancelled() -> AbstractContextManager[FakeCardClient]:
    raise KeyboardInterrupt


def run(
    capsys: pytest.CaptureFixture[str],
    *args: str,
    client: FakeCardClient | None = None,
) -> tuple[int, str, str]:
    """Run the app with ``args`` and return the exit code, output and errors."""
    client = client or FakeCardClient(PACK_ORDER)
    code = main(list(args), factory(client))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_a_game_reports_every_pile(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys)

    assert code == 0
    assert err == ""
    report = out[out.index("Game complete") :]
    assert report.splitlines() == [
        "Game complete: 5 piles.",
        "Pile       Bottom card       Top card           Cards",
        "---------  ----------------  -----------------  -----",
        "discard_1  Ace of Spades     Queen of Spades       12",
        "discard_2  King of Spades    Queen of Diamonds     13",
        "discard_3  King of Diamonds  Queen of Clubs        13",
        "discard_4  King of Clubs     Queen of Hearts       13",
        "discard_5  King of Hearts    King of Hearts         1",
        "",
        "Total discarded: 52",
        "Cards remaining: 0",
    ]


def test_progress_keeps_every_card_face_down(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out, _ = run(capsys)

    progress = out[: out.index("\nGame complete")].splitlines()
    assert progress[:4] == [
        f"Cards are dealt face down (card back: {CARD_BACK_IMAGE}).",
        f"Created deck {DECK_ID} with 52 cards.",
        "Card  1/52 -> discard_1 [face down, new pile]",
        "Card  2/52 -> discard_1 [face down]",
    ]
    assert progress[-1] == "Card 52/52 -> discard_5 [face down, new pile]"
    assert len(progress) == 2 + 52
    names = {make_card(code).name for code in PACK_ORDER}
    for line in progress:
        assert not any(name in line for name in names), line
        assert not any(f" {code} " in f" {line} " for code in PACK_ORDER), line


def test_a_joker_game_bins_and_reports_the_jokers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeCardClient(["X1", *PACK_ORDER, "X2"])

    code, out, _ = run(capsys, "--jokers", client=client)

    assert code == 0
    assert client.calls[0] == ("create_deck", False, True)
    assert f"Shuffled deck {DECK_ID}." in out
    assert "Card  1/54 -> binned (Joker)" in out
    assert "Card 54/54 -> binned (Joker)" in out
    assert out.endswith("Cards binned: 2 (Black Joker, Red Joker)\n")


def test_an_interrupted_game_exits_1_and_shows_the_confirmed_piles(
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeout = RequestTimeoutError("request timed out")
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 3): timeout})

    code, out, err = run(capsys, client=client)

    assert code == 1
    assert err == (
        "error: game interrupted: add to pile had an unknown outcome: "
        "request timed out; not confirmed in a pile: 3S\n"
    )
    assert "Game complete" not in out
    assert out.endswith(
        "Piles confirmed before the game stopped:\n"
        "Pile       Bottom card    Top card     Cards\n"
        "---------  -------------  -----------  -----\n"
        "discard_1  Ace of Spades  2 of Spades      2\n"
    )


def test_a_game_stopped_before_any_pile_shows_no_table(
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure = RequestTimeoutError("request timed out")
    client = FakeCardClient(PACK_ORDER, fail={("create_deck", 1): failure})

    code, out, err = run(capsys, client=client)

    assert code == 1
    assert "create deck" in err
    assert "Piles confirmed" not in out


def test_a_failed_completion_check_exits_1(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise GameInvariantError("the game broke its rules: example")

    monkeypatch.setattr("card_game.engine.check_invariants", broken)

    code, out, err = run(capsys)

    assert code == 1
    assert err == "error: the game broke its rules: example\n"
    assert "Game complete" not in out


def test_cancelling_exits_130(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([], cancelled)

    assert code == 130
    assert capsys.readouterr().err == "Game cancelled.\n"


def test_verbose_logs_every_transaction_with_the_cards(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out, err = run(capsys, "--verbose")

    lines = err.splitlines()
    assert lines[0] == "DEBUG #1 operation.started operation=create deck jokers=False"
    assert "INFO #4 card.drawn deck_id=fakedeck01 remaining=51 card=AS" in lines
    assert lines[-1].startswith("INFO #216 game.completed")
    assert "card=" not in out


def test_the_log_file_gets_every_transaction_as_json(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "audit.jsonl"

    code, _, _ = run(capsys, "--log-file", str(path))

    entries = [json.loads(line) for line in path.read_text().splitlines()]
    assert code == 0
    assert [entry["sequence"] for entry in entries] == list(range(1, 217))
    drawn = [entry["card"] for entry in entries if entry["event"] == "card.drawn"]
    assert drawn == PACK_ORDER


def test_a_log_file_that_cannot_be_opened_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, _, err = run(capsys, "--log-file", str(tmp_path / "missing" / "a.jsonl"))

    assert code == 1
    assert err.startswith("error: cannot open the log file:")


def test_the_log_file_is_appended_to(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "audit.jsonl"

    run(capsys, "--log-file", str(path))
    run(capsys, "--log-file", str(path))

    entries = [json.loads(line) for line in path.read_text().splitlines()]
    assert [entry["sequence"] for entry in entries] == [*range(1, 217)] * 2


def test_the_log_file_records_an_interrupted_game(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "audit.jsonl"
    timeout = RequestTimeoutError("request timed out")
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 3): timeout})

    run(capsys, "--log-file", str(path), client=client)

    entries = [json.loads(line) for line in path.read_text().splitlines()]
    assert [entry["event"] for entry in entries[-2:]] == [
        "operation.failed",
        "game.interrupted",
    ]
    assert entries[-1]["unplaced"] == ["3S"]


def test_verbose_shows_the_failure_before_the_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeout = RequestTimeoutError("request timed out")
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 3): timeout})

    _, _, err = run(capsys, "--verbose", client=client)

    lines = err.splitlines()
    assert lines[-3].startswith(
        "ERROR #15 operation.failed operation=add to pile outcome=unknown"
    )
    assert lines[-2] == (
        "ERROR #16 game.interrupted deck_id=fakedeck01 outcome=unknown piles=1 "
        "discarded=2 binned=0 unplaced=3S"
    )
    assert lines[-1].startswith("error: game interrupted: add to pile")


@pytest.mark.parametrize(
    "fail",
    [{}, {("add_to_pile", 3): RequestTimeoutError("request timed out")}],
    ids=["completed", "interrupted"],
)
def test_the_client_is_closed_after_the_game(
    capsys: pytest.CaptureFixture[str],
    fail: dict[tuple[str, int], RequestTimeoutError],
) -> None:
    closed: list[str] = []
    client = FakeCardClient(PACK_ORDER, fail=fail)

    main([], closing_factory(client, closed))

    assert closed == ["closed"]


@pytest.mark.parametrize(
    "client_factory",
    [
        factory(FakeCardClient(PACK_ORDER)),
        factory(
            FakeCardClient(
                PACK_ORDER, fail={("draw_cards", 2): RequestTimeoutError("timed out")}
            )
        ),
        cancelled,
    ],
    ids=["completed", "interrupted", "cancelled"],
)
def test_logging_is_restored_after_a_game(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, client_factory: Factory
) -> None:
    logger = logging.getLogger("card_game")
    before = (list(logger.handlers), logger.level, logger.propagate)

    main(["--verbose", "--log-file", str(tmp_path / "a.jsonl")], client_factory)

    assert (list(logger.handlers), logger.level, logger.propagate) == before


def test_cli_transactions_do_not_propagate_to_the_root_logger(
    capsys: pytest.CaptureFixture[str],
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        code, _, _ = run(capsys)
    finally:
        root.removeHandler(handler)
        handler.close()

    assert code == 0
    assert stream.getvalue() == ""


def test_the_real_client_is_used_by_default() -> None:
    default = inspect.signature(main).parameters["client_factory"].default

    assert default is DeckOfCardsClient


def test_invalid_options_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--colour"])

    assert error.value.code == 2
    assert "unrecognized arguments: --colour" in capsys.readouterr().err


def test_python_dash_m_runs_the_app(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["card_game", "--help"])

    with pytest.raises(SystemExit) as error:
        runpy.run_module("card_game", run_name="__main__")

    assert error.value.code == 0
    assert "usage: card-game" in capsys.readouterr().out
