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

> **Change (2026-11-09):** Joker parsing was restored: `parse_card` accepts
> `X1` (`BLACK`) and `X2` (`RED`) with value `JOKER`, and `Card.is_joker` is
> back (OBS-02, DEC-02).
>
> **Reason:** rejecting Jokers made a game with Jokers enabled stop with an
> error. Instead the game bins them (steps 9 to 13), so the SDK must be able
> to recognise them.

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

> **Change (2026-11-09):** `JOKER_SUITS` and `JOKER_VALUE` were added to
> `validation.py`, and `is_card_code` and `validate_card_codes` also accept
> `X1` and `X2` (DEC-02).
>
> **Reason:** Jokers are now real cards in the SDK (see step 3), so they can
> be named in requests such as returning cards to the deck.

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

> **Change (2026-11-09):** a missing or non-boolean `success` raises
> `ResponseFormatError`; only `"success": false` raises `ApiError`.
>
> **Reason:** `false` means the API refused the request, while a missing
> field means the response cannot be trusted. Step 11 treats these
> differently, as `rejected` and `unknown`.

> **Change (2026-11-09):** `HttpStatusError` and `ApiError` messages use the
> API's own `error` text when the body is JSON, such as
> `HTTP 404: Deck ID does not exist.`, and otherwise the HTTP reason phrase.
> HTML error pages are never included.
>
> **Reason:** the live API sends useful error text with some failures
> (OBS-04), and the architecture says raw response bodies are not put in
> error messages.

> **Change (2026-11-09):** any other `httpx` network error, such as a read
> error, raises the base `TransportError`. The base URL must also have a host,
> a missing trailing `/` is added, and `close()` only closes a client the
> transport created itself, not one passed in. The tests cover each of these.
>
> **Reason:** callers should never need to catch `httpx` exceptions, and a
> transport must not close a client that someone else owns.

> **Change (2026-11-09):** added empty `tests/integration/__init__.py` and
> `tests/integration/sdk/__init__.py` files.
>
> **Reason:** the same as in step 3: test modules with the same name in
> different folders must not clash.

> **Note (2026-11-09):** drawing more cards than remain still draws the cards
> that were left, even though it reports `"success": false` (OBS-04). The game
> avoids this by drawing one card at a time only while cards remain; step 11
> should treat an `ApiError` from a draw as a possible change of state.

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

> **Change (2026-11-09):** replaces the note above. Drawing a Joker returns a
> normal `Card` with `is_joker` true; deciding what to do with it is left to
> the game (DEC-02).
>
> **Reason:** the game now bins Jokers rather than failing.

> **Change (2026-11-09):** `create_deck` only allows the documented
> combinations. A shuffled deck accepts `deck_count` (API-01) and `cards`
> (API-05); an unshuffled deck accepts `jokers_enabled` (API-04). Any other
> combination raises `InvalidArgumentError` before a request is sent. A
> shuffled deck with Jokers is made by creating an unshuffled deck with
> `jokers_enabled=True` and then calling `shuffle_deck` (API-03).
>
> **Reason:** to follow the brief, which documents each option on one
> endpoint only. Both steps of the Joker route are documented, and it was
> checked against the live API.

> **Change (2026-11-09):** `close()` only closes a transport the client
> created itself, and `__init__.py` also exports `HttpTransport`. Unit tests
> for `parse_deck` and `parse_draw` were added to
> `tests/unit/sdk/test_models.py`.
>
> **Reason:** callers can pass in their own transport, which the client must
> not close. The parsers' error cases are simpler to test directly than
> through the client.

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

> **Change (2026-11-09):** `piles` is a read-only `Mapping[str, int]`, not a
> `dict`, and is empty when the response has no `piles` field. A listing of
> an unknown pile, or a pile with no `cards` field, has no cards.
>
> **Reason:** the models are frozen, so their contents should not be
> changeable either. The live API returns no `piles` when returning drawn
> cards to the deck, and lists an unknown pile with no entry for it (OBS-05).

> **Change (2026-11-09):** `draw_from_pile` rejects `count` and `cards`
> together, and allows `cards` only when drawing from the top. With neither,
> the API draws one card from the top.
>
> **Reason:** to follow the brief, which shows `cards` only on the top route
> and says the bottom and random routes "also accept the count parameter".

> **Change (2026-11-09):** `__init__.py` exports `PileResult`,
> `PileDrawResult` and `PileListing`, and unit tests for the pile parsers'
> error cases were added to `tests/unit/sdk/test_models.py`.
>
> **Reason:** the same as in step 6.

> **Change (2026-11-09):** `DeckOfCardsClient` keeps a private record
> (`_CardRecord`) of the cards it has drawn from each deck and the pile each
> one is in. `add_to_pile` checks it first, and raises
> `InvalidArgumentError` without sending a request for a card that was not
> drawn through this client, is already in a pile, or is listed twice. Deck
> draws, pile draws, returns and full reshuffles update the record. The
> tests in `test_client_pile.py` cover each case.
>
> **Reason:** a review of this step (prompt 0005) found that the live API
> accepts adding a card that was never drawn, and silently moves a card that
> is already in another pile (OBS-05). The API cannot be asked which cards
> are drawn, so the client must remember them (DEC-06).

> **Note (2026-11-09):** an over-draw raises `ApiError` even though the API
> still draws the cards that were left (OBS-04), so those cards are not
> recorded and cannot be added to a pile. Pile operations do not work with
> several decks, so the record treats each card code as one card.

> **Note (2026-11-10):** step 11 fixes the over-draw gap: the client raises
> `IncompleteDrawError` carrying those cards, and records them.

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

> **Change (2026-11-10):** the smoke test covers OBS-01 to OBS-05 and the
> reason for DEC-06, in five tests that each use a small deck of their own:
>
> - a shuffled pack has 52 different cards, with 4 Kings and the observed
>   value and suit names (OBS-01);
> - an unshuffled deck with Jokers has 54 cards, including `X1` (BLACK) and
>   `X2` (RED) (OBS-02);
> - a drawn card is added to a pile, listed, drawn back and returned, and
>   an unknown pile lists no cards (OBS-03, OBS-05);
> - an unknown deck and a pile over-draw give HTTP 404, and a deck over-draw
>   gives `success: false` (OBS-04, OBS-05);
> - through `HttpTransport` without the client, the API still accepts adding
>   a card that was not drawn, and moves a card already in another pile
>   (DEC-06).
>
> `tests/smoke/__init__.py` was added, like the other test folders.
>
> **Reason:** the SDK now relies on OBS-04 and OBS-05 as well, and the
> guard in step 7 is only needed while the API accepts those adds.

> **Note (2026-11-10):** the live run showed that adding a card that was
> never drawn reports success but does not move the card: it stays in the
> deck, and the pile is created empty. OBS-05 has a change note for this.

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

> **Change (2026-11-09):** `rules.py` also gets
> `should_bin_card(card: Card) -> bool`, which returns `card.is_joker`, and
> `GameResult` gains `binned: tuple[Card, ...]`. The tests cover a Joker
> being binned and a King or other card not being binned.
>
> **Reason:** Jokers are binned instead of placed in a pile (DEC-02). Keeping
> the check in `rules.py` puts every game rule in one place.

> **Change (2026-11-10):** `DiscardPile` raises `ValueError` if it is created
> with no cards, keeps its own copy of the list, and has `add(card)` to place
> the next card on top. `binned` defaults to `()`. `tests/cards.py` adds
> `make_card(code)` to build cards for game tests, and
> `tests/unit/game/__init__.py` was added like the other test folders. The
> rule tests also show an Ace rule replacing the King rule (CH-13).
>
> **Reason:** the architecture says a pile only exists once its first card is
> placed, so an empty pile is a bug. `make_card` is shared with the step 10
> fakes instead of each test file building cards itself.

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

> **Change (2026-11-09):** after each draw, a card matching
> `should_bin_card` is binned: it is not added to any pile, does not start a
> pile, and is recorded in `GameResult.binned`. The invariants become "every
> card drawn is either placed once or binned once". The tests add a Joker
> drawn first, between Kings and last, and a 54-card game.
>
> **Reason:** Jokers are binned instead of placed in a pile (DEC-02).

> **Change (2026-11-09):** the engine runs on `DeckOfCardsClient`, whose card
> record (DEC-06) rejects adding a card that was not drawn or is already in
> a pile. The engine still keeps its own record of each pile, in the order
> adds were confirmed, for the top and bottom cards (INT-07).
> `FakeCardClient` does not copy the guard.
>
> **Reason:** the guard was added to the SDK in step 7. The SDK's record
> does not keep the order of cards in a pile, so the game still needs its
> own.

> **Change (2026-11-10):** `GameEngine` takes `jokers: bool = False`. When
> true, it creates an unshuffled deck with `jokers_enabled=True` and then
> calls `shuffle_deck`, so `CardClient` also lists `shuffle_deck`. A default
> game still uses one standard shuffled pack.
>
> **Reason:** without it, a real game could never include Jokers, so binning
> them (DEC-02) could only happen in tests. The API documents Jokers only for
> an unshuffled deck (API-04), then reshuffling it (API-03).

> **Change (2026-11-10):** the invariants are in a separate function,
> `check_invariants`, which raises `GameInvariantError` listing every rule
> broken. It checks the deck size (52, or 54 with Jokers), that every card
> was drawn once, that the piles hold every non-Joker card in draw order and
> the binned cards are the Jokers drawn, that the cards drawn are one
> standard pack, zero remaining, pile names from `discard_1` upwards, and the
> rule boundaries. The pack check looks at the cards drawn, not at which ones
> were binned, so changing `should_bin_card` needs no other change (CH-13). `tests/unit/game/test_invariants.py` tests each check, and
> `tests/integration/app/__init__.py` was added. `FakeCardClient` also
> records the piles it was asked to add to, so the tests can compare them
> with the engine's piles (prompt 0007).
>
> **Reason:** a separate function can be tested with broken games that the
> engine itself would never produce. "Every rule-matching card at the bottom
> of a pile" and "total equals cards drawn" follow from checking the piles
> against the draw order, and a pile cannot be empty (step 9).

> **Note (2026-11-10):** the engine still assumes each draw returns exactly
> one card, and does not catch SDK errors. Step 11 adds both.

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

> **Change (2026-11-10):** before adding error handling, this step also:
>
> - freezes `GameResult`'s piles when the game ends, so the result cannot be
>   changed;
> - splits `GameEngine.run()` into small methods for drawing and placing a
>   card;
> - defines the pack order once for the tests;
> - moves `_CardRecord` out of `client.py` into its own SDK module;
> - keeps the cards an over-draw did draw: the error carries them, and the
>   card record includes them (OBS-04).
>
> **Reason:** recommendations from the sanity check (prompt 0008). Cleaning
> the engine first keeps it readable once every call has error handling.

> **Change (2026-11-10):** as built:
>
> - `GameInterruptedError` holds `unplaced`, the cards drawn but not
>   confirmed in a pile, in place of one optional card. It also holds the
>   deck ID and the Jokers binned so far. Its operations are `create deck`,
>   `shuffle deck`, `draw` and `add to pile`.
> - `rejected` covers `InvalidArgumentError`, `ApiError` and HTTP 4xx;
>   `unknown` covers timeouts, connection and other network failures, HTTP
>   5xx, bad responses, and a draw that does not return exactly one card.
> - `DiscardPile` is frozen with a tuple of cards, and `with_card` replaces
>   `add`. `run()` is split into `_create_deck`, `_draw_one` and `_place`.
> - `PACK_ORDER` lives in `tests/cards.py`.
> - `CardRecord` is in `src/deck_of_cards_sdk/card_record.py`.
> - `ApiError` keeps the response body as `body`. The client turns an
>   over-draw into `IncompleteDrawError`, a kind of `ApiError` whose
>   `result` holds the cards drawn, after recording them. The smoke test
>   checks this against the live API, where a pile over-draw was also found
>   to draw nothing.
> - The failure tests are in `tests/integration/app/test_engine_failures.py`,
>   and `FakeCardClient` takes `fail`, errors to raise on chosen calls, and
>   `deal`, how many cards a chosen draw returns.
>
> **Reason:** a faulty draw can return two cards, so one optional card was
> not enough. A server error does not show whether the request took effect.
> A separate test file keeps the happy-path tests short.

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

> **Change (2026-11-09):** added a `card.binned` event, logged each time a
> Joker is binned.
>
> **Reason:** binning a card is a game transaction (CH-09, INT-06, DEC-02).

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

> **Change (2026-11-09):** a binned Joker shows a progress line such as
> `Card 17/54 → binned (Joker)`, and the final report adds a
> `Jokers binned: N` line. The tests cover a game with Jokers.
>
> **Reason:** the user sees each Joker being binned and the total at the end
> (DEC-02).

> **Change (2026-11-10):** a `--jokers` option plays with the two Jokers, by
> passing `jokers=True` to `GameEngine`. Without it, the game uses one
> standard pack.
>
> **Reason:** the engine gained the `jokers` option in step 10, so a real
> game can include Jokers and show them being binned.

> **Note (2026-11-10):** if the output shows a card back, add the card-back
> image URL (API-12) to the SDK as a constant in this step.

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

> **Note (2026-11-09):** `python -m build` needs the `build` package, which
> is not in the `dev` dependencies. Add it to `dev` in this step.

> **Change (2026-11-10):** this step is done straight after step 10, before
> step 11. The workflow tests on Python 3.12 and 3.14, adds a `pip-audit`
> dependency check, and installs pinned versions of the dev tools.
>
> **Reason:** the sanity check (prompt 0008) found CI was the biggest gap
> against the role. Doing it first means every later pull request is
> checked, and pinned tools make CI results repeatable.

> **Change (2026-11-10):** as built:
>
> - `constraints.txt` at the repository root pins the exact version of every
>   package CI installs, and CI installs with
>   `pip install -c constraints.txt -e ".[dev]"`. `pyproject.toml` keeps
>   minimum versions, so the SDK stays easy to install alongside other
>   packages.
> - `pip-audit` checks `constraints.txt` rather than the CI environment, and
>   `build` and `pip-audit` are added to `dev`.
> - The coverage settings live in `pyproject.toml`: branch coverage, the two
>   packages as the source, and `fail_under = 90`. CI runs `pytest --cov`,
>   and the same threshold applies locally.
> - The actions are pinned to commit hashes, the workflow token is
>   read-only, and the checkout does not keep credentials.
>
> **Reason:** auditing the pinned list checks exactly what is installed and
> leaves out the installer, whose local copy had a known vulnerability that
> says nothing about this project. Settings in `pyproject.toml` mean local
> runs match CI. Hash pinning stops a moved tag changing what CI runs.

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

> **Change (2026-11-10):** this step also:
>
> - adds an introduction to the prompt sheet and the attribution: the bulk
>   of the code is credited to me, and the AI is credited with the work each
>   prompt produced;
> - adds to the interview guide: a short story of how AI output was checked
>   and corrected, what to change for rules that need more than one card to
>   decide (such as a pile-size limit), and the reasoning behind the pile-add
>   guard (DEC-06);
> - adds a `LICENSE`, and adds to "Before the interview": make the
>   repository public or share it (CH-14), and revoke the access tokens used
>   during development.
>
> **Reason:** recommendations from the sanity check (prompt 0008), and my
> decision on attribution.

**Commit:** `docs: add usage and interview guide`

---

## Before the interview

- Practise one rule change on its own branch, without merging it (CH-13).
- Run `DECK_API_SMOKE=1 pytest -m smoke` and one live game.

