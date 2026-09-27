"""Draw the stratified reference sample (seeded) and write a blind labelling worksheet.

    python scripts/make_reference_sample.py --n 180

Strata = storefront x rating band (1-2 / 3 / 4-5). Allocation is proportional to stratum size,
with 1-2 star strata weighted x2 (the ops analysis is about complaints) and a floor of 5 per
stratum (or the whole stratum if smaller). Largest-remainder rounding; seed fixed.

Writes data/labels/reference_sample.csv (committed: keys + stratum) and
data/work/reference_worksheet.jsonl (gitignored: title + text only - no rating, no model output,
so the reference labels are made blind to both methods).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import LABEL_DIR, WORK_DIR, read_csv, write_csv  # noqa: E402

SEED = 20260927
FLOOR = 5


def band(rating: int) -> str:
    return "neg" if rating <= 2 else ("mid" if rating == 3 else "pos")


def allocate(sizes: dict, n: int) -> dict:
    weights = {k: v * (2 if k[1] == "neg" else 1) for k, v in sizes.items()}
    alloc = {k: min(FLOOR, sizes[k]) for k in sizes}
    rest = n - sum(alloc.values())
    tot = sum(weights.values())
    raw = {k: rest * weights[k] / tot for k in sizes}
    for k in sizes:
        alloc[k] = min(sizes[k], alloc[k] + int(np.floor(raw[k])))
    order = sorted(sizes, key=lambda k: -(raw[k] - np.floor(raw[k])))
    i = 0
    while sum(alloc.values()) < n and any(alloc[k] < sizes[k] for k in sizes):
        k = order[i % len(order)]
        if alloc[k] < sizes[k]:
            alloc[k] += 1
        i += 1
    return alloc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=180)
    args = ap.parse_args()
    rows = read_csv(WORK_DIR / "reviews_full.csv")
    strata = {}
    for r in rows:
        strata.setdefault((r["storefront"], band(int(r["rating"]))), []).append(r)
    alloc = allocate({k: len(v) for k, v in strata.items()}, args.n)
    rng = np.random.default_rng(SEED)
    picked = []
    for k in sorted(strata):
        members = sorted(strata[k], key=lambda r: r["review_key"])
        idx = rng.choice(len(members), size=alloc[k], replace=False)
        picked += [(members[i], k) for i in sorted(idx)]
    write_csv(LABEL_DIR / "reference_sample.csv",
              [{"review_key": r["review_key"], "storefront": k[0], "band": k[1]} for r, k in picked],
              ["review_key", "storefront", "band"])
    order = rng.permutation(len(picked))  # shuffle so strata are not visible while labelling
    with open(WORK_DIR / "reference_worksheet.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i in order:
            r = picked[i][0]
            f.write(json.dumps({"review_key": r["review_key"], "title": r["title"], "text": r["text"]},
                               ensure_ascii=False) + "\n")
    print({f"{k[0]}/{k[1]}": v for k, v in sorted(alloc.items())}, "total", sum(alloc.values()))


if __name__ == "__main__":
    main()
