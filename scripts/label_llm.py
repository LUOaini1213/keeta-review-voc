"""Method 2: label reviews with a local LLM via Ollama (NOT run in CI; its outputs are frozen).

    python scripts/label_llm.py --model qwen2.5:3b [--limit N]

Resumable: every call is appended to data/work/llm_log_full.jsonl (gitignored: it contains the
review text inside the prompt). At the end it writes
  data/labels/llm.csv            review_key, labels ('' when the output was invalid), status
  data/labels/llm_log.jsonl      the same log with the user prompt removed (committed)
  data/labels/llm_system_prompt.txt
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import LABEL_DIR, WORK_DIR, read_csv, write_labels  # noqa: E402
from keeta_voc.llm import label_one, system_prompt  # noqa: E402

FULL_LOG = WORK_DIR / "llm_log_full.jsonl"


def load_log() -> dict:
    done = {}
    if FULL_LOG.exists():
        for line in FULL_LOG.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            done[rec["review_key"]] = rec
    return done


def finalise(rows, done):
    keys = [r["review_key"] for r in rows if r["review_key"] in done]
    labels = {k: done[k]["labels"] for k in keys}
    extra = {k: {"status": done[k]["status"]} for k in keys}
    write_labels(LABEL_DIR / "llm.csv", labels, extra)
    with open(LABEL_DIR / "llm_log.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for k in sorted(keys):
            rec = {x: v for x, v in done[k].items() if x != "user_prompt"}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (LABEL_DIR / "llm_system_prompt.txt").write_text(system_prompt() + "\n", encoding="utf-8", newline="\n")
    n_bad = sum(1 for k in keys if done[k]["status"] != "ok")
    print(f"labelled {len(keys)} reviews, invalid outputs: {n_bad}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--finalise-only", action="store_true")
    ap.add_argument("--reference-first", action="store_true", help="label the reference sample before the rest")
    args = ap.parse_args()
    rows = read_csv(WORK_DIR / "reviews_full.csv")
    done = load_log()
    if not args.finalise_only:
        first = {r["review_key"] for r in read_csv(LABEL_DIR / "reference_sample.csv")} if args.reference_first else set()
        todo = [r for r in rows if r["review_key"] not in done]
        todo = sorted(todo, key=lambda r: r["review_key"] not in first)[: args.limit]  # stable: reference first
        FULL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FULL_LOG, "a", encoding="utf-8", newline="\n") as f:
            for i, r in enumerate(todo, 1):
                rec = label_one(args.model, r["review_key"], r["title"], r["text"])
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[r["review_key"]] = rec
                if i % 25 == 0:
                    print(f"{i}/{len(todo)} last {rec['seconds']}s status={rec['status']}", flush=True)
    finalise(rows, done)


if __name__ == "__main__":
    main()
