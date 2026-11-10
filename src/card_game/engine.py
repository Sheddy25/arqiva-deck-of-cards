"""The discard game (CH-03 to CH-08, INT-01 to INT-04, INT-07, DEC-02).

The engine draws a shuffled deck one card at a time. Each card goes face down
on the current discard pile, a card matching the rule (a King by default)
starts a new pile, and a Joker is binned.
"""

from collections.abc import Sequence

from card_game.models import DiscardPile, GameResult
from card_game.ports import CardClient
from card_game.rules import PileRule, should_bin_card, should_start_new_pile
from deck_of_cards_sdk import Card, Deck

STANDARD_DECK = frozenset(rank + suit for rank in "A234567890JQK" for suit in "SDCH")
JOKERS = frozenset({"X1", "X2"})


class GameInvariantError(Exception):
    """A game finished but broke a rule it must keep, so its result cannot be
    trusted."""


class GameEngine:
    """Plays one game through a :class:`CardClient`.

    Args:
        client: the client used to create the deck, draw and add to piles.
        rule: decides whether a card starts a new pile; a King by default.
        jokers: include the two Jokers, which are drawn and binned (DEC-02).
    """

    def __init__(
        self,
        client: CardClient,
        rule: PileRule = should_start_new_pile,
        *,
        jokers: bool = False,
    ) -> None:
        self._client = client
        self._rule = rule
        self._jokers = jokers

    def run(self) -> GameResult:
        """Play the game to the end and return the confirmed piles.

        Each card is drawn on its own (INT-02) and added to its pile through
        the API. It joins the local pile only after the API confirms the add,
        so the local piles keep the order cards were placed (INT-07).

        Raises:
            GameInvariantError: if the finished game breaks a rule it must
                keep.
        """
        deck = self._create_deck()
        remaining = deck.remaining
        drawn: list[Card] = []
        piles: list[DiscardPile] = []
        binned: list[Card] = []

        while remaining > 0:
            draw = self._client.draw_cards(deck.deck_id, 1)
            card = draw.cards[0]
            drawn.append(card)
            remaining = draw.remaining
            if should_bin_card(card):
                binned.append(card)
                continue

            starts_pile = not piles or self._rule(card)
            name = f"discard_{len(piles) + 1}" if starts_pile else piles[-1].name
            added = self._client.add_to_pile(deck.deck_id, name, [card.code])
            remaining = added.remaining
            if starts_pile:
                piles.append(DiscardPile(name, [card]))
            else:
                piles[-1].add(card)

        result = GameResult(deck.deck_id, tuple(piles), remaining, tuple(binned))
        check_invariants(
            result,
            drawn,
            deck_size=deck.remaining,
            rule=self._rule,
            jokers=self._jokers,
        )
        return result

    def _create_deck(self) -> Deck:
        if not self._jokers:
            return self._client.create_deck()
        # The API documents Jokers only for an unshuffled deck (API-04).
        deck = self._client.create_deck(shuffled=False, jokers_enabled=True)
        return self._client.shuffle_deck(deck.deck_id)


def check_invariants(
    result: GameResult,
    drawn: Sequence[Card],
    *,
    deck_size: int,
    rule: PileRule,
    jokers: bool,
) -> None:
    """Check a finished game against the rules it must keep.

    Args:
        result: the finished game.
        drawn: every card drawn, in order.
        deck_size: how many cards the new deck held.
        rule: the rule that decided where piles start.
        jokers: whether the deck included the Jokers.

    Raises:
        GameInvariantError: listing every rule that was broken.
    """
    problems = _find_problems(result, drawn, deck_size, rule, jokers)
    if problems:
        raise GameInvariantError("the game broke its rules: " + "; ".join(problems))


def _find_problems(
    result: GameResult,
    drawn: Sequence[Card],
    deck_size: int,
    rule: PileRule,
    jokers: bool,
) -> list[str]:
    problems: list[str] = []
    placed = [card for pile in result.piles for card in pile.cards]
    expected_pack = (STANDARD_DECK | JOKERS) if jokers else STANDARD_DECK

    expected_size = len(expected_pack)
    if deck_size != expected_size:
        problems.append(f"the deck held {deck_size} cards, not {expected_size}")
    if len(drawn) != deck_size:
        problems.append(f"{len(drawn)} cards were drawn from a deck of {deck_size}")
    if len({card.code for card in drawn}) != len(drawn):
        problems.append("a card was drawn more than once")
    if placed != [card for card in drawn if not should_bin_card(card)]:
        problems.append("the piles do not hold every non-Joker card in draw order")
    if list(result.binned) != [card for card in drawn if should_bin_card(card)]:
        problems.append("the binned cards are not the Jokers drawn")
    if {card.code for card in drawn} != expected_pack:
        problems.append("the cards drawn are not one standard pack")
    if result.cards_remaining != 0:
        problems.append(f"the API reports {result.cards_remaining} cards remaining")

    names = [pile.name for pile in result.piles]
    if names != [f"discard_{n}" for n in range(1, len(names) + 1)]:
        problems.append(f"the piles are not named discard_1 upwards: {names}")
    for index, pile in enumerate(result.piles):
        if index > 0 and not rule(pile.bottom):
            problems.append(f"{pile.name} does not start with a card matching the rule")
        if any(rule(card) for card in pile.cards[1:]):
            problems.append(
                f"{pile.name} holds a card matching the rule above its bottom"
            )
    return problems
