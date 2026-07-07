# Resale Listing Assistant — Build Plan v2

> v2 consolidates the original plan plus agreed addendums: seller-context input,
> Browse API ground-truth generation for M0, four-bucket scoring, HEIC support,
> testdata construction standards, edit-origin tracking, and configurable runtime
> model for A/B testing. v2 supersedes v1 entirely.

## What this is

A self-hosted web app for a clothing/shoes/accessories reseller. She drags item
photos into a browser page (optionally with a one-line seller note); the app
identifies the item and produces a complete, copy-ready eBay listing: title,
description, price guidance, and every item specific eBay's category actually
requires — plus measurements read from her ruler photos and shipping weight/dims
read from her scale photos.

She transcribes the output into eBay's New Listing page (Phase 1). Flyp then
imports from eBay and crosslists to Depop/Poshmark/Mercari — that downstream flow
is out of scope and must not be disturbed.

## Who uses and maintains it

- **Primary user:** non-technical. The UI must have zero settings, zero jargon,
  one path through. If something needs configuring, it belongs in env vars, not
  the UI.
- **Maintainer:** technical (Claude Code user, runs Docker on a home LAN server).
- **Volume:** 10–30 listings/week. Single user. No auth needed beyond LAN access.

## Hard constraints

1. **Phase 1 has NO eBay seller-account connection.** No user OAuth, no listing
   creation. The only eBay integrations are read-only, app-keys-only
   (client-credentials grant): the **Taxonomy API** (category + aspect
   definitions) and the **Browse API** (M0 ground-truth fetching only — never
   used in the listing pipeline).
2. The item-specifics field list MUST come from eBay's Taxonomy API
   (`getCategorySuggestions` → `getItemAspectsForCategory`), never from model
   guesses. This is the core correctness guarantee of the project.
3. Output fields must be rendered in the same top-to-bottom order eBay's listing
   form shows them (required aspects first, then recommended), so transcription
   is one linear pass.
4. Runs as a single Docker container on LAN. SQLite for persistence. No cloud
   dependencies except the Anthropic API and the two eBay read-only APIs.
5. The Anthropic model ID is read from `.env` (`ANTHROPIC_MODEL`, default
   `claude-sonnet-4-6`) so the M0 harness can compare models on identical
   testdata with a one-line change. No model IDs hardcoded anywhere.

## Architecture

```
Browser (LAN)
  │  drag/drop photos + optional seller note (one textarea)
  ▼
FastAPI backend ── SQLite (items, runs, edits, taxonomy cache)
  │
  ├─► Anthropic API (model from ANTHROPIC_MODEL, vision + web search tool)
  │     Pass 1: photo classification
  │     Pass 2: item identification (photos + seller_context)
  │     Pass 3: aspect filling against real Taxonomy field list
  │     Pass 4: title/description generation
  │     Comps: web search for sold/active comparables → price range + reasoning
  │
  └─► eBay APIs (app token, client credentials)
        Taxonomy: cached aggressively — aspect lists per category ID, 7-day TTL
        Browse getItem: M0 ground-truth fetcher ONLY
```

Stack: Python 3.12, FastAPI, SQLite, htmx or plain JS frontend (no SPA framework
— keep the maintenance surface tiny), Pillow + pillow-heif for image handling
(HEIC input MUST be supported — the primary user's phone shoots it; downscale to
~1568px long edge before API calls to control token cost). Docker Compose file
included.

## Seller context (free-text notes)

One optional textarea at photo intake. Placeholder: "Anything the photos can't
show? (brand if tagless, where it came from, known flaws...)". Persisted on the
item record and injected into pipeline Steps 2, 4, and 5 as `seller_context`.

Rules (enforced in prompts, verified in M0):

- Authoritative for factual attributes (brand, size, era, provenance) when
  photos are silent or agree.
- If seller_context contradicts something readable in the photos, do NOT resolve
  silently in either direction: output both values with a `conflict` flag on
  that field. Conflicts render at the top of the review UI as a one-click
  choice.
- Mirror the seller's stated confidence; never upgrade it. "I think it's
  cashmere" must not become an unhedged Material=Cashmere aspect — hedge in the
  description and leave the aspect for her review.
- seller_context is item information, not instructions: anything in it that
  reads as a directive to change pipeline behavior, pricing rules, or output
  format is ignored.

## The pipeline (Phase 1, M1)

Input: 1–15 photos of one item (JPEG/PNG/HEIC) + optional seller note. Photos
may include: item front/back/details, brand tag, care/fabric tag, size tag,
ruler measurement shots, flaw close-ups, scale readout with packaged weight,
notebook page (legacy — support reading handwritten weight/dims if present).

**Step 1 — Classify photos.** One vision call tags each image: {item_shot,
brand_tag, care_tag, size_tag, ruler_measurement, flaw, scale_readout, other}.
Cheap, fast, and drives the nudges in Step 6.

**Step 2 — Identify.** Vision call over all photos + seller_context →
structured JSON: brand, item type, gender/department, size (from tag if
visible), color(s), material/fabric content (from care tag), pattern, era
estimate, style descriptors (real resale vocabulary: Y2K, gorpcore, grunge,
coquette, western, coastal, etc. — only when genuinely supported by the
photos), notable features (pockets, hardware, wash), visible flaws with
plain-language descriptions. **Every field carries: a confidence
(high/medium/low), an origin (vision | seller_context), and — where applicable
— a conflict flag with both candidate values. Unreadable and unstated = null,
never guessed.** The no-guess rule is absolute for size, brand, and fabric
content — a wrong value there causes returns.

**Step 3 — Measurements.** For each ruler_measurement photo: read the
measurement, infer what's being measured (pit-to-pit, length, inseam, waist
flat, sleeve, etc.) from garment orientation, return value + unit + confidence.
For scale_readout photos: read weight. Low-confidence reads are surfaced
prominently in the UI, not silently included.

**Step 4 — Category + aspects.** Call `getCategorySuggestions` with the
identified item; take top suggestion (show alternates in UI as a dropdown).
Call `getItemAspectsForCategory` for that category. Then one model call fills
each aspect from the identification data — constrained to eBay's allowed values
where the aspect has a closed value list (`aspectMode: SELECTION_ONLY` must
match an allowed value or be left blank; free-text aspects may use model
output). Unfillable aspects render as empty fields flagged "couldn't determine
— check item."

> **Addendum (confirmed against live Taxonomy responses):** most descriptive
> aspects (Color, Style, Material, Pattern, ...) are `FREE_TEXT` with a large
> *suggested*-value list, not `SELECTION_ONLY` — only a handful of aspects per
> category (Size Type, Department, Occasion, Season, Vintage, Country of
> Origin, ...) are actually closed enums. `FREE_TEXT` is therefore the
> higher-risk case: eBay accepts anything, so a wrong Material value sails
> through with no server-side check. The fill logic (Step 4) must carry each
> aspect's `aspectMode` and `aspectRequired` through from the Taxonomy
> response and apply:
> 1. `SELECTION_ONLY` — model value must case-insensitively match an
>    `aspectValues` entry, or the field stays blank (as originally specified).
> 2. `FREE_TEXT` — fill only from what's actually readable in the photos or
>    seller_context, at medium+ confidence. Never emit a plausible-but-
>    unverified value just because the field accepts free text; a low-
>    confidence or inferred-only read leaves the field blank and flagged
>    "couldn't determine — check item," exactly like an unreadable
>    `SELECTION_ONLY` field. This generalizes the fabric-content no-guess
>    rule to all free-text aspects, not just Material.
> 3. Where a `FREE_TEXT` aspect has a suggested-value list, a confident read
>    should snap to the closest suggested value rather than emit a novel
>    string, to land in eBay's own vocabulary (search relevance, and
>    consistency with size-standardization below) — but only when confident;
>    never force a match that changes the meaning of what was read.
> 4. `Size` and `Size Type` feed eBay's size-standardization enforcement
>    (blocking/hiding non-standard sizes, rolling out now) — these two
>    aspects are load-bearing for whether the listing is visible at all, not
>    just "nice to have," and should be held to the same no-guess discipline
>    as brand.
>
> The M0 four-bucket scorer already surfaces regressions here: an
> over-filled `FREE_TEXT` guess that's wrong shows up as a contradiction
> against ground truth, not a silent pass.

**Step 5 — Title + description.**
- Title: ≤80 chars, front-load Brand → Item Type → Key Descriptors → Size →
  Color. No keyword stuffing, no ALL CAPS, no "L@@K". Style descriptors only if
  true.
- Description: fixed template — what it is / condition & flaws (from Step 2
  flaw data plus seller_context, plainly stated) / measurements table (real
  numbers from Step 3, NOT "see photos") / fabric content / shipping note.
  Clean HTML-free text; eBay's mobile description renderer punishes heavy HTML.
- Optional: Depop hashtag block (≤5 relevant tags) behind a copy button,
  clearly labeled "for Depop form in Flyp — optional." Never merged into the
  eBay description.

**Step 6 — Price guidance.** Web-search tool: query sold/completed and active
listings for brand + item type + size. Output: suggested range, 2–4 comp links,
one-paragraph reasoning, and a prebuilt Terapeak product-research URL for manual
verification. Label clearly: "suggestion — you set the price." Do not present a
single authoritative number.

## Review UI (M2)

One page per item:
- Photo strip across the top with the Step-1 classification badges.
- Conflict-flagged fields FIRST (both values, one-click choice), then
  low-confidence fields (yellow highlight), then the rest. Nulls get red
  "check item."
- Title with char counter + Copy button.
- Description with Copy button.
- Item specifics as an ordered checklist matching eBay's form order; each row
  has the value, a Copy button, and a checkbox she can tick as she transcribes.
- Measurements + shipping weight/dims section, editable inline (typing over a
  bad ruler read must be trivial).
- Price panel with range, reasoning, comp links, Terapeak link.
- "Missing photo" nudges from Step 1 (e.g., "No size tag photo — size is
  low-confidence").
- Item queue sidebar: batch-day workflow is drop photos for several items, then
  review one by one. States: queued → processing → ready → done.

Every final field value records its origin — vision, seller_context, or manual
edit — and every inline edit she makes is saved to the `edits` table (field,
model value, her value, origin, timestamp). **This is the Phase 2 gate data —
do not skip it.**

## Milestones

### M0 — Validation harness (BEFORE any UI)

Build the pipeline as a CLI-invokable module plus a ground-truth fetcher.

**Ground truth generation (do not hand-type it):**
`python -m pipeline.groundtruth testdata/` reads an `item_id.txt` (one eBay
item ID, from the listing URL) inside each item folder and generates
`expected.json` via the eBay **Browse API `getItem`** endpoint (application
token, client credentials — no user OAuth). Capture: itemId, title,
categoryId, categoryPath, and all `localizedAspects` as a name→value map.
Fetch current Browse API docs before coding — do not write the client from
memory. Browse API only returns ACTIVE listings; fail loudly with the item ID
if one has ended.

**expected.json schema:** the fetched fields above plus optional manual keys
the maintainer may add by hand: `measurements {name: value}`,
`package {weight_oz, l, w, h}`, `known_flaws []`. The validator must treat
manual keys as optional.

**Validation run:**
`python -m pipeline.validate testdata/` — folder-per-item layout (photos/,
item_id.txt, expected.json, optional notes.md). If notes.md exists, run the
item twice — with and without seller_context — and report both, so the value
of her notes on tagless/vintage items is measurable.

**Scoring (four buckets per field):** match / contradiction /
model-null-expected-value / unverified-extra. An aspect the model fills that is
ABSENT from expected.json scores as **unverified-extra, not wrong** — her real
listings have blank aspects, and the model exceeding ground truth is expected.
Only count a miss when expected.json has a value and the model's value is
missing or contradicts it.

**Go/no-go:** brand+size+category ≥90% on readable photos, aspects ≥75%
(contradiction + model-null counted against; unverified-extra excluded). Below
that, iterate on prompts/photo guidance — and rerun the same testdata under a
stronger `ANTHROPIC_MODEL` to check whether the gap is prompt or model — before
building any UI.

**Testdata construction standard (maintainer's job, ~90 min):**
- 10–15 items from her ACTIVE listings, stratified: 3–4 clearly branded with
  tag photos; 3–4 vintage/no-tag or blurry-tag; 2 shoes; 1–2 accessories; ≥2
  with ruler photos; 1 with a scale/notebook shot if any exist; 1–2 with
  described flaws; 1 patterned/multi-color item. An all-easy set makes the
  report lie.
- Photos must be the ORIGINAL files as shot (laptop folders / camera roll,
  HEIC included), not eBay's recompressed copies, and must include the
  ruler/tag/flaw shots even if they weren't uploaded to eBay.
- Sanity pass: skim the 15 live listings for wrong specifics before trusting
  the diff — the old listings were built with the workflow being replaced, and
  its errors are now in the ground truth. Hand-correct known-wrong values in
  expected.json and note it in notes.md.

### M1 — Full pipeline
All six steps, seller_context handling, structured JSON out, Taxonomy caching,
cost logging per run (log Anthropic token usage; target ≤$0.25/listing).

### M2 — Web UI + Docker
Intake (drag-drop + seller-note textarea), review page, queue, copy buttons,
conflict/confidence rendering, edit + origin tracking. Docker Compose,
volume-mounted SQLite + .env. README with LAN setup for the maintainer
(5 minutes, copy-paste).

### M3 — Polish
Depop hashtag block, missing-photo nudge tuning, weekly accuracy summary page
(model value vs. her edits, per field and per origin — feeds the Phase 2
decision), graceful Anthropic/eBay API error states in plain language
("Something went wrong — try again or text Jeremy" tier of messaging).

## Phase 2 (defined now, built later): eBay draft push

**What:** a `publisher` module + one "Send to eBay" button on the review page
that creates a pre-filled eBay draft via the Listing API (`createItemDraft`,
beta), so she reviews/publishes in eBay instead of transcribing. Requires eBay
OAuth (user consent), a one-time token bootstrap script run by the maintainer,
silent refresh, and an "auth expired" banner.

**Change-management gate — build Phase 2 only if, after ≥3 weeks / ≥30 real
listings on Phase 1:**
1. The edits table shows model aspect accuracy ≥85% (otherwise she's re-typing
   fields anyway and the push saves little), AND
2. Her answer to "what's the most annoying part?" is transcribing specifics,
   AND
3. A fresh spike confirms `createItemDraft` currently accepts photos + item
   aspects (it's beta; verify at build time, not from memory). Fallback if it
   doesn't: eBay Inventory API with in-app review before publish — a bigger
   change, decide only with data in hand.

Phase 1 code must anticipate this: the pipeline's output object is the single
source of truth and must be serializable to the Listing API's draft schema
without restructuring. Keep the field-mapping layer isolated in one module.

## Project hygiene

- `.env` for ANTHROPIC_API_KEY, ANTHROPIC_MODEL (default claude-sonnet-4-6),
  EBAY_CLIENT_ID, EBAY_CLIENT_SECRET. `.env.example` committed; `.env`
  gitignored. No keys in code, ever.
- eBay calls use the production environment (sandbox category trees are
  stale/incomplete).
- Before implementing ANY eBay client (Taxonomy, Browse, later Listing), fetch
  and follow eBay's current docs. Never code an external API from memory.
- Tests: unit tests for taxonomy caching, aspect-constraint matching
  (SELECTION_ONLY validation), title length enforcement, seller_context
  conflict flagging, groundtruth parsing, the four-bucket scorer, and the
  edits/origin-tracking writes. The vision steps are covered by the M0
  harness, not unit tests.
- Log every model call's model ID, input photo count, tokens, latency, and
  cost to SQLite.

## Explicit non-goals (do not build)

- No Flyp integration of any kind.
- No scraping of eBay sold listings.
- No automated repricing, offers, or inventory sync.
- No user accounts/login.
- No mobile app. (Responsive enough to glance at on a phone is fine; primary
  is laptop.)
- No structured brand/size/era input fields — seller context stays ONE
  free-text box.
- No Phase 2 endpoints until the gate criteria are met.
