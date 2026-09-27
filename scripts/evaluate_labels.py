"""Score both labelers against the reference set; write results/label_quality.json.

    python scripts/evaluate_labels.py           # write
    python scripts/evaluate_labels.py --check   # recompute from committed labels, fail on any difference
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import DERIVED_DIR, LABEL_DIR, RESULTS_DIR, read_csv, read_labels  # noqa: E402
from keeta_voc.evaluate import evaluate, paired_diff, to_matrix  # noqa: E402
from keeta_voc.jsoncmp import assert_close  # noqa: E402
from keeta_voc.taxonomy import label_names, validate_labels  # noqa: E402

OUT = RESULTS_DIR / "label_quality.json"
N_BOOT = 2000


def compute() -> dict:
    ref_rows = read_csv(LABEL_DIR / "reference.csv")
    ref = {r["review_key"]: validate_labels(r["labels"].split("|")) for r in ref_rows}
    keys = sorted(ref)
    sample = {r["review_key"] for r in read_csv(LABEL_DIR / "reference_sample.csv")}
    if set(keys) != sample:
        raise SystemExit("reference.csv does not cover exactly the drawn reference sample")
    rules = read_labels(LABEL_DIR / "rules.csv")
    llm_rows = read_csv(LABEL_DIR / "llm.csv")
    llm = {r["review_key"]: (r["labels"].split("|") if r["labels"] else None) for r in llm_rows}
    names = label_names()
    Y = to_matrix(keys, ref, names)
    R = to_matrix(keys, rules, names)
    L = to_matrix(keys, llm, names)
    out = {
        "n_reference": len(keys),
        "labels": list(names),
        "reference_label_counts": {n: int(Y[:, j].sum()) for j, n in enumerate(names)},
        "rules": evaluate(Y, R, names, n_boot=N_BOOT, seed=0),
        "llm": evaluate(Y, L, names, n_boot=N_BOOT, seed=0),
        "llm_minus_rules": paired_diff(Y, R, L, n_boot=N_BOOT, seed=0),
    }
    status = collections.Counter(r["status"] for r in llm_rows)
    out["llm_status_all"] = dict(sorted(status.items()))
    out["llm_n_all"] = len(llm_rows)
    out["llm_invalid_all"] = sum(v for k, v in status.items() if k != "ok")
    out["llm_invalid_in_reference"] = sum(1 for k in keys if llm.get(k) is None)
    # language detector vs the reference language tag
    meta = {r["review_key"]: r for r in read_csv(DERIVED_DIR / "reviews_meta.csv")}
    agree = [meta[r["review_key"]]["lang"] == r["lang"] for r in ref_rows]
    confusion = collections.Counter(f'{r["lang"]}->{meta[r["review_key"]]["lang"]}' for r in ref_rows)
    out["language_detection"] = {"n": len(agree), "accuracy": sum(agree) / len(agree),
                                 "confusion_ref_to_detected": dict(sorted(confusion.items()))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = compute()
    if args.check:
        assert_close(json.loads(OUT.read_text(encoding="utf-8")), json.loads(json.dumps(fresh)), "label_quality")
        print("label_quality.json matches a fresh computation")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fresh, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}")
    for m in ("rules", "llm"):
        o = fresh[m]["overall"]
        print(m, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in o.items()})


if __name__ == "__main__":
    main()
