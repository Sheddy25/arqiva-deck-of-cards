# Prompt sheet

## Prompt 0001 — Review and format the architecture design


```text
Role
Act as a senior Python software engineer and technical reviewer.

Context
docs/architecture.md describes the planned design for the Arqiva Deck of Cards
technical challenge: a reusable Python SDK for https://deckofcardsapi.com/ and a
command-line application that uses it. The application draws a shuffled deck one
card at a time into face-down discard piles, starts a new pile whenever a King is
drawn (the King becomes that pile's first card), logs every transaction, and
reports the top card, bottom card and count of every pile. No code exists yet.

Task
1. Review the design for correctness against those requirements, paying
   particular attention to:
   - the first card not being a King (a pre-King pile) and consecutive Kings;
   - how top and bottom cards are tracked;
   - what happens when a card is drawn but adding it to a pile fails;
   - keeping the SDK free of game rules;
   - unnecessary complexity that would be hard to explain in an interview.
2. Report findings first, ordered by severity, each with the section affected
   and a concrete correction.
3. After I approve the findings, reformat docs/architecture.md to improve
   readability: clear headings, short paragraphs, consistent tables and lists,
   and diagrams that render in GitHub Markdown.

Constraints
- Do not change the meaning of the design while reformatting; list any
  wording change that alters behaviour separately for my approval.
- Do not invent API behaviour; cite the public API documentation where relevant.
- Do not edit any other file.
- Keep British English spelling.

Output
- A prioritised list of review findings.
- The reformatted document as a reviewable diff.
- A short summary of what changed and what I should check.

Verification
I will read the full diff, check the Markdown renders correctly on GitHub, and
confirm every requirement above is still covered before committing.
```

## Prompt 0002 — Write the implementation plan




```text
Role
Act as a senior Python software engineer and technical mentor.

Context
docs/architecture.md defines the design: an SDK package (exceptions,
validation, models, transport, client) and a game package (rules, models,
ports, engine, events, cli). Step 1, the empty project structure, is done.
I will build the rest myself.

Task
Write docs/implementation-plan.md: a step-by-step plan from tooling through
to CI and documentation. For each step, list:
- the files to create or change;
- what each file should contain (classes, functions and responsibilities);
- the tests to write;
- what "done" means;
- a suggested Conventional Commit message.

Constraints
- Use the module names from docs/architecture.md.
- Size each step to one focused session and one commit.
- Order steps so each builds only on earlier ones.
- Keep the King rule in a single place and never retry state-changing calls.
- Plan only; write no code.

Output
The plan file and a short summary of the steps.

Verification
I will check the plan against the challenge requirements and the
architecture.
```

## Prompt 0003 — Review code and suggest improvements

```text
Role
Act as a senior Python software engineer reviewing a pull request.

Context
I have written src/deck_of_cards_sdk/models.py and
tests/unit/sdk/test_models.py for step 3 of docs/implementation-plan.md: a
Card model and a parse_card function for card objects returned by
https://deckofcardsapi.com/. docs/requirements.md lists the requirements this
step must meet (API-06, API-13, OBS-01, OBS-02, DEC-02), and
docs/architecture.md describes the overall design.

Task
1. Review the code and tests against those requirements and the plan's
   step 3, checking:
   - correctness, including edge cases such as ten ("0"), lower-case codes,
     Jokers, missing fields and wrong types;
   - whether the tests cover every behaviour and would fail if the code
     were wrong;
   - readability, naming, type hints and docstrings;
   - consistency with the architecture, and anything that belongs in a
     later step instead.
2. Report findings ordered by severity (bug, risk, improvement, nitpick). For
   each, give the file and line, the problem, and a concrete suggestion.
3. Point out anything that is already done well, so I know what to keep.

Constraints
- Suggest only; do not edit any file.
- Do not invent API behaviour; cite the requirement ID or API documentation.
- Avoid suggestions that add complexity without a clear benefit.


Output
A prioritised list of findings with suggested changes, then a one-line
verdict on whether the step is ready to commit.

Verification
I will check each finding against the code, apply the ones I agree with,
then re-run ruff, mypy and pytest before committing.
```

## Prompt 0004 — Remove undocumented Joker support

```text
Role
Act as a senior Python software engineer keeping an SDK aligned with its
specification.

Context
The challenge brief and the supplied API reference
(Deck_of_Cards_API_Developer_Reference.docx) only document two-character card
codes: a rank (A, 2-9, 0, J, Q, K) followed by a suit (S, D, C, H). The
reference mentions Jokers only as the jokers_enabled=true option on a new
unshuffled deck, and never documents their card codes. The merged step 3 code
in src/deck_of_cards_sdk/models.py accepts the Joker codes X1 and X2, based
only on live API observation (OBS-02, DEC-02 in docs/requirements.md).

Task
1. Remove the Joker parsing and the is_joker property from models.py, so
   parse_card accepts only the documented card codes.
2. Update tests/unit/sdk/test_models.py so X1 and X2 are rejected as unknown
   card codes.
3. Rewrite DEC-02 in docs/requirements.md: the SDK supports only documented
   codes, still offers the documented jokers_enabled option, and raises a
   clear error if a Joker is parsed. Keep OBS-02 as a record of what the live
   API returned.
4. Update every Joker reference in docs/implementation-plan.md and
   docs/architecture.md to match.

Constraints
- Follow the brief exactly; do not keep behaviour that relies on
  undocumented API responses.
- Do not remove the documented jokers_enabled option.


Output
The code, test and documentation changes as a reviewable diff, and a short
summary of each change.

Verification
I will confirm no Joker handling remains in the code, check the
documentation against both briefs, and re-run ruff, mypy and pytest.
```

## Prompt 0005 — Review the pile operations step

```text
Role
Act as a senior Python software engineer reviewing a pull request.

Context
Step 7 of docs/implementation-plan.md adds pile operations to the SDK:
PileResult, PileDrawResult and PileListing with their parsers in
src/deck_of_cards_sdk/models.py, and add_to_pile, shuffle_pile, list_pile,
draw_from_pile and return_cards in src/deck_of_cards_sdk/client.py. The tests
are in tests/integration/sdk/test_client_pile.py and
tests/unit/sdk/test_models.py. The step must meet CH-01 and API-07 to API-11
in docs/requirements.md. The live API behaves differently from the reference
examples in places (OBS-03, OBS-05), and the game in steps 9 to 11 will add
each drawn card to a pile and report every pile's top and bottom card
(INT-07).

Task
1. Review the code and tests against those requirements, the API page
   (https://deckofcardsapi.com/) and the plan's step 7, checking:
   - every route, parameter and combination matches the API page, and
     undocumented combinations are rejected;
   - the parsers accept the response shapes seen on the live API, including
     counts sent as strings, a missing piles field and an unknown pile;
   - what the API allows that could corrupt the game's piles, such as adding
     a card that was never drawn or is already in another pile, and whether
     the SDK should guard against it;
   - whether the tests would fail if the code were wrong;
   - readability, naming, type hints and docstrings.
2. Report findings ordered by severity (bug, risk, improvement, nitpick). For
   each, give the file and line, the problem, and a concrete suggestion.
3. Point out anything that is already done well, so I know what to keep.

Constraints
- Suggest only; do not edit any file.
- Check API behaviour against the live API where the page is unclear, and
  record what you observe; do not invent behaviour.
- Keep game rules out of the SDK.
- Avoid suggestions that add complexity without a clear benefit.

Output
A prioritised list of findings with suggested changes, then a one-line
verdict on whether the step is ready to commit.

Verification
I will check each finding against the code and the live API, apply the ones
I agree with, then re-run ruff, mypy and pytest before committing.
```

> **Outcome (2026-11-09):** the findings included: "the API doesn't stop you
> adding a card that was never drawn, and adding a card that's already in
> another pile silently moves it. The SDK can't detect either case, so the
> game will only ever add the card it has just drawn and keep its own record
> of each pile. That record is what we planned for step 10 anyway, so nothing
> changes." I chose to have the SDK guard against this as well, so a fix
> will be applied in step 7: `DeckOfCardsClient` records the cards it has
> drawn and the pile each one is in, and `add_to_pile` rejects any other card
> before sending a request (DEC-06).

## Prompt 0006 — Write the live API smoke test

```text
Role
Act as a senior Python software engineer writing tests for an SDK.

Context
src/deck_of_cards_sdk/ is a client for https://deckofcardsapi.com/. Its unit
and integration tests run over httpx.MockTransport, so they never prove that
the live API still behaves as recorded. docs/requirements.md lists the
observed behaviour the SDK relies on (OBS-01 to OBS-05): card value and suit
names, Joker codes, counts sent as numbers or strings, the form of errors,
and pile responses. It also records why DeckOfCardsClient guards
add_to_pile (DEC-06): the API accepts adding a card that was never drawn,
and silently moves a card that is already in another pile. pyproject.toml
already defines a smoke marker that is excluded by default.

Task
1. Write tests/smoke/test_live_api.py for step 8 of
   docs/implementation-plan.md, marked smoke and skipped unless the
   environment variable DECK_API_SMOKE=1 is set.
2. Re-check each observation through the public client: a full shuffled
   pack, a deck with Jokers, a drawn card added to a pile then listed, drawn
   back and returned, an unknown pile, and the errors for an unknown deck, a
   pile over-draw and a deck over-draw.
3. Check, through HttpTransport without the client's guard, that the API
   still accepts adding a card that was not drawn, and moves a card already
   in another pile, so the test fails if the guard stops being needed.
4. Run the tests against the live API and report anything that differs from
   docs/requirements.md.

Constraints
- Keep live calls few: each test creates one small deck of its own.
- Do not depend on the order of a shuffled deck; use the card actually drawn.
- Do not change SDK code; if the API differs from the requirements, report
  it so I can decide what to change.
- The default pytest run must still make no network calls.

Output
The test file, the result of a live run, and any observations that need
updating in docs/requirements.md.

Verification
I will run pytest to confirm the smoke tests are deselected, then run
DECK_API_SMOKE=1 pytest -m smoke several times to confirm they pass
reliably.
```

> **Outcome (2026-11-10):** the live run found that adding a card that was
> never drawn reports success but leaves the card in the deck, creating an
> empty pile. OBS-05 has a change note for this, and the guard (DEC-06)
> stays, because a caller would otherwise believe the card had been placed.

## Prompt 0007 — Build a fake card client for engine tests

```text
Role
Act as a senior Python software engineer writing tests for a game engine.

Context
Step 10 of docs/implementation-plan.md adds the game engine:
src/card_game/engine.py plays a shuffled deck one card at a time, starting a
new discard pile at each King and binning Jokers, through the CardClient
protocol in src/card_game/ports.py. The real client, DeckOfCardsClient, calls
the live API, and its shuffled decks deal cards in a random order, so it
cannot test specific sequences such as a King drawn first or last.
docs/requirements.md lists the rules the engine must meet (CH-04 to CH-08,
INT-01 to INT-04, INT-07, DEC-02), and docs/architecture.md lists the
completion checks.

Task
1. Write tests/fakes.py with a FakeCardClient that satisfies CardClient
   without inheriting from the SDK client. It should:
   - deal cards in a fixed order given as card codes;
   - report the cards remaining after each draw and add;
   - record every call, so tests can check that cards are drawn and added
     one at a time;
   - record the piles it was asked to add to, so tests can compare them with
     the engine's own piles.
2. Write tests/integration/app/test_engine.py using the fake: a full
   52-card game, a King drawn first, a King drawn last, consecutive Kings,
   cards before the first King, draws always using count=1, an Ace rule
   changing the pile boundaries, and Jokers drawn first, last and between
   Kings in a 54-card game.
3. Test each completion check on its own, with finished games that are
   deliberately broken.
4. Update docs/implementation-plan.md, docs/architecture.md,
   docs/requirements.md and README.md to match, adding a change note under
   the plan step wherever the work differs from the plan.

Constraints
- Keep the fake simple and predictable; do not copy the SDK's pile-add
  guard (DEC-06) into it.
- Build full decks in a known order, so the completion checks run in every
  engine test.
- Make no network calls in these tests.
- Keep the original plan wording; record changes with dated change notes and
  reasons.

Output
The fake, the tests and the documentation changes as a reviewable diff, and a
short summary of each change.

Verification
I will run ruff, mypy and pytest, check the game package coverage, and play
one live game to confirm the engine also works with the real client.
```

> **Outcome (2026-11-10):** `FakeCardClient` deals a fixed sequence, records
> every call and the piles added to, and does not copy the SDK guard. The
> engine tests build full decks in a known order, and
> `tests/unit/game/test_invariants.py` tests each completion check with a
> broken game. The plan, architecture, requirements and README were updated,
> including the `jokers` option chosen during this step.

## Prompt 0008 — Sanity-check the project against the brief and the role

```text
Role
Act as a senior software engineer and technical interviewer for an Arqiva
Software Engineer role, reviewing a candidate's take-home challenge.

Context
The challenge brief (Deck of Cards - Technical Challenge.docx) asks for an
SDK for https://deckofcardsapi.com/ and an application that uses it: get a
new shuffled pack, take cards from the top one by one, discard them face
down one by one, start a new pile at each King with the King as its first
card, log each transaction, and report the top card, bottom card and count
of each pile. It also asks the candidate to record AI prompts, make the
solution stand out, demonstrate it, and make ad hoc code changes to model new
rules in the interview. Deck_of_Cards_API_Developer_Reference.docx describes
the API. Arqiva_Software_Engineer_Beginner_to_Interview_Master_Pack.docx
describes the skills the role needs: the software lifecycle, Python, APIs,
testing, CI/CD, code review, observability, troubleshooting, and
AI-assisted engineering with human ownership.

The repository has a finished SDK (src/deck_of_cards_sdk/), a game rules
module, pile model and engine (src/card_game/), tests in tests/, and
docs/requirements.md, docs/architecture.md, docs/implementation-plan.md and
docs/prompt-sheet.md. Steps 11 to 15 of the plan (failure handling, logging,
command-line app, CI and documentation) are not built yet.

Task
Review the whole repository and answer each question with evidence:
1. Brief: does the work meet every requirement in the brief and the API
   reference? What is missing or at risk?
2. Scope: has the work gone too far? Name anything that adds complexity
   without serving the brief, the demonstration or the role, and say
   whether to keep, simplify or remove it.
3. Efficiency: is the code as efficient as it needs to be, in API calls,
   algorithms and memory? Point out wasted work.
4. Infrastructure: are the tooling, packaging, dependency management, test
   layout, Git workflow and planned CI sound and proportionate?
5. Engineering principles: does the code show single responsibility,
   separation of concerns, DRY without over-abstraction, clear naming,
   type safety, safe failure handling and meaningful tests?
6. Role skills: does the work demonstrate the skills in the interview pack?
   Which are shown well, which are weak, and which could the remaining
   steps show?

Constraints
- Suggest only; do not edit any file.
- Cite the file and line, or the brief's wording, for each finding.
- Judge against the brief and the role, not against an ideal of unlimited
  scope; prefer removing complexity to adding it.
- Be candid about weaknesses, and also say what is already done well.

Output
Findings for each question, ordered by severity (risk, improvement,
nitpick), each with a concrete recommendation; then a short list of the
changes I should make before the interview, in priority order.

Verification
I will check each finding against the code and the briefs, decide which to
apply, and re-run ruff, mypy and pytest after any change.
```

> **Outcome (2026-11-10):** the review found the work meets the brief so far
> without going too far, but logging (CH-09) and the pile report (CH-10) are
> not built yet, CI is missing, and the guard (DEC-06) is the most debatable
> design choice. It also found that changing the binning rule, a likely
> interview change, made the completion check fail, because the check
> required the binned cards to be exactly the Jokers. I chose to fix only
> that now: the check compares the cards drawn with one standard pack, and a
> test bins the 2s to prove a new binning rule needs no other change. The
> other findings stay as recommendations for later steps.

## Prompt 0009 — Add transaction logging to the game

```text
Role
Act as a senior Python software engineer adding observability to a
command-line game.

Context
The brief asks the game to "log each transaction in the game" (CH-09).
docs/requirements.md defines a transaction as each game action: creating
the deck, each draw, starting a pile, each pile add, binning a Joker, any
failure, and game completion (INT-06). Step 12 of
docs/implementation-plan.md plans src/card_game/events.py with an Event
enum, a logging helper that numbers each event, and a JSON Lines formatter
for an optional audit file, and asks the engine to log each attempt before
an API call and the confirmed result after it. docs/architecture.md says
the console must keep cards face down, while a verbose or audit log may
show card codes. The engine (src/card_game/engine.py) already raises
GameInterruptedError when a call fails.

Task
1. Write src/card_game/events.py: the events, a way to log one game's
   events with a sequence number starting at 1 and context such as deck
   ID, card, pile and cards remaining, and a formatter that writes one JSON
   object per line.
2. Make the engine log every transaction, including the shuffle of a Joker
   deck, each binned Joker, a failed call, an interrupted game and a failed
   completion check.
3. Write unit tests for the events module, and engine tests that check the
   events logged in a full game, a Joker game and a failed game.
4. Update docs/implementation-plan.md, docs/architecture.md,
   docs/requirements.md and README.md to match, adding a change note
   wherever the work differs from the plan.

Constraints
- Use only the standard logging package.
- Keep card codes out of log messages, so a plain console log cannot reveal
  the draw order; keep them available to the audit file.
- Never log request headers, environment variables or response bodies.
- Keep the engine's game logic unchanged; logging must not alter the
  result.
- Keep the original plan wording; record changes with dated change notes and
  reasons.

Output
The module, engine changes, tests and documentation changes as a
reviewable diff, and a short summary of each design choice.

Verification
I will run ruff, mypy and pytest with coverage, and play one live game with
a console handler and a JSON Lines file handler attached to check both
outputs.
```

> **Outcome (2026-11-10):** the AI built this step. `TransactionLog`
> numbers each game's events, the engine logs every attempt at `DEBUG` and
> every confirmed result, and `JsonLinesFormatter` writes the full context,
> including card codes, to an audit file. Card codes are left out of log
> messages, so the console stays face down. It added `operation.started`
> and `deck.shuffled` events, with change notes. A live game logged 216
> transactions to the console and the audit file.
