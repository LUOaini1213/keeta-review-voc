"""Pull a fresh snapshot of public Keeta App Store reviews (the ONLY step that needs network).

    python scripts/fetch_reviews.py            # writes data/raw/snapshot_<date>.json + pull log
    python scripts/fetch_reviews.py --merge    # top-up: union with today's snapshot (feed is flaky)

The rest of the pipeline never calls this; it reads the frozen snapshot.
"""
import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from keeta_voc.fetch import LOOKUP_URL, PullLog, dedupe, http_get_json, pull_storefront  # noqa: E402

APP_ID = "1662451643"
STOREFRONTS = ["sa", "kw", "ae", "qa", "bh", "om", "hk"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storefronts", default=",".join(STOREFRONTS))
    ap.add_argument("--pause", type=float, default=3.0)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--merge", action="store_true", help="union with an existing snapshot of the same day")
    args = ap.parse_args()

    fetched_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    log = PullLog()
    lookups, all_reviews = {}, []
    for cc in args.storefronts.split(","):
        status, lk = http_get_json(LOOKUP_URL.format(app_id=APP_ID, cc=cc))
        r = lk["results"][0] if lk.get("results") else {}
        lookups[cc] = {k: r.get(k) for k in ("trackId", "trackName", "sellerName", "artistName", "bundleId",
                                             "primaryGenreName", "userRatingCount", "averageUserRating",
                                             "version", "currentVersionReleaseDate", "releaseDate")}
        time.sleep(args.pause)
        got = pull_storefront(APP_ID, cc, retries=args.retries, pause=args.pause, log=log)
        print(f"{cc}: {len(got)} reviews", flush=True)
        all_reviews.extend(got)

    stamp = fetched_at[:10]
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    snap_path = raw_dir / f"snapshot_{stamp}.json"
    log_path = ROOT / "data" / "derived" / f"pull_log_{stamp}.json"
    runs = []
    if args.merge and snap_path.exists():
        old = json.loads(snap_path.read_text(encoding="utf-8"))
        all_reviews = old["reviews"] + all_reviews   # earlier pull wins on duplicates
        runs = json.loads(log_path.read_text(encoding="utf-8"))["runs"]
    reviews = dedupe(all_reviews)
    snap = {"app_id": APP_ID, "fetched_at": fetched_at, "source": "Apple customer-reviews RSS (public)",
            "reviews": reviews}
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    runs.append({"fetched_at": fetched_at, "lookups": lookups, "requests": log.requests})
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps({"app_id": APP_ID, "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total unique reviews in {snap_path.name}: {len(reviews)}")


if __name__ == "__main__":
    main()
