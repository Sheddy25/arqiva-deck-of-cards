"""Discard piles and the game result (CH-10, INT-04, INT-07)."""

from dataclasses import dataclass

from deck_of_cards_sdk import Card


@dataclass(frozen=True)
class DiscardPile:
    """A face-down discard pile, holding its cards in the order they were
    placed.

    The bottom card is the first placed and the top card the most recently
    placed (INT-04). A pile is created with its first card, so it is never
    empty. Piles cannot be changed; :meth:`with_card` returns a new pile.
    """

    name: str
    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        if not self.cards:
            raise ValueError(f"pile {self.name!r} must start with a card")

    def with_card(self, card: Card) -> "DiscardPile":
        """This pile with ``card`` placed on top."""
        return DiscardPile(self.name, (*self.cards, card))

    @property
    def bottom(self) -> Card:
        """The first card placed."""
        return self.cards[0]

    @property
    def top(self) -> Card:
        """The most recently placed card."""
        return self.cards[-1]

    @property
    def count(self) -> int:
        """How many cards the pile holds."""
        return len(self.cards)


@dataclass(frozen=True)
class GameResult:
    """The outcome of a completed game.

    ``piles`` are in the order they were started, and ``binned`` holds the
    Jokers drawn, which are never placed in a pile (DEC-02).
    """

    deck_id: str
    piles: tuple[DiscardPile, ...]
    cards_remaining: int
    binned: tuple[Card, ...] = ()

    @property
    def total_discarded(self) -> int:
        """How many cards were placed in piles."""
        return sum(pile.count for pile in self.piles)
