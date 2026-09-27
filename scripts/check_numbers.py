"""Render README.md / REPORT.md from templates + results, and check that the committed docs match.

    python scripts/check_numbers.py --write   # regenerate README.md and REPORT.md
    python scripts/check_numbers.py --check   # fail if (a) a committed doc differs from a fresh render,
                                              # or (b) a template contains a hand-typed number that is
                                              # not on the explicit allow-list below

Every figure in the docs is a {{placeholder}} resolved from results/*.json or
data/derived/snapshot_manifest.json, so (a) catches any number edited by hand or left stale, and
(b) stops new numbers from being typed straight into the prose.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from keeta_voc.facts import build_context, build_quotes, build_tables  # noqa: E402
from keeta_voc.render import literal_numbers, render  # noqa: E402

DOCS = [("docs/templates/README.md.tmpl", "README.md"), ("docs/templates/REPORT.md.tmpl", "REPORT.md")]

# Literal digit runs allowed in the templates, each with the reason it is not a result.
ALLOWED_LITERALS = {
    "1": "star ratings (1-2 star = complaint band), list numbering",
    "2": "star ratings, list numbering",
    "3": "star ratings, list numbering, 'qwen2.5:3b' model tag, three-command reproduction",
    "4": "star ratings, list numbering",
    "5": "star ratings, list numbering",
    "95": "95% confidence level",
    "2026": "project date / snapshot year",
    "09": "project month (2026-09)",
    "3.10": "minimum Python version",
    "2.5": "model tag qwen2.5",
    "10": "Apple's RSS feed serves at most 10 pages per storefront",
    "50": "Apple's RSS feed serves 50 reviews per page",
    "500": "10 pages x 50 reviews = the feed's hard cap per storefront",
    "2000": "number of bootstrap resamples (a setting, not a result)",
    "0": "temperature 0 (a setting)",
    "6": "list / section numbering",
    "16": "length of the review key in hex characters (a setting)",
    "256": "name of the hash function SHA-256",
}


def render_all() -> dict[str, str]:
    ctx, tables, quotes = build_context(), build_tables(), build_quotes()
    out = {}
    for tmpl, doc in DOCS:
        text = (ROOT / tmpl).read_text(encoding="utf-8")
        out[doc] = render(text, ctx, tables, quotes)
    return out


def problems(root: Path = ROOT, rendered: dict[str, str] | None = None) -> list[str]:
    rendered = rendered if rendered is not None else render_all()
    errs = []
    for tmpl_rel, doc in DOCS:
        tmpl = (root / tmpl_rel).read_text(encoding="utf-8")
        bad = [(i, t) for i, t in literal_numbers(tmpl) if t not in ALLOWED_LITERALS]
        for i, t in bad:
            errs.append(f"{tmpl_rel}:{i}: hand-typed number {t!r} (use a placeholder or allow-list it)")
        path = root / doc
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered[doc]:
            cur_lines, new_lines = current.splitlines(), rendered[doc].splitlines()
            first = next((i for i, (a, b) in enumerate(zip(cur_lines, new_lines)) if a != b),
                         min(len(cur_lines), len(new_lines)))
            got = cur_lines[first] if first < len(cur_lines) else "<EOF>"
            want = new_lines[first] if first < len(new_lines) else "<EOF>"
            errs.append(f"{doc}:{first + 1}: differs from results\n  doc:     {got}\n  results: {want}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.write:
        for doc, text in render_all().items():
            (ROOT / doc).write_text(text, encoding="utf-8", newline="\n")
            print("wrote", doc)
    errs = problems()
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    print(f"OK: every number in {', '.join(d for _, d in DOCS)} matches the results files")


if __name__ == "__main__":
    main()
