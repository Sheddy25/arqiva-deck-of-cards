# Arqiva Deck of Cards challenge

A reusable Python SDK for the [Deck of Cards API](https://deckofcardsapi.com/)
and a command-line game that uses it. The game draws a shuffled deck one card
at a time into face-down discard piles, and every King starts a new pile.

> **Status:** in progress. The SDK's card model, validation, errors, HTTP
> transport, deck operations, pile operations and live smoke test are done.
> The game's rules, pile model, engine, failure handling, transaction
> logging and command-line app are done, and CI checks every pull request;
> the final documentation is next.
> See [the implementation plan](docs/implementation-plan.md).

## Layout

```text
src/
├── deck_of_cards_sdk/   # Reusable API client, independent of the game
└── card_game/           # Game rules and command-line application
docs/
├── requirements.md      # Requirements from the briefs, with traceability
├── architecture.md      # Design
├── implementation-plan.md  # Step-by-step build plan
└── prompt-sheet.md      # AI prompts used
tests/
├── unit/                # Fast tests of single modules
├── integration/         # SDK over a mock HTTP transport; game over a fake client
└── smoke/               # Opt-in checks against the live API
```

## Setup

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

To install the exact tool versions CI uses, add `-c constraints.txt` to the
install command.

## Play the game

```bash
card-game                         # or: python -m card_game
card-game --jokers                # include the two Jokers, which are binned
card-game --verbose               # also log every transaction, with the cards
card-game --log-file game.jsonl   # append every transaction as JSON Lines
```

Cards are shown face down while they are dealt; the final table shows the
bottom card, top card and count of each pile. The game calls the live API,
so it needs an internet connection.

## Checks

```bash
ruff format --check .   # formatting
ruff check .            # linting
mypy src tests          # type checking
pytest                  # tests (live API smoke tests excluded)
pytest --cov            # tests with coverage, failing below 90%
pip-audit -r constraints.txt --no-deps --disable-pip   # known vulnerabilities
python -m build         # package build
DECK_API_SMOKE=1 pytest -m smoke   # live API smoke tests
```

[CI](.github/workflows/ci.yml) runs every check except the smoke tests on
Python 3.12 and 3.14 for each push and pull request to `main`.

The smoke tests call the real API, so they are opt-in; see
[why the smoke test is opt-in](docs/architecture.md#why-the-smoke-test-is-opt-in).
