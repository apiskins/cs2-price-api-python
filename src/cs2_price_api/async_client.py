"""The async client, on httpx: pip install "cs2-price-api[async]"."""

import asyncio
from typing import Any, Iterable, List, Optional, Tuple

from ._core import (
    ApiSkinsError,
    ItemOffers,
    ItemOrders,
    Settings,
    Usage,
    backoff_seconds,
    batches,
    error_message,
    item_path,
    parse,
    provider_query,
    read_usage,
    retry_after,
    wait_before_retry,
)

try:
    import httpx
except ImportError as error:  # pragma: no cover
    raise ImportError('The async client needs httpx: pip install "cs2-price-api[async]"') from error


class AsyncApiSkins:
    """The async API Skins client. Use it as an async context manager, or call ``aclose()``.

    >>> async with AsyncApiSkins(api_key=os.environ["APISKINS_API_KEY"]) as api:
    ...     await api.offers.get("AK-47 | Redline (Field-Tested)")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        max_retries: int = 2,
        max_retry_wait_seconds: float = 60,
        timeout: float = 120,
        http_client: Optional["httpx.AsyncClient"] = None,
    ) -> None:
        self._settings = Settings.make(api_key, base_url, max_retries, max_retry_wait_seconds, timeout)
        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_http = http_client is None
        #: Usage left this 30-day period, as of the last answer. None before the first request.
        self.last_usage: Optional[Usage] = None
        self.offers = _AsyncOffers(self)
        self.orders = _AsyncOrders(self)

    async def __aenter__(self) -> "AsyncApiSkins":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _request(self, path: str, query: List[Tuple[str, str]]) -> Any:
        request = self._settings.request(path, query)
        attempt = 0

        while True:
            try:
                response = await self._http.get(request.url, headers=request.headers)
            except httpx.TransportError:
                if attempt < self._settings.max_retries:
                    await asyncio.sleep(backoff_seconds(attempt))
                    attempt += 1
                    continue
                raise

            headers = {key.lower(): value for key, value in response.headers.items()}
            usage = read_usage(headers)
            if usage:
                self.last_usage = usage

            if 200 <= response.status_code < 300:
                return parse(response.content)

            wait = wait_before_retry(self._settings, attempt, response.status_code, headers)
            if wait is not None:
                await asyncio.sleep(wait)
                attempt += 1
                continue

            raise ApiSkinsError(response.status_code, error_message(response.status_code, response.content), retry_after(headers))

    async def _one(self, route: str, market_hash_name: str, providers: Optional[Iterable[str]]) -> Any:
        try:
            return await self._request(item_path(route, market_hash_name), provider_query(providers))
        except ApiSkinsError as error:
            if error.status == 404:
                return None
            raise

    async def _many(self, route: str, market_hash_names: Optional[Iterable[str]], providers: Optional[Iterable[str]]) -> List[Any]:
        base = provider_query(providers)
        if market_hash_names is None:
            return await self._request(f"/v1/{route}", base)

        results: List[Any] = []
        for batch in batches(market_hash_names):
            results.extend(await self._request(f"/v1/{route}", base + [("market_hash_name", name) for name in batch]))
        return results


class _AsyncOffers:
    def __init__(self, client: AsyncApiSkins) -> None:
        self._client = client

    async def get(self, market_hash_name: str, providers: Optional[Iterable[str]] = None) -> Optional[ItemOffers]:
        """One item's cheapest offer on every marketplace. None when no marketplace lists it."""
        return await self._client._one("offers", market_hash_name, providers)

    async def list(self, market_hash_names: Optional[Iterable[str]] = None, providers: Optional[Iterable[str]] = None) -> List[ItemOffers]:
        """Many items' offers: those named (100 per request, split for you), or every listed item when left out."""
        return await self._client._many("offers", market_hash_names, providers)


class _AsyncOrders:
    def __init__(self, client: AsyncApiSkins) -> None:
        self._client = client

    async def get(self, market_hash_name: str, providers: Optional[Iterable[str]] = None) -> Optional[ItemOrders]:
        """One item's highest buy order on every marketplace. None when none has one."""
        return await self._client._one("orders", market_hash_name, providers)

    async def list(self, market_hash_names: Optional[Iterable[str]] = None, providers: Optional[Iterable[str]] = None) -> List[ItemOrders]:
        """Many items' buy orders: those named (100 per request, split for you), or every item with one when left out."""
        return await self._client._many("orders", market_hash_names, providers)
