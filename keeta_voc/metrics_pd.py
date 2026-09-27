"""Independent pandas re-implementation of every query in sql/ (used to cross-check SQL results)."""
from __future__ import annotations

import pandas as pd

from .db import region_of
from .taxonomy import label_names

NOT_PAIN = ("positive_praise", "other")


def _long(reviews: pd.DataFrame, lab: dict[str, list[str] | None]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(labelled reviews, one row per review-label) for one method."""
    keys = {k for k, v in lab.items() if v}
    base = reviews[reviews["review_key"].isin(keys)].copy()
    pairs = [(k, x) for k, v in lab.items() if v and k in set(base["review_key"]) for x in v]
    long = pd.DataFrame(pairs, columns=["review_key", "label"]).drop_duplicates()
    return base, long.merge(base, on="review_key")


def _shares(base, long, by):
    denom = base.groupby(by).size().rename("n_reviews").reset_index()
    tax = pd.DataFrame({"label": list(label_names()), "ord": range(len(label_names()))})
    grid = denom.merge(tax, how="cross")
    hits = long.groupby(by + ["label"]).size().rename("n_label").reset_index()
    out = grid.merge(hits, on=by + ["label"], how="left").fillna({"n_label": 0})
    out["n_label"] = out["n_label"].astype(int)
    out["share"] = out["n_label"] / out["n_reviews"]
    return out.sort_values(by + ["ord"]).reset_index(drop=True)


def overview(reviews):
    g = reviews.groupby("storefront")
    out = pd.DataFrame({
        "n_reviews": g.size(),
        "mean_rating": g["rating"].mean(),
        "share_negative": g["rating"].apply(lambda s: (s <= 2).mean()),
        "first_date": g["review_date"].min(),
        "last_date": g["review_date"].max(),
    }).reset_index()
    return out.sort_values("storefront").reset_index(drop=True)


def issue_share_by_storefront(reviews, lab):
    base, long = _long(reviews, lab)
    return _shares(base, long, ["storefront"])[["storefront", "label", "n_reviews", "n_label", "share"]]


def issue_share_by_rating(reviews, lab):
    base, long = _long(reviews, lab)
    return _shares(base, long, ["rating"])[["rating", "label", "n_reviews", "n_label", "share"]]


def pain_points(reviews, lab):
    base, long = _long(reviews, lab)
    base = base[base["rating"] <= 2]
    long = long[long["rating"] <= 2]
    out = _shares(base, long, ["storefront"]).rename(columns={"n_reviews": "n_negative"})
    out = out[~out["label"].isin(NOT_PAIN)].copy()
    out["rank"] = out.groupby("storefront")["n_label"].rank(method="min", ascending=False).astype(int)
    out = out.sort_values(["storefront", "rank", "ord"]).reset_index(drop=True)
    return out[["storefront", "label", "n_negative", "n_label", "share", "rank"]]


def _grouped_with_rating(reviews, lab, key, min_n=1):
    base, long = _long(reviews, lab)
    g = base.groupby(["storefront", key])
    head = pd.DataFrame({"n_reviews": g.size(), "mean_rating": g["rating"].mean(),
                         "share_negative": g["rating"].apply(lambda s: (s <= 2).mean())}).reset_index()
    head = head[head["n_reviews"] >= min_n]
    sh = _shares(base, long, ["storefront", key]).drop(columns=["n_reviews"])
    out = head.merge(sh, on=["storefront", key])
    out = out.sort_values(["storefront", key, "ord"]).reset_index(drop=True)
    return out[["storefront", key, "n_reviews", "mean_rating", "share_negative", "label", "n_label", "share"]]


def by_version(reviews, lab, min_n):
    return _grouped_with_rating(reviews, lab, "app_version", min_n)


def month_trend(reviews, lab):
    return _grouped_with_rating(reviews, lab, "month")


def language_mix(reviews):
    out = reviews.groupby(["storefront", "lang"]).size().rename("n_reviews").reset_index()
    out["share"] = out["n_reviews"] / out.groupby("storefront")["n_reviews"].transform("sum")
    return out.sort_values(["storefront", "n_reviews", "lang"], ascending=[True, False, True]).reset_index(drop=True)


def _band(r: int) -> str:
    return "neg" if r <= 2 else ("mid" if r == 3 else "pos")


def cooccurrence(reviews, lab):
    _, long = _long(reviews, lab)
    long = long[(long["rating"] <= 2) & ~long["label"].isin(NOT_PAIN)].copy()
    long["region"] = long["storefront"].map(region_of)
    order = {n: i for i, n in enumerate(label_names())}
    n_a = long.groupby(["region", "label"]).size().rename("n_a").reset_index().rename(columns={"label": "label_a"})
    pairs = long[["review_key", "region", "label"]].merge(long[["review_key", "label"]], on="review_key",
                                                           suffixes=("_a", "_b"))
    pairs = pairs[pairs["label_a"] != pairs["label_b"]]
    n_ab = pairs.groupby(["region", "label_a", "label_b"]).size().rename("n_ab").reset_index()
    issues = [n for n in label_names() if n not in NOT_PAIN]
    grid = n_a.merge(pd.DataFrame({"label_b": issues}), how="cross")
    grid = grid[grid["label_a"] != grid["label_b"]]
    out = grid.merge(n_ab, on=["region", "label_a", "label_b"], how="left").fillna({"n_ab": 0})
    out["n_ab"] = out["n_ab"].astype(int)
    out["share_b_given_a"] = out["n_ab"] / out["n_a"]
    out["oa"], out["ob"] = out["label_a"].map(order), out["label_b"].map(order)
    out = out.sort_values(["region", "oa", "ob"]).reset_index(drop=True)
    return out[["region", "label_a", "label_b", "n_a", "n_ab", "share_b_given_a"]]


def region_band(reviews, lab):
    base, long = _long(reviews, lab)
    base = base.assign(region=base["storefront"].map(region_of), band=base["rating"].map(_band))
    long = long.assign(region=long["storefront"].map(region_of), band=long["rating"].map(_band))
    return _shares(base, long, ["region", "band"])[["region", "band", "label", "n_reviews", "n_label", "share"]]
