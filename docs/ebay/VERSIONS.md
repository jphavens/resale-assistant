# eBay API contract versions

Pinned OpenAPI 3 contracts in this directory, pulled directly from developer.ebay.com
(direct `curl` fetches were blocked with HTTP 403; contracts were retrieved via an
authenticated browser session instead).

| API | File | info.version | Pull date |
|---|---|---|---|
| Taxonomy API | `commerce_taxonomy_v1_oas3.json` | v1.1.1 | 2026-07-07 |
| Browse API | `buy_browse_v1_oas3.json` | v1.20.4 | 2026-07-07 |

Both clients (`ebay_client/taxonomy.py`, `ebay_client/browse.py`) are built strictly
against the paths, parameters, and response schemas in these pinned files — not from
memory or general docs. Re-pull and diff these files before assuming eBay hasn't
changed a contract.
