"""One-off smoke test: mint an eBay app token and make one live Taxonomy call.

Run: .venv/bin/python scripts/smoke_test_ebay.py
Verifies the keyset is actually active end to end. Never prints token or
credential values.
"""
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from db.connection import connect
from ebay_client.auth import EbayAuthClient
from ebay_client.taxonomy import TaxonomyClient

client_id = os.environ["EBAY_CLIENT_ID"]
client_secret = os.environ["EBAY_CLIENT_SECRET"]

auth = EbayAuthClient(client_id, client_secret)
token = auth.get_token()
print(f"Token minted OK (length={len(token)}, not printing value)")

conn = connect(":memory:")
taxonomy = TaxonomyClient(auth, conn)

tree_id = taxonomy.get_default_category_tree_id("EBAY_US")
print(f"Default category tree ID for EBAY_US: {tree_id}")

suggestions = taxonomy.get_category_suggestions(tree_id, "levis 501 jeans")
print(f"Category suggestions for 'levis 501 jeans': {len(suggestions.get('categorySuggestions', []))} results")
for s in suggestions.get("categorySuggestions", [])[:5]:
    cat = s["category"]
    print(f"  - categoryId={cat['categoryId']!r} categoryName={cat['categoryName']!r}")
