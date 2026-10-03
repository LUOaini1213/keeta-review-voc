"""Exercise the real CSV/scoring/SQL boundaries with small, complete cohorts."""
import csv

import pandas as pd
import pytest

from keeta_voc.dataset import read_labels
from keeta_voc.db import connect
from scripts import compute_metrics, evaluate_labels


def write_rows(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def cohort(tmp_path, monkeypatch):
    labels, derived = tmp_path / "labels", tmp_path / "derived"
    labels.mkdir()
    derived.mkdir()
    meta = [{"review_key": k, "storefront": "ae", "rating": "1", "app_version": "1",
             "review_date": "2026-09-01", "month": "2026-09", "lang": "en", "n_chars": "5"}
            for k in "abc"]
    fixtures = {
        "meta": (derived / "reviews_meta.csv", list(meta[0]), meta),
        "reference": (labels / "reference.csv", ["review_key", "labels", "lang"],
                      [{"review_key": k, "labels": "delivery_time", "lang": "en"} for k in "ab"]),
        "sample": (labels / "reference_sample.csv", ["review_key", "storefront", "band"],
                   [{"review_key": k, "storefront": "ae", "band": "neg"} for k in "ab"]),
        "rules": (labels / "rules.csv", ["review_key", "labels"],
                  [{"review_key": k, "labels": "delivery_time"} for k in "abc"]),
        "llm": (labels / "llm.csv", ["review_key", "labels", "status"],
                [{"review_key": k, "labels": "delivery_time", "status": "ok"} for k in "abc"]),
    }
    for path, fields, rows in fixtures.values():
        write_rows(path, fields, rows)
    (labels / "llm_log.jsonl").write_text("", encoding="utf-8")
    for mod in (compute_metrics, evaluate_labels):
        monkeypatch.setattr(mod, "LABEL_DIR", labels)
        monkeypatch.setattr(mod, "DERIVED_DIR", derived)
    monkeypatch.setattr(evaluate_labels, "N_BOOT", 8)
    return fixtures


def rewrite(cohort, name, rows):
    path, fields, _ = cohort[name]
    write_rows(path, fields, rows)


def test_nonok_prediction_is_zero_even_with_residual_labels(cohort):
    rows = cohort["llm"][2]
    rows[0].update(status="bad_labels", labels="unknown_residual_label")
    rewrite(cohort, "llm", rows)
    assert read_labels(cohort["llm"][0])["a"] is None
    score = evaluate_labels.compute()
    assert score["llm"]["overall"]["micro_f1"] == pytest.approx(2 / 3)
    assert score["llm_invalid_all"] == score["llm_invalid_in_reference"] == 1
    frames = compute_metrics.sql_and_pandas(compute_metrics.load_reviews(), compute_metrics.load_labels())
    assert set(frames["llm"]["issue_share_by_storefront"]["n_reviews"]) == {2}


@pytest.mark.parametrize("name", ["reference", "sample", "meta", "rules", "llm"])
def test_duplicate_keys_rejected_before_scoring(cohort, name):
    rows = cohort[name][2]
    duplicate = dict(rows[0])
    if "labels" in duplicate:
        duplicate["labels"] = "other"
    rewrite(cohort, name, rows + [duplicate])
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_labels.compute()


@pytest.mark.parametrize("name", ["rules", "llm"])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_predictions_cover_entire_metadata_not_just_reference(cohort, name, change):
    rows = cohort[name][2]
    rows = rows[:2] if change == "missing" else rows + [dict(rows[0], review_key="outside")]
    rewrite(cohort, name, rows)
    with pytest.raises(ValueError, match="cohort"):
        evaluate_labels.compute()
    with pytest.raises(ValueError, match="cohort"):
        compute_metrics.sql_and_pandas(compute_metrics.load_reviews(), compute_metrics.load_labels())


@pytest.mark.parametrize("labels", ["not_in_taxonomy", "other|delivery_time", ""])
def test_ok_prediction_requires_valid_nonempty_taxonomy_labels(cohort, labels):
    rows = cohort["llm"][2]
    rows[0]["labels"] = labels
    rewrite(cohort, "llm", rows)
    with pytest.raises(ValueError):
        read_labels(cohort["llm"][0])


def test_reference_and_sample_must_match_and_belong_to_metadata(cohort):
    refs = cohort["reference"][2]
    sample = cohort["sample"][2]
    rewrite(cohort, "reference", [dict(r, review_key="outside") if r["review_key"] == "a" else r for r in refs])
    with pytest.raises(ValueError, match="cohort"):
        evaluate_labels.compute()
    rewrite(cohort, "sample", [dict(r, review_key="outside") if r["review_key"] == "a" else r for r in sample])
    with pytest.raises(ValueError, match="cohort"):
        evaluate_labels.compute()


@pytest.mark.parametrize("name", ["meta", "rules", "llm"])
def test_metrics_reject_duplicate_inputs(cohort, name):
    rows = cohort[name][2]
    rewrite(cohort, name, rows + [rows[0]])
    with pytest.raises(ValueError, match="duplicate"):
        compute_metrics.sql_and_pandas(compute_metrics.load_reviews(), compute_metrics.load_labels())


@pytest.mark.parametrize("bad", [["unknown_label"], ["other", "delivery_time"], [], "delivery_time"])
def test_direct_sql_boundary_validates_labels(cohort, bad):
    with pytest.raises(ValueError):
        connect(compute_metrics.load_reviews(), {"m": {"a": bad, "b": None, "c": None}})


def test_explicit_none_preserves_cohort_and_all_invalid_is_valid(cohort):
    reviews = compute_metrics.load_reviews()
    frames = compute_metrics.sql_and_pandas(reviews, {"m": {k: None for k in "abc"}})
    assert all(frame.empty for frame in frames["m"].values())


def test_complete_valid_cohort_is_compatible(cohort):
    score = evaluate_labels.compute()
    assert score["n_reference"] == score["language_detection"]["n"] == 2
    assert score["rules"]["overall"]["micro_f1"] == 1
    assert score["llm"]["overall"]["micro_f1"] == 1
