"""Multi-objective / multi-criteria / multimodal mapping decision types."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from gis2dgs.config.models import MappingConfig

OBJECTIVE_NAMES: tuple[str, ...] = (
    "coverage",
    "lexical",
    "type_consistency",
    "table_uniqueness",
    "connectivity_readiness",
    "compactness",
)

# Default TOPSIS weights (must sum to 1.0).
DEFAULT_TOPSIS_WEIGHTS: dict[str, float] = {
    "coverage": 0.28,
    "lexical": 0.18,
    "type_consistency": 0.16,
    "table_uniqueness": 0.12,
    "connectivity_readiness": 0.16,
    "compactness": 0.10,
}


class DecisionModality(str, Enum):
    """How a mapping is selected from the search / Pareto set."""

    NSGA_TOPSIS = "nsga_topsis"
    GREEDY = "greedy"
    LLM = "llm"
    PARETO = "pareto"


@dataclass(frozen=True, slots=True)
class MappingDecision:
    """Result of a multi-objective mapping search with an explicit selection modality."""

    mapping: MappingConfig
    report: dict[str, Any]
    pareto: tuple[dict[str, Any], ...]
    modality: DecisionModality
    selected_index: int
    weights: dict[str, float]


def normalize_topsis_weights(
    weights: dict[str, float] | tuple[float, ...] | list[float] | None = None,
) -> dict[str, float]:
    """Return a weight dict covering all OBJECTIVE_NAMES and summing to 1.0."""

    if weights is None:
        raw = dict(DEFAULT_TOPSIS_WEIGHTS)
    elif isinstance(weights, (tuple, list)):
        if len(weights) != len(OBJECTIVE_NAMES):
            raise ValueError(
                f"Expected {len(OBJECTIVE_NAMES)} TOPSIS weights, got {len(weights)}."
            )
        raw = {
            name: float(value) for name, value in zip(OBJECTIVE_NAMES, weights, strict=True)
        }
    else:
        raw = {name: float(DEFAULT_TOPSIS_WEIGHTS[name]) for name in OBJECTIVE_NAMES}
        for key, value in weights.items():
            name = str(key).strip().lower()
            if name not in raw:
                raise ValueError(f"Unknown TOPSIS weight key: {key!r}")
            raw[name] = float(value)

    total = sum(raw.values())
    if total <= 0:
        raise ValueError("TOPSIS weights must sum to a positive value.")
    return {name: raw[name] / total for name in OBJECTIVE_NAMES}


def weights_tuple(weights: dict[str, float]) -> tuple[float, ...]:
    normalized = normalize_topsis_weights(weights)
    return tuple(normalized[name] for name in OBJECTIVE_NAMES)


def parse_weights_string(raw: str) -> dict[str, float]:
    """Parse ``coverage=0.3,lexical=0.2,...`` or ``coverage:0.3,...``."""

    text = raw.strip()
    if not text:
        return dict(DEFAULT_TOPSIS_WEIGHTS)
    parts = re.split(r"[,;]\s*", text)
    parsed: dict[str, float] = {}
    for part in parts:
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        elif ":" in part:
            key, value = part.split(":", 1)
        else:
            raise ValueError(f"Invalid weight fragment: {part!r}")
        parsed[key.strip().lower()] = float(value.strip())
    return normalize_topsis_weights(parsed)


def weights_from_env(
    *,
    default: dict[str, float] | None = None,
) -> dict[str, float]:
    """Load weights from ``GIS2DGS_TOPSIS_WEIGHTS`` or return defaults."""

    raw = os.environ.get("GIS2DGS_TOPSIS_WEIGHTS", "").strip()
    if not raw:
        return normalize_topsis_weights(default)
    return parse_weights_string(raw)


def objectives_as_dict(values: tuple[float, ...] | list[float]) -> dict[str, float]:
    if len(values) != len(OBJECTIVE_NAMES):
        raise ValueError(
            f"Expected {len(OBJECTIVE_NAMES)} objectives, got {len(values)}."
        )
    return {
        name: float(value) for name, value in zip(OBJECTIVE_NAMES, values, strict=True)
    }


def parse_modality(value: str | DecisionModality | None) -> DecisionModality:
    if value is None:
        return DecisionModality.NSGA_TOPSIS
    if isinstance(value, DecisionModality):
        return value
    token = str(value).strip().lower().replace("-", "_")
    aliases = {
        "nsga": DecisionModality.NSGA_TOPSIS,
        "nsga_topsis": DecisionModality.NSGA_TOPSIS,
        "topsis": DecisionModality.NSGA_TOPSIS,
        "auto": DecisionModality.NSGA_TOPSIS,
        "greedy": DecisionModality.GREEDY,
        "llm": DecisionModality.LLM,
        "pareto": DecisionModality.PARETO,
        "pareto_index": DecisionModality.PARETO,
    }
    if token not in aliases:
        raise ValueError(f"Unknown decision modality: {value!r}")
    return aliases[token]
