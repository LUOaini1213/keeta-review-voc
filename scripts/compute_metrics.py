"""Ops metrics: load reviews + labels into SQLite, run every query in sql/, cross-check each one
against the pandas re-implementation, add interval estimates, write results/metrics.json.

    python scripts/compute_metrics.py           # write
    python scripts/compute_metrics.py --check   # recompute from committed data, fail on any difference

Primary labeler (pre-registered before any label-quality number was seen): the method with the
higher micro-F1 against the reference set in results/label_quality.json. Both methods' tables are
kept so every finding can be read under the other labeler too.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc import metrics_pd  # noqa: E402
from keeta_voc.dataset import DERIVED_DIR, LABEL_DIR, RESULTS_DIR, read_csv, read_labels  # noqa: E402
from keeta_voc.db import connect, run  # noqa: E402
from keeta_voc.frames import assert_frames_equal  # noqa: E402
from keeta_voc.jsoncmp import assert_close  # noqa: E402
from keeta_voc.stats import bootstrap_ranking, wilson  # noqa: E402

OUT = RESULTS_DIR / "metrics.json"
MIN_VERSION_N = 10
METHODS = ("rules", "llm")


def load_reviews() -> pd.DataFrame:
    df = pd.DataFrame(read_csv(DERIVED_DIR / "reviews_meta.csv"))
    return df.astype({"rating": int, "n_chars": int})


def load_labels() -> dict:
    return {"rules": read_labels(LABEL_DIR / "rules.csv"), "llm": read_labels(LABEL_DIR / "llm.csv")}


def primary_method() -> str:
    q = json.loads((RESULTS_DIR / "label_quality.json").read_text(encoding="utf-8"))
    return max(METHODS, key=lambda m: (q[m]["overall"]["micro_f1"], m == "rules"))


def sql_and_pandas(reviews: pd.DataFrame, labels: dict) -> dict:
    """Run every SQL query and assert it equals the pandas version. Returns SQL frames."""
    con = connect(reviews, labels)
    out = {"overview": run(con, "overview"), "language_mix": run(con, "language_mix")}
    assert_frames_equal(out["overview"], metrics_pd.overview(reviews), "overview")
    assert_frames_equal(out["language_mix"], metrics_pd.language_mix(reviews), "language_mix")
    for m in labels:
        lab = labels[m]
        per = {
            "issue_share_by_storefront": (run(con, "issue_share_by_storefront", method=m),
                                          metrics_pd.issue_share_by_storefront(reviews, lab)),
            "issue_share_by_rating": (run(con, "issue_share_by_rating", method=m),
                                      metrics_pd.issue_share_by_rating(reviews, lab)),
            "pain_points": (run(con, "pain_points", method=m), metrics_pd.pain_points(reviews, lab)),
            "by_version": (run(con, "by_version", method=m, min_n=MIN_VERSION_N),
                           metrics_pd.by_version(reviews, lab, MIN_VERSION_N)),
            "month_trend": (run(con, "month_trend", method=m), metrics_pd.month_trend(reviews, lab)),
        }
        for name, (s, p) in per.items():
            assert_frames_equal(s, p, f"{m}/{name}")
        out[m] = {name: s for name, (s, p) in per.items()}
    return out


def pain_point_intervals(reviews: pd.DataFrame, lab: dict, pain: pd.DataFrame) -> dict:
    out = {}
    for sf, grp in pain.groupby("storefront"):
        names = list(grp["label"])
        neg = reviews[(reviews["storefront"] == sf) & (reviews["rating"] <= 2)]
        keys = [k for k in neg["review_key"] if lab.get(k)]
        X = np.array([[1 if n in lab[k] else 0 for n in names] for k in keys], dtype=float).reshape(len(keys),
                                                                                                    len(names))
        boot = bootstrap_ranking(X, names, n_boot=2000, seed=0)
        out[sf] = {}
        for _, row in grp.iterrows():
            lo, hi = wilson(int(row["n_label"]), int(row["n_negative"]))
            out[sf][row["label"]] = {"n_label": int(row["n_label"]), "n_negative": int(row["n_negative"]),
                                    "share": float(row["share"]), "rank": int(row["rank"]),
                                    "wilson_ci": [lo, hi], **boot[row["label"]]}
    return out


def records(df: pd.DataFrame) -> list:
    return json.loads(df.to_json(orient="records"))


def compute() -> dict:
    reviews = load_reviews()
    labels = load_labels()
    frames = sql_and_pandas(reviews, labels)
    prim = primary_method()
    other = [m for m in METHODS if m != prim][0]
    res = {
        "primary_method": prim,
        "secondary_method": other,
        "min_version_n": MIN_VERSION_N,
        "n_reviews": int(len(reviews)),
        "overview": records(frames["overview"]),
        "language_mix": records(frames["language_mix"]),
        "methods": {m: {k: records(v) for k, v in frames[m].items()} for m in METHODS},
        "pain_point_intervals": {m: pain_point_intervals(reviews, labels[m], frames[m]["pain_points"])
                                 for m in METHODS},
        "sql_equals_pandas": True,
    }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = json.loads(json.dumps(compute()))
    if args.check:
        assert_close(json.loads(OUT.read_text(encoding="utf-8")), fresh, "metrics")
        print("metrics.json matches a fresh computation; every SQL query equals its pandas re-implementation")
        return
    OUT.write_text(json.dumps(fresh, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}; primary method = {fresh['primary_method']}")


if __name__ == "__main__":
    main()
