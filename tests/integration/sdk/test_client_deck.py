"""Tests for DeckOfCardsClient deck operations over httpx.MockTransport
(API-01 to API-05, OBS-03, DEC-02)."""

import httpx
import pytest

from deck_of_cards_sdk import (
    Card,
    Deck,
    DeckOfCardsClient,
    DrawResult,
    HttpTransport,
    InvalidArgumentError,
    ResponseFormatError,
)

DECK_ID = "3p40paa87x90"


class FakeApi:
    """Returns one JSON body for every request and records the requests."""

    def __init__(self, body: dict[str, object]) -> None:
        self.body = body
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=self.body)

    @property
    def last_url(self) -> str:
        return str(self.requests[-1].url)


def make_client(api: FakeApi) -> DeckOfCardsClient:
    http_client = httpx.Client(transport=httpx.MockTransport(api))
    return DeckOfCardsClient(HttpTransport(client=http_client))


def deck_body(shuffled: bool = True, remaining: object = 52) -> dict[str, object]:
    return {
        "success": True,
        "deck_id": DECK_ID,
        "shuffled": shuffled,
        "remaining": remaining,
    }


def card_body(code: str, value: str, suit: str) -> dict[str, object]:
    image = f"https://deckofcardsapi.com/static/img/{code}.png"
    return {
        "code": code,
        "image": image,
        "images": {"svg": image.replace(".png", ".svg"), "png": image},
        "value": value,
        "suit": suit,
    }


BASE = "https://deckofcardsapi.com/api/"


def test_create_shuffled_deck() -> None:
    api = FakeApi(deck_body())

    deck = make_client(api).create_deck()

    assert api.last_url == f"{BASE}deck/new/shuffle/?deck_count=1"
    assert deck == Deck(deck_id=DECK_ID, shuffled=True, remaining=52)


def test_create_shuffled_deck_with_several_decks() -> None:
    api = FakeApi(deck_body(remaining=312))

    deck = make_client(api).create_deck(deck_count=6)

    assert api.last_url == f"{BASE}deck/new/shuffle/?deck_count=6"
    assert deck.remaining == 312


def test_create_partial_deck_upper_cases_the_codes() -> None:
    api = FakeApi(deck_body(remaining=3))

    make_client(api).create_deck(cards=["as", "2S", "kS"])

    assert api.requests[-1].url.path == "/api/deck/new/shuffle/"
    assert dict(api.requests[-1].url.params) == {
        "deck_count": "1",
        "cards": "AS,2S,KS",
    }


def test_create_unshuffled_deck() -> None:
    api = FakeApi(deck_body(shuffled=False))

    deck = make_client(api).create_deck(shuffled=False)

    assert api.last_url == f"{BASE}deck/new/"
    assert deck.shuffled is False


def test_create_unshuffled_deck_with_jokers() -> None:
    api = FakeApi(deck_body(shuffled=False, remaining=54))

    deck = make_client(api).create_deck(shuffled=False, jokers_enabled=True)

    assert api.last_url == f"{BASE}deck/new/?jokers_enabled=true"
    assert deck.remaining == 54


@pytest.mark.parametrize(
    ("kwargs", "body"),
    [
        ({}, deck_body(shuffled=False)),
        ({"shuffled": False}, deck_body(shuffled=True)),
    ],
)
def test_create_deck_requires_the_requested_shuffled_state(
    kwargs: dict[str, object], body: dict[str, object]
) -> None:
    api = FakeApi(body)

    with pytest.raises(ResponseFormatError, match="field 'shuffled'"):
        make_client(api).create_deck(**kwargs)  # type: ignore[arg-type]

    assert len(api.requests) == 1


def test_draw_cards_parses_cards_including_a_joker() -> None:
    body: dict[str, object] = {
        "success": True,
        "deck_id": DECK_ID,
        "cards": [card_body("KH", "KING", "HEARTS"), card_body("X1", "JOKER", "BLACK")],
        "remaining": 50,
    }
    api = FakeApi(body)

    result = make_client(api).draw_cards(DECK_ID, count=2)

    assert api.last_url == f"{BASE}deck/{DECK_ID}/draw/?count=2"
    assert result == DrawResult(
        deck_id=DECK_ID,
        cards=(
            Card(
                "KH", "KING", "HEARTS", "https://deckofcardsapi.com/static/img/KH.png"
            ),
            Card(
                "X1", "JOKER", "BLACK", "https://deckofcardsapi.com/static/img/X1.png"
            ),
        ),
        remaining=50,
    )
    assert result.cards[0].is_king
    assert result.cards[1].is_joker


def test_draw_defaults_to_one_card() -> None:
    body: dict[str, object] = {
        "success": True,
        "deck_id": DECK_ID,
        "cards": [card_body("6H", "6", "HEARTS")],
        "remaining": 51,
    }
    api = FakeApi(body)

    make_client(api).draw_cards(DECK_ID)

    assert api.last_url == f"{BASE}deck/{DECK_ID}/draw/?count=1"


def test_string_remaining_is_accepted() -> None:
    api = FakeApi(deck_body(remaining="42"))

    assert make_client(api).shuffle_deck(DECK_ID).remaining == 42


def test_shuffle_deck() -> None:
    api = FakeApi(deck_body())

    make_client(api).shuffle_deck(DECK_ID)

    assert api.last_url == f"{BASE}deck/{DECK_ID}/shuffle/"


def test_shuffle_only_the_remaining_cards() -> None:
    api = FakeApi(deck_body(remaining=40))

    make_client(api).shuffle_deck(DECK_ID, remaining_only=True)

    assert api.last_url == f"{BASE}deck/{DECK_ID}/shuffle/?remaining=true"


def test_shuffle_deck_requires_a_shuffled_response() -> None:
    api = FakeApi(deck_body(shuffled=False))

    with pytest.raises(ResponseFormatError, match="field 'shuffled'"):
        make_client(api).shuffle_deck(DECK_ID)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"deck_count": 0}, "count"),
        ({"deck_count": True}, "count"),
        ({"cards": []}, "at least one"),
        ({"cards": ["AS", "1S"]}, "invalid card codes"),
        ({"cards": "AS,2S"}, "must be a list"),
        ({"jokers_enabled": True}, "unshuffled"),
        ({"shuffled": "false"}, "shuffled must be true or false"),
        (
            {"shuffled": False, "jokers_enabled": 1},
            "jokers_enabled must be true or false",
        ),
        ({"shuffled": False, "deck_count": 2}, "shuffled deck"),
        ({"shuffled": False, "cards": ["AS"]}, "shuffled deck"),
    ],
)
def test_invalid_create_arguments_send_no_request(
    kwargs: dict[str, object], message: str
) -> None:
    api = FakeApi(deck_body())

    with pytest.raises(InvalidArgumentError, match=message):
        make_client(api).create_deck(**kwargs)  # type: ignore[arg-type]

    assert api.requests == []


@pytest.mark.parametrize(
    ("deck_id", "count"),
    [("", 1), ("bad id", 1), ("../new", 1), (DECK_ID, 0), (DECK_ID, True)],
)
def test_invalid_draw_arguments_send_no_request(deck_id: str, count: int) -> None:
    api = FakeApi(deck_body())

    with pytest.raises(InvalidArgumentError):
        make_client(api).draw_cards(deck_id, count)

    assert api.requests == []


def test_invalid_shuffle_deck_id_sends_no_request() -> None:
    api = FakeApi(deck_body())

    with pytest.raises(InvalidArgumentError, match="deck ID"):
        make_client(api).shuffle_deck("not/valid")

    assert api.requests == []


def test_invalid_shuffle_boolean_sends_no_request() -> None:
    api = FakeApi(deck_body())

    with pytest.raises(InvalidArgumentError, match="remaining_only"):
        make_client(api).shuffle_deck(
            DECK_ID,
            remaining_only="false",  # type: ignore[arg-type]
        )

    assert api.requests == []


def test_closing_the_client_closes_a_transport_it_created() -> None:
    client = DeckOfCardsClient()

    with client:
        pass

    assert client._transport._client.is_closed


def test_closing_the_client_leaves_an_injected_transport_open() -> None:
    http_client = httpx.Client(transport=httpx.MockTransport(FakeApi(deck_body())))

    with DeckOfCardsClient(HttpTransport(client=http_client)):
        pass

    assert not http_client.is_closed
    http_client.close()
