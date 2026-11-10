"""Tests for the SDK error hierarchy."""

import pytest

from deck_of_cards_sdk.exceptions import (
    ApiError,
    ConnectionFailedError,
    DeckOfCardsError,
    HttpStatusError,
    IncompleteDrawError,
    InvalidArgumentError,
    RequestTimeoutError,
    ResponseFormatError,
    TransportError,
)
from deck_of_cards_sdk.models import DrawResult
from tests.cards import make_card


@pytest.mark.parametrize(
    "error_type",
    [
        InvalidArgumentError,
        TransportError,
        RequestTimeoutError,
        ConnectionFailedError,
        HttpStatusError,
        ResponseFormatError,
        ApiError,
        IncompleteDrawError,
    ],
)
def test_every_error_is_a_deck_of_cards_error(error_type: type[Exception]) -> None:
    assert issubclass(error_type, DeckOfCardsError)


@pytest.mark.parametrize("error_type", [RequestTimeoutError, ConnectionFailedError])
def test_timeouts_and_connection_failures_are_transport_errors(
    error_type: type[Exception],
) -> None:
    assert issubclass(error_type, TransportError)


def test_http_status_error_keeps_the_status_code() -> None:
    error = HttpStatusError(404, "Not Found")

    assert error.status_code == 404
    assert str(error) == "HTTP 404: Not Found"


def test_incomplete_draw_error_keeps_the_result_and_body() -> None:
    result = DrawResult("abc123", (make_card("AS"),), 0)
    body: dict[str, object] = {"success": False, "remaining": 0}

    error = IncompleteDrawError("not enough cards", result, body=body)

    assert isinstance(error, ApiError)
    assert error.result is result
    assert error.body is body
