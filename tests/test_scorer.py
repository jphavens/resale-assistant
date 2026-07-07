from pipeline.scorer import ScoreBucket, accuracy, score_fields, summarize


def test_match_case_and_whitespace_insensitive():
    expected = {"Brand": "Levi's", "Color": "  Blue  "}
    actual = {"Brand": "levi's", "Color": "blue"}
    results = {r.field: r.bucket for r in score_fields(expected, actual)}
    assert results["Brand"] == ScoreBucket.MATCH
    assert results["Color"] == ScoreBucket.MATCH


def test_contradiction_when_values_differ():
    results = score_fields({"Size": "34x32"}, {"Size": "36x34"})
    assert results[0].bucket == ScoreBucket.CONTRADICTION


def test_model_null_when_expected_has_value_but_actual_missing():
    results = score_fields({"Material": "100% Cotton"}, {})
    assert results[0].bucket == ScoreBucket.MODEL_NULL_EXPECTED_VALUE


def test_model_null_when_actual_value_is_none():
    results = score_fields({"Material": "100% Cotton"}, {"Material": None})
    assert results[0].bucket == ScoreBucket.MODEL_NULL_EXPECTED_VALUE


def test_unverified_extra_when_actual_has_field_absent_from_expected():
    results = score_fields({}, {"Theme": "Y2K"})
    assert results[0].bucket == ScoreBucket.UNVERIFIED_EXTRA
    assert results[0].field == "Theme"


def test_unverified_extra_excluded_from_accuracy():
    expected = {"Brand": "Levi's"}
    actual = {"Brand": "Levi's", "Theme": "Y2K"}
    results = score_fields(expected, actual)
    assert accuracy(results) == 1.0


def test_accuracy_counts_contradiction_and_model_null_against():
    expected = {"Brand": "Levi's", "Size": "34x32", "Material": "Cotton"}
    actual = {"Brand": "Levi's", "Size": "36x34"}  # Material missing -> model_null
    results = score_fields(expected, actual)
    # match=1 (Brand), contradiction=1 (Size), model_null=1 (Material) -> 1/3
    assert accuracy(results) == 1 / 3


def test_accuracy_filters_to_given_fields():
    expected = {"Brand": "Levi's", "Theme": "Y2K"}
    actual = {"Brand": "wrong", "Theme": "Y2K"}
    results = score_fields(expected, actual)
    assert accuracy(results, fields={"Theme"}) == 1.0
    assert accuracy(results, fields={"Brand"}) == 0.0


def test_accuracy_returns_none_when_no_scorable_fields():
    results = score_fields({}, {"Theme": "Y2K"})  # only unverified_extra
    assert accuracy(results) is None


def test_summarize_counts_all_buckets():
    expected = {"Brand": "Levi's", "Size": "34x32", "Material": "Cotton"}
    actual = {"Brand": "Levi's", "Size": "36x34", "Theme": "Y2K"}
    results = score_fields(expected, actual)
    counts = summarize(results)
    assert counts["match"] == 1
    assert counts["contradiction"] == 1
    assert counts["model_null_expected_value"] == 1
    assert counts["unverified_extra"] == 1
