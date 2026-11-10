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
