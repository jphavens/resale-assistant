"""Title building/validation (Step 5): <=80 chars, front-loaded
Brand -> Item Type -> Key Descriptors -> Size -> Color, no keyword stuffing,
no ALL CAPS, no "L@@K" (PLAN_v2.md Step 5).
"""
from __future__ import annotations

MAX_TITLE_LENGTH = 80


def build_title(
    brand: str | None,
    item_type: str | None,
    size: str | None = None,
    color: str | None = None,
    descriptors: list[str] | None = None,
    max_len: int = MAX_TITLE_LENGTH,
) -> str:
    """Assemble a title within max_len, dropping style descriptors (least
    essential) before ever dropping brand/type/size/color.
    """
    core = [p for p in (brand, item_type) if p]
    tail = [p for p in (size, color) if p]
    remaining_descriptors = list(descriptors or [])

    def assemble(descs: list[str]) -> str:
        return " ".join(core + descs + tail)

    title = assemble(remaining_descriptors)
    while len(title) > max_len and remaining_descriptors:
        remaining_descriptors.pop()
        title = assemble(remaining_descriptors)

    if len(title) > max_len:
        clipped = title[:max_len].rstrip()
        # Don't cut mid-word — back up to the last whole-word boundary. If
        # there's no space at all (one giant token), fall back to the hard
        # char clip rather than returning an empty string.
        if " " in clipped and len(clipped) < len(title):
            clipped = clipped.rsplit(" ", 1)[0]
        title = clipped

    return title


def validate_title(title: str) -> list[str]:
    """Return a list of violation descriptions; empty list means the title is clean."""
    violations = []

    if len(title) > MAX_TITLE_LENGTH:
        violations.append(f"exceeds {MAX_TITLE_LENGTH} characters ({len(title)})")

    letters = [c for c in title if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        violations.append("title is ALL CAPS")

    if "l@@k" in title.lower().replace(" ", ""):
        violations.append('title contains "L@@K"-style keyword spam')

    words = [w.lower() for w in title.split() if w.isalpha()]
    for word in set(words):
        if len(word) > 2 and words.count(word) > 2:
            violations.append(f'keyword stuffing: "{word}" repeated {words.count(word)} times')

    return violations
