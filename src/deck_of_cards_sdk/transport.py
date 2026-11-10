"""HTTP transport for the Deck of Cards API.

:class:`HttpTransport` sends every request and turns ``httpx`` failures into
SDK errors, so callers never need to handle ``httpx`` exceptions.
"""

from collections.abc import Mapping
from types import TracebackType
from typing import Self

import httpx

from deck_of_cards_sdk.exceptions import (
    ApiError,
    ConnectionFailedError,
    HttpStatusError,
    InvalidArgumentError,
    RequestTimeoutError,
    ResponseFormatError,
    TransportError,
)

DEFAULT_BASE_URL = "https://deckofcardsapi.com/api/"
DEFAULT_TIMEOUT = httpx.Timeout(10.0)

QueryParams = Mapping[str, str | int]


class HttpTransport:
    """Sends GET requests to the API and returns the JSON object.

    Requests are never retried. Many API calls change state even though they
    use ``GET``, so a retry could draw or move a card twice (INT-08).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        """Create a transport.

        Args:
            base_url: the API root; must use HTTPS.
            timeout: used only when the transport creates its own client.
            client: an existing ``httpx.Client``, for example one using
                ``httpx.MockTransport`` in tests. The caller keeps ownership
                of it, so :meth:`close` does not close it.
        """
        if not _is_https_url(base_url):
            raise InvalidArgumentError(
                f"base URL must be an HTTPS URL, got {base_url!r}"
            )
        self._base_url = base_url if base_url.endswith("/") else base_url + "/"
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(timeout=timeout)

    def get_json(
        self, path: str, params: QueryParams | None = None
    ) -> dict[str, object]:
        """Send ``GET`` to ``path`` and return the response's JSON object.

        Raises:
            RequestTimeoutError: the request timed out.
            ConnectionFailedError: the API could not be reached.
            TransportError: the request failed for another network reason.
            HttpStatusError: the API responded with a non-2xx status.
            ResponseFormatError: the body is not a JSON object, or its
                ``success`` field is missing or not a boolean.
            ApiError: the API responded with ``"success": false``.
        """
        url = self._base_url + path.lstrip("/")
        try:
            response = self._client.get(url, params=params)
        except httpx.TimeoutException as error:
            raise RequestTimeoutError(f"request to {path!r} timed out") from error
        except httpx.ConnectError as error:
            raise ConnectionFailedError(
                f"could not connect to the API for {path!r}"
            ) from error
        except httpx.TransportError as error:
            raise TransportError(f"request to {path!r} failed: {error}") from error

        if not response.is_success:
            raise HttpStatusError(
                response.status_code,
                _api_error_message(response) or response.reason_phrase,
            )

        data = _json_object(response)
        success = data.get("success")
        if success is False:
            raise ApiError(
                _error_text(data) or "the API reported success: false", body=data
            )
        if success is not True:
            raise ResponseFormatError(
                f"field 'success' must be true or false, got {success!r}"
            )
        return data

    def close(self) -> None:
        """Close the HTTP client, if this transport created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _is_https_url(url: str) -> bool:
    try:
        parsed = httpx.URL(url)
    except httpx.InvalidURL:
        return False
    return parsed.scheme == "https" and bool(parsed.host)


def _json_object(response: httpx.Response) -> dict[str, object]:
    try:
        data = response.json()
    except ValueError as error:
        raise ResponseFormatError("response body is not valid JSON") from error
    if not isinstance(data, dict):
        raise ResponseFormatError(
            f"response body must be a JSON object, not {type(data).__name__}"
        )
    return data


def _api_error_message(response: httpx.Response) -> str | None:
    """The API's ``error`` text from a JSON error body, if there is one.

    For example, an unknown deck ID gives HTTP 404 with
    ``{"success": false, "error": "Deck ID does not exist."}`` (OBS-04).
    Other bodies, such as HTML error pages, are not included.
    """
    try:
        return _error_text(_json_object(response))
    except ResponseFormatError:
        return None


def _error_text(data: Mapping[str, object]) -> str | None:
    error = data.get("error")
    return error if isinstance(error, str) and error else None
