"""Method 1: keyword/rule baseline (English regex, Arabic and Chinese substrings)."""
from __future__ import annotations

import re
from functools import lru_cache

from .taxonomy import finalise, load_taxonomy
from .text import match_form, normalise_arabic

PRAISE = "positive_praise"
NEG_WINDOW_TOKENS = 2   # en/ar: negator within the 2 preceding tokens cancels a praise hit
NEG_WINDOW_CHARS = 1    # zh: negator immediately before the praise term


@lru_cache(maxsize=None)
def _compiled():
    tax = load_taxonomy()
    out = {}
    for name, spec in tax["labels"].items():
        kw = spec.get("keywords") or {}
        en = kw.get("en") or []
        en_re = re.compile(r"(?<![a-z0-9])(?:" + "|".join(en) + r")(?![a-z0-9])") if en else None
        ar = tuple(normalise_arabic(w).lower() for w in (kw.get("ar") or []))
        zh = tuple(kw.get("zh") or [])
        out[name] = (en_re, ar, zh)
    neg = tax.get("negation", {})
    negs = (frozenset(neg.get("en", [])), frozenset(normalise_arabic(w) for w in neg.get("ar", [])),
            tuple(neg.get("zh", [])))
    return out, negs


def _negated_token(prefix: str, negators: frozenset) -> bool:
    toks = re.findall(r"[\w']+", prefix)[-NEG_WINDOW_TOKENS:]
    return any(t in negators or t.endswith("n't") for t in toks)


def _praise_hit(text: str, en_re, ar, zh, negs) -> bool:
    en_neg, ar_neg, zh_neg = negs
    if en_re:
        for m in en_re.finditer(text):
            if not _negated_token(text[:m.start()], en_neg):
                return True
    for w in ar:
        for m in re.finditer(re.escape(w), text):
            if not _negated_token(text[:m.start()], ar_neg):
                return True
    for w in zh:
        for m in re.finditer(re.escape(w), text):
            before = text[max(0, m.start() - NEG_WINDOW_CHARS):m.start()]
            if not any(n in before for n in zh_neg):
                return True
    return False


def rule_labels(title: str, text: str) -> list[str]:
    """Label a review from its title + body. Returns a validated, taxonomy-ordered list."""
    s = match_form(f"{title} . {text}")
    compiled, negs = _compiled()
    hits = set()
    for name, (en_re, ar, zh) in compiled.items():
        if name == PRAISE:
            if _praise_hit(s, en_re, ar, zh, negs):
                hits.add(name)
            continue
        if (en_re and en_re.search(s)) or any(w in s for w in ar) or any(w in s for w in zh):
            hits.add(name)
    return finalise(hits)
