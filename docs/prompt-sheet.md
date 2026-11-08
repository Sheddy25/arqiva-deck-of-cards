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
