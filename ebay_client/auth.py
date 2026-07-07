"""eBay OAuth client-credentials grant (production, app-token only).

No user OAuth anywhere in Phase 1 — this mints an application access token
for the Taxonomy and Browse read-only APIs. Never log the token or the
client secret.
"""
from __future__ import annotations

import base64
import time

import httpx

from ebay_client.exceptions import EbayApiError

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
DEFAULT_SCOPE = "https://api.ebay.com/oauth/api_scope"

# Re-mint this many seconds before actual expiry to avoid racing a request
# against a token that expires mid-flight.
EXPIRY_SAFETY_MARGIN_SECONDS = 60


class EbayAuthClient:
    def __init__(self, client_id: str, client_secret: str, scope: str = DEFAULT_SCOPE, http_client: httpx.Client | None = None):
        if not client_id or not client_secret:
            raise ValueError("EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must both be set")
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._http = http_client or httpx.Client(timeout=30.0)
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        return self._mint_token()

    def _mint_token(self) -> str:
        credentials = f"{self._client_id}:{self._client_secret}"
        basic = base64.b64encode(credentials.encode()).decode()
        response = self._http.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": self._scope},
        )
        if response.status_code != 200:
            raise EbayApiError(
                "Failed to mint eBay OAuth token",
                status_code=response.status_code,
                body=response.text,
            )
        payload = response.json()
        self._token = payload["access_token"]
        expires_in = payload.get("expires_in", 7200)
        self._expires_at = time.monotonic() + expires_in - EXPIRY_SAFETY_MARGIN_SECONDS
        return self._token
