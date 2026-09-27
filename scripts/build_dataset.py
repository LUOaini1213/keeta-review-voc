"""Frozen snapshot -> cleaned tables (offline).

    python scripts/build_dataset.py [--snapshot data/raw/snapshot_YYYY-MM-DD.json]

Writes data/work/reviews_full.csv (gitignored, has text), data/derived/reviews_meta.csv (committed,
text-free) and data/derived/snapshot_manifest.json (committed: file hash, counts, date range).
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import (DERIVED_DIR, FULL_COLUMNS, META_COLUMNS, ROOT, WORK_DIR, clean_reviews,  # noqa: E402
                               latest_snapshot, load_snapshot, sha256_file, write_csv)


def page_coverage(runs: list) -> dict:
    """Per storefront: feed pages that returned reviews in at least one pull run, and pages that
    were requested but never returned any (gaps left by the flaky feed, or past the real last page)."""
    got, tried = collections.defaultdict(set), collections.defaultdict(set)
    for run in runs:
        for r in run["requests"]:
            tried[r["storefront"]].add(r["page"])
            if not r.get("gap") and r.get("n"):
                got[r["storefront"]].add(r["page"])
    return {cc: {"pages_obtained": sorted(got[cc]), "pages_never_obtained": sorted(tried[cc] - got[cc])}
            for cc in sorted(tried)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=None)
    args = ap.parse_args()
    snap_path = args.snapshot or latest_snapshot()
    snap = load_snapshot(snap_path)
    rows, dropped = clean_reviews(snap["reviews"])
    write_csv(WORK_DIR / "reviews_full.csv", rows, FULL_COLUMNS)
    write_csv(DERIVED_DIR / "reviews_meta.csv", rows, META_COLUMNS)
    by_sf = collections.Counter(r["storefront"] for r in rows)
    dates = collections.defaultdict(list)
    for r in rows:
        dates[r["storefront"]].append(r["review_date"])
    manifest = {
        "snapshot_file": snap_path.name,
        "snapshot_sha256": sha256_file(snap_path),
        "fetched_at": snap["fetched_at"],
        "app_id": snap["app_id"],
        "n_raw": len(snap["reviews"]),
        "n_clean": len(rows),
        "dropped": dropped,
        "by_storefront": {k: {"n": by_sf[k], "first": min(dates[k]), "last": max(dates[k])} for k in sorted(by_sf)},
    }
    log_path = DERIVED_DIR / f"pull_log_{snap_path.stem.split('_', 1)[1]}.json"
    if log_path.exists():
        runs = json.loads(log_path.read_text(encoding="utf-8"))["runs"]
        manifest["pull_runs"] = len(runs)
        manifest["lookups"] = runs[-1]["lookups"]
        manifest["page_coverage"] = page_coverage(runs)
    (DERIVED_DIR / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(manifest, indent=1))
    print("wrote", (WORK_DIR / "reviews_full.csv").relative_to(ROOT), "and data/derived/reviews_meta.csv")


if __name__ == "__main__":
    main()
