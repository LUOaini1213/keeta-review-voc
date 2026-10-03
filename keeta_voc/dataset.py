"""Snapshot -> cleaned review table. Paths and I/O helpers shared by the scripts."""
from __future__ import annotations

import csv
import hashlib
import json
from numbers import Integral
from pathlib import Path

from .taxonomy import validate_labels
from .text import clean_text, detect_language, review_date

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"          # gitignored: full review text
WORK_DIR = ROOT / "data" / "work"        # gitignored: full-text working tables, full LLM log
DERIVED_DIR = ROOT / "data" / "derived"  # committed: text-free tables
LABEL_DIR = ROOT / "data" / "labels"     # committed: labels per method
RESULTS_DIR = ROOT / "results"

META_COLUMNS = ["review_key", "storefront", "rating", "app_version", "review_date", "month", "lang", "n_chars",
                "text_sha256"]
FULL_COLUMNS = META_COLUMNS + ["title", "text"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_reviews(raw_reviews: list[dict]) -> tuple[list[dict], dict]:
    """Clean, language-tag and de-duplicate. Returns (rows, drop counts)."""
    rows, seen = [], set()
    dropped = {"duplicate": 0, "empty": 0, "bad_rating": 0}
    for r in raw_reviews:
        key = r["review_key"]
        if key in seen:
            dropped["duplicate"] += 1
            continue
        title, text = clean_text(r.get("title")), clean_text(r.get("text"))
        if not (title or text):
            dropped["empty"] += 1
            continue
        value = r.get("rating")
        # Snapshot ratings may be integer strings. Never round floats or treat True as 1.
        rating = int(value) if ((isinstance(value, Integral) and not isinstance(value, bool))
                                or (isinstance(value, str) and value in ("1", "2", "3", "4", "5"))) else 0
        if not 1 <= rating <= 5:
            dropped["bad_rating"] += 1
            continue
        seen.add(key)
        combined = f"{title}\n{text}"
        day = review_date(r["updated"])
        rows.append({
            "review_key": key,
            "storefront": r["storefront"],
            "rating": rating,
            "app_version": r.get("app_version") or "unknown",
            "review_date": day,
            "month": day[:7],
            # The body decides the language; the title is used only if the body has no letters.
            "lang": detect_language(text) if detect_language(text) != "other" else detect_language(combined),
            "n_chars": len(combined),
            "text_sha256": hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16],
            "title": title,
            "text": text,
        })
    rows.sort(key=lambda x: (x["storefront"], x["review_date"], x["review_key"]))
    return rows, dropped


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_snapshot(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest_snapshot() -> Path:
    snaps = sorted(RAW_DIR.glob("snapshot_*.json"))
    if not snaps:
        raise FileNotFoundError("no snapshot in data/raw; run scripts/fetch_reviews.py first")
    return snaps[-1]


def keyed_rows(rows: list[dict], source: str) -> dict[str, dict]:
    """Index a CSV cohort without silently overwriting a repeated or missing key."""
    out = {}
    for r in rows:
        key = r.get("review_key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{source}: review_key must be a nonempty string")
        if key in out:
            raise ValueError(f"{source}: duplicate review_key {key!r}")
        out[key] = r
    return out


def read_keyed_csv(path: Path) -> dict[str, dict]:
    return keyed_rows(read_csv(path), str(path))


def require_cohort(keys, expected_keys, source: str) -> None:
    """Missing predictions must be represented explicitly by None, not absent rows."""
    keys, expected = set(keys), set(expected_keys)
    if keys != expected:
        missing, extra = sorted(expected - keys), sorted(keys - expected)
        raise ValueError(f"{source}: cohort mismatch; missing={missing[:5]!r}, extra={extra[:5]!r}")


def validate_predictions(labels: dict, expected_keys=None, source: str = "labels") -> dict:
    """Canonical label sets for a complete cohort; None is an explicit invalid prediction."""
    for key in labels:
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{source}: review_key must be a nonempty string")
    if expected_keys is not None:
        require_cohort(labels, expected_keys, source)
    return {k: None if v is None else validate_labels(v) for k, v in labels.items()}


def labels_from_rows(rows: list[dict], source: str = "labels", expected_keys=None) -> dict:
    """A non-ok status always predicts nothing, even if residual label text is present.

    Legacy CSVs without status retain the empty-field-as-None convention. A claimed ok
    prediction must instead contain a valid nonempty taxonomy label set.
    """
    out = {}
    for key, row in keyed_rows(rows, source).items():
        if "labels" not in row or row["labels"] is None:
            raise ValueError(f"{source}: missing labels field for {key!r}")
        if "status" in row and row["status"] != "ok":
            out[key] = None
        elif not row["labels"] and "status" not in row:
            out[key] = None
        else:
            out[key] = row["labels"].split("|")
    return validate_predictions(out, expected_keys, source)


def read_labels(path: Path, expected_keys=None) -> dict[str, list[str] | None]:
    """Read unique, validated predictions; optionally require the exact review cohort."""
    return labels_from_rows(read_csv(path), str(path), expected_keys)


def write_labels(path: Path, labels: dict[str, list[str] | None], extra: dict[str, dict] | None = None) -> None:
    cols = ["review_key", "labels"] + (sorted(next(iter(extra.values())).keys()) if extra else [])
    rows = []
    for k in sorted(labels):
        row = {"review_key": k, "labels": "|".join(labels[k]) if labels[k] else ""}
        if extra:
            row.update(extra[k])
        rows.append(row)
    write_csv(path, rows, cols)
