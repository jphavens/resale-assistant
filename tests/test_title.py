from pipeline.title import MAX_TITLE_LENGTH, build_title, validate_title


def test_build_title_assembles_in_correct_order():
    title = build_title(brand="Levi's", item_type="Jeans", size="34x32", color="Blue", descriptors=["Y2K", "Straight Leg"])
    assert title == "Levi's Jeans Y2K Straight Leg 34x32 Blue"


def test_build_title_drops_descriptors_first_when_too_long():
    # Core fields alone ("Levi's Jeans 34x32 Blue Denim") fit comfortably
    # under 80 chars; the long descriptor list is what pushes it over.
    long_descriptors = ["Extremely", "Long", "Style", "Descriptor", "Words", "Here", "Padding", "Extra"]
    title = build_title(
        brand="Levi's",
        item_type="Jeans",
        size="34x32",
        color="Blue Denim",
        descriptors=long_descriptors,
        max_len=80,
    )
    assert len(title) <= 80
    assert title.startswith("Levi's Jeans")
    assert title.endswith("34x32 Blue Denim")


def test_build_title_hard_clips_if_still_too_long_with_no_descriptors():
    title = build_title(
        brand="A" * 40,
        item_type="B" * 60,
        size=None,
        color=None,
        descriptors=[],
        max_len=80,
    )
    assert len(title) == 80


def test_build_title_omits_missing_fields():
    title = build_title(brand="Levi's", item_type="Jeans", size=None, color=None)
    assert title == "Levi's Jeans"


def test_validate_title_flags_too_long():
    violations = validate_title("A" * (MAX_TITLE_LENGTH + 1))
    assert any("exceeds" in v for v in violations)


def test_validate_title_flags_all_caps():
    violations = validate_title("LEVIS 501 JEANS SIZE 34X32 BLUE DENIM")
    assert any("ALL CAPS" in v for v in violations)


def test_validate_title_allows_mixed_case():
    violations = validate_title("Levi's 501 Jeans Size 34x32 Blue Denim")
    assert violations == []


def test_validate_title_flags_look_spam():
    violations = validate_title("L@@K Levi's 501 Jeans Rare!!")
    assert any("L@@K" in v for v in violations)


def test_validate_title_flags_keyword_stuffing():
    violations = validate_title("jeans jeans jeans levis levis levis 34x32")
    assert any("stuffing" in v for v in violations)


def test_validate_title_clean_title_has_no_violations():
    violations = validate_title("Levi's 501 Original Fit Jeans 34x32 Blue")
    assert violations == []
