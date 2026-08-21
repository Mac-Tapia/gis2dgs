from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from gis2dgs.gis.normalizer import is_missing, normalize_identifier, normalize_number

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _normalize_token(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    return _TOKEN_SPLIT.sub("", ascii_only)


def _is_numeric_dtype(dtype: str) -> bool:
    lowered = dtype.lower()
    return any(token in lowered for token in ("int", "float", "double", "number", "decimal"))


def _lexical_score(candidate: str, aliases: tuple[str, ...]) -> float:
    token = _normalize_token(candidate)
    if not token:
        return 0.0
    best = 0.0
    for alias in aliases:
        alias_token = _normalize_token(alias)
        if not alias_token:
            continue
        if token == alias_token:
            return 1.0
        if token.startswith(alias_token) or alias_token.startswith(token):
            shorter = token if len(token) <= len(alias_token) else alias_token
            longer = alias_token if shorter == token else token
            overlap = len(shorter) / len(longer)
            best = max(best, 0.72 + 0.20 * overlap)
    return best


@dataclass(frozen=True, slots=True)
class VoltageLookup:
    """Resolve nominal-voltage codes through a tabular lookup layer."""

    table_name: str
    code_column: str
    voltage_column: str
    by_code: dict[str, float]

    def resolve(self, value: object) -> float:
        try:
            return normalize_number(value)
        except ValueError:
            code = normalize_identifier(value)
            try:
                return self.by_code[code]
            except KeyError as exc:
                raise ValueError(f"Unknown voltage code: {value!r}") from exc


def _table_name_matches_lookup(name: str) -> bool:
    token = _normalize_token(name)
    return any(
        marker in token
        for marker in ("tension", "tensiones", "voltage", "voltaje", "tennomi")
    )


def _detect_code_column(columns: tuple[str, ...], dtypes: dict[str, str]) -> str | None:
    best_name: str | None = None
    best_score = 0.0
    aliases = ("codtennomi", "code", "id", "codigo")
    for name in columns:
        token = _normalize_token(name)
        if "tennomi" in token and "cod" in token:
            return name
        score = _lexical_score(name, aliases)
        if score > best_score and not _is_numeric_dtype(dtypes.get(name, "")):
            best_score = score
            best_name = name
    if best_score >= 0.65:
        return best_name
    return None


def _detect_voltage_column(columns: tuple[str, ...], dtypes: dict[str, str]) -> str | None:
    best_name: str | None = None
    best_score = 0.0
    aliases = ("tension", "voltage", "voltaje", "tensionkv", "voltagekv", "kv")
    for name in columns:
        dtype = dtypes.get(name, "")
        if not _is_numeric_dtype(dtype):
            continue
        token = _normalize_token(name)
        if token in {"tension", "voltage", "voltaje"}:
            return name
        score = _lexical_score(name, aliases)
        if score > best_score:
            best_score = score
            best_name = name
    if best_score >= 0.55:
        return best_name
    return None


def detect_voltage_lookup(dataset: "GisDataset") -> VoltageLookup | None:
    """Return a voltage-code lookup when the dataset exposes a matching table."""

    best: tuple[float, VoltageLookup] | None = None
    for name, frame in dataset.layers.items():
        if not _table_name_matches_lookup(name):
            continue
        columns = tuple(frame.columns)
        dtypes = {column: str(frame[column].dtype) for column in columns}
        code_column = _detect_code_column(columns, dtypes)
        voltage_column = _detect_voltage_column(columns, dtypes)
        if code_column is None or voltage_column is None:
            continue
        by_code: dict[str, float] = {}
        for code_value, voltage_value in zip(
            frame[code_column].tolist(),
            frame[voltage_column].tolist(),
            strict=False,
        ):
            if is_missing(code_value) or is_missing(voltage_value):
                continue
            by_code[normalize_identifier(code_value)] = normalize_number(voltage_value)
        if not by_code:
            continue
        score = _lexical_score(name, ("tensiones", "tension", "voltage", "voltaje"))
        candidate = VoltageLookup(
            table_name=name,
            code_column=code_column,
            voltage_column=voltage_column,
            by_code=by_code,
        )
        if best is None or score > best[0]:
            best = (score, candidate)
    return best[1] if best is not None else None
