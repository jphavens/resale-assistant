from pipeline.models import Confidence, Origin
from pipeline.seller_context import infer_seller_confidence, resolve_field


def test_resolve_field_both_none_returns_null_field():
    field = resolve_field("brand", None, None, None, None)
    assert field.value is None
    assert field.confidence is None
    assert field.origin is None
    assert field.conflict is None


def test_resolve_field_vision_only():
    field = resolve_field("brand", "Levi's", Confidence.HIGH, None, None)
    assert field.value == "Levi's"
    assert field.origin == Origin.VISION
    assert field.confidence == Confidence.HIGH


def test_resolve_field_seller_only():
    field = resolve_field("brand", None, None, "Levi's", Confidence.MEDIUM)
    assert field.value == "Levi's"
    assert field.origin == Origin.SELLER_CONTEXT
    assert field.confidence == Confidence.MEDIUM


def test_resolve_field_agreement_case_and_whitespace_insensitive():
    field = resolve_field("brand", "levi's", Confidence.HIGH, "  Levi's  ", Confidence.MEDIUM)
    assert field.value == "levi's"
    assert field.origin == Origin.VISION
    assert field.conflict is None


def test_resolve_field_conflict_does_not_silently_resolve():
    field = resolve_field("brand", "Levi's", Confidence.HIGH, "Wrangler", Confidence.MEDIUM)
    assert field.value is None  # unresolved — no silent pick
    assert field.conflict is not None
    assert field.conflict.vision_value == "Levi's"
    assert field.conflict.seller_context_value == "Wrangler"


def test_resolve_field_conflict_on_size():
    field = resolve_field("size", "M", Confidence.HIGH, "L", Confidence.HIGH)
    assert field.value is None
    assert field.conflict.vision_value == "M"
    assert field.conflict.seller_context_value == "L"


def test_infer_seller_confidence_hedged_phrase_is_low():
    assert infer_seller_confidence("I think it's cashmere") == Confidence.LOW
    assert infer_seller_confidence("not sure but maybe vintage") == Confidence.LOW


def test_infer_seller_confidence_plain_statement_is_medium():
    assert infer_seller_confidence("It's a size medium") == Confidence.MEDIUM


def test_resolve_field_never_upgrades_hedged_seller_confidence():
    seller_conf = infer_seller_confidence("I think it's cashmere")
    field = resolve_field("material", None, None, "cashmere", seller_conf)
    assert field.confidence == Confidence.LOW
