# Requirements

This document lists the requirements this project follows and where each one
is implemented and tested. Code, tests and other documents refer to the IDs
below.

## Sources

| Prefix | Source | Authority |
| --- | --- | --- |
| `CH` | *Deck of Cards – Technical Challenge* brief | Authoritative for what the application must do |
| `API` | *Deck of Cards API Developer Reference* (from <https://deckofcardsapi.com/>) | Authoritative for how the API behaves |
| `OBS` | Behaviour observed from the live API where the reference is silent | Evidence, re-checked by the live smoke test |
| `INT` | Interpretations needed to make a brief requirement testable | Project decision, explained below |
| `DEC` | Decisions made by the project owner | Project decision |

Where an `INT` or `DEC` entry applies, it never contradicts a `CH` or `API`
entry; it only fills a gap the briefs leave open.

## Challenge requirements (`CH`)

Quoted from the challenge brief.

| ID | Requirement |
| --- | --- |
| CH-01 | "Build an SDK for this API - Any language" |
| CH-02 | "When using AI then record the prompts you used and be prepared to discuss how you approached the problem." |
| CH-03 | "Once you have created the SDK then write an application that uses the SDK to do the following:" |
| CH-04 | "Get a new shuffled pack of cards" |
| CH-05 | "Take cards from the top of the pack one by one" |
| CH-06 | "Discard in another pile one by one face down" |
| CH-07 | "If the card is a King, then start a new discard pile" |
| CH-08 | "The King will be the first card in the new discard pile" |
| CH-09 | "Log each transaction in the game" |
| CH-10 | "Report the top and bottom card in each pile and how many cards are in each pile" |
| CH-11 | "Think about how you can make your solution stand out" |
| CH-12 | "record the prompts you used to create the game - and be prepared to discuss the decisions you made." |
| CH-13 | "You must be able to demonstrate the solution in the interview and make some manual ad hoc code changes to model some new rules." |
| CH-14 | "Please create a publicly accessible Git repo. Include your SDK and App code and documentation in the repo." The brief adds that a private repository is acceptable, with access granted on request. |
| CH-15 | "Send us a link to the repo when you have completed the challenge." |

## API reference (`API`)

Facts taken from the API developer reference.

| ID | Operation | Endpoint and behaviour |
| --- | --- | --- |
| API-01 | Create a shuffled deck | `/api/deck/new/shuffle/?deck_count=1`. `deck_count` sets the number of decks; the default is 1. |
| API-02 | Draw cards | `/api/deck/{deck_id}/draw/?count=2`. `count` is the number of cards. A deck ID expires after about two weeks without activity. `new` in place of the deck ID creates a shuffled deck and draws from it. |
| API-03 | Reshuffle | `/api/deck/{deck_id}/shuffle/`. `remaining=true` shuffles only the cards still in the main stack. |
| API-04 | New unshuffled deck | `/api/deck/new/`. Ordered spades, diamonds, clubs, hearts, each Ace to King. `jokers_enabled=true` adds two Jokers. |
| API-05 | Partial deck | `/api/deck/new/shuffle/?cards=AS,2S,KS`. Creates a shuffled deck containing only the listed cards. |
| API-06 | Card codes | Two characters: a rank then a suit. Ranks `A 2 3 4 5 6 7 8 9 0 J Q K`, where `0` is ten. Suits `S` (spades), `D` (diamonds), `C` (clubs), `H` (hearts). Codes are case-insensitive. |
| API-07 | Add to a pile | `/api/deck/{deck_id}/pile/{pile_name}/add/?cards=AS,2S`. A pile is created the first time its name is used. Drawn cards can move between piles. Does not work with multiple decks. |
| API-08 | Shuffle a pile | `/api/deck/{deck_id}/pile/{pile_name}/shuffle/`. Does not work with multiple decks. |
| API-09 | List a pile | `/api/deck/{deck_id}/pile/{pile_name}/list/`. Does not work with multiple decks. The example response shows `remaining` values as strings. |
| API-10 | Draw from a pile | `.../pile/{pile_name}/draw/?cards=AS` or `?count=2` draws from the top (the pile is a stack). `/draw/bottom/` and `/draw/random/` also accept `count`. Does not work with multiple decks. |
| API-11 | Return cards | `/api/deck/{deck_id}/return/` and `/api/deck/{deck_id}/pile/{pile_name}/return/`, each with an optional `cards` list. |
| API-12 | Card back image | `https://deckofcardsapi.com/static/img/back.png`, usable to show a card face down. |
| API-13 | Response fields | Responses include `success`, `deck_id` and `remaining`; deck responses include `shuffled`; pile responses include `piles`. Cards include `code`, `image`, `images` (`svg`, `png`), `value` and `suit`. |

## Observed API behaviour (`OBS`)

Recorded from live API responses on 2026-11-08 where the reference does not
say.

| ID | Observation |
| --- | --- |
| OBS-01 | Card `value` names are `ACE`, `2` to `10`, `JACK`, `QUEEN` and `KING`; code rank `0` has value `10`. Suit names are `SPADES`, `DIAMONDS`, `CLUBS` and `HEARTS`. |
| OBS-02 | With `jokers_enabled=true`, the Jokers are `X1` (value `JOKER`, suit `BLACK`) and `X2` (value `JOKER`, suit `RED`). |
| OBS-03 | The draw response returns `remaining` as a JSON number, while the pile list example (API-09) shows strings, so both forms must be accepted. |
| OBS-04 | Recorded 2026-11-09. An unknown deck ID returns HTTP 404 with `{"success": false, "error": "Deck ID does not exist."}`. Drawing more cards than remain returns HTTP 200 with `"success": false` and an `error` message, but still draws the cards that were left. An invalid parameter such as `count=abc` returns an HTML HTTP 500 page. |
| OBS-05 | Recorded 2026-11-09. Unlike the reference examples, a draw-from-pile response has no top-level `remaining`, and returning drawn cards to the deck gives no `piles` or `shuffled`. Listing an unknown pile succeeds with no entry for it. After a pile is shuffled, the list order no longer matches the order cards were added. Adding a card that was never drawn succeeds, and adding a card already in another pile moves it. Drawing more cards than a pile holds returns HTTP 404 with an `error` message. A full reshuffle (without `remaining=true`) empties every pile. Returning drawn cards to the deck leaves cards in piles where they are, even when they are listed in `cards`. |

> **Change to OBS-05 (2026-11-10):** "adding a card that was never drawn
> succeeds" is incomplete. The response reports success, but the card stays
> in the deck and the pile is created empty.
>
> **Reason:** found by the live smoke test (plan step 8). The client's guard
> (DEC-06) is still needed, because a caller would otherwise believe the
> card had been placed.

> **Note (2026-11-10):** asking a pile for more cards than it holds fails
> with HTTP 404 and leaves every card in the pile, whether drawing from the
> top or the bottom of the pile. A deck is different: asking it for more
> cards than remain fails but still draws the cards that were left (OBS-04).
> Checked live while building plan step 11.

## Interpretations (`INT`)

| ID | Interpretation | Based on |
| --- | --- | --- |
| INT-01 | The game uses one standard 52-card deck, because pile operations do not work with multiple decks. | CH-04, API-07 |
| INT-02 | "One by one" means each card is drawn with its own request using `count=1`, and added to its pile before the next draw. | CH-05, CH-06 |
| INT-03 | Cards drawn before the first King go into the first pile, `discard_1`. Each King starts the next pile (`discard_2`, ...). If the first card is a King, it starts `discard_1`; no empty pile is created. | CH-06, CH-07, CH-08 |
| INT-04 | The bottom card of a pile is the first card placed in it; the top card is the most recently placed. | CH-08, CH-10 |
| INT-05 | The API has no face-up or face-down property, so "face down" is shown in the output: cards are displayed as a card back during play, and only the final report reveals the top and bottom cards. | CH-06, CH-10, API-12 |
| INT-06 | A transaction is each game action: creating the deck, each draw, starting a pile, each pile add, binning a Joker (DEC-02), any failure, and game completion. | CH-09 |
| INT-07 | Top and bottom cards are tracked from the order in which pile adds were confirmed, because the reference does not define the order of the pile list response. | CH-10, API-09 |
| INT-08 | If an API call fails, the game stops and reports what happened. Calls that change state are not retried automatically, because a retry could draw or move a card twice. | CH-09 |

> **Change to INT-06 (2026-11-10):** the transactions also include shuffling
> a Joker deck, and the attempt before each API call, logged at `DEBUG`.
>
> **Reason:** the shuffle is an API call that changes the deck, and logging
> each attempt shows what was being tried if a call fails (plan step 12).

## Owner decisions (`DEC`)

| ID | Decision | Relates to |
| --- | --- | --- |
| DEC-01 | The SDK and application are written in Python 3.12 or newer. | CH-01 |
| DEC-02 | Jokers are binned. The SDK recognises Jokers by the observed format (OBS-02) and returns them as cards. The game never places a Joker in a pile: it bins each one drawn, logs it as a transaction, and reports how many were binned. The game uses a standard shuffled pack (CH-04), so Jokers only appear if they are enabled. | API-04, OBS-02, CH-04, CH-09 |
| DEC-03 | The repository is private during development and is made public or shared at submission. | CH-14 |
| DEC-04 | AI prompts are recorded in [prompt-sheet.md](prompt-sheet.md). | CH-02, CH-12 |
| DEC-05 | Each step is developed on its own feature branch and merged through a pull request with a merge commit. Branches are kept after merging. | CH-11, CH-14 |
| DEC-06 | The SDK client guards pile adds. It records the cards it has drawn from each deck and the pile each one is in, and `add_to_pile` raises `InvalidArgumentError`, before any request, for a card it has not drawn, a card already in a pile, or a card listed twice. The record follows deck draws, pile draws, returns and full reshuffles, so only cards drawn through the same client can be added to piles. | API-07, OBS-05, INT-07 |

> **Change to DEC-02 (2026-11-09):** DEC-02 first accepted Jokers in the
> observed format, then rejected them with an error to follow the brief, and
> now bins them in the game.
>
> **Reason:** rejecting Jokers made a game with Jokers enabled fail with an
> error. Binning keeps the brief's piles unchanged, while still handling the
> documented `jokers_enabled` option (API-04). Recognising a Joker relies on
> observed behaviour (OBS-02), because the reference does not document Joker
> codes.

> **Change to DEC-02 (2026-11-10):** Jokers are enabled with the game's
> `jokers` option (`--jokers` on the command line). The game then creates an
> unshuffled deck with Jokers and shuffles it (API-03, API-04).
>
> **Reason:** without an option, a real game could never include Jokers, so
> binning them could only happen in tests.

## Traceability

Planned implementation and tests follow [implementation-plan.md](implementation-plan.md).

| Requirement | Plan step | Implementation | Tests |
| --- | --- | --- | --- |
| CH-01, DEC-01 | 2–8 | `src/deck_of_cards_sdk/` | `tests/unit/sdk/`, `tests/integration/sdk/`, `tests/smoke/` |
| API-06, OBS-01, OBS-02, DEC-02 | 3, 4 | `deck_of_cards_sdk/models.py` (`Card`, `parse_card`), `validation.py` | `tests/unit/sdk/test_models.py`, `test_validation.py` |
| DEC-02 (binning) | 9, 10, 12, 13 | `card_game/rules.py`, `engine.py`, `events.py`, `cli.py` | `test_rules.py`, `test_engine.py`, `test_events.py`, `test_cli.py` |
| API-01–API-05, OBS-03 | 4–6 | `validation.py`, `transport.py`, `client.py` | `tests/unit/sdk/`, `tests/integration/sdk/` |
| API-07–API-11, OBS-05, DEC-06 | 7, 11 | `client.py` pile operations, `card_record.py`, `models.py` pile results | `tests/integration/sdk/test_client_pile.py`, `tests/unit/sdk/test_models.py` |
| OBS-01–OBS-05, DEC-06 | 8 | Live checks of the SDK | `tests/smoke/test_live_api.py`, run with `DECK_API_SMOKE=1 pytest -m smoke` |
| CH-03 | 10, 13 | `card_game/engine.py`, `ports.py`, `cli.py` | `tests/integration/app/` |
| CH-04, INT-01 | 10 | `engine.py` | `tests/integration/app/test_engine.py` |
| CH-05, INT-02 | 10 | `engine.py` | `tests/integration/app/test_engine.py` |
| CH-06, INT-05, API-12 | 10, 13 | `engine.py`, `cli.py` | `test_engine.py`, `tests/unit/game/test_cli.py` |
| CH-07, CH-08, INT-03 | 9, 10 | `card_game/rules.py`, `engine.py` | `tests/unit/game/test_rules.py`, `test_engine.py` |
| CH-09, INT-06 | 12 | `card_game/events.py`, `engine.py` | `tests/unit/game/test_events.py`, `tests/integration/app/test_engine_logging.py` |
| CH-10, INT-04, INT-07 | 9, 13 | `card_game/models.py`, `cli.py` | `tests/unit/game/test_models.py`, `test_cli.py` |
| INT-08 | 5, 11 | `transport.py`, `engine.py` | `test_transport.py`, `test_engine_failures.py` |
| API-13, OBS-04 | 5, 11 | `deck_of_cards_sdk/transport.py`, `client.py`, `card_game/engine.py` | `tests/integration/sdk/test_transport.py`, `test_client_pile.py`, `tests/integration/app/test_engine_failures.py` |
| CH-13 | 9, 15 | `rules.py`, `docs/interview-guide.md` | Ace-rule test in `test_engine.py` |
| CH-02, CH-12, DEC-04 | All | `docs/prompt-sheet.md` | Reviewed before each commit |
| CH-11, CH-14, CH-15, DEC-03, DEC-05 | All, 14 | Repository, `.github/workflows/ci.yml`, `constraints.txt` | CI on every pull request |
