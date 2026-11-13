"""Where is an item cheapest right now?

APISKINS_API_KEY=... python examples/cheapest_marketplace.py "AK-47 | Redline (Field-Tested)"
"""

import os
import sys

from cs2_price_api import ApiSkins, lowest_offer

api = ApiSkins(api_key=os.environ["APISKINS_API_KEY"])
name = sys.argv[1] if len(sys.argv) > 1 else "AK-47 | Redline (Field-Tested)"

item = api.offers.get(name)

if item is None:
    print(f"No marketplace lists {name}")
else:
    for offer in sorted(item["offers"], key=lambda offer: offer["price"]):
        print(f"{offer['provider']:<14} ${offer['price']:.2f}")

    cheapest = lowest_offer(item)
    print(f"\nCheapest: {cheapest['provider']} at ${cheapest['price']:.2f}")
