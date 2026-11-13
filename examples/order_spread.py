"""For a few items: the cheapest listing anywhere against the best buy order, and the gap between them.

APISKINS_API_KEY=... python examples/order_spread.py
"""

import os

from cs2_price_api import ApiSkins, highest_order, lowest_offer

api = ApiSkins(api_key=os.environ["APISKINS_API_KEY"])

names = [
    "AK-47 | Redline (Field-Tested)",
    "AWP | Asiimov (Field-Tested)",
    "M4A1-S | Printstream (Minimal Wear)",
    "Glock-18 | Fade (Factory New)",
]

offers = api.offers.list(names)
orders = {item["market_hash_name"]: item for item in api.orders.list(names)}

for item in offers:
    offer = lowest_offer(item)
    order = highest_order(orders.get(item["market_hash_name"]))

    if offer is None or order is None:
        continue

    gap = (offer["price"] - order["price"]) / offer["price"] * 100
    print(f"{item['market_hash_name']}\n  listing ${offer['price']:.2f} on {offer['provider']}, order ${order['price']:.2f} on {order['provider']}, gap {gap:.1f}%")

print(f"\nRequests left this period: {api.last_usage.remaining if api.last_usage else '?'}")
