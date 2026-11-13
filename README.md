# cs2-price-api

The official Python client for the [API Skins](https://apiskins.com) CS2 price API:

- **Offers**: every CS2 item's cheapest listing on each marketplace
- **Buy orders**: every item's highest buy order on each marketplace that has them

Typed, no dependencies (httpx only for the async client), Python 3.10+.

```sh
pip install cs2-price-api
```

## Quick start

Sign in with Steam on [apiskins.com](https://apiskins.com) and copy your key from the [API docs page](https://apiskins.com/api-docs) (the free plan works).

```python
import os
from cs2_price_api import ApiSkins, lowest_offer

api = ApiSkins(api_key=os.environ["APISKINS_API_KEY"])

item = api.offers.get("AK-47 | Redline (Field-Tested)")
# {"market_hash_name": "AK-47 | Redline (Field-Tested)", "offers": [{"provider": "buff_163", "price": 31.42}, ...]}

print(lowest_offer(item))  # {"provider": "buff_163", "price": 31.42}
```

Prices are in USD. Item names are Steam's `market_hash_name`.

## Offers

```python
# one item, every marketplace (None when nothing lists it)
api.offers.get("AWP | Asiimov (Field-Tested)")

# only some marketplaces
api.offers.get("AWP | Asiimov (Field-Tested)", providers=["cs_float", "skinport"])

# many items: 100 per request, longer lists are split for you
api.offers.list(["AWP | Asiimov (Field-Tested)", "★ Karambit | Doppler (Factory New)"])

# every listed item in one answer
api.offers.list()
```

## Buy orders

```python
api.orders.get("AK-47 | Redline (Field-Tested)")
# {"market_hash_name": "...", "orders": [{"provider": "dmarket", "price": 24.51}, {"provider": "steam", "price": 26.1}]}

api.orders.list([...], providers=["dmarket", "market_csgo"])
api.orders.list()  # every item with a buy order
```

`highest_order(item)` picks the best one.

## Async

```sh
pip install "cs2-price-api[async]"
```

```python
import asyncio
from cs2_price_api import AsyncApiSkins

async def main():
    async with AsyncApiSkins(api_key="...") as api:
        offers, orders = await asyncio.gather(
            api.offers.get("AK-47 | Redline (Field-Tested)"),
            api.orders.get("AK-47 | Redline (Field-Tested)"),
        )

asyncio.run(main())
```

## Marketplaces

`OFFER_PROVIDERS` and `ORDER_PROVIDERS` list the ids: `cs_float`, `buff_163`, `youpin`, `dmarket`, `skinport`, `cs_money`, `market_csgo`, `buff_market`, `waxpeer`, `lis_skins`, `skin_baron`, `halo_skins`, `white_market`, `shadow_pay`, `skins`, `skin_swap`, `cs_deals`, `loot_farm`, `cs_trade`, `tradeit`, `steam`, `sih`.

## Plans

The **free plan answers Steam's prices and buy orders**, 100 requests per 30 days. Every other marketplace, and higher limits, need a paid plan ([pricing](https://apiskins.com/pricing)). Asking for a marketplace your plan lacks raises a 403.

Each answer carries what is left of your 30-day limit:

```python
api.offers.get("AK-47 | Redline (Field-Tested)")
print(api.last_usage)  # Usage(limit=100, remaining=99) on the free plan
```

## Errors and limits

Errors raise `ApiSkinsError` with the API's `status` and message:

```python
from cs2_price_api import ApiSkinsError

try:
    api.offers.list()
except ApiSkinsError as error:
    if error.status == 403:
        print("Upgrade needed:", error.message)
```

A short rate limit (429 with a `Retry-After` up to 60 seconds) and server errors are retried for you, twice by default. The 30-day limit is raised at once.

```python
ApiSkins(
    api_key="...",
    max_retries=2,              # 0 turns retrying off
    max_retry_wait_seconds=60,  # longest Retry-After worth waiting for
    timeout=120,
)
```

## Examples

- [examples/cheapest_marketplace.py](examples/cheapest_marketplace.py): where an item is cheapest right now
- [examples/order_spread.py](examples/order_spread.py): the cheapest listing against the best buy order

## Links

- [API docs](https://apiskins.com/api-docs)
- [Price API](https://apiskins.com/price-api) and [buy order API](https://apiskins.com/buy-order-api)
- [Skin prices across marketplaces](https://apiskins.com/prices)
- [JavaScript / TypeScript client](https://github.com/apiskins/cs2-price-api)

## License

MIT
