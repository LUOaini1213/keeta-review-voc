"""Method 2: label reviews with a local LLM via Ollama (NOT run in CI; its outputs are frozen).

    python scripts/label_llm.py --model qwen2.5:3b [--limit N]

Resumable: attempts are appended to data/work/llm_log_full.jsonl (gitignored: prompts and complete
requests contain review text). Only matching request identities are reused, including invalid
predictions. Legacy attempts without complete request identity require explicit --new-run;
this authorises new attempts for them, never deletes history or retries verified matches.
An incomplete --limit run returns 2 and keeps previous exports untouched. Only after every
current review has a matching attempt does this script publish
  data/labels/llm.csv            review_key, labels ('' when the output was invalid), status
  data/labels/llm_log.jsonl      selected attempts with private request/prompts removed (committed)
  data/labels/llm_system_prompt.txt
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keeta_voc.dataset import LABEL_DIR, WORK_DIR, read_csv, write_labels  # noqa: E402
from keeta_voc import llm  # noqa: E402
from keeta_voc.llm import label_one  # noqa: E402

FULL_LOG = WORK_DIR / "llm_log_full.jsonl"


def _replace_bytes(path, data):
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            name = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def _check_record(rec):
    if not isinstance(rec, dict) or not isinstance(rec.get("review_key"), str) or not rec["review_key"]:
        raise ValueError("invalid review key in LLM log")
    if rec.get("status") not in ("ok", "bad_json", "bad_labels", "http_error") or "labels" not in rec:
        raise ValueError("invalid attempt in LLM log")
    if ("request" in rec) != ("request_sha256" in rec):
        raise ValueError("incomplete request identity in LLM log")
    if "request" in rec:
        req = rec["request"]
        if (not isinstance(req, dict) or rec.get("model") != req.get("model")
                or rec["request_sha256"] != llm.request_sha256(req)):
            raise ValueError("request fingerprint mismatch in LLM log")


def load_log() -> list[dict]:
    """Keep all attempts; quarantine only an unterminated, undecodable final line."""
    if not FULL_LOG.exists():
        return []
    data = FULL_LOG.read_bytes()
    lines = data.splitlines(keepends=True)
    history, offset = [], 0
    for number, line in enumerate(lines, 1):
        try:
            rec = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if number != len(lines) or line.endswith((b"\n", b"\r")):
                raise ValueError(f"corrupt LLM log at line {number}; history was not changed") from exc
            # Keep the exact interrupted bytes before restoring the complete prefix.
            tail = FULL_LOG.with_name(FULL_LOG.name + ".interrupted-" + hashlib.sha256(line).hexdigest()[:16])
            if tail.exists():
                if tail.read_bytes() != line:
                    raise ValueError("interrupted-log backup conflicts with existing file")
            else:
                with tail.open("xb") as f:
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())
            _replace_bytes(FULL_LOG, data[:offset])
            print(f"recovered interrupted final log line; bytes preserved in {tail.name}")
            break
        _check_record(rec)
        history.append(rec)
        offset += len(line)
    return history


def _selected(requests, history):
    identities = {key: llm.request_sha256(req) for key, req in requests.items()}
    done = {}
    for rec in history:
        key = rec["review_key"]
        if key in identities and rec.get("request_sha256") == identities[key]:
            _check_record(rec)
            if key in done and rec != done[key]:
                raise ValueError("conflicting attempts for one review/request; history requires review")
            if rec["status"] == "http_error":
                if rec["labels"] is not None:
                    raise ValueError("http_error attempt must not contain labels")
            else:
                status, labels, _ = llm.parse_response(rec.get("raw_response"))
                if (status, labels) != (rec["status"], rec["labels"]):
                    raise ValueError("cached labels/status disagree with the recorded response")
            done[key] = rec
    return done


def finalise(rows, done, requests):
    keys = [r["review_key"] for r in rows]
    selected = _selected(requests, list(done.values()))
    if len(set(keys)) != len(keys) or set(selected) != set(keys):
        raise ValueError("incomplete current-request results; exports were not changed")
    done = selected
    prompts = {requests[k]["messages"][0]["content"] for k in keys}
    if len(prompts) != 1:
        raise ValueError("export requires one consistent system prompt")
    labels = {k: done[k]["labels"] for k in keys}
    extra = {k: {"status": done[k]["status"]} for k in keys}
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    # Prepare all outputs first. Each file is then replaced atomically.
    with tempfile.TemporaryDirectory(dir=LABEL_DIR, prefix=".llm-export-") as directory:
        stage = Path(directory)
        write_labels(stage / "llm.csv", labels, extra)
        with (stage / "llm_log.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for k in sorted(keys):
                rec = {x: v for x, v in done[k].items() if x not in ("user_prompt", "request")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        (stage / "llm_system_prompt.txt").write_text(prompts.pop() + "\n", encoding="utf-8", newline="\n")
        for name in ("llm.csv", "llm_log.jsonl", "llm_system_prompt.txt"):
            os.replace(stage / name, LABEL_DIR / name)
    n_bad = sum(1 for k in keys if done[k]["status"] != "ok")
    print(f"complete: labelled {len(keys)}/{len(rows)} reviews, invalid outputs: {n_bad}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--finalise-only", action="store_true")
    ap.add_argument("--new-run", action="store_true", help="authorise new attempts for unverifiable legacy records; keep history")
    ap.add_argument("--reference-first", action="store_true", help="label the reference sample before the rest")
    args = ap.parse_args()
    if args.limit is not None and args.limit < 0:
        ap.error("--limit must be nonnegative")
    if not args.model.strip():
        ap.error("--model must not be empty")
    if args.new_run and args.finalise_only:
        ap.error("--new-run cannot be combined with --finalise-only")
    rows = read_csv(WORK_DIR / "reviews_full.csv")
    keys = [r["review_key"] for r in rows]
    if not keys or any(not k for k in keys) or len(set(keys)) != len(keys):
        raise ValueError("reviews must have nonempty, unique keys")
    requests = {r["review_key"]: llm.build_request(args.model, r["title"], r["text"]) for r in rows}
    history = load_log()
    done = _selected(requests, history)
    legacy = {r["review_key"] for r in history if "request_sha256" not in r} & (set(keys) - set(done))
    if legacy and not args.new_run:
        raise ValueError(f"{len(legacy)} legacy reviews lack complete request identity; use --new-run to label them explicitly")
    if not args.finalise_only:
        first = {r["review_key"] for r in read_csv(LABEL_DIR / "reference_sample.csv")} if args.reference_first else set()
        todo = [r for r in rows if r["review_key"] not in done]
        todo = sorted(todo, key=lambda r: r["review_key"] not in first)[: args.limit]  # stable: reference first
        FULL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FULL_LOG, "a", encoding="utf-8", newline="\n") as f:
            if todo and FULL_LOG.stat().st_size:
                with FULL_LOG.open("rb") as existing:
                    existing.seek(-1, os.SEEK_END)
                    if existing.read(1) != b"\n":
                        f.write("\n")
            for i, r in enumerate(todo, 1):
                rec = label_one(args.model, r["review_key"], r["title"], r["text"], request=requests[r["review_key"]])
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                done[r["review_key"]] = rec
                if i % 25 == 0:
                    print(f"{i}/{len(todo)} last {rec['seconds']}s status={rec['status']}", flush=True)
    if len(done) != len(rows) and not args.finalise_only:
        print(f"incomplete: labelled {len(done)}/{len(rows)} current requests; exports were not changed")
        return 2
    finalise(rows, done, requests)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as exc:
        sys.exit(f"label run failed: {exc}")
