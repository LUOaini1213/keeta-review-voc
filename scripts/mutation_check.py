"""Mutation-test the test suite: break the code on purpose, confirm the tests notice.

Each mutation runs in a temporary copy, leaving the working tree untouched. Clean tests must
pass; only actual test failures kill a mutation. Syntax, collection, fixture, timeout and runner
errors are inconclusive and fail this check. JUnit reports and logs are retained for inspection.

    python scripts/mutation_check.py            # all mutations, writes MUTATION.md
    python scripts/mutation_check.py --only M3  # one mutation, no MUTATION.md
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (id, file, original text, mutated text, what the bug means, tests to run)
MUTATIONS = [
    ("M1", "keeta_voc/text.py", '"\\u0629": "\\u0647"', '"\\u0629": "\\u0629"',
     "ta marbuta no longer normalised (Arabic keywords silently miss)", "tests/test_text.py tests/test_rules.py"),
    ("M2", "keeta_voc/text.py", 'weights = {"ar": c["ar"], "zh": 3 * c["zh"], "latin": c["latin"]}',
     'weights = {"ar": c["ar"], "zh": c["zh"], "latin": c["latin"]}',
     "Han characters weighted like single letters", "tests/test_text.py"),
    ("M3", "keeta_voc/text.py", 'return "en" if words & _EN_WORDS else "other"', 'return "en"',
     "any Latin-script text is called English", "tests/test_text.py"),
    ("M4", "keeta_voc/text.py", "return t.astimezone(dt.timezone.utc).date().isoformat()",
     "return t.date().isoformat()", "review date kept in Apple's local offset, not UTC", "tests/test_text.py"),
    ("M5", "keeta_voc/rules.py", 'r"(?<![a-z0-9])(?:" + "|".join(en) + r")(?![a-z0-9])"', 'r"(?:" + "|".join(en) + r")"',
     "English keywords match inside other words", "tests/test_rules.py"),
    ("M6", "keeta_voc/rules.py", "            if not _negated_token(text[:m.start()], en_neg):\n",
     "            if True:\n", "negation ignored for English praise", "tests/test_rules.py"),
    ("M7", "keeta_voc/rules.py", 'NEG_WINDOW_TOKENS = 2', 'NEG_WINDOW_TOKENS = 12',
     "negation window so wide that distant negators cancel praise", "tests/test_rules.py"),
    ("M8", "keeta_voc/rules.py", 's = match_form(f"{title} . {text}")', 's = match_form(text)',
     "review title ignored", "tests/test_rules.py"),
    ("M9", "keeta_voc/taxonomy.py", "    if OTHER in uniq and len(uniq) > 1:\n", "    if False:\n",
     "'other' may be combined with real labels", "tests/test_taxonomy.py tests/test_llm_parse.py"),
    ("M10", "keeta_voc/taxonomy.py", '        if x not in names:\n            raise InvalidLabels(f"unknown label {x!r}")',
     '        if x not in names:\n            continue', "unknown LLM labels silently accepted",
     "tests/test_taxonomy.py tests/test_llm_parse.py"),
    ("M11", "keeta_voc/llm.py", 'return "bad_json", None, "missing \'labels\' key"', 'return "ok", [], None',
     "JSON without a labels key counted as a valid empty answer", "tests/test_llm_parse.py"),
    ("M12", "keeta_voc/llm.py", '"temperature": 0,', '"temperature": 0.8,', "LLM sampling no longer deterministic",
     "tests/test_llm_parse.py"),
    ("M13", "keeta_voc/fetch.py", 'return hashlib.sha256(f"{storefront}:{apple_review_id}".encode("utf-8")).hexdigest()[:16]',
     'return f"{storefront}:{apple_review_id}"', "raw Apple review id stored instead of a hash", "tests/test_fetch.py"),
    ("M14", "keeta_voc/fetch.py", "            variant = attempt - 1", "            variant = 0",
     "retries keep hitting the same (empty) URL spelling", "tests/test_fetch.py"),
    ("M15", "keeta_voc/evaluate.py", "    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float(\"nan\")",
     "    f1 = 2 * tp / (2 * tp + fp + fn + 1) if (2 * tp + fp + fn) else float(\"nan\")", "F1 off by a smoothing term",
     "tests/test_evaluate.py"),
    ("M16", "keeta_voc/evaluate.py", "    pe = py1 * pp1 + (1 - py1) * (1 - pp1)", "    pe = py1 * pp1",
     "kappa chance agreement ignores the negative class", "tests/test_evaluate.py"),
    ("M17", "keeta_voc/evaluate.py", "            m[i, idx[lab]] = 1", "            m[i, idx[lab]] = 1 if lab != 'other' else 0",
     "'other' predictions dropped from the label matrix", "tests/test_evaluate.py"),
    ("M18", "sql/04_pain_points.sql", "WHERE r.rating <= 2", "WHERE r.rating <= 3",
     "3-star reviews counted as complaints (SQL only)", "tests/test_sql_vs_pandas.py"),
    ("M19", "sql/02_issue_share_by_storefront.sql", "SELECT r.* FROM reviews r JOIN labelled USING (review_key)",
     "SELECT r.* FROM reviews r", "reviews without valid labels kept in the denominator (SQL only)",
     "tests/test_sql_vs_pandas.py"),
    ("M20", "keeta_voc/metrics_pd.py", 'rank(method="min", ascending=False)', 'rank(method="first", ascending=False)',
     "tied pain points broken arbitrarily (pandas only)", "tests/test_sql_vs_pandas.py"),
    ("M21", "keeta_voc/stats.py", "    den = 1 + z * z / n", "    den = 1", "Wilson interval loses its denominator",
     "tests/test_stats.py"),
    ("M22", "keeta_voc/stats.py", "ranks = 1 + (shares[:, None, :] > shares[:, :, None]).sum(axis=2)",
     "ranks = 1 + (shares[:, None, :] < shares[:, :, None]).sum(axis=2)", "bootstrap ranks inverted",
     "tests/test_stats.py"),
    ("M23", "keeta_voc/render.py", '    "pct1": lambda v: f"{100 * v:.1f}%",', '    "pct1": lambda v: f"{v:.1f}%",',
     "percentages rendered without x100", "tests/test_check_numbers.py"),
    ("M24", "scripts/check_numbers.py", "        if current != rendered[doc]:", "        if False:",
     "check_numbers --check never compares the docs", "tests/test_check_numbers.py"),
    ("M25", "scripts/check_numbers.py", "        bad = [(i, t) for i, t in literal_numbers(tmpl) if t not in ALLOWED_LITERALS]",
     "        bad = []", "hand-typed numbers in templates no longer flagged", "tests/test_check_numbers.py"),
    ("M26", "keeta_voc/dataset.py", '            dropped["duplicate"] += 1\n            continue',
     '            dropped["duplicate"] += 1', "duplicate reviews kept", "tests/test_dataset.py"),
    ("M27", "keeta_voc/frames.py", "            bad = ~np.isclose(a, b, rtol=0, atol=tol)", "            bad = ~np.isclose(a, b, rtol=0.01, atol=tol)",
     "SQL-vs-pandas check tolerates 1% differences", "tests/test_sql_vs_pandas.py"),
]


# Harness self-test: a behaviour-preserving edit (a comment) that the tests must NOT flag.
# If it were reported "killed", the harness would be counting something other than test failures.
EQUIVALENT = ("M0", "keeta_voc/stats.py", '    """Wilson score interval for a binomial proportion k/n."""',
              '    """Wilson score interval for a binomial proportion k/n (harness self-test edit)."""',
              "equivalent edit (docstring only) - must SURVIVE", "tests/test_stats.py")


def classify_report(returncode: int, report: Path) -> dict:
    """A pytest exit code alone cannot distinguish a killed mutant from a broken runner."""
    result = {"outcome": "error", "returncode": returncode,
              "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError) as exc:
        return {**result, "reason": f"missing or invalid JUnit report: {type(exc).__name__}"}
    if root.tag not in ("testsuites", "testsuite"):
        return {**result, "reason": "unexpected JUnit root"}
    for case in root.iter("testcase"):
        if case.find("error") is not None:
            result["errors"] += 1
        elif case.find("failure") is not None:
            result["failed"] += 1
        elif case.find("skipped") is not None:
            result["skipped"] += 1
        else:
            result["passed"] += 1
    if result["errors"]:
        result["reason"] = "collection, setup or teardown error"
    elif returncode == 0 and result["passed"] > 0 and result["failed"] == 0:
        result["outcome"] = "passed"
    elif returncode == 1 and result["failed"] > 0:
        result["outcome"] = "failed"
    else:
        result["reason"] = "no executed tests or inconsistent pytest result"
    return result


def run_tests(tests: str, cwd: Path, evidence: Path, timeout: float) -> dict:
    evidence.mkdir(parents=True, exist_ok=False)
    report = evidence / "junit.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
           f"--junitxml={report}", *tests.split()]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(cwd)}
    # Host add-ons must not change the meaning of this project's test run.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    t0 = time.monotonic()
    try:
        group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                 else {"start_new_session": True})
        with subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, **group) as process:
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                result = classify_report(process.returncode, report)
            except subprocess.TimeoutExpired:
                # A Windows venv launcher has a child Python process. Killing only the
                # launcher leaves pytest (and its children) alive in the temporary copy.
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=15)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                stdout, stderr = process.communicate(timeout=15)
                result = {"outcome": "error", "reason": "timeout", "returncode": None}
        (evidence / "stdout.log").write_bytes(stdout)
        (evidence / "stderr.log").write_bytes(stderr)
    except OSError as exc:
        result = {"outcome": "error", "reason": f"runner error: {type(exc).__name__}",
                  "returncode": None}
    result["seconds"] = round(time.monotonic() - t0, 3)
    (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def copy_snapshot(source: Path, target: Path, output_dir: Path) -> None:
    def ignore(directory, names):
        return [name for name in names if name in
                {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules",
                 "mutation-artifacts", ".mutation_backup"}
                or name.endswith(".pyc") or (Path(directory) / name).resolve() == output_dir.resolve()
                or (Path(directory) == source / "data" and name in {"raw", "work"})]
    shutil.copytree(source, target, ignore=ignore)


def check_mutations(source: Path, mutations: list, equivalent: tuple,
                    output_dir: Path, timeout: float = 120) -> dict:
    """Run a frozen source copy and a fresh copy for every variant, even on interruption."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # Separate run directories prevent stale XML from converting a runner error into a kill.
    evidence = Path(tempfile.mkdtemp(prefix="run-", dir=output_dir)).resolve()
    summary = {"schema_version": 2, "status": "failed", "equivalent": None,
               "results": [], "source_sha256": {}}
    with tempfile.TemporaryDirectory(prefix="keeta-mutations-") as tmp:
        snapshot = Path(tmp) / "snapshot"
        copy_snapshot(source, snapshot, output_dir)
        for index, (mid, rel, old, new, desc, tests) in enumerate([equivalent] + mutations):
            entry = {"id": mid, "file": rel, "description": desc, "tests": tests,
                     "outcome": "error"}
            original = (snapshot / rel).read_bytes()
            summary["source_sha256"][rel] = hashlib.sha256(original).hexdigest()
            code = original.decode("utf-8")
            if code.count(old) != 1:
                entry["reason"] = f"target found {code.count(old)} times (must be exactly 1)"
            else:
                variant = Path(tmp) / f"variant-{index}"
                copy_snapshot(snapshot, variant, output_dir)
                baseline = run_tests(tests, variant, evidence / f"{mid}-baseline", timeout)
                entry["baseline"] = baseline
                if baseline["outcome"] != "passed":
                    entry["reason"] = "clean baseline did not pass"
                else:
                    changed = code.replace(old, new)
                    try:
                        if Path(rel).suffix == ".py":
                            compile(changed, rel, "exec")
                    except (SyntaxError, ValueError) as exc:
                        entry["reason"] = f"invalid mutation: {type(exc).__name__}"
                    else:
                        (variant / rel).write_bytes(changed.encode("utf-8"))
                        trial = run_tests(tests, variant, evidence / f"{mid}-mutation", timeout)
                        entry["mutation"] = trial
                        entry["outcome"] = {"passed": "survived", "failed": "killed",
                                            "error": "error"}[trial["outcome"]]
                        if trial["outcome"] == "error":
                            entry["reason"] = trial["reason"]
            print(f"{mid} {entry['outcome'].upper()}  {desc}", flush=True)
            if index == 0:
                summary["equivalent"] = entry
                if entry["outcome"] != "survived":
                    break
            else:
                summary["results"].append(entry)
        summary["killed"] = sum(x["outcome"] == "killed" for x in summary["results"])
        summary["requested"] = len(mutations)
        if (summary["equivalent"]["outcome"] == "survived" and mutations
                and summary["killed"] == len(mutations)):
            summary["status"] = "passed"
    (evidence / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{summary['killed']}/{len(mutations)} killed; evidence: {evidence}", flush=True)
    return summary


def report_markdown(summary: dict) -> str:
    lines = ["# Mutation check", "",
             "Generated by `python scripts/mutation_check.py`. Every mutation runs alone in a",
             "temporary source copy after its selected tests pass on clean code. Only test-call",
             "failures count as kills; syntax, collection, fixture, runner and timeout errors fail",
             "the check. M0 is a docstring-only control and must survive. Working files are never mutated.", "",
             f"**{summary['killed']}/{summary['requested']} killed; check {summary['status']}.**", "",
             "JUnit, stdout, stderr, source hashes and a JSON manifest are saved under",
             "`mutation-artifacts/run-*/`; CI uploads these files as an artifact.", "",
             "History: the original 2026-09-27 run reported 26/27, followed by 27/27 after a",
             "discriminating Han-character weighting test was added. That older harness treated",
             "any nonzero pytest exit as a kill; the current run below uses the stricter classification.", "",
             "| id | file | injected bug | tests | result |", "|---|---|---|---|---|"]
    for entry in [summary["equivalent"]] + summary["results"]:
        outcome = entry["outcome"]
        if entry.get("reason"):
            outcome += ": " + entry["reason"]
        lines.append(f"| {entry['id']} | `{entry['file']}` | {entry['description']} | "
                     f"`{entry['tests']}` | {outcome} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=[m[0] for m in MUTATIONS])
    ap.add_argument("--output-dir", type=Path, default=ROOT / "mutation-artifacts")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--no-report", action="store_true", help="do not update MUTATION.md")
    args = ap.parse_args()
    if args.timeout <= 0:
        ap.error("--timeout must be positive")
    muts = [m for m in MUTATIONS if args.only in (None, m[0])]
    summary = check_mutations(ROOT, muts, EQUIVALENT, args.output_dir.resolve(), args.timeout)
    if args.only is None and not args.no_report:
        (ROOT / "MUTATION.md").write_text(report_markdown(summary), encoding="utf-8", newline="\n")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
