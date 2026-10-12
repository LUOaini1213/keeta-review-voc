"""Exercise the real CLI functions using isolated logs and a counted fake model."""
import csv
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from keeta_voc import llm
from keeta_voc.dataset import read_csv


@pytest.fixture
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("resume_script", Path(__file__).parents[1] / "scripts/label_llm.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    work, labels = tmp_path / "work", tmp_path / "labels"
    work.mkdir()
    labels.mkdir()
    monkeypatch.setattr(script, "WORK_DIR", work)
    monkeypatch.setattr(script, "LABEL_DIR", labels)
    monkeypatch.setattr(script, "FULL_LOG", work / "llm_log_full.jsonl")
    calls, responses = [], []

    def call(request):
        calls.append(request)
        raw = responses.pop(0) if responses else '{"labels":["app_ux"]}'
        if isinstance(raw, Exception):
            raise raw
        return {"message": {"content": raw}}

    def label(*args, **kwargs):
        return llm.label_one(*args, **kwargs, call=call)

    monkeypatch.setattr(script, "label_one", label)

    def rows(values):
        with (work / "reviews_full.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["review_key", "title", "text"])
            writer.writeheader()
            writer.writerows(values)

    def run(*args):
        monkeypatch.setattr(sys, "argv", ["label_llm.py", *args])
        return script.main()

    rows([{"review_key": "r1", "title": "Title", "text": "The app crashes"}])
    return script, rows, run, calls, responses


@pytest.mark.parametrize("raw,status", [("not JSON", "bad_json"), ('{"labels":[]}', "bad_labels"),
                                       (TimeoutError("offline fake"), "http_error")])
def test_identical_request_reuses_result_and_keeps_invalid_attempts(runner, raw, status):
    script, _, run, calls, responses = runner
    responses.append(raw)
    run("--model", "model-a")
    run("--model", "model-a", "--new-run")
    before = script.FULL_LOG.read_bytes()
    run("--model", "model-a")
    assert len(calls) == 1
    assert script.FULL_LOG.read_bytes() == before
    assert read_csv(script.LABEL_DIR / "llm.csv") == [{"review_key": "r1", "labels": "", "status": status}]


@pytest.mark.parametrize("change", ["model", "title", "text", "system", "options", "schema"])
def test_request_changes_cannot_hit_old_cache(runner, monkeypatch, change):
    script, rows, run, calls, _ = runner
    run("--model", "model-a")
    first = script.FULL_LOG.read_bytes()
    model = "model-a"
    if change == "model":
        model = "model-b"
    elif change in ("title", "text"):
        row = {"review_key": "r1", "title": "Title", "text": "The app crashes"}
        row[change] = "A different review"
        rows([row])
    elif change == "system":
        monkeypatch.setattr(llm, "system_prompt", lambda: "New system instructions")
    elif change == "options":
        original = llm.build_request
        def changed(*args, **kwargs):
            request = original(*args, **kwargs)
            request["options"]["seed"] = 17
            return request
        monkeypatch.setattr(llm, "build_request", changed)
    else:
        original = llm.response_schema
        monkeypatch.setattr(llm, "response_schema", lambda: {**original(), "additionalProperties": False})
    run("--model", model)
    assert len(calls) == 2
    assert script.FULL_LOG.read_bytes().startswith(first)
    records = [json.loads(line) for line in script.FULL_LOG.read_text().splitlines()]
    assert len(records) == 2 and records[0]["request_sha256"] != records[1]["request_sha256"]
    exported = json.loads((script.LABEL_DIR / "llm_log.jsonl").read_text())
    assert exported["request_sha256"] == records[-1]["request_sha256"]
    assert "request" not in exported and "user_prompt" not in exported


def test_finalise_only_rejects_stale_request_without_touching_exports(runner):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    before = {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()}
    with pytest.raises((ValueError, SystemExit)):
        run("--model", "model-b", "--finalise-only")
    assert len(calls) == 1
    assert {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()} == before


def test_legacy_log_requires_explicit_new_run_and_preserves_history(runner):
    script, _, run, calls, _ = runner
    legacy = llm.label_one("model-a", "r1", "Title", "The app crashes", call=lambda r: {"message": {"content": "bad"}})
    legacy.pop("request", None)
    legacy.pop("request_sha256", None)
    original = (json.dumps(legacy) + "\n").encode()
    script.FULL_LOG.write_bytes(original)
    for args in ((), ("--finalise-only",)):
        with pytest.raises((ValueError, SystemExit)):
            run("--model", "model-a", *args)
    assert calls == [] and script.FULL_LOG.read_bytes() == original
    run("--model", "model-a", "--new-run")
    assert len(calls) == 1 and script.FULL_LOG.read_bytes().startswith(original)
    run("--model", "model-a")
    assert len(calls) == 1


def test_truncated_last_record_is_quarantined_and_resume_keeps_complete_history(runner):
    script, rows, run, calls, _ = runner
    run("--model", "model-a")
    complete = script.FULL_LOG.read_bytes()
    tail = b'{"review_key":"r2","text":"\xe4\xb8'
    script.FULL_LOG.write_bytes(complete + tail)
    rows([{"review_key": "r1", "title": "Title", "text": "The app crashes"},
          {"review_key": "r2", "title": "Another", "text": "Slow app"}])
    run("--model", "model-a")
    assert len(calls) == 2
    assert script.FULL_LOG.read_bytes().startswith(complete)
    assert len(script.FULL_LOG.read_text().splitlines()) == 2
    assert any(p.read_bytes() == tail for p in script.WORK_DIR.glob("*.interrupted-*"))


def test_middle_corruption_is_rejected_without_log_or_export_changes(runner):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    good = script.FULL_LOG.read_bytes()
    corrupt = good + b'{"broken":\n' + good
    script.FULL_LOG.write_bytes(corrupt)
    before = {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()}
    with pytest.raises(ValueError):
        run("--model", "model-a")
    assert len(calls) == 1 and script.FULL_LOG.read_bytes() == corrupt
    assert {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()} == before


def test_valid_last_record_without_newline_is_kept_separate_when_appending(runner):
    script, rows, run, calls, _ = runner
    run("--model", "model-a")
    first = script.FULL_LOG.read_bytes().rstrip(b"\n")
    script.FULL_LOG.write_bytes(first)
    rows([{"review_key": "r1", "title": "Title", "text": "The app crashes"},
          {"review_key": "r2", "title": "Another", "text": "Slow app"}])
    run("--model", "model-a")
    assert len(calls) == 2
    assert script.FULL_LOG.read_bytes().startswith(first + b"\n")
    assert len([json.loads(line) for line in script.FULL_LOG.read_text().splitlines()]) == 2


def test_partial_run_preserves_prior_exports_until_all_current_rows_are_labelled(runner, capsys):
    script, rows, run, calls, _ = runner
    old = b"prior complete output\n"
    (script.LABEL_DIR / "llm.csv").write_bytes(old)
    rows([{"review_key": "r1", "title": "Title", "text": "The app crashes"},
          {"review_key": "r2", "title": "Another", "text": "Slow app"}])
    assert run("--model", "model-a", "--limit", "1") == 2
    assert len(calls) == 1
    assert (script.LABEL_DIR / "llm.csv").read_bytes() == old
    assert "incomplete" in capsys.readouterr().out.lower()
    with pytest.raises((ValueError, SystemExit)):
        run("--model", "model-a", "--finalise-only")
    run("--model", "model-a")
    assert len(calls) == 2 and len(read_csv(script.LABEL_DIR / "llm.csv")) == 2


@pytest.mark.parametrize("limit", ["-1", "1.5", "not-a-number"])
def test_invalid_limit_is_rejected_before_calls_or_output(runner, limit):
    script, _, run, calls, _ = runner
    with pytest.raises(SystemExit):
        run("--limit", limit)
    assert calls == [] and not script.FULL_LOG.exists()
    assert list(script.LABEL_DIR.iterdir()) == []


def test_tampered_request_fingerprint_is_not_silently_reused(runner):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    rec = json.loads(script.FULL_LOG.read_text())
    rec["request_sha256"] = "0" * 64
    script.FULL_LOG.write_text(json.dumps(rec) + "\n")
    with pytest.raises(ValueError):
        run("--model", "model-a")
    assert len(calls) == 1


@pytest.mark.parametrize("bad_first", [True, False])
def test_conflicting_attempts_for_one_request_are_not_selected_by_log_order(runner, bad_first):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    good = json.loads(script.FULL_LOG.read_text())
    bad = copy.deepcopy(good)
    bad.update(raw_response="not JSON", status="bad_json", labels=None, error="invalid JSON")
    records = [bad, good] if bad_first else [good, bad]
    history = "".join(json.dumps(rec) + "\n" for rec in records).encode()
    script.FULL_LOG.write_bytes(history)
    before = {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()}
    with pytest.raises(ValueError, match="conflicting"):
        run("--model", "model-a", "--new-run")
    assert script.FULL_LOG.read_bytes() == history and len(calls) == 1
    assert {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()} == before


def test_exact_duplicate_attempt_can_be_reused_without_creating_another_call(runner):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    record = script.FULL_LOG.read_bytes()
    script.FULL_LOG.write_bytes(record + record)
    assert run("--model", "model-a", "--finalise-only") == 0
    assert len(calls) == 1 and script.FULL_LOG.read_bytes() == record + record
    assert len(read_csv(script.LABEL_DIR / "llm.csv")) == 1


def test_complete_but_malformed_last_line_is_not_treated_as_interruption(runner):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    corrupt = script.FULL_LOG.read_bytes() + b'{"incomplete":\n'
    script.FULL_LOG.write_bytes(corrupt)
    with pytest.raises(ValueError):
        run("--model", "model-a")
    assert script.FULL_LOG.read_bytes() == corrupt and len(calls) == 1
    assert list(script.WORK_DIR.glob("*.interrupted-*")) == []


def test_distinct_keys_are_not_collapsed_and_reference_priority_is_kept(runner):
    script, rows, run, calls, _ = runner
    rows([{"review_key": key, "title": "Same", "text": "Same app issue"} for key in ("r1", "r2")])
    (script.LABEL_DIR / "reference_sample.csv").write_text("review_key\nr2\n")
    assert run("--model", "model-a", "--reference-first", "--limit", "1") == 2
    assert json.loads(script.FULL_LOG.read_text())["review_key"] == "r2"
    assert run("--model", "model-a") == 0
    assert len(calls) == 2
    assert {r["review_key"] for r in read_csv(script.LABEL_DIR / "llm.csv")} == {"r1", "r2"}


def test_export_preparation_failure_preserves_all_existing_outputs(runner, monkeypatch):
    script, _, run, calls, _ = runner
    run("--model", "model-a")
    before = {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()}
    def fail(*args):
        raise OSError("synthetic export disk error")
    monkeypatch.setattr(script, "write_labels", fail)
    with pytest.raises(OSError):
        run("--model", "model-a", "--finalise-only")
    assert len(calls) == 1
    assert {p.name: p.read_bytes() for p in script.LABEL_DIR.iterdir()} == before


def test_real_cli_exit_code_blocks_downstream_work_for_partial_results(runner):
    script, rows, _, _, _ = runner
    rows([{"review_key": key, "title": "Same", "text": "Same app issue"} for key in ("r1", "r2")])
    repo = Path(__file__).resolve().parents[1]
    # Run the actual __main__ block. All I/O paths and the sole model callable
    # are injected before import; the fake writes a persistent call counter.
    code = '''
import json, runpy, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from keeta_voc import dataset, llm
dataset.WORK_DIR = Path(sys.argv[2])
dataset.LABEL_DIR = Path(sys.argv[3])
original = llm.label_one
def fake(request):
    with (dataset.WORK_DIR / 'calls.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(request) + '\\n')
    return {'message': {'content': '{"labels":["app_ux"]}'}}
llm.label_one = lambda *a, **kw: original(*a, **kw, call=fake)
path = str(Path(sys.argv[1]) / 'scripts/label_llm.py')
sys.argv = [path, '--model', 'model-a', *sys.argv[4:]]
runpy.run_path(path, run_name='__main__')
'''
    command = [sys.executable, "-B", "-c", code, str(repo), str(script.WORK_DIR), str(script.LABEL_DIR)]
    partial = subprocess.run([*command, "--limit", "1"], capture_output=True, text=True, timeout=15)
    assert partial.returncode == 2, partial.stderr
    assert "incomplete" in partial.stdout and not (script.LABEL_DIR / "llm.csv").exists()
    complete = subprocess.run(command, capture_output=True, text=True, timeout=15)
    assert complete.returncode == 0, complete.stderr
    assert "complete: labelled 2/2" in complete.stdout
    assert len((script.WORK_DIR / "calls.jsonl").read_text().splitlines()) == 2
    assert len(read_csv(script.LABEL_DIR / "llm.csv")) == 2
