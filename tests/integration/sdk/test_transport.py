"""Tests for HttpTransport using httpx.MockTransport (API-13, OBS-04, INT-08)."""

from collections.abc import Callable

import httpx
import pytest

from deck_of_cards_sdk.exceptions import (
    ApiError,
    ConnectionFailedError,
    HttpStatusError,
    InvalidArgumentError,
    RequestTimeoutError,
    ResponseFormatError,
    TransportError,
)
from deck_of_cards_sdk.transport import HttpTransport

Handler = Callable[[httpx.Request], httpx.Response]


class RecordingHandler:
    """Returns a fixed response, or raises an error, and records each request."""

    def __init__(
        self,
        response: httpx.Response | None = None,
        error: type[httpx.TransportError] | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error("simulated failure", request=request)
        assert self.response is not None
        return self.response


def make_transport(handler: Handler) -> HttpTransport:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpTransport(client=client)


def test_returns_the_json_object_and_sends_path_and_params() -> None:
    body = {"success": True, "deck_id": "abc123", "remaining": 52}
    handler = RecordingHandler(httpx.Response(200, json=body))

    data = make_transport(handler).get_json("deck/new/shuffle/", {"deck_count": 1})

    assert data == body
    [request] = handler.requests
    assert request.method == "GET"
    assert str(request.url) == (
        "https://deckofcardsapi.com/api/deck/new/shuffle/?deck_count=1"
    )


def test_custom_base_url_without_trailing_slash_is_joined_correctly() -> None:
    handler = RecordingHandler(httpx.Response(200, json={"success": True}))
    client = httpx.Client(transport=httpx.MockTransport(handler))

    HttpTransport("https://example.test/api", client=client).get_json("/deck/new/")

    assert str(handler.requests[0].url) == "https://example.test/api/deck/new/"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectTimeout, RequestTimeoutError),
        (httpx.ReadTimeout, RequestTimeoutError),
        (httpx.ConnectError, ConnectionFailedError),
        (httpx.ReadError, TransportError),
        (httpx.RemoteProtocolError, TransportError),
    ],
)
def test_network_failures_become_sdk_errors_without_retrying(
    error: type[httpx.TransportError], expected: type[Exception]
) -> None:
    handler = RecordingHandler(error=error)

    with pytest.raises(expected) as raised:
        make_transport(handler).get_json("deck/abc123/draw/", {"count": 1})

    assert isinstance(raised.value.__cause__, error)
    assert len(handler.requests) == 1


def test_non_2xx_status_includes_the_api_error_message() -> None:
    body = {"success": False, "error": "Deck ID does not exist."}
    handler = RecordingHandler(httpx.Response(404, json=body))

    with pytest.raises(HttpStatusError) as raised:
        make_transport(handler).get_json("deck/missing/draw/")

    assert raised.value.status_code == 404
    assert str(raised.value) == "HTTP 404: Deck ID does not exist."


def test_non_2xx_status_with_html_body_uses_the_reason_phrase() -> None:
    html = "<html><h1>Server Error (500)</h1></html>"
    handler = RecordingHandler(httpx.Response(500, text=html))

    with pytest.raises(HttpStatusError) as raised:
        make_transport(handler).get_json("deck/abc123/draw/")

    assert raised.value.status_code == 500
    assert str(raised.value) == "HTTP 500: Internal Server Error"
    assert len(handler.requests) == 1


def test_success_false_raises_api_error_with_the_api_message() -> None:
    body = {
        "success": False,
        "cards": [],
        "remaining": 0,
        "error": "Not enough cards remaining to draw 1 additional",
    }
    handler = RecordingHandler(httpx.Response(200, json=body))

    with pytest.raises(ApiError, match="Not enough cards remaining"):
        make_transport(handler).get_json("deck/abc123/draw/", {"count": 1})


def test_success_false_without_a_message_still_raises_api_error() -> None:
    handler = RecordingHandler(httpx.Response(200, json={"success": False}))

    with pytest.raises(ApiError, match="success: false"):
        make_transport(handler).get_json("deck/new/")


@pytest.mark.parametrize(
    "body",
    [
        {"deck_id": "abc123"},
        {"success": "true"},
        {"success": 1},
        {"success": None},
    ],
)
def test_missing_or_non_boolean_success_is_a_format_error(
    body: dict[str, object],
) -> None:
    handler = RecordingHandler(httpx.Response(200, json=body))

    with pytest.raises(ResponseFormatError, match="'success'"):
        make_transport(handler).get_json("deck/new/")


@pytest.mark.parametrize("text", ["not json", "", "{", "<html></html>"])
def test_invalid_json_is_a_format_error(text: str) -> None:
    handler = RecordingHandler(httpx.Response(200, text=text))

    with pytest.raises(ResponseFormatError, match="not valid JSON"):
        make_transport(handler).get_json("deck/new/")


@pytest.mark.parametrize("text", ['[{"success": true}]', '"success"', "1", "null"])
def test_non_object_json_root_is_a_format_error(text: str) -> None:
    handler = RecordingHandler(httpx.Response(200, text=text))

    with pytest.raises(ResponseFormatError, match="must be a JSON object"):
        make_transport(handler).get_json("deck/new/")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://deckofcardsapi.com/api/",
        "ftp://deckofcardsapi.com/api/",
        "deckofcardsapi.com/api/",
        "https://",
        "https://:80/",
        "",
        "https://[::1",
    ],
)
def test_base_url_must_be_https(base_url: str) -> None:
    with pytest.raises(InvalidArgumentError, match="HTTPS"):
        HttpTransport(base_url)


def test_closing_closes_a_client_the_transport_created() -> None:
    transport = HttpTransport()

    with transport:
        pass

    assert transport._client.is_closed


def test_closing_leaves_an_injected_client_open() -> None:
    client = httpx.Client(transport=httpx.MockTransport(RecordingHandler()))

    with HttpTransport(client=client):
        pass

    assert not client.is_closed
    client.close()
