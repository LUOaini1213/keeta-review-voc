import random

import pandas as pd
import pytest

from keeta_voc import metrics_pd
from keeta_voc.db import connect, run
from keeta_voc.frames import FrameMismatch, assert_frames_equal
from keeta_voc.taxonomy import finalise, issue_labels


def synthetic(n=400, seed=1):
    rnd = random.Random(seed)
    rows, lab_a, lab_b = [], {}, {}
    for i in range(n):
        key = f"k{i:04d}"
        day = f"2026-{rnd.choice([6, 7, 8, 9]):02d}-{rnd.randint(1, 28):02d}"
        rows.append({"review_key": key, "storefront": rnd.choice(["ae", "hk", "kw"]), "rating": rnd.randint(1, 5),
                     "app_version": rnd.choice(["3.10.1", "3.11.0", "3.12.401", "2.9"]), "review_date": day,
                     "month": day[:7], "lang": rnd.choice(["en", "ar", "zh", "other"]), "n_chars": rnd.randint(1, 900)})
        lab_a[key] = finalise({x for x in issue_labels() if rnd.random() < 0.18})
        # method b: some invalid outputs (None) that must be excluded from denominators
        lab_b[key] = None if rnd.random() < 0.1 else finalise({x for x in issue_labels() if rnd.random() < 0.25})
    return pd.DataFrame(rows), {"a": lab_a, "b": lab_b}


@pytest.fixture(scope="module")
def data():
    reviews, labels = synthetic()
    return reviews, labels, connect(reviews, labels)


def test_overview_and_language(data):
    reviews, labels, con = data
    assert_frames_equal(run(con, "overview"), metrics_pd.overview(reviews), "overview")
    assert_frames_equal(run(con, "language_mix"), metrics_pd.language_mix(reviews), "language_mix")


@pytest.mark.parametrize("method", ["a", "b"])
def test_label_queries(data, method):
    reviews, labels, con = data
    lab = labels[method]
    assert_frames_equal(run(con, "issue_share_by_storefront", method=method),
                        metrics_pd.issue_share_by_storefront(reviews, lab), "storefront")
    assert_frames_equal(run(con, "issue_share_by_rating", method=method),
                        metrics_pd.issue_share_by_rating(reviews, lab), "rating")
    assert_frames_equal(run(con, "pain_points", method=method), metrics_pd.pain_points(reviews, lab), "pain")
    assert_frames_equal(run(con, "by_version", method=method, min_n=30), metrics_pd.by_version(reviews, lab, 30),
                        "version")
    assert_frames_equal(run(con, "month_trend", method=method), metrics_pd.month_trend(reviews, lab), "month")


def test_hand_computed_case():
    """Both implementations could share a mistake; pin a tiny case to numbers worked out by hand."""
    reviews = pd.DataFrame([
        {"review_key": "a", "storefront": "ae", "rating": 1, "app_version": "1", "review_date": "2026-09-01",
         "month": "2026-09", "lang": "en", "n_chars": 5},
        {"review_key": "b", "storefront": "ae", "rating": 2, "app_version": "1", "review_date": "2026-09-02",
         "month": "2026-09", "lang": "en", "n_chars": 5},
        {"review_key": "c", "storefront": "ae", "rating": 5, "app_version": "1", "review_date": "2026-08-30",
         "month": "2026-08", "lang": "ar", "n_chars": 5},
        {"review_key": "d", "storefront": "ae", "rating": 1, "app_version": "1", "review_date": "2026-09-03",
         "month": "2026-09", "lang": "en", "n_chars": 5},
    ])
    lab = {"a": ["delivery_time", "customer_service"], "b": ["delivery_time"], "c": ["positive_praise"], "d": None}
    con = connect(reviews, {"m": lab})
    pain = run(con, "pain_points", method="m")
    top = pain.iloc[0]
    # 'd' has no valid labels -> denominator is 2 negative reviews, not 3
    assert (top["label"], top["n_negative"], top["n_label"], top["share"], top["rank"]) == ("delivery_time", 2, 2, 1.0, 1)
    cs = pain[pain["label"] == "customer_service"].iloc[0]
    assert (cs["n_label"], cs["share"], cs["rank"]) == (1, 0.5, 2)
    assert set(pain["label"]) == set(issue_labels()) - {"positive_praise"}
    ov = run(con, "overview").iloc[0]
    assert (ov["n_reviews"], ov["mean_rating"], ov["share_negative"]) == (4, 2.25, 0.75)
    assert (ov["first_date"], ov["last_date"]) == ("2026-08-30", "2026-09-03")
    by_rating = run(con, "issue_share_by_rating", method="m")
    r1 = by_rating[(by_rating["rating"] == 1) & (by_rating["label"] == "delivery_time")].iloc[0]
    assert (r1["n_reviews"], r1["n_label"]) == (1, 1)
    trend = run(con, "month_trend", method="m")
    assert sorted(set(trend["month"])) == ["2026-08", "2026-09"]


def test_frame_check_can_fail():
    a = pd.DataFrame({"x": [1.0, 2.0], "y": ["p", "q"]})
    assert_frames_equal(a, a.copy(), "same")
    with pytest.raises(FrameMismatch):
        assert_frames_equal(a, pd.DataFrame({"x": [1.0, 2.0 + 1e-9], "y": ["p", "q"]}), "float")
    with pytest.raises(FrameMismatch):
        assert_frames_equal(a, pd.DataFrame({"x": [1.0, 2.0], "y": ["p", "Q"]}), "str")
    with pytest.raises(FrameMismatch):
        assert_frames_equal(a, a.iloc[:1], "rows")
    with pytest.raises(FrameMismatch):
        assert_frames_equal(a, a[["y", "x"]], "cols")
