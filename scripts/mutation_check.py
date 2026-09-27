"""Mutation-test the test suite: break the code on purpose, confirm the tests notice.

Each mutation is an exact, single-occurrence text replacement in one source file. For each one
the script (1) requires the selected tests to PASS on clean code, (2) applies the mutation and
requires them to FAIL, (3) restores the file byte-for-byte (and verifies the restore).
A mutation whose target text is not found exactly once is an error, not a silent skip.

    python scripts/mutation_check.py            # all mutations, writes MUTATION.md
    python scripts/mutation_check.py --only M3  # one mutation, no MUTATION.md
"""
import argparse
import hashlib
import subprocess
import sys
import time
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


def run_tests(tests: str) -> bool:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests.split()]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    muts = [m for m in MUTATIONS if args.only in (None, m[0])]
    results = []
    for mid, rel, old, new, desc, tests in [EQUIVALENT] + muts:
        path = ROOT / rel
        original = path.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        text = original.decode("utf-8")
        count = text.count(old)
        if count != 1:
            sys.exit(f"{mid}: target text found {count} times in {rel} (must be exactly 1)")
        if not run_tests(tests):
            sys.exit(f"{mid}: tests fail on CLEAN code: {tests}")
        t0 = time.time()
        try:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            killed = not run_tests(tests)
        finally:
            path.write_bytes(original)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            sys.exit(f"{mid}: restore failed for {rel}")
        print(f"{mid} {'KILLED' if killed else 'SURVIVED'}  {desc}", flush=True)
        if mid == EQUIVALENT[0]:
            if killed:
                sys.exit("harness self-test failed: an equivalent (comment-only) edit was reported as killed")
            continue
        results.append((mid, rel, desc, tests, killed, time.time() - t0))
    n_killed = sum(r[4] for r in results)
    print(f"{n_killed}/{len(results)} mutations killed")
    if args.only is None:
        lines = ["# Mutation check", "",
                 "Generated by `python scripts/mutation_check.py`. Each row is one deliberate bug, applied alone;",
                 "the tests listed must pass on clean code and fail on the mutated code (\"killed\").",
                 "Before the real mutations, the harness applies a behaviour-preserving edit (M0, a docstring change)",
                 "and requires it to survive, so a harness that reports everything as killed would stop here.", "",
                 f"**{n_killed}/{len(results)} killed.**", "",
                 "History: the first full run (2026-09-27) killed 26/27. M2 survived because the only test of",
                 "the Han-character weighting used a string that is classified the same way with or without the",
                 "weight (a tie broken alphabetically). A discriminating case was added to tests/test_text.py and",
                 "the table below is the re-run.", "",
                 "| id | file | injected bug | tests | result |", "|---|---|---|---|---|"]
        for mid, rel, desc, tests, killed, _ in results:
            lines.append(f"| {mid} | `{rel}` | {desc} | `{tests}` | {'killed' if killed else '**SURVIVED**'} |")
        (ROOT / "MUTATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    sys.exit(0 if n_killed == len(results) else 1)


if __name__ == "__main__":
    main()
