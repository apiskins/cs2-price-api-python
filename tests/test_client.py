"""Tests against a stand-in transport, plus live ones (a wrong key; real prices when APISKINS_API_KEY is set)."""

import asyncio
import json
import os
import unittest
from urllib.parse import parse_qs, urlparse

from cs2_price_api import ApiSkins, ApiSkinsError, Usage, highest_order, lowest_offer

REDLINE = "AK-47 | Redline (Field-Tested)"


def stand_in(*answers):
    """A transport answering in turn; an answer may be a function of the URL."""
    calls = []
    queue = list(answers)

    def transport(request, timeout):
        calls.append(request)
        answer = queue.pop(0)
        if callable(answer):
            answer = answer(request.url)
        headers = {key.lower(): value for key, value in answer.get("headers", {}).items()}
        return answer.get("status", 200), headers, json.dumps(answer.get("body", {})).encode()

    return transport, calls


def query(url):
    return parse_qs(urlparse(url).query)


class ClientTest(unittest.TestCase):
    def test_needs_a_key(self):
        with self.assertRaisesRegex(ValueError, "api_key is required"):
            ApiSkins(api_key="")

    def test_get_sends_the_key_encodes_the_name_and_passes_providers(self):
        transport, calls = stand_in({"body": {"market_hash_name": REDLINE, "offers": [{"provider": "cs_float", "price": 33.1}]}, "headers": {"X-Usage-Limit": "1000", "X-Usage-Remaining": "999"}})
        api = ApiSkins(api_key="k", transport=transport)
        item = api.offers.get(REDLINE, providers=["cs_float", "buff_163"])

        self.assertEqual(item["offers"][0]["price"], 33.1)
        self.assertEqual(calls[0].headers["X-API-KEY"], "k")
        self.assertEqual(urlparse(calls[0].url).path, "/v1/offers/AK-47%20%7C%20Redline%20%28Field-Tested%29")
        self.assertEqual(query(calls[0].url)["providers"], ["cs_float,buff_163"])
        self.assertEqual(api.last_usage, Usage(limit=1000, remaining=999))

    def test_get_answers_none_on_404(self):
        transport, _ = stand_in({"status": 404, "body": {"error": "No such item"}})
        self.assertIsNone(ApiSkins(api_key="k", transport=transport).orders.get("Nope"))

    def test_list_splits_more_than_100_names_and_drops_repeats(self):
        names = [f"Item {i}" for i in range(250)]
        answer = lambda url: {"body": [{"market_hash_name": name, "orders": []} for name in query(url)["market_hash_name"]]}
        transport, calls = stand_in(answer, answer, answer)
        items = ApiSkins(api_key="k", transport=transport).orders.list(names + ["Item 0"])

        self.assertEqual([len(query(call.url)["market_hash_name"]) for call in calls], [100, 100, 50])
        self.assertEqual(len(items), 250)

    def test_list_without_names_asks_for_every_item_once(self):
        transport, calls = stand_in({"body": []})
        ApiSkins(api_key="k", transport=transport).offers.list()
        self.assertEqual(len(calls), 1)
        self.assertEqual(urlparse(calls[0].url).query, "")

    def test_waits_out_a_short_429(self):
        transport, calls = stand_in({"status": 429, "body": {"error": "slow down"}, "headers": {"Retry-After": "0"}}, {"body": []})
        ApiSkins(api_key="k", transport=transport).offers.list([REDLINE])
        self.assertEqual(len(calls), 2)

    def test_raises_a_429_asking_for_a_long_wait(self):
        transport, calls = stand_in({"status": 429, "body": {"error": "Limit reached"}, "headers": {"Retry-After": "86400"}})
        with self.assertRaises(ApiSkinsError) as caught:
            ApiSkins(api_key="k", transport=transport).offers.list([REDLINE])
        self.assertEqual((caught.exception.status, caught.exception.retry_after, str(caught.exception)), (429, 86400, "Limit reached"))
        self.assertEqual(len(calls), 1)

    def test_raises_the_api_error_message(self):
        transport, _ = stand_in({"status": 403, "body": {"error": "A paid subscription is needed"}})
        with self.assertRaises(ApiSkinsError) as caught:
            ApiSkins(api_key="k", transport=transport).offers.get(REDLINE, providers=["buff_163"])
        self.assertEqual((caught.exception.status, caught.exception.message), (403, "A paid subscription is needed"))

    def test_lowest_offer_and_highest_order(self):
        self.assertEqual(lowest_offer({"market_hash_name": REDLINE, "offers": [{"provider": "steam", "price": 40}, {"provider": "buff_163", "price": 31}]}), {"provider": "buff_163", "price": 31})
        self.assertEqual(highest_order({"market_hash_name": REDLINE, "orders": [{"provider": "steam", "price": 30}, {"provider": "dmarket", "price": 24}]}), {"provider": "steam", "price": 30})
        self.assertIsNone(lowest_offer(None))


try:
    import httpx
except ImportError:
    httpx = None


@unittest.skipIf(httpx is None, "httpx not installed")
class AsyncClientTest(unittest.TestCase):
    def test_get_and_batched_list(self):
        from cs2_price_api import AsyncApiSkins

        seen = []

        def handler(request):
            seen.append(request)
            names = request.url.params.get_list("market_hash_name")
            if names:
                return httpx.Response(200, json=[{"market_hash_name": name, "offers": []} for name in names])
            return httpx.Response(200, json={"market_hash_name": REDLINE, "offers": [{"provider": "steam", "price": 40}]}, headers={"X-Usage-Limit": "100", "X-Usage-Remaining": "98"})

        async def run():
            async with AsyncApiSkins(api_key="k", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as api:
                item = await api.offers.get(REDLINE)
                items = await api.offers.list([f"Item {i}" for i in range(150)])
                return api, item, items

        api, item, items = asyncio.run(run())
        self.assertEqual(item["offers"][0]["price"], 40)
        self.assertEqual(len(items), 150)
        self.assertEqual(len(seen), 3)
        self.assertEqual(seen[0].headers["x-api-key"], "k")
        self.assertEqual(api.last_usage, Usage(limit=100, remaining=98))


class LiveTest(unittest.TestCase):
    def test_a_wrong_key_is_refused(self):
        with self.assertRaises(ApiSkinsError) as caught:
            ApiSkins(api_key="wrong-key").offers.get(REDLINE)
        self.assertEqual(caught.exception.status, 401)

    @unittest.skipUnless(os.environ.get("APISKINS_API_KEY"), "set APISKINS_API_KEY to run")
    def test_steam_offers_and_orders(self):
        api = ApiSkins(api_key=os.environ["APISKINS_API_KEY"])
        offers = api.offers.get(REDLINE, providers=["steam"])
        orders = api.orders.get(REDLINE, providers=["steam"])

        self.assertEqual(offers["market_hash_name"], REDLINE)
        self.assertTrue(all(offer["provider"] == "steam" and offer["price"] > 0 for offer in offers["offers"]))
        self.assertTrue(all(order["provider"] == "steam" and order["price"] > 0 for order in orders["orders"]))
        self.assertGreater(api.last_usage.limit, 0)


if __name__ == "__main__":
    unittest.main()
