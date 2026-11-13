"""What the sync and async clients share: the types, building requests and reading answers."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, TypedDict, Union
from urllib.parse import quote, urlencode

__version__ = "1.0.0"

DEFAULT_BASE_URL = "https://api.apiskins.com"
USER_AGENT = f"cs2-price-api-python/{__version__}"

#: How many names one request takes; longer lists are split into several requests.
BATCH_SIZE = 100

KEY_HELP = "sign in at https://apiskins.com and copy it from https://apiskins.com/api-docs"


class Offer(TypedDict):
    """One marketplace's cheapest listing of an item, in USD."""

    provider: str
    price: float


class Order(TypedDict):
    """One marketplace's highest buy order for an item, in USD."""

    provider: str
    price: float


class ItemOffers(TypedDict):
    """An item's cheapest offer on every marketplace that lists it."""

    market_hash_name: str
    offers: List[Offer]


class ItemOrders(TypedDict):
    """An item's highest buy order on every marketplace that has one."""

    market_hash_name: str
    orders: List[Order]


@dataclass(frozen=True)
class Usage:
    """What the subscription allows per 30 days, from the last answer's headers."""

    limit: int
    remaining: int


class ApiSkinsError(Exception):
    """The API answered with an error: 400, 401, 403, 404, 409, 429 or a server error."""

    def __init__(self, status: int, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        #: Seconds the API asked to wait, on a 429.
        self.retry_after = retry_after

    def __repr__(self) -> str:
        return f"ApiSkinsError(status={self.status}, message={self.message!r})"


@dataclass(frozen=True)
class Request:
    url: str
    headers: Dict[str, str]


@dataclass
class Settings:
    api_key: str
    base_url: str
    max_retries: int
    max_retry_wait_seconds: float
    timeout: float

    @staticmethod
    def make(api_key: str, base_url: Optional[str], max_retries: int, max_retry_wait_seconds: float, timeout: float) -> "Settings":
        if not api_key:
            raise ValueError(f"api_key is required: {KEY_HELP}")

        return Settings(
            api_key=api_key,
            base_url=(base_url or DEFAULT_BASE_URL).rstrip("/"),
            max_retries=max_retries,
            max_retry_wait_seconds=max_retry_wait_seconds,
            timeout=timeout,
        )

    def request(self, path: str, query: Sequence[Tuple[str, str]]) -> Request:
        search = urlencode(list(query))
        return Request(
            url=f"{self.base_url}{path}{'?' + search if search else ''}",
            headers={
                "X-API-KEY": self.api_key,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "User-Agent": USER_AGENT,
            },
        )


def provider_query(providers: Optional[Iterable[str]]) -> List[Tuple[str, str]]:
    if providers is None:
        return []
    if isinstance(providers, str):
        providers = [providers]
    joined = ",".join(providers)
    return [("providers", joined)] if joined else []


def item_path(route: str, market_hash_name: str) -> str:
    if not market_hash_name:
        raise ValueError("market_hash_name is required")
    return f"/v1/{route}/{quote(market_hash_name, safe='')}"


def batches(names: Union[str, Iterable[str]]) -> List[List[str]]:
    if isinstance(names, str):
        names = [names]
    unique = list(dict.fromkeys(names))
    return [unique[index:index + BATCH_SIZE] for index in range(0, len(unique), BATCH_SIZE)]


def read_usage(headers: Mapping[str, str]) -> Optional[Usage]:
    limit = headers.get("x-usage-limit")
    remaining = headers.get("x-usage-remaining")
    try:
        return Usage(limit=int(limit), remaining=int(remaining)) if limit is not None and remaining is not None else None
    except ValueError:
        return None


def retry_after(headers: Mapping[str, str]) -> Optional[float]:
    value = headers.get("retry-after")
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def error_message(status: int, body: bytes) -> str:
    text = body.decode("utf-8", "replace")
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("error"), str):
            return parsed["error"]
    except ValueError:
        pass
    return text[:300] or f"HTTP {status}"


def backoff_seconds(attempt: int) -> float:
    return min(2.0 ** attempt, 10.0)


def wait_before_retry(settings: Settings, attempt: int, status: int, headers: Mapping[str, str]) -> Optional[float]:
    """Seconds to wait before trying again, or None to give up and raise."""
    if attempt >= settings.max_retries:
        return None
    if status == 429:
        wait = retry_after(headers)
        return wait if wait is not None and wait <= settings.max_retry_wait_seconds else None
    if status in (502, 503, 504):
        return backoff_seconds(attempt)
    return None


def parse(body: bytes) -> Any:
    return json.loads(body.decode("utf-8"))


def lowest_offer(item: Optional[ItemOffers]) -> Optional[Offer]:
    """The cheapest offer of an item across the marketplaces in the answer, or None."""
    offers = (item or {}).get("offers") or []
    return min(offers, key=lambda offer: offer["price"]) if offers else None


def highest_order(item: Optional[ItemOrders]) -> Optional[Order]:
    """The highest buy order of an item across the marketplaces in the answer, or None."""
    orders = (item or {}).get("orders") or []
    return max(orders, key=lambda order: order["price"]) if orders else None
