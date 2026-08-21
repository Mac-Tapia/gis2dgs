from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_SPLIT = re.compile(r"[^a-z0-9]+")


def normalize_token(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    return _SPLIT.sub("", ascii_only)


def lexical_score(candidate: str, aliases: tuple[str, ...]) -> float:
    token = normalize_token(candidate)
    if not token:
        return 0.0
    best = 0.0
    for alias in aliases:
        alias_token = normalize_token(alias)
        if not alias_token:
            continue
        if token == alias_token:
            return 1.0
        if token.startswith(alias_token) or alias_token.startswith(token):
            shorter = token if len(token) <= len(alias_token) else alias_token
            longer = alias_token if shorter == token else token
            overlap = len(shorter) / len(longer)
            best = max(best, 0.72 + 0.20 * overlap)
            continue
        if len(alias_token) >= 3 and alias_token in token:
            overlap = len(alias_token) / len(token)
            best = max(best, 0.68 + 0.24 * overlap)
            continue
        if len(token) >= 3 and token in alias_token:
            overlap = len(token) / len(alias_token)
            best = max(best, 0.68 + 0.24 * overlap)
            continue
        ratio = SequenceMatcher(None, token, alias_token).ratio()
        best = max(best, ratio)
    return best


def is_numeric_dtype(dtype: str) -> bool:
    lowered = dtype.lower()
    return any(token in lowered for token in ("int", "float", "double", "number", "decimal"))
