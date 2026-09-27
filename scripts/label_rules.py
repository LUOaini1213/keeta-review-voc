"""Method 1: label every review with the keyword/rule baseline (offline, deterministic).

    python scripts/label_rules.py           # writes data/labels/rules.csv
    python scripts/label_rules.py --check   # re-label and fail if data/labels/rules.csv differs
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import LABEL_DIR, WORK_DIR, read_csv, read_labels, write_labels  # noqa: E402
from keeta_voc.rules import rule_labels  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = read_csv(WORK_DIR / "reviews_full.csv")
    labels = {r["review_key"]: rule_labels(r["title"], r["text"]) for r in rows}
    out = LABEL_DIR / "rules.csv"
    if args.check:
        committed = read_labels(out)
        if committed != labels:
            diff = [k for k in labels if committed.get(k) != labels[k]]
            sys.exit(f"rules.csv is stale: {len(diff)} reviews differ (e.g. {diff[:3]})")
        print(f"rules.csv matches a fresh run ({len(labels)} reviews)")
        return
    write_labels(out, labels)
    print(f"wrote {out} ({len(labels)} reviews)")


if __name__ == "__main__":
    main()
