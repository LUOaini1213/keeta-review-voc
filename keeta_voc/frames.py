"""Strict DataFrame equality for the SQL-vs-pandas cross-check."""
from __future__ import annotations

import numpy as np
import pandas as pd


class FrameMismatch(AssertionError):
    pass


def assert_frames_equal(sql: pd.DataFrame, pdf: pd.DataFrame, name: str, tol: float = 1e-12) -> None:
    """Same columns, same row order, same values (floats within tol, ints/strings exact)."""
    if list(sql.columns) != list(pdf.columns):
        raise FrameMismatch(f"{name}: columns {list(sql.columns)} != {list(pdf.columns)}")
    if len(sql) != len(pdf):
        raise FrameMismatch(f"{name}: {len(sql)} rows (SQL) != {len(pdf)} rows (pandas)")
    for c in sql.columns:
        a, b = sql[c].to_numpy(), pdf[c].to_numpy()
        if pd.api.types.is_numeric_dtype(sql[c]) and pd.api.types.is_numeric_dtype(pdf[c]):
            a, b = a.astype(float), b.astype(float)
            bad = ~np.isclose(a, b, rtol=0, atol=tol)
        else:
            bad = np.array([str(x) != str(y) for x, y in zip(a, b)])
        if bad.any():
            i = int(np.argmax(bad))
            raise FrameMismatch(f"{name}: column {c!r} row {i}: SQL {a[i]!r} != pandas {b[i]!r}")
