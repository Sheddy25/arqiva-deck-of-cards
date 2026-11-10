"""Tests for DeckOfCardsClient pile operations over httpx.MockTransport
(API-07 to API-11, OBS-03, OBS-05), including the card record that guards
add_to_pile (DEC-06)."""

from collections.abc import Callable

import httpx
import pytest

from deck_of_cards_sdk import (
    ApiError,
    Card,
    DeckOfCardsClient,
    HttpStatusError,
    HttpTransport,
    IncompleteDrawError,
    InvalidArgumentError,
    PileDrawResult,
    PileListing,
    PileResult,
)
from deck_of_cards_sdk.validation import RANK_VALUES, SUIT_NAMES

DECK_ID = "3p40paa87x90"
BASE = f"https://deckofcardsapi.com/api/deck/{DECK_ID}/"


class FakeApi:
    """Answers requests with the given responses in order, repeating the last
    one, and records the requests.

    A dict is sent as a successful JSON body for ``DECK_ID``.
    """

    def __init__(self, *responses: dict[str, object] | httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        response = (
            self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        )
        if isinstance(response, httpx.Response):
            return response
        return httpx.Response(
            200, json={"success": True, "deck_id": DECK_ID, **response}
        )

    @property
    def last_url(self) -> str:
        return str(self.requests[-1].url)


def make_client(api: FakeApi) -> DeckOfCardsClient:
    http_client = httpx.Client(transport=httpx.MockTransport(api))
    return DeckOfCardsClient(HttpTransport(client=http_client))


def card_body(code: str, value: str, suit: str) -> dict[str, object]:
    return {
        "code": code,
        "image": f"https://deckofcardsapi.com/static/img/{code}.png",
        "value": value,
        "suit": suit,
    }


def card(code: str, value: str, suit: str) -> Card:
    return Card(code, value, suit, f"https://deckofcardsapi.com/static/img/{code}.png")


def cards_body(*codes: str) -> dict[str, object]:
    return {
        "cards": [card_body(c, RANK_VALUES[c[0]], SUIT_NAMES[c[1]]) for c in codes],
        "remaining": 0,
    }


PILES = {"piles": {"discard": {"remaining": 2}}}
ADDED = {"remaining": 0, **PILES}


def test_add_to_pile() -> None:
    api = FakeApi(cards_body("AS", "2S"), {"remaining": 50, **PILES})
    client = make_client(api)
    client.draw_cards(DECK_ID, 2)

    result = client.add_to_pile(DECK_ID, "discard", ["as", "2S"])

    assert api.last_url == f"{BASE}pile/discard/add/?cards=AS%2C2S"
    assert result == PileResult(deck_id=DECK_ID, remaining=50, piles={"discard": 2})


def test_pile_counts_sent_as_strings_are_accepted() -> None:
    api = FakeApi({"remaining": "42", "piles": {"player1": {"remaining": "3"}}})

    result = make_client(api).shuffle_pile(DECK_ID, "player1")

    assert result.remaining == 42
    assert result.piles == {"player1": 3}


def test_pile_counts_are_read_only() -> None:
    api = FakeApi({"remaining": 50, **PILES})

    result = make_client(api).shuffle_pile(DECK_ID, "discard")

    with pytest.raises(TypeError):
        result.piles["discard"] = 99  # type: ignore[index]


def test_shuffle_pile() -> None:
    api = FakeApi({"remaining": 50, **PILES})

    result = make_client(api).shuffle_pile(DECK_ID, "discard")

    assert api.last_url == f"{BASE}pile/discard/shuffle/"
    assert result.piles == {"discard": 2}


def test_list_pile_returns_only_the_named_pile() -> None:
    body: dict[str, object] = {
        "remaining": "42",
        "piles": {
            "player1": {"remaining": "3"},
            "player2": {
                "cards": [
                    card_body("KH", "KING", "HEARTS"),
                    card_body("8C", "8", "CLUBS"),
                ],
                "remaining": "2",
            },
        },
    }
    api = FakeApi(body)

    listing = make_client(api).list_pile(DECK_ID, "player2")

    assert api.last_url == f"{BASE}pile/player2/list/"
    assert listing == PileListing(
        deck_id=DECK_ID,
        pile_name="player2",
        cards=(card("KH", "KING", "HEARTS"), card("8C", "8", "CLUBS")),
    )


def test_listing_an_unknown_pile_gives_no_cards() -> None:
    api = FakeApi({"remaining": 0, **PILES})

    assert make_client(api).list_pile(DECK_ID, "nope").cards == ()


@pytest.mark.parametrize(
    ("kwargs", "url"),
    [
        ({}, "pile/discard/draw/"),
        ({"count": 2}, "pile/discard/draw/?count=2"),
        ({"cards": ["as"]}, "pile/discard/draw/?cards=AS"),
        ({"position": "bottom"}, "pile/discard/draw/bottom/"),
        ({"position": "bottom", "count": 2}, "pile/discard/draw/bottom/?count=2"),
        ({"position": "random", "count": 1}, "pile/discard/draw/random/?count=1"),
    ],
)
def test_draw_from_pile_routes(kwargs: dict[str, object], url: str) -> None:
    api = FakeApi({"cards": [card_body("AS", "ACE", "SPADES")], **PILES})

    result = make_client(api).draw_from_pile(DECK_ID, "discard", **kwargs)  # type: ignore[arg-type]

    assert api.last_url == BASE + url
    assert result == PileDrawResult(
        deck_id=DECK_ID,
        cards=(card("AS", "ACE", "SPADES"),),
        piles={"discard": 2},
    )


def test_return_drawn_cards_to_the_deck_without_piles_in_the_response() -> None:
    api = FakeApi({"remaining": 52})

    result = make_client(api).return_cards(DECK_ID)

    assert api.last_url == f"{BASE}return/"
    assert result == PileResult(deck_id=DECK_ID, remaining=52, piles={})


@pytest.mark.parametrize(
    ("kwargs", "url"),
    [
        ({"cards": ["AS", "2s"]}, "return/?cards=AS%2C2S"),
        ({"pile_name": "discard"}, "pile/discard/return/"),
        ({"pile_name": "discard", "cards": ["AS"]}, "pile/discard/return/?cards=AS"),
    ],
)
def test_return_cards_routes(kwargs: dict[str, object], url: str) -> None:
    api = FakeApi({"remaining": 52, "piles": {"discard": {"remaining": 0}}})

    make_client(api).return_cards(DECK_ID, **kwargs)  # type: ignore[arg-type]

    assert api.last_url == BASE + url


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda c: c.add_to_pile("bad id", "discard", ["AS"]), "deck ID"),
        (lambda c: c.add_to_pile(DECK_ID, "bad name", ["AS"]), "pile name"),
        (lambda c: c.add_to_pile(DECK_ID, "../x", ["AS"]), "pile name"),
        (lambda c: c.add_to_pile(DECK_ID, "discard", []), "at least one"),
        (lambda c: c.add_to_pile(DECK_ID, "discard", "AS"), "must be a list"),
        (lambda c: c.shuffle_pile(DECK_ID, ""), "pile name"),
        (lambda c: c.list_pile(DECK_ID, "a/b"), "pile name"),
        (lambda c: c.draw_from_pile(DECK_ID, "discard", count=0), "count"),
        (
            lambda c: c.draw_from_pile(DECK_ID, "discard", count=1, cards=["AS"]),
            "not both",
        ),
        (
            lambda c: c.draw_from_pile(
                DECK_ID, "discard", cards=["AS"], position="bottom"
            ),
            "top of a pile",
        ),
        (
            lambda c: c.draw_from_pile(DECK_ID, "discard", position="middle"),
            "position",
        ),
        (lambda c: c.return_cards(DECK_ID, cards=["1S"]), "invalid card codes"),
        (lambda c: c.return_cards(DECK_ID, pile_name="x y"), "pile name"),
    ],
)
def test_invalid_arguments_send_no_request(
    call: Callable[[DeckOfCardsClient], object], message: str
) -> None:
    api = FakeApi({"remaining": 0})
    client = make_client(api)

    with pytest.raises(InvalidArgumentError, match=message):
        call(client)

    assert api.requests == []


def test_adding_a_card_that_was_not_drawn_sends_no_request() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)

    with pytest.raises(InvalidArgumentError, match="card 2S has not been drawn"):
        client.add_to_pile(DECK_ID, "discard", ["AS", "2S"])

    assert len(api.requests) == 1


def test_adding_a_card_already_in_a_pile_sends_no_request() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)
    client.add_to_pile(DECK_ID, "discard_1", ["AS"])

    with pytest.raises(InvalidArgumentError, match="already in pile 'discard_1'"):
        client.add_to_pile(DECK_ID, "discard_2", ["AS"])

    assert len(api.requests) == 2


def test_a_card_listed_twice_is_rejected() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)

    with pytest.raises(InvalidArgumentError, match="listed more than once"):
        client.add_to_pile(DECK_ID, "discard", ["AS", "as"])


def test_cards_drawn_from_one_deck_cannot_be_added_to_another() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)

    with pytest.raises(InvalidArgumentError, match="has not been drawn"):
        client.add_to_pile("otherdeck1", "discard", ["AS"])


def test_cards_drawn_by_another_client_cannot_be_added() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    make_client(api).draw_cards(DECK_ID)

    with pytest.raises(InvalidArgumentError, match="has not been drawn"):
        make_client(api).add_to_pile(DECK_ID, "discard", ["AS"])


def test_drawing_from_new_records_the_created_deck() -> None:
    api = FakeApi(cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards("new")

    client.add_to_pile(DECK_ID, "discard", ["AS"])


def test_a_failed_add_leaves_the_card_held() -> None:
    error = httpx.Response(404, json={"success": False, "error": "Not found"})
    api = FakeApi(cards_body("AS"), error, ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)

    with pytest.raises(HttpStatusError):
        client.add_to_pile(DECK_ID, "discard", ["AS"])
    client.add_to_pile(DECK_ID, "discard", ["AS"])


def test_an_over_draw_keeps_the_cards_the_api_drew() -> None:
    over_draw = httpx.Response(
        200,
        json={
            "success": False,
            "deck_id": DECK_ID,
            **cards_body("AS"),
            "error": "Not enough cards remaining to draw 2 additional",
        },
    )
    api = FakeApi(over_draw, ADDED)
    client = make_client(api)

    with pytest.raises(IncompleteDrawError, match="Not enough cards") as error:
        client.draw_cards(DECK_ID, 2)
    client.add_to_pile(DECK_ID, "discard", ["AS"])

    assert isinstance(error.value, ApiError)
    assert error.value.result.cards == (card("AS", "ACE", "SPADES"),)
    assert error.value.result.remaining == 0


def test_a_failed_draw_without_cards_is_a_plain_api_error() -> None:
    api = FakeApi(httpx.Response(200, json={"success": False, "error": "No deck"}))

    with pytest.raises(ApiError, match="No deck") as error:
        make_client(api).draw_cards(DECK_ID)

    assert not isinstance(error.value, IncompleteDrawError)


def test_a_card_drawn_from_a_pile_can_be_added_to_another() -> None:
    api = FakeApi(cards_body("AS"), ADDED, cards_body("AS"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)
    client.add_to_pile(DECK_ID, "discard_1", ["AS"])
    client.draw_from_pile(DECK_ID, "discard_1")

    client.add_to_pile(DECK_ID, "discard_2", ["AS"])

    assert api.last_url == f"{BASE}pile/discard_2/add/?cards=AS"


@pytest.mark.parametrize(
    ("kwargs", "added"),
    [
        ({}, False),
        ({"cards": ["AS"]}, False),
        ({"cards": ["2S"]}, True),
    ],
)
def test_returning_drawn_cards_to_the_deck(
    kwargs: dict[str, object], added: bool
) -> None:
    api = FakeApi(cards_body("AS"), {"remaining": 1}, ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID)
    client.return_cards(DECK_ID, **kwargs)  # type: ignore[arg-type]

    if added:
        client.add_to_pile(DECK_ID, "discard", ["AS"])
    else:
        with pytest.raises(InvalidArgumentError, match="has not been drawn"):
            client.add_to_pile(DECK_ID, "discard", ["AS"])


def test_returning_drawn_cards_leaves_cards_in_piles() -> None:
    api = FakeApi(cards_body("AS"), ADDED, {"remaining": 0})
    client = make_client(api)
    client.draw_cards(DECK_ID)
    client.add_to_pile(DECK_ID, "discard_1", ["AS"])
    client.return_cards(DECK_ID)

    with pytest.raises(InvalidArgumentError, match="already in pile"):
        client.add_to_pile(DECK_ID, "discard_2", ["AS"])


@pytest.mark.parametrize(
    ("kwargs", "returned"),
    [
        ({"pile_name": "discard_1"}, {"AS", "2S"}),
        ({"pile_name": "discard_1", "cards": ["AS"]}, {"AS"}),
        ({"pile_name": "discard_2"}, set()),
    ],
)
def test_returning_a_pile_to_the_deck(
    kwargs: dict[str, object], returned: set[str]
) -> None:
    api = FakeApi(cards_body("AS", "2S"), ADDED)
    client = make_client(api)
    client.draw_cards(DECK_ID, 2)
    client.add_to_pile(DECK_ID, "discard_1", ["AS", "2S"])
    client.return_cards(DECK_ID, **kwargs)  # type: ignore[arg-type]

    for code in ("AS", "2S"):
        reason = "has not been drawn" if code in returned else "already in pile"
        with pytest.raises(InvalidArgumentError, match=reason):
            client.add_to_pile(DECK_ID, "discard_3", [code])


@pytest.mark.parametrize(
    ("remaining_only", "reason"),
    [(False, "has not been drawn"), (True, "already in pile")],
)
def test_a_full_reshuffle_returns_every_card(remaining_only: bool, reason: str) -> None:
    deck: dict[str, object] = {"shuffled": True, "remaining": 2}
    api = FakeApi(cards_body("AS"), ADDED, deck)
    client = make_client(api)
    client.draw_cards(DECK_ID)
    client.add_to_pile(DECK_ID, "discard_1", ["AS"])
    client.shuffle_deck(DECK_ID, remaining_only=remaining_only)

    with pytest.raises(InvalidArgumentError, match=reason):
        client.add_to_pile(DECK_ID, "discard_2", ["AS"])
