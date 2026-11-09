# Arqiva Deck of Cards challenge

A reusable Python SDK for the [Deck of Cards API](https://deckofcardsapi.com/)
and a command-line game that uses it. The game draws a shuffled deck one card
at a time into face-down discard piles, and every King starts a new pile.

> **Status:** in progress. The SDK's card model, validation, errors, HTTP
> transport, deck operations and pile operations are done; the live smoke
> test and the game are next. See
> [the implementation plan](docs/implementation-plan.md).

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
└── integration/         # SDK tests over a mock HTTP transport
```

## Setup

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Checks

```bash
ruff format --check .   # formatting
ruff check .            # linting
mypy src tests          # type checking
pytest                  # tests (live API smoke tests excluded)
```
