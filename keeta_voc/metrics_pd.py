"""Independent pandas re-implementation of every query in sql/ (used to cross-check SQL results)."""
from __future__ import annotations

import pandas as pd

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
