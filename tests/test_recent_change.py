import pandas as pd

from scripts.compute_metrics import recent_change


def reviews(months):
    return pd.DataFrame([{"review_key": str(i), "storefront": "ae", "rating": 1, "month": m}
                         for i, m in enumerate(months)])


def test_gaps_do_not_pull_older_reviews_into_calendar_baseline():
    rows = reviews(["2025-01", "2026-01", "2026-08", "2026-09"])
    out = recent_change(rows, {str(i): ["delivery_time"] for i in range(4)}, min_n=1)["ae"]
    assert out["base_months"] == ["2026-06", "2026-07", "2026-08"]
    assert out["n_base"] == out["negative"]["k_base"] == 1


def test_calendar_baseline_crosses_year_and_keeps_empty_months():
    rows = reviews(["2025-05", "2025-11", "2026-01"])
    out = recent_change(rows, {str(i): ["other"] for i in range(3)}, min_n=1)["ae"]
    assert out["base_months"] == ["2025-10", "2025-11", "2025-12"]
    assert out["n_base"] == 1


def test_latest_month_is_not_moved_back_when_its_predictions_are_invalid():
    rows = reviews(["2026-07", "2026-08", "2026-09"])
    out = recent_change(rows, {"0": ["other"], "1": ["other"], "2": None}, min_n=1)["ae"]
    assert out["recent_month"] == "2026-09"
    assert out["n_recent"] == 0 and out["n_base"] == 2
    assert "skipped" in out


def test_all_invalid_storefront_is_reported_as_skipped():
    rows = reviews(["2026-09"])
    out = recent_change(rows, {"0": None}, min_n=1)["ae"]
    assert out["n_recent"] == out["n_base"] == 0
    assert "skipped" in out
