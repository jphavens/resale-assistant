"""eBay Taxonomy API client.

Built strictly against docs/ebay/commerce_taxonomy_v1_oas3.json (info.version
v1.1.1, pulled 2026-07-07) — paths, params, and response shapes below match
that contract, not general docs or memory. Re-check docs/ebay/VERSIONS.md
before assuming a shape here is still current.

Responses are cached in SQLite (7-day TTL) since category trees and aspect
lists change rarely and this call is the one that must never be skipped —
this is the core correctness guarantee of the project (PLAN_v2.md).
"""
from __future__ import annotations

import sqlite3

import httpx

from ebay_client.auth import EbayAuthClient
from ebay_client.cache import get_cached, set_cached
from ebay_client.exceptions import EbayApiError

BASE_URL = "https://api.ebay.com/commerce/taxonomy/v1"


class TaxonomyClient:
    def __init__(self, auth: EbayAuthClient, conn: sqlite3.Connection, http_client: httpx.Client | None = None):
        self._auth = auth
        self._conn = conn
        self._http = http_client or httpx.Client(timeout=30.0)

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = self._http.get(
            f"{BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self._auth.get_token()}"},
        )
        if response.status_code != 200:
            raise EbayApiError(
                f"Taxonomy API call to {path} failed",
                status_code=response.status_code,
                body=response.text,
            )
        return response.json()

    def get_default_category_tree_id(self, marketplace_id: str) -> str:
        """GET /get_default_category_tree_id -> BaseCategoryTree.categoryTreeId"""
        cache_key = f"default_category_tree_id:{marketplace_id}"
        cached = get_cached(self._conn, cache_key)
        if cached is not None:
            return cached["categoryTreeId"]

        data = self._get("/get_default_category_tree_id", {"marketplace_id": marketplace_id})
        set_cached(self._conn, cache_key, data)
        return data["categoryTreeId"]

    def get_category_suggestions(self, category_tree_id: str, query: str) -> dict:
        """GET /category_tree/{category_tree_id}/get_category_suggestions -> CategorySuggestionResponse"""
        cache_key = f"category_suggestions:{category_tree_id}:{query}"
        cached = get_cached(self._conn, cache_key)
        if cached is not None:
            return cached

        data = self._get(
            f"/category_tree/{category_tree_id}/get_category_suggestions",
            {"q": query},
        )
        set_cached(self._conn, cache_key, data)
        return data

    def get_item_aspects_for_category(self, category_tree_id: str, category_id: str) -> dict:
        """GET /category_tree/{category_tree_id}/get_item_aspects_for_category -> AspectMetadata"""
        cache_key = f"item_aspects:{category_tree_id}:{category_id}"
        cached = get_cached(self._conn, cache_key)
        if cached is not None:
            return cached

        data = self._get(
            f"/category_tree/{category_tree_id}/get_item_aspects_for_category",
            {"category_id": category_id},
        )
        set_cached(self._conn, cache_key, data)
        return data
