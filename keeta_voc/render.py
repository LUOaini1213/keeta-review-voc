"""Tiny template engine for README/REPORT: every number in the docs comes from a results file.

Placeholders:
  {{ path.to.value | fmt }}  value looked up in the context dict (dotted path), then formatted
  {{ table:name }}           a Markdown table produced by a registered function
  {{ quote:id }}             a short anonymised excerpt from data/derived/excerpts.json

Literal digits outside placeholders are audited by scripts/check_numbers.py.
"""
from __future__ import annotations

import re

PLACEHOLDER = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class RenderError(KeyError):
    pass


def lookup(ctx: dict, path: str):
    cur = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            cur = cur[int(part)]
        else:
            raise RenderError(f"no value at {path!r} (stuck at {part!r})")
    return cur


def _dash(a: str, b: str) -> str:
    return f"{a}–{b}"


FORMATS = {
    "int": lambda v: f"{int(v):,}",
    "raw": lambda v: str(v),
    "f1": lambda v: f"{v:.1f}",
    "f2": lambda v: f"{v:.2f}",
    "pct0": lambda v: f"{100 * v:.0f}%",
    "pct1": lambda v: f"{100 * v:.1f}%",
    "pp0": lambda v: f"{100 * v:+.0f} pp",
    "ci_pct0": lambda v: "[" + _dash(f"{100 * v[0]:.0f}", f"{100 * v[1]:.0f}%") + "]",
    "ci_f2": lambda v: "[" + _dash(f"{v[0]:.2f}", f"{v[1]:.2f}") + "]",
    "ci_int": lambda v: _dash(f"{int(v[0])}", f"{int(v[1])}"),
}


def render(template: str, ctx: dict, tables: dict | None = None, quotes: dict | None = None) -> str:
    tables, quotes = tables or {}, quotes or {}

    def sub(m):
        expr = m.group(1)
        if expr.startswith("table:"):
            name = expr[6:].strip()
            if name not in tables:
                raise RenderError(f"unknown table {name!r}")
            return tables[name]()
        if expr.startswith("quote:"):
            qid = expr[6:].strip()
            if qid not in quotes:
                raise RenderError(f"unknown quote {qid!r}")
            return quotes[qid]
        path, _, fmt = (x.strip() for x in expr.partition("|"))
        fmt = fmt or "raw"
        if fmt not in FORMATS:
            raise RenderError(f"unknown format {fmt!r}")
        value = lookup(ctx, path)
        if value is None:
            return "n/a"
        return FORMATS[fmt](value)

    return PLACEHOLDER.sub(sub, template)


def literal_numbers(template: str) -> list[tuple[int, str]]:
    """(line number, token) for every digit run written literally in the template."""
    out = []
    for i, line in enumerate(template.splitlines(), 1):
        stripped = PLACEHOLDER.sub(" ", line)
        out += [(i, t) for t in NUMBER.findall(stripped)]
    return out
