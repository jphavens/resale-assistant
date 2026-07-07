"""Exceptions for eBay API clients."""


class EbayApiError(Exception):
    """Raised for any non-2xx response from an eBay API."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class EbayItemUnavailableError(EbayApiError):
    """Raised by the Browse API groundtruth fetcher when an item can't be
    retrieved — ended listings, bad item IDs, etc. Carries the item_id so the
    caller can fail loudly with a specific reference.
    """

    def __init__(self, item_id: str, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message, status_code=status_code, body=body)
        self.item_id = item_id
