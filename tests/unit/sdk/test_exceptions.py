"""Tests for the SDK error hierarchy."""

import pytest

from deck_of_cards_sdk.exceptions import (
    ApiError,
    ConnectionFailedError,
    DeckOfCardsError,
    HttpStatusError,
    InvalidArgumentError,
    RequestTimeoutError,
    ResponseFormatError,
    TransportError,
)


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
