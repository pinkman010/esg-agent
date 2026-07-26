import pytest

from src.config.settings import PROJECT_ROOT
from src.tools.evaluate_shadow_retrieval import (
    compute_retrieval_metrics,
    parse_page_list,
)
from src.tools.shadow_vector_retrieval import main, resolve_shadow_output


def test_resolve_shadow_output_accepts_only_tmp_embedding():
    output = resolve_shadow_output("tmp/embedding/search.csv")

    assert output == (PROJECT_ROOT / "tmp/embedding/search.csv").resolve()

    with pytest.raises(ValueError, match="tmp/embedding"):
        resolve_shadow_output("tmp/search.csv")


def test_shadow_vector_retrieval_requires_report_id():
    with pytest.raises(SystemExit):
        main(["--query", "温室气体排放"])


def test_compute_retrieval_metrics_uses_only_cases_with_gold_pages():
    cases = [
        {
            "requirement_id": "GRI 305-1-a",
            "gold_pages": [40, 41],
            "vector_pages": [41, 8, 40],
            "rule_pages": [40],
        },
        {
            "requirement_id": "GRI 305-2-a",
            "gold_pages": [],
            "vector_pages": [42],
            "rule_pages": [],
        },
    ]

    metrics = compute_retrieval_metrics(cases, k_values=(1, 3))

    assert metrics["case_count"] == 2
    assert metrics["evaluated_case_count"] == 1
    assert metrics["no_gold_page_case_count"] == 1
    assert metrics["hit_at_1"] == 1.0
    assert metrics["recall_at_1"] == 0.5
    assert metrics["recall_at_3"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["both_hit_count"] == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("[1, 3, 3]", [1, 3]),
        ("1, 3; 5", [1, 3, 5]),
        (7, [7]),
        ("[]", []),
        (None, []),
    ],
)
def test_parse_page_list_normalizes_supported_values(value, expected):
    assert parse_page_list(value) == expected
