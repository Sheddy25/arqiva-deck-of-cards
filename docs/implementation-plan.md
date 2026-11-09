# Implementation plan

A step-by-step plan for building the SDK and game. Each step is a small,
reviewable unit of work. Module names follow
[architecture.md](architecture.md), and the requirement IDs listed for each
step are defined in [requirements.md](requirements.md).

## How to work through each step

1. Read the step, its requirements and the files it touches.
2. Create a feature branch from the latest `main`, for example
   `feat/sdk-card-model` (DEC-05).
3. Write the tests first where practical, then the code.
4. Run the checks:

   ```bash
   ruff format .
   ruff check .
   mypy src tests
   pytest
   ```

5. Review the full diff with `git diff`.
6. Add any AI prompt you used to `docs/prompt-sheet.md` (CH-02, CH-12).
7. Stage the files by name and commit with the suggested message.
8. Push the branch, open a pull request, and merge it into `main` with a merge
   commit. Keep the branch.

## Final file layout

```text
.github/workflows/ci.yml
docs/
src/
├── deck_of_cards_sdk/
│   ├── __init__.py        # public exports
│   ├── exceptions.py      # error hierarchy
│   ├── validation.py      # input and field checks
│   ├── models.py          # Card, Deck, DrawResult, pile models
│   ├── transport.py       # all HTTP handling
│   └── client.py          # DeckOfCardsClient
└── card_game/
    ├── __init__.py
    ├── __main__.py        # python -m card_game
    ├── rules.py           # when to start a new pile
    ├── models.py          # DiscardPile, GameResult
    ├── ports.py           # CardClient protocol the engine needs
    ├── engine.py          # the game loop
    ├── events.py          # transaction logging
    └── cli.py             # arguments, output, exit codes
tests/
├── fakes.py               # FakeCardClient for game tests
├── unit/sdk/
├── unit/game/
├── integration/sdk/
├── integration/app/
└── smoke/
```

---

## Step 1 — Project structure ✅

**Requirements:** CH-01, CH-14, DEC-01

**Files:** `.gitignore`, `README.md`, `pyproject.toml`,
`src/deck_of_cards_sdk/__init__.py`, `src/card_game/__init__.py`

**Commit:** `chore: initialise Python project structure`

---

## Step 2 — Quality tooling ✅

**Requirements:** CH-01, CH-11

**`pyproject.toml`** — add:

- `[project.optional-dependencies] dev = [...]` with `pytest`, `pytest-cov`,
  `ruff` and `mypy`.
- `[tool.ruff]`: `line-length = 88`, `target-version = "py312"`, and a
  `[tool.ruff.lint]` `select` list such as `["E", "F", "I", "B", "UP", "SIM"]`.
- `[tool.mypy]`: `strict = true`, `python_version = "3.12"`.
- `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, a `smoke` marker, and
  `addopts = "-m 'not smoke'"` so live API tests never run by default.

**`tests/test_imports.py`** — one real test: both packages import, and
importing `deck_of_cards_sdk` does not import `card_game`. This proves the SDK
is independent from day one.

**Done when:** `pip install -e ".[dev]"` works and all four checks pass.

**Commit:** `chore: configure linting, typing and tests`

---

## Step 3 — Card model

**Requirements:** CH-01, API-06, API-13, OBS-01, DEC-02

**`src/deck_of_cards_sdk/models.py`**

- `Card`: a frozen dataclass with `code`, `value`, `suit` and `image`.
- Properties: `rank` (first character of the code) and `is_king`
  (`rank == "K"`).
- `parse_card(data: Mapping[str, object]) -> Card`:
  - requires `code`, `value` and `suit` to be strings;
  - upper-cases the code;
  - checks the code is two characters and its suit letter matches `suit`;
  - accepts `0` as the code for ten (value `"10"`);
  - raises `ValueError` for now (replaced by the SDK error in step 4).

**`tests/unit/sdk/test_models.py`** — valid card; ten (`0H`); King (`KS`,
`is_king` is true); lower-case code; missing field; wrong type; suit
mismatch.

> **Change (2026-11-08):** `parse_card` also requires `image` to be a
> string, checks the code's rank against `value` as well as its suit against
> `suit`, rejects unknown codes, and ignores extra fields such as `images`.
> The tests also cover Ace, Jack and Queen, unknown codes, a value mismatch,
> extra fields and immutability.
>
> **Reason:** every card in the API reference has an `image` (API-13), and
> checking only the suit would accept a card whose value contradicts its
> code (API-06, OBS-01).

> **Change (2026-11-08):** added empty `tests/__init__.py`,
> `tests/unit/__init__.py` and `tests/unit/sdk/__init__.py` files.
>
> **Reason:** they make the test folders packages, so test modules with the
> same name in different folders (such as `test_models.py` for the SDK and
> the game) do not clash in pytest or mypy.

> **Change (2026-11-08):** `parse_card` accepted the Joker codes `X1`
> (`BLACK`) and `X2` (`RED`) with value `JOKER`, and `Card` gained an
> `is_joker` property.
>
> **Reason:** the live API returns these codes for a deck created with
> `jokers_enabled=true` (OBS-02), so the documented Joker option would work.

> **Change (2026-11-09):** Joker support was removed. `X1` and `X2` are
> rejected as unknown card codes, and `is_joker` no longer exists (DEC-02).
>
> **Reason:** to follow the brief. The API reference documents only
> two-character rank-and-suit codes (API-06) and never documents Joker codes,
> so the SDK does not rely on undocumented behaviour.

**Commit:** `feat(sdk): add card model and parsing`

---

## Step 4 — Exceptions and validation

**Requirements:** CH-01, API-06, API-09, OBS-03, DEC-02

**`src/deck_of_cards_sdk/exceptions.py`** — a small hierarchy:

```text
DeckOfCardsError
├── InvalidArgumentError     # bad input, raised before any request
├── TransportError           # could not get a response
│   ├── RequestTimeoutError
│   └── ConnectionFailedError
├── HttpStatusError          # non-2xx; stores status_code
├── ResponseFormatError      # bad JSON or unexpected fields/types
└── ApiError                 # API returned success: false; stores message
```

**`src/deck_of_cards_sdk/validation.py`**

- `validate_deck_id(deck_id)`: non-empty letters and digits only.
- `validate_count(count)`: an `int`, not a `bool`, at least 1.
- `validate_pile_name(name)`: letters, digits, `_` and `-` only.
- `validate_card_codes(codes)`: a non-empty list of valid two-character codes
  (`A 2-9 0 J Q K` + `S D C H`), returned upper-cased.
- `parse_int_field(value, field)`: accepts `int` or a decimal string such as
  `"42"`; rejects `bool`, negatives and other strings. The API sometimes sends
  numbers as strings.

Update `parse_card` to raise `ResponseFormatError`.

**Tests:** `tests/unit/sdk/test_validation.py` with valid and invalid cases
for every function, including `True` passed as a count and `"4x"` as a
number.

> **Change (2026-11-09):** the card-code tables
> (`RANK_VALUES`, `SUIT_NAMES`) and a new `is_card_code(code)` function were
> moved from `models.py` into `validation.py`.
>
> **Reason:** `parse_card` and `validate_card_codes` need the same list of
> valid codes, so they share one copy. The copy cannot stay in `models.py`,
> because step 6 makes `models.py` import `validation.py` for
> `parse_int_field`, and two modules importing each other would fail.

> **Change (2026-11-09):** added
> `tests/unit/sdk/test_exceptions.py`, which checks that every error is a
> `DeckOfCardsError` and that `HttpStatusError` keeps its `status_code`.
>
> **Reason:** the hierarchy is part of the SDK's public contract, and a few
> small tests stop it changing by accident.

> **Change (2026-11-09):** `ApiError` stores the API's
> message as the normal exception message (`str(error)`), not as a separate
> `message` attribute.
>
> **Reason:** a separate attribute would duplicate what every Python
> exception already holds.

**Commit:** `feat(sdk): add exceptions and input validation`

---

## Step 5 — HTTP transport

**Requirements:** CH-01, API-13, INT-08

**`pyproject.toml`** — add `httpx` to `dependencies`.

**`src/deck_of_cards_sdk/transport.py`**

- `DEFAULT_BASE_URL = "https://deckofcardsapi.com/api/"`.
- `DEFAULT_TIMEOUT = httpx.Timeout(10.0)`.
- `HttpTransport` class:
  - `__init__(base_url=..., timeout=..., client: httpx.Client | None = None)`;
    rejects a base URL that isn't HTTPS;
  - `get_json(path, params=None) -> dict[str, object]`, the only method that
    sends requests;
  - `close()`, `__enter__` and `__exit__`.
- `get_json` translates failures into SDK errors:
  - `httpx.TimeoutException` → `RequestTimeoutError`;
  - `httpx.ConnectError` → `ConnectionFailedError`;
  - non-2xx → `HttpStatusError`;
  - invalid JSON or a non-object root → `ResponseFormatError`;
  - `success` not exactly `true` → `ApiError`.
- No automatic retries. Many API calls change state even though they use
  `GET`, so retrying could draw or move a card twice.

**`tests/integration/sdk/test_transport.py`** — use `httpx.MockTransport`
for: success, 404, 500, timeout, connection error, invalid JSON, a list root,
`success: false`, a missing `success`, and an HTTP base URL being rejected.

**Commit:** `feat(sdk): add HTTP transport with error handling`

---

## Step 6 — Deck operations

**Requirements:** CH-01, API-01 to API-05, OBS-03, DEC-02

**`src/deck_of_cards_sdk/models.py`** — add:

- `Deck(deck_id, shuffled, remaining)`;
- `DrawResult(deck_id, cards: tuple[Card, ...], remaining)`;
- `parse_deck(...)` and `parse_draw(...)`, using `parse_int_field` for
  `remaining`.

**`src/deck_of_cards_sdk/client.py`** — `DeckOfCardsClient`:

- `__init__(transport: HttpTransport | None = None)`, plus context-manager
  support;
- `create_deck(*, shuffled=True, deck_count=1, cards=None,
  jokers_enabled=False) -> Deck`, which uses `deck/new/shuffle/` or
  `deck/new/`;
- `draw_cards(deck_id, count=1) -> DrawResult`;
- `shuffle_deck(deck_id, *, remaining_only=False) -> Deck`.

Validate every argument before calling the transport.

> **Change (2026-11-09):** `jokers_enabled` is kept, but drawing a Joker
> from a deck created with it raises `ResponseFormatError` (DEC-02).
>
> **Reason:** the option is documented (API-04), but the Joker card codes are
> not, so the SDK cannot parse them (see step 3).

**`src/deck_of_cards_sdk/__init__.py`** — export the client, the models and
the exceptions.

**`tests/integration/sdk/test_client_deck.py`** — assert the exact path and
query parameters for each call, the parsed result, string `remaining` values,
and that invalid input makes no request.

**Commit:** `feat(sdk): implement deck operations`

---

## Step 7 — Pile operations

**Requirements:** CH-01, API-07 to API-11

**`src/deck_of_cards_sdk/models.py`** — add:

- `PileResult(deck_id, remaining, piles: dict[str, int])`;
- `PileDrawResult(deck_id, cards, piles)`;
- `PileListing(deck_id, pile_name, cards)`.

**`src/deck_of_cards_sdk/client.py`** — add:

- `add_to_pile(deck_id, pile_name, cards: Sequence[str]) -> PileResult`;
- `shuffle_pile(deck_id, pile_name) -> PileResult`;
- `list_pile(deck_id, pile_name) -> PileListing`;
- `draw_from_pile(deck_id, pile_name, *, count=None, cards=None,
  position: Literal["top", "bottom", "random"] = "top")`;
- `return_cards(deck_id, *, pile_name=None, cards=None) -> PileResult`.

**`tests/integration/sdk/test_client_pile.py`** — paths and parameters for
each route (`draw/bottom/`, `draw/random/`, pile and deck returns), parsing,
and argument errors.

**Commit:** `feat(sdk): implement pile operations`

---

## Step 8 — Live API smoke test

**Requirements:** CH-01, OBS-01 to OBS-03

**`tests/smoke/test_live_api.py`**

- marked `@pytest.mark.smoke`;
- skipped unless the environment variable `DECK_API_SMOKE=1` is set;
- creates a small partial deck, draws one card, adds it to a pile and lists
  the pile.

Run it by hand with `DECK_API_SMOKE=1 pytest -m smoke` and note the result.

**Commit:** `test(sdk): add opt-in live API smoke test`

---

## Step 9 — Rule and pile model

**Requirements:** CH-07, CH-08, CH-10, CH-13, INT-04

**`src/card_game/rules.py`**

- `PileRule = Callable[[Card], bool]`;
- `should_start_new_pile(card: Card) -> bool`, which returns `card.is_king`.

This is the only place the King rule lives.

**`src/card_game/models.py`**

- `DiscardPile`: `name` and an ordered `cards: list[Card]`;
  - `bottom` is `cards[0]` (first placed);
  - `top` is `cards[-1]` (last placed);
  - `count` is `len(cards)`.
- `GameResult(deck_id, piles: tuple[DiscardPile, ...], cards_remaining)` with
  a `total_discarded` property.

**Tests:** `tests/unit/game/test_rules.py` and
`tests/unit/game/test_models.py` cover a King versus other ranks, top and
bottom, and counts.

**Commit:** `feat(game): add King rule and discard pile model`

---

## Step 10 — Game engine

**Requirements:** CH-03 to CH-08, INT-01 to INT-03, INT-07

**`src/card_game/ports.py`** — a `CardClient` protocol listing only what the
engine needs: `create_deck`, `draw_cards` and `add_to_pile`.

**`src/card_game/engine.py`** — `GameEngine(client: CardClient,
rule: PileRule = should_start_new_pile)` with `run() -> GameResult`:

1. Create one shuffled deck.
2. While cards remain, draw exactly one card.
3. If there is no current pile, or the rule matches, start the next pile
   (`discard_1`, `discard_2`, and so on).
4. Add the card to that pile through the API.
5. Only after the API confirms it, append the card to the local pile.
6. At the end, check the invariants: every card placed exactly once, no
   empty piles, total equals cards drawn, zero remaining, and every
   rule-matching card at the bottom of a pile.

**`tests/fakes.py`** — `FakeCardClient(sequence: list[str])`, which returns
cards in a fixed order and records every call.

**`tests/integration/app/test_engine.py`** — full 52-card game; first card a
King; last card a King; consecutive Kings; cards before the first King; draws
always use `count=1`; and an Ace rule changing the boundaries without
touching other code.

**Commit:** `feat(game): implement discard engine`

---

## Step 11 — Failure handling

**Requirements:** CH-09, INT-08

**`src/card_game/engine.py`** — add:

- `GameInterruptedError` with `operation`, `outcome`, an optional `card`, an
  optional `pile` and the piles confirmed so far.
- Outcomes: `rejected` (the API said no) and `unknown` (a timeout, connection
  loss or bad response, so the remote state is uncertain).
- On any SDK error, stop immediately. Never retry and never report success.
  A card that was drawn but not confirmed in a pile stays visible in the
  error.

**Tests:** in `test_engine.py`, a draw failure, an add rejection, an add
timeout, a draw returning zero or two cards, and no success result in any of
these cases.

**Commit:** `feat(game): handle interrupted games safely`

---

## Step 12 — Transaction logging

**Requirements:** CH-09, INT-06

**`src/card_game/events.py`**

- an `Event` `StrEnum`: `deck.created`, `card.drawn`, `pile.created`,
  `card.discarded`, `operation.failed`, `game.completed` and
  `game.interrupted`;
- `log_event(logger, event, **context)`, which logs with a sequence number
  and context such as deck ID, card, pile and remaining count;
- `JsonLinesFormatter`, which writes one JSON object per line for an
  optional audit file.

**`src/card_game/engine.py`** — call `log_event` at each step, logging the
attempt before the call and the confirmed result after it.

**`tests/unit/game/test_events.py`** — use `caplog` to check that every event
appears with the right context, and that the JSON formatter produces valid
JSON.

**Commit:** `feat(game): add transaction logging`

---

## Step 13 — Command-line app

**Requirements:** CH-03, CH-06, CH-10, CH-13, INT-05, API-12

**`src/card_game/cli.py`**

- `main(argv=None, client_factory=DeckOfCardsClient) -> int`;
- `argparse` options: `--verbose` (show card codes in logs) and
  `--log-file PATH` (JSON Lines audit);
- progress lines that keep cards face down, such as
  `Card 17/52 → discard_2 [face down]`;
- a final table of pile, bottom card, top card and count, plus total
  discarded and cards remaining;
- returns 0 on success, and 1 with a clear message on any SDK or game error.

**`src/card_game/__main__.py`** — `raise SystemExit(main())`.

**`pyproject.toml`** — `[project.scripts] card-game = "card_game.cli:main"`.

**`tests/unit/game/test_cli.py`** — run `main` with the fake client: success
output and exit 0, face-down progress, the final table values, and a failure
with a non-zero exit.

**Commit:** `feat(cli): add game demonstration`

---

## Step 14 — Continuous integration

**Requirements:** CH-11, CH-14, DEC-05

**`.github/workflows/ci.yml`**

- runs on pushes and pull requests to `main`;
- uses Python 3.12 via `actions/setup-python`;
- steps: install `.[dev]`, `ruff format --check .`, `ruff check .`,
  `mypy src tests`, `pytest --cov --cov-fail-under=90`, then
  `python -m build`;
- no live API calls, because the smoke tests stay excluded.

**Commit:** `ci: add quality checks workflow`

---

## Step 15 — Documentation

**Requirements:** CH-02, CH-12, CH-13, CH-14

- **`README.md`**: installation, running the game, using the SDK on its own
  (a short code example), running the tests, CI, real example output,
  error handling, and limitations.
- **`docs/interview-guide.md`**: the architecture in plain English, where to
  change the rule, which tests to update, and two practice changes (an Ace
  rule; King or Queen).
- **`docs/prompt-sheet.md`**: check that every prompt used is recorded.
- **`docs/requirements.md`**: check every requirement is traced to the
  final code and tests.

**Commit:** `docs: add usage and interview guide`

---

## Before the interview

- Practise one rule change on its own branch, without merging it (CH-13).
- Run `DECK_API_SMOKE=1 pytest -m smoke` and one live game.
- Revoke the access tokens, then make the repository public or invite the
  reviewers, and send the link (CH-14, CH-15).
