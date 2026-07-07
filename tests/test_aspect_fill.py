from pipeline.aspect_fill import fill_aspect
from pipeline.models import Confidence, Field, Origin

SELECTION_ASPECT = {
    "localizedAspectName": "Department",
    "aspectConstraint": {"aspectMode": "SELECTION_ONLY", "aspectRequired": True},
    "aspectValues": [
        {"localizedValue": "Women"},
        {"localizedValue": "Teens"},
        {"localizedValue": "Unisex Adults"},
    ],
}

FREE_TEXT_ASPECT_NO_LIST = {
    "localizedAspectName": "Brand",
    "aspectConstraint": {"aspectMode": "FREE_TEXT", "aspectRequired": True},
    "aspectValues": [],
}

FREE_TEXT_ASPECT_WITH_LIST = {
    "localizedAspectName": "Color",
    "aspectConstraint": {"aspectMode": "FREE_TEXT", "aspectRequired": True},
    "aspectValues": [{"localizedValue": "Beige"}, {"localizedValue": "Black"}, {"localizedValue": "Blue"}],
}


def test_selection_only_matches_allowed_value_case_insensitive():
    candidate = Field(value="women", confidence=Confidence.HIGH, origin=Origin.VISION)
    result = fill_aspect(SELECTION_ASPECT, candidate)
    assert result.value == "Women"  # snapped to canonical casing
    assert result.confidence == Confidence.HIGH


def test_selection_only_blanks_when_value_not_in_allowed_list():
    candidate = Field(value="Kids", confidence=Confidence.HIGH, origin=Origin.VISION)
    result = fill_aspect(SELECTION_ASPECT, candidate)
    assert result.value is None
    assert result.confidence is None


def test_selection_only_blanks_when_candidate_value_is_none():
    candidate = Field(value=None, confidence=None, origin=None)
    result = fill_aspect(SELECTION_ASPECT, candidate)
    assert result.value is None


def test_free_text_blanks_low_confidence_reads():
    candidate = Field(value="Levi's", confidence=Confidence.LOW, origin=Origin.VISION)
    result = fill_aspect(FREE_TEXT_ASPECT_NO_LIST, candidate)
    assert result.value is None
    assert result.confidence is None


def test_free_text_blanks_when_confidence_missing():
    candidate = Field(value="Levi's", confidence=None, origin=Origin.VISION)
    result = fill_aspect(FREE_TEXT_ASPECT_NO_LIST, candidate)
    assert result.value is None


def test_free_text_keeps_medium_confidence_novel_value_when_no_suggested_list():
    candidate = Field(value="Levi's", confidence=Confidence.MEDIUM, origin=Origin.VISION)
    result = fill_aspect(FREE_TEXT_ASPECT_NO_LIST, candidate)
    assert result.value == "Levi's"
    assert result.confidence == Confidence.MEDIUM


def test_free_text_snaps_confident_read_to_suggested_value():
    candidate = Field(value="black", confidence=Confidence.HIGH, origin=Origin.VISION)
    result = fill_aspect(FREE_TEXT_ASPECT_WITH_LIST, candidate)
    assert result.value == "Black"  # snapped to canonical casing from the suggested list


def test_free_text_keeps_novel_value_not_in_suggested_list_at_high_confidence():
    candidate = Field(value="Chartreuse", confidence=Confidence.HIGH, origin=Origin.VISION)
    result = fill_aspect(FREE_TEXT_ASPECT_WITH_LIST, candidate)
    assert result.value == "Chartreuse"  # not forced into the suggested list — it's not closed


def test_fill_preserves_origin_through():
    candidate = Field(value="Women", confidence=Confidence.HIGH, origin=Origin.SELLER_CONTEXT)
    result = fill_aspect(SELECTION_ASPECT, candidate)
    assert result.origin == Origin.SELLER_CONTEXT
