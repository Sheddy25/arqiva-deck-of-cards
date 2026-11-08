# Arqiva Deck of Cards challenge

A reusable Python SDK for the [Deck of Cards API](https://deckofcardsapi.com/)
and a command-line game that uses it. The game draws a shuffled deck one card
at a time into face-down discard piles, and every King starts a new pile.

> **Status:** project structure only. The SDK and game are not implemented yet.

## Layout

```text
src/
├── deck_of_cards_sdk/   # Reusable API client, independent of the game
└── card_game/           # Game rules and command-line application
docs/
├── architecture.md      # Design
└── prompt-sheet.md      # AI prompts used
```

## Setup

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```
