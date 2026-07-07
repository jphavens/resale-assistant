import json
from pathlib import Path

import pytest

from ebay_client.exceptions import EbayItemUnavailableError
from pipeline.groundtruth import (
    build_expected_json,
    find_item_folders,
    flatten_expected,
    generate_groundtruth,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "browse_item_sample.json").read_text())


def test_flatten_expected_extracts_captured_fields():
    result = flatten_expected(FIXTURE)
    assert result["itemId"] == "v1|123456789012|0"
    assert result["categoryId"] == "11483"
    assert result["categoryPath"] == "Clothing, Shoes & Accessories|Men|Men's Clothing|Jeans"
    assert result["aspects"]["Brand"] == "Levi's"
    assert result["aspects"]["Size"] == "34x32"
    assert result["aspects"]["Size Type"] == "Regular"
    assert len(result["aspects"]) == 7


def test_flatten_expected_ignores_non_captured_top_level_fields():
    result = flatten_expected(FIXTURE)
    assert "condition" not in result
    assert "itemEndDate" not in result


def test_build_expected_json_with_no_existing_file():
    result = build_expected_json(FIXTURE, existing=None)
    assert "measurements" not in result
    assert "package" not in result
    assert "known_flaws" not in result


def test_build_expected_json_preserves_manual_keys():
    existing = {
        "measurements": {"pit_to_pit": "21 in"},
        "package": {"weight_oz": 18.5, "l": 12, "w": 9, "h": 3},
        "known_flaws": ["small stain on left cuff"],
        "categoryId": "stale-value-should-be-overwritten",
    }
    result = build_expected_json(FIXTURE, existing=existing)
    assert result["measurements"] == {"pit_to_pit": "21 in"}
    assert result["package"]["weight_oz"] == 18.5
    assert result["known_flaws"] == ["small stain on left cuff"]
    # Non-manual keys are always refreshed from the live fetch, never held over.
    assert result["categoryId"] == "11483"


def test_find_item_folders_only_returns_folders_with_item_id_txt(tmp_path: Path):
    (tmp_path / "item-a").mkdir()
    (tmp_path / "item-a" / "item_id.txt").write_text("v1|1|0\n")
    (tmp_path / "item-b").mkdir()  # no item_id.txt
    (tmp_path / "not-a-folder.txt").write_text("stray file")

    folders = find_item_folders(tmp_path)
    assert [f.name for f in folders] == ["item-a"]


class _FakeBrowseClient:
    def __init__(self, items: dict[str, dict], unavailable: set[str] = frozenset()):
        self._items = items
        self._unavailable = unavailable

    def get_item(self, item_id: str) -> dict:
        if item_id in self._unavailable:
            raise EbayItemUnavailableError(item_id, f"ended listing: {item_id}", status_code=404)
        return self._items[item_id]


def test_generate_groundtruth_writes_expected_json(tmp_path: Path):
    item_dir = tmp_path / "item-1"
    item_dir.mkdir()
    (item_dir / "item_id.txt").write_text("v1|123456789012|0\n")

    client = _FakeBrowseClient({"v1|123456789012|0": FIXTURE})
    succeeded, failed = generate_groundtruth(tmp_path, client)

    assert succeeded == ["item-1"]
    assert failed == []
    written = json.loads((item_dir / "expected.json").read_text())
    assert written["itemId"] == "v1|123456789012|0"


def test_generate_groundtruth_fails_loudly_with_item_id_on_ended_listing(tmp_path: Path):
    item_dir = tmp_path / "item-ended"
    item_dir.mkdir()
    (item_dir / "item_id.txt").write_text("v1|999|0\n")

    client = _FakeBrowseClient({}, unavailable={"v1|999|0"})
    succeeded, failed = generate_groundtruth(tmp_path, client)

    assert succeeded == []
    assert len(failed) == 1
    folder_name, message = failed[0]
    assert folder_name == "item-ended"
    assert "v1|999|0" in message
    assert not (item_dir / "expected.json").exists()


def test_generate_groundtruth_preserves_manual_keys_on_regeneration(tmp_path: Path):
    item_dir = tmp_path / "item-1"
    item_dir.mkdir()
    (item_dir / "item_id.txt").write_text("v1|123456789012|0\n")
    (item_dir / "expected.json").write_text(json.dumps({
        "itemId": "stale",
        "known_flaws": ["small stain"],
    }))

    client = _FakeBrowseClient({"v1|123456789012|0": FIXTURE})
    generate_groundtruth(tmp_path, client)

    written = json.loads((item_dir / "expected.json").read_text())
    assert written["itemId"] == "v1|123456789012|0"  # refreshed, not "stale"
    assert written["known_flaws"] == ["small stain"]  # preserved
