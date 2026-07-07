"""`python -m pipeline.groundtruth testdata/`

Reads item_id.txt in each testdata/<item>/ folder and generates expected.json
via the eBay Browse API getItem endpoint (PLAN_v2.md M0). Fails loudly with
the item ID if a listing has ended (Browse API only returns ACTIVE
listings), rather than silently skipping it.

expected.json schema:
    {
      "itemId": str, "title": str, "categoryId": str, "categoryPath": str,
      "aspects": {name: value, ...},
      # optional, hand-added by the maintainer — preserved across regeneration:
      "measurements": {name: value, ...},
      "package": {"weight_oz": number, "l": number, "w": number, "h": number},
      "known_flaws": [str, ...]
    }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ebay_client.auth import EbayAuthClient
from ebay_client.browse import BrowseClient
from ebay_client.exceptions import EbayItemUnavailableError

MANUAL_KEYS = ("measurements", "package", "known_flaws")


def flatten_expected(item: dict) -> dict:
    """Extract the groundtruth-captured field subset from a raw Browse Item payload."""
    return {
        "itemId": item.get("itemId"),
        "title": item.get("title"),
        "categoryId": item.get("categoryId"),
        "categoryPath": item.get("categoryPath"),
        "aspects": BrowseClient.extract_aspects(item),
    }


def build_expected_json(item: dict, existing: dict | None) -> dict:
    """Merge freshly-fetched Browse fields with any hand-added manual keys
    already present in an existing expected.json, so regenerating groundtruth
    never clobbers manual corrections.
    """
    result = flatten_expected(item)
    if existing:
        for key in MANUAL_KEYS:
            if key in existing:
                result[key] = existing[key]
    return result


def find_item_folders(testdata_dir: Path) -> list[Path]:
    return sorted(
        p.parent for p in testdata_dir.glob("*/item_id.txt")
    )


def generate_groundtruth(testdata_dir: Path, browse_client: BrowseClient) -> tuple[list[str], list[tuple[str, str]]]:
    """Returns (succeeded_folder_names, [(folder_name, error_message), ...])."""
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []

    for folder in find_item_folders(testdata_dir):
        item_id = (folder / "item_id.txt").read_text().strip()
        expected_path = folder / "expected.json"
        existing = json.loads(expected_path.read_text()) if expected_path.exists() else None

        try:
            item = browse_client.get_item(item_id)
        except EbayItemUnavailableError as e:
            failed.append((folder.name, str(e)))
            continue

        expected = build_expected_json(item, existing)
        expected_path.write_text(json.dumps(expected, indent=2) + "\n")
        succeeded.append(folder.name)

    return succeeded, failed


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m pipeline.groundtruth <testdata_dir>", file=sys.stderr)
        return 2

    testdata_dir = Path(argv[0])
    if not testdata_dir.is_dir():
        print(f"Not a directory: {testdata_dir}", file=sys.stderr)
        return 2

    load_dotenv()
    auth = EbayAuthClient(os.environ["EBAY_CLIENT_ID"], os.environ["EBAY_CLIENT_SECRET"])
    browse_client = BrowseClient(auth)

    succeeded, failed = generate_groundtruth(testdata_dir, browse_client)

    for name in succeeded:
        print(f"OK    {name}")
    for name, message in failed:
        print(f"FAIL  {name}: {message}", file=sys.stderr)

    print(f"\n{len(succeeded)} succeeded, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
