# Arqiva Deck of Cards challenge

A reusable Python SDK for the [Deck of Cards API](https://deckofcardsapi.com/)
and a command-line game that uses it. The game draws a shuffled deck one card
at a time into face-down discard piles, and every King starts a new pile. It
logs each transaction, then reports the bottom card, top card and count of
each pile.

> **Status:** complete. The SDK, the game, the command-line app and CI are
> built and tested; see [the implementation plan](docs/implementation-plan.md).

## Layout

```text
src/
├── deck_of_cards_sdk/   # Reusable API client, independent of the game
└── card_game/           # Game rules, engine and command-line app
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

### Example output

From a live game, with the middle of the deal left out:

```text
$ card-game
Cards are dealt face down (card back: https://deckofcardsapi.com/static/img/back.png).
Created deck 7o3lry9bmfl3 with 52 cards.
Card  1/52 -> discard_1 [face down, new pile]
Card  2/52 -> discard_1 [face down]
Card  3/52 -> discard_1 [face down]
...
Card 50/52 -> discard_4 [face down]
Card 51/52 -> discard_5 [face down, new pile]
Card 52/52 -> discard_5 [face down]

Game complete: 5 piles.
Pile       Bottom card       Top card         Cards
---------  ----------------  ---------------  -----
discard_1  7 of Diamonds     Jack of Spades      22
discard_2  King of Spades    10 of Hearts         8
discard_3  King of Hearts    Ace of Clubs        11
discard_4  King of Clubs     3 of Clubs           9
discard_5  King of Diamonds  Queen of Spades      2

Total discarded: 52
Cards remaining: 0
```

The first card was not a King, so the cards before the first King form
`discard_1`. Each King is the bottom card of the pile it starts.

With `--jokers`, each Joker is binned instead of placed in a pile, and the
report adds a line for the binned cards:

```text
Card 48/54 -> binned (Joker)
...
Cards binned: 2 (Red Joker, Black Joker)
```

`--verbose` writes the numbered transaction log, with the cards, to standard
error. Attempts are logged at `DEBUG` before each API call, and confirmed
results at `INFO`:

```text
DEBUG #1 operation.started operation=create deck jokers=True
INFO #2 deck.created deck_id=xe1ubmrecfih shuffled=False remaining=54
DEBUG #3 operation.started operation=shuffle deck deck_id=xe1ubmrecfih
INFO #4 deck.shuffled deck_id=xe1ubmrecfih remaining=54
...
INFO #199 card.binned deck_id=xe1ubmrecfih card=X2
...
INFO #224 game.completed deck_id=xe1ubmrecfih piles=5 discarded=52 binned=2 remaining=0
```

`--log-file` writes the same transactions as one JSON object per line, with
the time, level, sequence, event and full context.

## Use the SDK on its own

The SDK knows nothing about the game, so it can be used for any program that
needs the API:

```python
from deck_of_cards_sdk import DeckOfCardsClient, DeckOfCardsError

with DeckOfCardsClient() as client:
    deck = client.create_deck()
    draw = client.draw_cards(deck.deck_id, 2)
    print([card.name for card in draw.cards], draw.remaining)
    # ['King of Diamonds', '2 of Diamonds'] 50

    client.add_to_pile(deck.deck_id, "hand", [card.code for card in draw.cards])
    print(client.list_pile(deck.deck_id, "hand").cards)

    try:
        client.add_to_pile(deck.deck_id, "hand", ["AS"])
    except DeckOfCardsError as error:
        print(error)
        # card AS has not been drawn from deck 7vl5zctambj8 by this client
```

`DeckOfCardsClient` covers every documented operation: shuffled, unshuffled
and partial decks, draws, reshuffles, pile add, shuffle, list and draw, and
returns. Results are frozen dataclasses such as `Card`, `Deck`, `DrawResult`
and `PileListing`.

The client only lets a card into a pile if this client drew it and it is not
already in a pile. The API itself accepts a card that was never drawn without
placing it, and silently moves a card from another pile (OBS-05, DEC-06 in
[the requirements](docs/requirements.md)).

## Error handling

Every SDK error is a `DeckOfCardsError`, so callers can catch one type:

| Error | When |
| --- | --- |
| `InvalidArgumentError` | An argument is invalid, so no request was sent |
| `RequestTimeoutError`, `ConnectionFailedError` (both `TransportError`) | No HTTP response was received |
| `HttpStatusError` | The API answered with a non-2xx status, such as 404 for an unknown deck |
| `ResponseFormatError` | The response was not the JSON the SDK expects |
| `ApiError` | The API answered `"success": false` |
| `IncompleteDrawError` (an `ApiError`) | A draw asked for more cards than remained; it holds the cards that were drawn |

The SDK never retries. The API uses `GET` even for calls that change state,
so a retry could draw or move a card twice.

The game stops at the first failed call and says whether the API refused it
(`rejected`) or whether it may have taken effect (`unknown`, such as after a
timeout). It then shows the piles the API confirmed before the failure:

```text
error: game interrupted: add to pile had an unknown outcome: request timed out; not confirmed in a pile: 3S

Piles confirmed before the game stopped:
Pile       Bottom card    Top card     Cards
---------  -------------  -----------  -----
discard_1  Ace of Spades  2 of Spades      2
```

At the end of a game, completion checks confirm the piles hold exactly one
standard pack in draw order and that every pile starts where the rule says.
A game that fails them is reported as an error, not a result.

The exit code is 0 for a completed game, 1 for an interrupted game, a failed
completion check or a log file that cannot be opened, 2 for invalid options,
and 130 when cancelled with Ctrl+C.

## Tests and checks

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

The default test run makes no network calls. The SDK tests use
`httpx.MockTransport`, and the game tests use a fake client that deals cards
in a fixed order, so a King first, a King last or consecutive Kings can be
tested exactly.

The smoke tests call the real API, so they are opt-in; see
[why the smoke test is opt-in](docs/architecture.md#why-the-smoke-test-is-opt-in).

## Continuous integration

[CI](.github/workflows/ci.yml) runs every check except the smoke tests on
Python 3.12 and 3.14 for each push and pull request to `main`. It installs
the pinned versions in `constraints.txt`, its actions are pinned to commit
hashes, and its token is read-only.

## Limitations

- The game needs the live API, which states no availability guarantee.
- After a timeout the result of that call is unknown. The game stops and
  reports it rather than trying to recover, and an interrupted game cannot be
  resumed.
- The game uses one deck, because the API's piles do not work with several
  decks.
- Joker codes (`X1`, `X2`) come from the live API, not the API reference, so
  a future API change could alter them.
- The pile guard only knows about cards drawn through the same client.

## How this was built

I wrote the bulk of the code. Where I used AI, [the prompt
sheet](docs/prompt-sheet.md) records each prompt and credits the AI with the
work it produced.
