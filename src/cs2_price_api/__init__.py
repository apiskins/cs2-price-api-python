"""Official client for the API Skins CS2 price API: cheapest offers across marketplaces and buy orders.

    from cs2_price_api import ApiSkins

    api = ApiSkins(api_key="...")
    api.offers.get("AK-47 | Redline (Field-Tested)")

The async client, ``AsyncApiSkins``, needs httpx: ``pip install "cs2-price-api[async]"``.
"""

from typing import Any

from ._core import (
    BATCH_SIZE,
    ApiSkinsError,
    ItemOffers,
    ItemOrders,
    Offer,
    Order,
    Usage,
    __version__,
    highest_order,
    lowest_offer,
)
from .client import ApiSkins
from .providers import OFFER_PROVIDERS, ORDER_PROVIDERS, OfferProvider, OrderProvider

__all__ = [
    "ApiSkins",
    "AsyncApiSkins",
    "ApiSkinsError",
    "BATCH_SIZE",
    "ItemOffers",
    "ItemOrders",
    "Offer",
    "Order",
    "OFFER_PROVIDERS",
    "ORDER_PROVIDERS",
    "OfferProvider",
    "OrderProvider",
    "Usage",
    "__version__",
    "highest_order",
    "lowest_offer",
]


def __getattr__(name: str) -> Any:
    # imported on first use, so the sync client works without httpx
    if name == "AsyncApiSkins":
        from .async_client import AsyncApiSkins

        return AsyncApiSkins
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
