"""Tests for a game interrupted by a failed API call (CH-09, INT-08, OBS-04)."""

import dataclasses
from collections.abc import Iterable

import httpx
import pytest

from card_game.engine import GameEngine, GameInterruptedError
from deck_of_cards_sdk import (
    ApiError,
    Card,
    ConnectionFailedError,
    Deck,
    DeckOfCardsClient,
    DeckOfCardsError,
    DrawResult,
    HttpStatusError,
    HttpTransport,
    IncompleteDrawError,
    InvalidArgumentError,
    PileResult,
    RequestTimeoutError,
    ResponseFormatError,
    TransportError,
)
from tests.cards import PACK_ORDER, make_card
from tests.fakes import DECK_ID, FakeCardClient


def interrupt(client: FakeCardClient, *, jokers: bool = False) -> GameInterruptedError:
    """Run a game that must stop, check it stopped at the failing call, and
    return the error."""
    with pytest.raises(GameInterruptedError) as error:
        GameEngine(client, jokers=jokers).run()
    return error.value


def codes(cards: tuple[Card, ...]) -> list[str]:
    return [card.code for card in cards]


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (InvalidArgumentError("card AS has not been drawn"), "rejected"),
        (ApiError("the API reported success: false"), "rejected"),
        (HttpStatusError(404, "Deck ID does not exist."), "rejected"),
        (HttpStatusError(503, "Service Unavailable"), "unknown"),
        (RequestTimeoutError("timed out"), "unknown"),
        (ConnectionFailedError("could not connect"), "unknown"),
        (TransportError("connection reset"), "unknown"),
        (ResponseFormatError("response body is not valid JSON"), "unknown"),
    ],
)
def test_an_add_failure_stops_the_game_without_retrying(
    error: DeckOfCardsError, outcome: str
) -> None:
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 3): error})

    interrupted = interrupt(client)

    assert interrupted.operation == "add to pile"
    assert interrupted.outcome == outcome
    assert interrupted.__cause__ is error
    assert client.calls[-1] == ("add_to_pile", DECK_ID, "discard_1", ["3S"])
    assert sum(call[0] == "add_to_pile" for call in client.calls) == 3


def test_an_add_failure_keeps_the_card_and_the_confirmed_piles() -> None:
    timeout = RequestTimeoutError("request to 'deck/x/pile/discard_2/add/' timed out")
    sequence = ["2S", "KH", "3S", *PACK_ORDER[3:]]
    client = FakeCardClient(sequence, fail={("add_to_pile", 3): timeout})

    interrupted = interrupt(client)

    assert interrupted.deck_id == DECK_ID
    assert codes(interrupted.unplaced) == ["3S"]
    assert interrupted.pile == "discard_2"
    assert [(p.name, codes(p.cards)) for p in interrupted.piles] == [
        ("discard_1", ["2S"]),
        ("discard_2", ["KH"]),
    ]
    assert str(interrupted) == (
        "game interrupted: add to pile had an unknown outcome: "
        f"{timeout}; not confirmed in a pile: 3S"
    )


def test_a_rejected_add_says_so() -> None:
    rejected = HttpStatusError(404, "Not found")
    client = FakeCardClient(PACK_ORDER, fail={("add_to_pile", 1): rejected})

    interrupted = interrupt(client)

    assert str(interrupted) == (
        "game interrupted: add to pile was rejected: HTTP 404: Not found; "
        "not confirmed in a pile: AS"
    )
    assert interrupted.piles == ()


def test_an_add_with_the_wrong_confirmed_pile_count_stops_the_game() -> None:
    class WrongPileCountClient(FakeCardClient):
        def add_to_pile(
            self, deck_id: str, pile_name: str, cards: Iterable[str]
        ) -> PileResult:
            result = super().add_to_pile(deck_id, pile_name, cards)
            return dataclasses.replace(result, piles={pile_name: 99})

    interrupted = interrupt(WrongPileCountClient(PACK_ORDER))

    assert interrupted.operation == "add to pile"
    assert interrupted.outcome == "unknown"
    assert codes(interrupted.unplaced) == ["AS"]
    assert interrupted.piles == ()
    assert "reported 99 cards" in str(interrupted)


def test_a_draw_failure_stops_the_game() -> None:
    lost = ConnectionFailedError("could not connect to the API")
    client = FakeCardClient(PACK_ORDER, fail={("draw_cards", 3): lost})

    interrupted = interrupt(client)

    assert interrupted.operation == "draw"
    assert interrupted.outcome == "unknown"
    assert interrupted.unplaced == ()
    assert interrupted.pile is None
    assert [codes(p.cards) for p in interrupted.piles] == [["AS", "2S"]]
    assert client.calls[-1] == ("draw_cards", DECK_ID, 1)


def test_an_over_draw_keeps_the_cards_the_api_drew() -> None:
    over_draw = IncompleteDrawError(
        "Not enough cards remaining to draw 1 additional",
        DrawResult(DECK_ID, (make_card("AS"),), 0),
    )
    client = FakeCardClient(PACK_ORDER, fail={("draw_cards", 1): over_draw})

    interrupted = interrupt(client)

    assert interrupted.outcome == "partial"
    assert codes(interrupted.unplaced) == ["AS"]
    assert "draw partially succeeded" in str(interrupted)


@pytest.mark.parametrize("count", [0, 2])
def test_a_draw_not_returning_one_card_stops_the_game(count: int) -> None:
    client = FakeCardClient(PACK_ORDER, deal={2: count})

    interrupted = interrupt(client)

    assert interrupted.operation == "draw"
    assert interrupted.outcome == "unknown"
    assert codes(interrupted.unplaced) == PACK_ORDER[1 : 1 + count]
    assert f"asked for 1 card, got {count}" in str(interrupted)
    assert client.calls[-1] == ("draw_cards", DECK_ID, 1)


def test_a_draw_that_does_not_reduce_remaining_stops_the_game() -> None:
    class StaleRemainingClient(FakeCardClient):
        def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult:
            draw = super().draw_cards(deck_id, count)
            return dataclasses.replace(draw, remaining=draw.remaining + 1)

    interrupted = interrupt(StaleRemainingClient(PACK_ORDER))

    assert interrupted.operation == "draw"
    assert interrupted.outcome == "unknown"
    assert codes(interrupted.unplaced) == ["AS"]
    assert interrupted.piles == ()
    assert "reported 52 cards remaining" in str(interrupted)


def test_a_duplicate_draw_stops_the_game_immediately() -> None:
    class DuplicateDrawClient(FakeCardClient):
        def draw_cards(self, deck_id: str, count: int = 1) -> DrawResult:
            draw = super().draw_cards(deck_id, count)
            if sum(call[0] == "draw_cards" for call in self.calls) == 2:
                return dataclasses.replace(draw, cards=(make_card("AS"),))
            return draw

    interrupted = interrupt(DuplicateDrawClient(PACK_ORDER))

    assert interrupted.operation == "draw"
    assert interrupted.outcome == "unknown"
    assert codes(interrupted.unplaced) == ["AS"]
    assert [codes(pile.cards) for pile in interrupted.piles] == [["AS"]]
    assert "returned card AS more than once" in str(interrupted)


def test_a_failed_deck_creation_has_no_deck() -> None:
    client = FakeCardClient(
        PACK_ORDER, fail={("create_deck", 1): RequestTimeoutError("timed out")}
    )

    interrupted = interrupt(client)

    assert interrupted.operation == "create deck"
    assert interrupted.deck_id is None
    assert interrupted.piles == ()
    assert len(client.calls) == 1


def test_an_unshuffled_new_deck_stops_the_game() -> None:
    class UnshuffledDeckClient(FakeCardClient):
        def create_deck(
            self, *, shuffled: bool = True, jokers_enabled: bool = False
        ) -> Deck:
            return dataclasses.replace(
                super().create_deck(shuffled=shuffled, jokers_enabled=jokers_enabled),
                shuffled=False,
            )

    interrupted = interrupt(UnshuffledDeckClient(PACK_ORDER))

    assert interrupted.operation == "create deck"
    assert interrupted.outcome == "unknown"
    assert interrupted.deck_id == DECK_ID
    assert "was not shuffled" in str(interrupted)


def test_a_failed_shuffle_of_a_joker_deck_keeps_the_deck_id() -> None:
    failure = HttpStatusError(404, "Deck ID does not exist.")
    sequence = [*PACK_ORDER, "X1", "X2"]
    client = FakeCardClient(sequence, fail={("shuffle_deck", 1): failure})

    interrupted = interrupt(client, jokers=True)

    assert interrupted.operation == "shuffle deck"
    assert interrupted.outcome == "rejected"
    assert interrupted.deck_id == DECK_ID


def test_an_unshuffled_shuffle_response_stops_a_joker_game() -> None:
    class UnshuffledJokerClient(FakeCardClient):
        def shuffle_deck(self, deck_id: str) -> Deck:
            return dataclasses.replace(super().shuffle_deck(deck_id), shuffled=False)

    client = UnshuffledJokerClient([*PACK_ORDER, "X1", "X2"])

    interrupted = interrupt(client, jokers=True)

    assert interrupted.operation == "shuffle deck"
    assert interrupted.outcome == "unknown"
    assert interrupted.deck_id == DECK_ID
    assert "was not shuffled" in str(interrupted)


def test_jokers_binned_before_a_failure_are_kept() -> None:
    sequence = ["X1", *PACK_ORDER, "X2"]
    failure = RequestTimeoutError("timed out")
    client = FakeCardClient(sequence, fail={("add_to_pile", 1): failure})

    interrupted = interrupt(client, jokers=True)

    assert codes(interrupted.binned) == ["X1"]


def test_a_timeout_from_the_sdk_client_interrupts_the_game() -> None:
    def api(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/add/"):
            raise httpx.ReadTimeout("timed out", request=request)
        if path.endswith("/draw/"):
            body = {
                "deck_id": DECK_ID,
                "remaining": 51,
                "cards": [dataclasses.asdict(make_card("KH"))],
            }
        else:
            body = {"deck_id": DECK_ID, "shuffled": True, "remaining": 52}
        return httpx.Response(200, json={"success": True, **body})

    http_client = httpx.Client(transport=httpx.MockTransport(api))
    with (
        DeckOfCardsClient(HttpTransport(client=http_client)) as client,
        pytest.raises(GameInterruptedError) as error,
    ):
        GameEngine(client).run()

    assert error.value.outcome == "unknown"
    assert error.value.pile == "discard_1"
    assert codes(error.value.unplaced) == ["KH"]
