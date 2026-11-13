"""The marketplaces the API answers for, by their ids."""

from typing import Literal, Tuple

OfferProvider = Literal[
    "cs_float",
    "buff_163",
    "youpin",
    "dmarket",
    "skinport",
    "cs_money",
    "market_csgo",
    "buff_market",
    "waxpeer",
    "lis_skins",
    "skin_baron",
    "halo_skins",
    "white_market",
    "shadow_pay",
    "skins",
    "skin_swap",
    "cs_deals",
    "loot_farm",
    "cs_trade",
    "tradeit",
    "steam",
    "sih",
]

OrderProvider = Literal["dmarket", "market_csgo", "steam"]

#: Every marketplace the offer methods answer for.
OFFER_PROVIDERS: Tuple[str, ...] = (
    "cs_float",
    "buff_163",
    "youpin",
    "dmarket",
    "skinport",
    "cs_money",
    "market_csgo",
    "buff_market",
    "waxpeer",
    "lis_skins",
    "skin_baron",
    "halo_skins",
    "white_market",
    "shadow_pay",
    "skins",
    "skin_swap",
    "cs_deals",
    "loot_farm",
    "cs_trade",
    "tradeit",
    "steam",
    "sih",
)

#: Every marketplace the order methods answer for.
ORDER_PROVIDERS: Tuple[str, ...] = ("dmarket", "market_csgo", "steam")
