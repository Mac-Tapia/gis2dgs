from __future__ import annotations

import os
from typing import Any

import pandas as pd

DEFAULT_INSPECT_SAMPLE_ROWS = 100_000


def env_sample_rows(default: int | None = DEFAULT_INSPECT_SAMPLE_ROWS) -> int | None:
    raw = os.environ.get("GIS2DGS_SAMPLE_ROWS", "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return None if value <= 0 else value


def compact_frame(frame: pd.DataFrame, *, copy: bool = False) -> pd.DataFrame:
    """Downcast numeric dtypes in place or on a copy. Does not categorize identifiers."""

    target = frame.copy() if copy else frame
    geometry_name = getattr(getattr(target, "geometry", None), "name", None)
    for column in target.columns:
        if column == geometry_name:
            continue
        series = target[column]
        if pd.api.types.is_float_dtype(series):
            target[column] = pd.to_numeric(series, downcast="float")
        elif pd.api.types.is_integer_dtype(series):
            try:
                target[column] = pd.to_numeric(series, downcast="integer")
            except (TypeError, ValueError):
                continue
    return target


def limit_rows(frame: pd.DataFrame, sample_rows: int | None) -> pd.DataFrame:
    if sample_rows is None or sample_rows <= 0 or len(frame) <= sample_rows:
        return frame
    return frame.iloc[:sample_rows]


def quoted_identifier(engine: Any, name: str) -> str:
    return str(engine.dialect.identifier_preparer.quote(name))


def sample_select_sql(engine: Any, table: str, sample_rows: int) -> str:
    quoted = quoted_identifier(engine, table)
    limit = int(sample_rows)
    if engine.dialect.name == "mssql":
        return f"SELECT TOP ({limit}) * FROM {quoted}"
    return f"SELECT * FROM {quoted} LIMIT {limit}"
