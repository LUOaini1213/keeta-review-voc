"""Text cleaning, Arabic normalisation and a lightweight script-based language detector."""
from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")
_WS = re.compile(r"\s+")
_AR_DIACRITICS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_AR_MAP = str.maketrans({"\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627", "\u0671": "\u0627",
                         "\u0649": "\u064a", "\u0629": "\u0647", "\u0624": "\u0648", "\u0626": "\u064a",
                         "\u0640": None})


def clean_text(s: str | None) -> str:
    """NFKC (folds Arabic presentation forms and full-width Latin), strip zero-width/bidi
    control characters, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = _ZERO_WIDTH.sub("", s)
    return _WS.sub(" ", s).strip()


def normalise_arabic(s: str) -> str:
    """Matching form for Arabic: drop diacritics and tatweel, unify alef / ya / ta marbuta / hamza seats."""
    return _AR_DIACRITICS.sub("", s).translate(_AR_MAP)


def match_form(s: str) -> str:
    """Lower-cased, Arabic-normalised form used by the rule labeler."""
    return normalise_arabic(clean_text(s)).lower()


def _is_arabic(ch: str) -> bool:
    o = ord(ch)
    return 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0x08A0 <= o <= 0x08FF or 0xFB50 <= o <= 0xFDFF \
        or 0xFE70 <= o <= 0xFEFF


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2A6DF


_EN_WORDS = frozenset("""the a an and or but is are was were be been it this that i you he she we they my your
their our to of in on for with at by from not no very so too good bad app order food delivery service
great best worst love hate always never time late fast slow customer driver please thank thanks""".split())


def script_counts(s: str) -> dict[str, int]:
    c = {"ar": 0, "zh": 0, "latin": 0}
    for ch in s:
        if _is_arabic(ch):
            c["ar"] += 1
        elif _is_cjk(ch):
            c["zh"] += 1
        elif ch.isascii() and ch.isalpha():
            c["latin"] += 1
    return c


def detect_language(s: str) -> str:
    """Return 'ar', 'en', 'zh' or 'other'.

    Script majority among letters, weighting each CJK character as 3 letters (one Han
    character carries roughly a word). Latin-script text is 'en' only if it contains at least
    one common English function/content word, otherwise 'other' (e.g. Arabizi, Tagalog).
    Text with no letters (emoji, digits) is 'other'.
    """
    s = clean_text(s)
    c = script_counts(s)
    weights = {"ar": c["ar"], "zh": 3 * c["zh"], "latin": c["latin"]}
    if sum(weights.values()) == 0:
        return "other"
    top = max(weights, key=lambda k: (weights[k], k))
    if top == "ar":
        return "ar"
    if top == "zh":
        return "zh"
    words = set(re.findall(r"[a-z']+", s.lower()))
    return "en" if words & _EN_WORDS else "other"


def review_date(updated: str) -> str:
    """'2026-09-25T11:46:41-07:00' -> '2026-09-25' in UTC."""
    import datetime as dt

    t = dt.datetime.fromisoformat(updated)
    return t.astimezone(dt.timezone.utc).date().isoformat()
