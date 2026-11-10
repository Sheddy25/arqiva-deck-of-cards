"""Live checks against https://deckofcardsapi.com/ (CH-01, OBS-01 to OBS-05).

These re-check the observed API behaviour the SDK relies on. They are excluded
by default and only run with ``DECK_API_SMOKE=1 pytest -m smoke``; see "Why the
smoke test is opt-in" in docs/architecture.md.
"""

import os
from collections.abc import Iterator

import pytest

from deck_of_cards_sdk import (
    ApiError,
    DeckOfCardsClient,
    HttpStatusError,
    HttpTransport,
    IncompleteDrawError,
)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.environ.get("DECK_API_SMOKE") != "1",
        reason="set DECK_API_SMOKE=1 to call the live API",
    ),
]


@pytest.fixture
def client() -> Iterator[DeckOfCardsClient]:
    with DeckOfCardsClient() as client:
        yield client


def test_a_shuffled_pack_has_52_cards_with_the_observed_names(
    client: DeckOfCardsClient,
) -> None:
    deck = client.create_deck()
    drawn = client.draw_cards(deck.deck_id, 52)

    assert deck.shuffled
    assert deck.remaining == 52
    assert drawn.remaining == 0
    assert len({card.code for card in drawn.cards}) == 52
    assert sum(card.is_king for card in drawn.cards) == 4


def test_jokers_have_the_observed_codes(client: DeckOfCardsClient) -> None:
    deck = client.create_deck(shuffled=False, jokers_enabled=True)
    drawn = client.draw_cards(deck.deck_id, deck.remaining)

    jokers = {card.code: card.suit for card in drawn.cards if card.is_joker}
    assert deck.remaining == 54
    assert jokers == {"X1": "BLACK", "X2": "RED"}


def test_a_drawn_card_can_be_added_to_a_pile_and_listed(
    client: DeckOfCardsClient,
) -> None:
    deck = client.create_deck(cards=["AS", "2S", "KH"])
    card = client.draw_cards(deck.deck_id).cards[0]

    added = client.add_to_pile(deck.deck_id, "discard_1", [card.code])
    listing = client.list_pile(deck.deck_id, "discard_1")
    unknown = client.list_pile(deck.deck_id, "discard_2")
    from_pile = client.draw_from_pile(deck.deck_id, "discard_1")
    returned = client.return_cards(deck.deck_id)

    assert added.remaining == 2
    assert added.piles == {"discard_1": 1}
    assert listing.cards == (card,)
    assert unknown.cards == ()
    assert from_pile.cards == (card,)
    assert from_pile.piles == {"discard_1": 0}
    assert returned.remaining == 3
    assert returned.piles == {}


def test_failures_have_the_observed_form(client: DeckOfCardsClient) -> None:
    deck = client.create_deck(cards=["AS", "2S"])
    card = client.draw_cards(deck.deck_id).cards[0]
    client.add_to_pile(deck.deck_id, "discard_1", [card.code])

    with pytest.raises(HttpStatusError, match="Deck ID does not exist") as unknown:
        client.draw_cards("nosuchdeck00")
    with pytest.raises(HttpStatusError, match="Not enough cards") as pile:
        client.draw_from_pile(deck.deck_id, "discard_1", count=2)
    with pytest.raises(IncompleteDrawError, match="Not enough cards") as over_draw:
        client.draw_cards(deck.deck_id, 2)
    last = over_draw.value.result.cards
    client.add_to_pile(deck.deck_id, "discard_1", [card.code for card in last])

    assert unknown.value.status_code == 404
    assert pile.value.status_code == 404
    assert isinstance(over_draw.value, ApiError)
    assert len(last) == 1
    assert over_draw.value.result.remaining == 0


def test_the_api_still_accepts_adds_the_client_guards_against() -> None:
    """The reasons the client guards add_to_pile (DEC-06), checked without the
    client. If this fails, the API has started to reject such adds itself."""
    with HttpTransport() as transport:
        deck = transport.get_json("deck/new/shuffle/", {"cards": "AS,2S"})
        pile = f"deck/{deck['deck_id']}/pile"
        not_drawn = transport.get_json(f"{pile}/discard_1/add/", {"cards": "AS"})
        drawn = transport.get_json(f"deck/{deck['deck_id']}/draw/", {"count": 1})
        code = drawn["cards"][0]["code"]  # type: ignore[index]
        transport.get_json(f"{pile}/discard_1/add/", {"cards": code})
        moved = transport.get_json(f"{pile}/discard_2/add/", {"cards": code})

    assert not_drawn["remaining"] == 2
    assert not_drawn["piles"] == {"discard_1": {"remaining": 0}}
    assert moved["piles"] == {
        "discard_1": {"remaining": 0},
        "discard_2": {"remaining": 1},
    }
