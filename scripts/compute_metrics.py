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
from keeta_voc.dataset import DERIVED_DIR, LABEL_DIR, RESULTS_DIR, read_keyed_csv, read_labels  # noqa: E402
from keeta_voc.db import connect, run  # noqa: E402
from keeta_voc.frames import assert_frames_equal  # noqa: E402
from keeta_voc.jsoncmp import assert_close  # noqa: E402
from keeta_voc.taxonomy import label_names  # noqa: E402
from keeta_voc.stats import bootstrap_ranking, newcombe_diff, wilson  # noqa: E402

OUT = RESULTS_DIR / "metrics.json"
MIN_VERSION_N = 10
RECENT_MIN_N = 30
METHODS = ("rules", "llm")


def load_reviews() -> pd.DataFrame:
    df = pd.DataFrame(read_keyed_csv(DERIVED_DIR / "reviews_meta.csv").values())
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
            "cooccurrence": (run(con, "cooccurrence", method=m), metrics_pd.cooccurrence(reviews, lab)),
            "region_band": (run(con, "region_band", method=m), metrics_pd.region_band(reviews, lab)),
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


def recent_change(reviews: pd.DataFrame, lab: dict, min_n: int = RECENT_MIN_N) -> dict:
    """Per storefront: latest calendar month in the data vs the three months before it.

    Compares the share of 1-2 star reviews and the share of reviews mentioning each label,
    with Newcombe 95% intervals for the difference. Storefronts where either period has fewer
    than `min_n` reviews are skipped (listed with the reason)."""
    out = {}
    for sf, all_reviews in reviews.groupby("storefront"):
        # Anchor to the observed review calendar, even if the newest predictions are invalid.
        month = pd.Period(all_reviews["month"].max(), freq="M")
        recent = str(month)
        base_months = [str(month - offset) for offset in (3, 2, 1)]
        g = all_reviews[all_reviews["review_key"].map(lambda k: bool(lab.get(k)))]
        a, b = g[g["month"] == recent], g[g["month"].isin(base_months)]
        entry = {"recent_month": recent, "base_months": list(base_months), "n_recent": int(len(a)),
                 "n_base": int(len(b))}
        if len(a) < min_n or len(b) < min_n:
            entry["skipped"] = f"fewer than {min_n} reviews in one period"
            out[sf] = entry
            continue

        def cmp(ka, kb):
            return {"recent": ka / len(a), "base": kb / len(b), "diff": ka / len(a) - kb / len(b),
                    "diff_ci": list(newcombe_diff(ka, len(a), kb, len(b))), "k_recent": int(ka), "k_base": int(kb)}
        entry["negative"] = cmp(int((a["rating"] <= 2).sum()), int((b["rating"] <= 2).sum()))
        entry["labels"] = {n: cmp(sum(n in lab[k] for k in a["review_key"]), sum(n in lab[k] for k in b["review_key"]))
                           for n in label_names()}
        out[sf] = entry
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
        "recent_min_n": RECENT_MIN_N,
        "n_reviews": int(len(reviews)),
        "overview": records(frames["overview"]),
        "language_mix": records(frames["language_mix"]),
        "methods": {m: {k: records(v) for k, v in frames[m].items()} for m in METHODS},
        "pain_point_intervals": {m: pain_point_intervals(reviews, labels[m], frames[m]["pain_points"])
                                 for m in METHODS},
        "recent_change": {m: recent_change(reviews, labels[m]) for m in METHODS},
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
    OUT.write_text(json.dumps(fresh, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n")
    print(f"wrote {OUT}; primary method = {fresh['primary_method']}")


if __name__ == "__main__":
    main()
