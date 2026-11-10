"""The discard game (CH-03 to CH-08, INT-01 to INT-04, INT-07, DEC-02).

The engine draws a shuffled deck one card at a time. Each card goes face down
on the current discard pile, a card matching the rule (a King by default)
starts a new pile, and a Joker is binned.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

from card_game.models import DiscardPile, GameResult
from card_game.ports import CardClient
from card_game.rules import PileRule, should_bin_card, should_start_new_pile
from deck_of_cards_sdk import (
    ApiError,
    Card,
    Deck,
    DeckOfCardsError,
    HttpStatusError,
    IncompleteDrawError,
    InvalidArgumentError,
)

STANDARD_DECK = frozenset(rank + suit for rank in "A234567890JQK" for suit in "SDCH")
JOKERS = frozenset({"X1", "X2"})

Operation = Literal["create deck", "shuffle deck", "draw", "add to pile"]
Outcome = Literal["rejected", "unknown"]


class GameInvariantError(Exception):
    """A game finished but broke a rule it must keep, so its result cannot be
    trusted."""


class GameInterruptedError(Exception):
    """A call to the API failed, so the game stopped before the end.

    Nothing is retried and no result is reported (INT-08).

    Attributes:
        operation: the call that failed.
        outcome: ``"rejected"`` if the API answered and refused the call;
            ``"unknown"`` after a timeout, lost connection, server error or
            unexpected response, when the call may have taken effect.
        deck_id: the deck, or ``None`` if none was created.
        unplaced: cards drawn but not confirmed in a pile.
        pile: the pile a card was being added to, if any.
        piles: the piles confirmed before the failure.
        binned: the Jokers binned before the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: Operation,
        outcome: Outcome,
        deck_id: str | None = None,
        unplaced: tuple[Card, ...] = (),
        pile: str | None = None,
        piles: tuple[DiscardPile, ...] = (),
        binned: tuple[Card, ...] = (),
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.outcome = outcome
        self.deck_id = deck_id
        self.unplaced = unplaced
        self.pile = pile
        self.piles = piles
        self.binned = binned


@dataclass
class _Progress:
    """What the API has confirmed so far in a game."""

    deck_id: str
    remaining: int
    drawn: list[Card] = field(default_factory=list)
    piles: list[DiscardPile] = field(default_factory=list)
    binned: list[Card] = field(default_factory=list)


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
            GameInterruptedError: if a call to the API fails, or a draw does
                not return exactly one card.
            GameInvariantError: if the finished game breaks a rule it must
                keep.
        """
        deck = self._create_deck()
        game = _Progress(deck.deck_id, deck.remaining)
        while game.remaining > 0:
            card = self._draw_one(game)
            if should_bin_card(card):
                game.binned.append(card)
            else:
                self._place(game, card)

        result = GameResult(
            game.deck_id, tuple(game.piles), game.remaining, tuple(game.binned)
        )
        check_invariants(
            result,
            game.drawn,
            deck_size=deck.remaining,
            rule=self._rule,
            jokers=self._jokers,
        )
        return result

    def _create_deck(self) -> Deck:
        try:
            if not self._jokers:
                return self._client.create_deck()
            # The API documents Jokers only for an unshuffled deck (API-04).
            deck = self._client.create_deck(shuffled=False, jokers_enabled=True)
        except DeckOfCardsError as error:
            raise _interrupted(str(error), "create deck", _outcome(error)) from error
        try:
            return self._client.shuffle_deck(deck.deck_id)
        except DeckOfCardsError as error:
            game = _Progress(deck.deck_id, deck.remaining)
            raise _interrupted(
                str(error), "shuffle deck", _outcome(error), game
            ) from error

    def _draw_one(self, game: _Progress) -> Card:
        try:
            draw = self._client.draw_cards(game.deck_id, 1)
        except IncompleteDrawError as error:
            cards = error.result.cards
            game.drawn.extend(cards)
            raise _interrupted(
                str(error), "draw", "rejected", game, unplaced=cards
            ) from error
        except DeckOfCardsError as error:
            raise _interrupted(str(error), "draw", _outcome(error), game) from error

        game.drawn.extend(draw.cards)
        game.remaining = draw.remaining
        if len(draw.cards) != 1:
            raise _interrupted(
                f"asked for 1 card, got {len(draw.cards)}",
                "draw",
                "unknown",
                game,
                unplaced=draw.cards,
            )
        return draw.cards[0]

    def _place(self, game: _Progress, card: Card) -> None:
        """Add ``card`` to its pile, and record it once the API confirms."""
        starts_pile = not game.piles or self._rule(card)
        name = f"discard_{len(game.piles) + 1}" if starts_pile else game.piles[-1].name
        try:
            added = self._client.add_to_pile(game.deck_id, name, [card.code])
        except DeckOfCardsError as error:
            raise _interrupted(
                str(error),
                "add to pile",
                _outcome(error),
                game,
                unplaced=(card,),
                pile=name,
            ) from error

        game.remaining = added.remaining
        if starts_pile:
            game.piles.append(DiscardPile(name, (card,)))
        else:
            game.piles[-1] = game.piles[-1].with_card(card)


def _outcome(error: DeckOfCardsError) -> Outcome:
    """``"rejected"`` if the API answered and refused, so the call did not
    take effect; ``"unknown"`` if it may have."""
    if isinstance(error, HttpStatusError):
        return "rejected" if error.status_code < 500 else "unknown"
    if isinstance(error, InvalidArgumentError | ApiError):
        return "rejected"
    return "unknown"


def _interrupted(
    reason: str,
    operation: Operation,
    outcome: Outcome,
    game: _Progress | None = None,
    *,
    unplaced: tuple[Card, ...] = (),
    pile: str | None = None,
) -> GameInterruptedError:
    status = "was rejected" if outcome == "rejected" else "had an unknown outcome"
    message = f"game interrupted: {operation} {status}: {reason}"
    if unplaced:
        codes = ", ".join(card.code for card in unplaced)
        message += f"; not confirmed in a pile: {codes}"
    return GameInterruptedError(
        message,
        operation=operation,
        outcome=outcome,
        deck_id=game.deck_id if game else None,
        unplaced=unplaced,
        pile=pile,
        piles=tuple(game.piles) if game else (),
        binned=tuple(game.binned) if game else (),
    )


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
