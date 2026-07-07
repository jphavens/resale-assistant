from db.connection import connect
from ebay_client.cache import get_cached, set_cached
from ebay_client.taxonomy import TaxonomyClient


def test_get_cached_returns_none_when_missing():
    conn = connect(":memory:")
    assert get_cached(conn, "missing-key") is None


def test_set_then_get_cached_round_trips():
    conn = connect(":memory:")
    set_cached(conn, "key1", {"categoryTreeId": "0"})
    assert get_cached(conn, "key1") == {"categoryTreeId": "0"}


def test_set_cached_overwrites_existing_key():
    conn = connect(":memory:")
    set_cached(conn, "key1", {"v": 1})
    set_cached(conn, "key1", {"v": 2})
    assert get_cached(conn, "key1") == {"v": 2}


def test_get_cached_expired_entry_returns_none():
    import datetime
    conn = connect(":memory:")
    stale = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)).isoformat()
    conn.execute(
        "INSERT INTO taxonomy_cache (cache_key, response_json, fetched_at) VALUES (?, ?, ?)",
        ("stale-key", '{"a": 1}', stale),
    )
    conn.commit()
    assert get_cached(conn, "stale-key") is None


class _FakeAuth:
    def get_token(self) -> str:
        return "fake-token"


class _FakeHttpResponse:
    def __init__(self, json_data):
        self._json = json_data
        self.status_code = 200
        self.text = ""

    def json(self):
        return self._json


class _FakeHttpClient:
    def __init__(self, response_json):
        self._response_json = response_json
        self.get_call_count = 0

    def get(self, url, params=None, headers=None):
        self.get_call_count += 1
        return _FakeHttpResponse(self._response_json)


def test_taxonomy_client_caches_get_default_category_tree_id():
    conn = connect(":memory:")
    fake_http = _FakeHttpClient({"categoryTreeId": "0", "categoryTreeVersion": "1"})
    client = TaxonomyClient(_FakeAuth(), conn, http_client=fake_http)

    first = client.get_default_category_tree_id("EBAY_US")
    second = client.get_default_category_tree_id("EBAY_US")

    assert first == "0"
    assert second == "0"
    assert fake_http.get_call_count == 1  # second call served from cache


def test_taxonomy_client_caches_item_aspects_for_category():
    conn = connect(":memory:")
    fake_http = _FakeHttpClient({"aspects": [{"localizedAspectName": "Brand"}]})
    client = TaxonomyClient(_FakeAuth(), conn, http_client=fake_http)

    client.get_item_aspects_for_category("0", "11483")
    client.get_item_aspects_for_category("0", "11483")

    assert fake_http.get_call_count == 1


def test_taxonomy_client_different_category_ids_not_cached_together():
    conn = connect(":memory:")
    fake_http = _FakeHttpClient({"aspects": []})
    client = TaxonomyClient(_FakeAuth(), conn, http_client=fake_http)

    client.get_item_aspects_for_category("0", "11483")
    client.get_item_aspects_for_category("0", "63861")

    assert fake_http.get_call_count == 2
