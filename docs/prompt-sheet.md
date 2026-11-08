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
