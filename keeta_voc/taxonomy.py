"""Load the issue taxonomy and validate label sets (used for LLM output and reference labels)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

TAXONOMY_PATH = Path(__file__).with_name("taxonomy.yaml")
OTHER = "other"


@lru_cache(maxsize=None)
def load_taxonomy(path: str | None = None) -> dict:
    data = yaml.safe_load(Path(path or TAXONOMY_PATH).read_text(encoding="utf-8"))
    labels = data["labels"]
    if OTHER not in labels:
        raise ValueError("taxonomy must define 'other'")
    for name, spec in labels.items():
        if not spec.get("definition"):
            raise ValueError(f"label {name} has no definition")
    return data


def label_names() -> tuple[str, ...]:
    return tuple(load_taxonomy()["labels"].keys())


def issue_labels() -> tuple[str, ...]:
    """All labels except the catch-all."""
    return tuple(n for n in label_names() if n != OTHER)


class InvalidLabels(ValueError):
    pass


def validate_labels(labels) -> list[str]:
    """Return a canonical (taxonomy-ordered, de-duplicated) label list or raise InvalidLabels.

    Rules: must be a non-empty list of strings; every string must be a taxonomy label;
    'other' may not be combined with any other label.
    """
    if not isinstance(labels, list) or not labels:
        raise InvalidLabels("labels must be a non-empty list")
    names = label_names()
    for x in labels:
        if not isinstance(x, str):
            raise InvalidLabels(f"non-string label {x!r}")
        if x not in names:
            raise InvalidLabels(f"unknown label {x!r}")
    uniq = set(labels)
    if OTHER in uniq and len(uniq) > 1:
        raise InvalidLabels("'other' combined with other labels")
    return [n for n in names if n in uniq]


def finalise(labels: set[str]) -> list[str]:
    """Apply the 'other iff nothing else' rule to a set of issue labels."""
    uniq = set(labels) - {OTHER}
    if not uniq:
        return [OTHER]
    return [n for n in label_names() if n in uniq]
