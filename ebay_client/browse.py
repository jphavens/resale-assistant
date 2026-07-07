"""eBay Browse API client — M0 groundtruth fetching ONLY, never used in the
listing pipeline (PLAN_v2.md hard constraint #1).

Built strictly against docs/ebay/buy_browse_v1_oas3.json (info.version
v1.20.4, pulled 2026-07-07). The Browse API only returns ACTIVE listings —
an ended listing surfaces as a non-200 response, which we convert to
EbayItemUnavailableError so the harness fails loudly with the item ID
instead of silently skipping it.
"""
from __future__ import annotations

from urllib.parse import quote

import httpx

from ebay_client.auth import EbayAuthClient
from ebay_client.exceptions import EbayItemUnavailableError

BASE_URL = "https://api.ebay.com/buy/browse/v1"


class BrowseClient:
    def __init__(self, auth: EbayAuthClient, marketplace_id: str = "EBAY_US", http_client: httpx.Client | None = None):
        self._auth = auth
        self._marketplace_id = marketplace_id
        self._http = http_client or httpx.Client(timeout=30.0)

    def get_item(self, item_id: str) -> dict:
        """GET /item/{item_id} -> Item.

        Returns the raw Item payload. Raises EbayItemUnavailableError (with
        item_id attached) on any non-200 response, e.g. an ended listing.
        """
        encoded_id = quote(item_id, safe="")
        response = self._http.get(
            f"{BASE_URL}/item/{encoded_id}",
            headers={
                "Authorization": f"Bearer {self._auth.get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            },
        )
        if response.status_code != 200:
            message = f"Browse getItem failed for item_id={item_id}"
            try:
                errors = response.json().get("errors", [])
                if errors:
                    message += f": {errors[0].get('message', '')}"
            except ValueError:
                pass
            raise EbayItemUnavailableError(
                item_id=item_id,
                message=message,
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    @staticmethod
    def extract_aspects(item: dict) -> dict[str, str]:
        """Flatten Item.localizedAspects (TypedNameValue[]) into a name->value map."""
        return {
            aspect["name"]: aspect["value"]
            for aspect in item.get("localizedAspects", [])
            if "name" in aspect and "value" in aspect
        }
