"""The client, on the standard library only."""

import gzip
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ._core import (
    ApiSkinsError,
    ItemOffers,
    ItemOrders,
    Request,
    Settings,
    Usage,
    batches,
    error_message,
    item_path,
    parse,
    provider_query,
    read_usage,
    retry_after,
    wait_before_retry,
    backoff_seconds,
)

# (status, lower-cased headers, body) for a request; replaceable for tests
Transport = Callable[[Request, float], Tuple[int, Dict[str, str], bytes]]


def _urllib_transport(request: Request, timeout: float) -> Tuple[int, Dict[str, str], bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(request.url, headers=request.headers), timeout=timeout) as response:
            status, raw_headers, body = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        status, raw_headers, body = error.code, error.headers, error.read()

    headers = {key.lower(): value for key, value in raw_headers.items()}
    if headers.get("content-encoding") == "gzip":
        body = gzip.decompress(body)
    return status, headers, body


class ApiSkins:
    """The API Skins client: CS2 skin prices across marketplaces.

    >>> api = ApiSkins(api_key=os.environ["APISKINS_API_KEY"])
    >>> api.offers.get("AK-47 | Redline (Field-Tested)")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        max_retries: int = 2,
        max_retry_wait_seconds: float = 60,
        timeout: float = 120,
        transport: Optional[Transport] = None,
    ) -> None:
        """
        :param api_key: your key, from https://apiskins.com/api-docs once signed in
        :param max_retries: how many times a request is tried again after a rate limit or a server error
        :param max_retry_wait_seconds: the longest Retry-After worth waiting for; a 429 asking for
            longer, such as the 30-day limit being reached, is raised at once
        :param timeout: seconds per request (every item at once is a large answer)
        """
        self._settings = Settings.make(api_key, base_url, max_retries, max_retry_wait_seconds, timeout)
        self._transport = transport or _urllib_transport
        #: Usage left this 30-day period, as of the last answer. None before the first request.
        self.last_usage: Optional[Usage] = None
        self.offers = _Offers(self)
        self.orders = _Orders(self)

    def _request(self, path: str, query: List[Tuple[str, str]]) -> Any:
        request = self._settings.request(path, query)
        attempt = 0

        while True:
            try:
                status, headers, body = self._transport(request, self._settings.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt < self._settings.max_retries:
                    time.sleep(backoff_seconds(attempt))
                    attempt += 1
                    continue
                raise

            usage = read_usage(headers)
            if usage:
                self.last_usage = usage

            if 200 <= status < 300:
                return parse(body)

            wait = wait_before_retry(self._settings, attempt, status, headers)
            if wait is not None:
                time.sleep(wait)
                attempt += 1
                continue

            raise ApiSkinsError(status, error_message(status, body), retry_after(headers))

    def _one(self, route: str, market_hash_name: str, providers: Optional[Iterable[str]]) -> Any:
        try:
            return self._request(item_path(route, market_hash_name), provider_query(providers))
        except ApiSkinsError as error:
            if error.status == 404:
                return None
            raise

    def _many(self, route: str, market_hash_names: Optional[Iterable[str]], providers: Optional[Iterable[str]]) -> List[Any]:
        base = provider_query(providers)
        if market_hash_names is None:
            return self._request(f"/v1/{route}", base)

        results: List[Any] = []
        for batch in batches(market_hash_names):
            results.extend(self._request(f"/v1/{route}", base + [("market_hash_name", name) for name in batch]))
        return results


class _Offers:
    def __init__(self, client: ApiSkins) -> None:
        self._client = client

    def get(self, market_hash_name: str, providers: Optional[Iterable[str]] = None) -> Optional[ItemOffers]:
        """One item's cheapest offer on every marketplace. None when no marketplace lists it."""
        return self._client._one("offers", market_hash_name, providers)

    def list(self, market_hash_names: Optional[Iterable[str]] = None, providers: Optional[Iterable[str]] = None) -> List[ItemOffers]:
        """Many items' offers: those named (100 per request, split for you), or every listed item when left out."""
        return self._client._many("offers", market_hash_names, providers)


class _Orders:
    def __init__(self, client: ApiSkins) -> None:
        self._client = client

    def get(self, market_hash_name: str, providers: Optional[Iterable[str]] = None) -> Optional[ItemOrders]:
        """One item's highest buy order on every marketplace. None when none has one."""
        return self._client._one("orders", market_hash_name, providers)

    def list(self, market_hash_names: Optional[Iterable[str]] = None, providers: Optional[Iterable[str]] = None) -> List[ItemOrders]:
        """Many items' buy orders: those named (100 per request, split for you), or every item with one when left out."""
        return self._client._many("orders", market_hash_names, providers)
