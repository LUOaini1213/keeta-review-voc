"""Deep comparison of JSON-like results with a float tolerance (for --check modes)."""
from __future__ import annotations

import math


class Mismatch(AssertionError):
    pass


def assert_close(a, b, path: str = "$", rel: float = 1e-9, abs_: float = 1e-12) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            raise Mismatch(f"{path}: keys differ: {sorted(set(a) ^ set(b))[:5]}")
        for k in a:
            assert_close(a[k], b[k], f"{path}.{k}", rel, abs_)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise Mismatch(f"{path}: length {len(a)} != {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            assert_close(x, y, f"{path}[{i}]", rel, abs_)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            raise Mismatch(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            return
        if not math.isclose(a, b, rel_tol=rel, abs_tol=abs_):
            raise Mismatch(f"{path}: {a!r} != {b!r}")
    elif a != b:
        raise Mismatch(f"{path}: {a!r} != {b!r}")
