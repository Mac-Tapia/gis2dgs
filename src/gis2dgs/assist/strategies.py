"""Multimodal conversion strategies scored with multi-criteria weights."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from gis2dgs.assist.decision import (
    DEFAULT_TOPSIS_WEIGHTS,
    OBJECTIVE_NAMES,
    normalize_topsis_weights,
    weights_tuple,
)
from gis2dgs.assist.topsis import topsis_select
from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.input.schema.discovery import DatasetSchema, TableSchema

COMPACT_LINE_ROW_LIMIT = 50_000


class InputModality(str, Enum):
    TABULAR = "tabular"
    CYMDIST = "cymdist"
    SPATIAL = "spatial"
    DATABASE = "database"
    MIXED = "mixed"


class ConversionStrategy(str, Enum):
    AUTO = "auto"
    FULL_MAPPED = "full_mapped"
    NETWORK_CORE = "network_core"
    COMPACT_LINES = "compact_lines"


@dataclass(frozen=True, slots=True)
class StrategyCandidate:
    name: ConversionStrategy
    mapping: MappingConfig
    objectives: dict[str, float]
    rationale: str


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    modality: InputModality
    selected: ConversionStrategy
    selected_index: int
    weights: dict[str, float]
    candidates: tuple[StrategyCandidate, ...]
    report: dict[str, Any]


def parse_strategy(value: str | ConversionStrategy | None) -> ConversionStrategy:
    if value is None:
        return ConversionStrategy.AUTO
    if isinstance(value, ConversionStrategy):
        return value
    token = str(value).strip().lower().replace("-", "_")
    try:
        return ConversionStrategy(token)
    except ValueError as exc:
        raise ValueError(f"Unknown conversion strategy: {value!r}") from exc


def detect_input_modality(
    schema: DatasetSchema,
    *,
    hint: str | None = None,
) -> InputModality:
    """Classify the package by schema shape (not vendor brand)."""

    if hint:
        token = hint.strip().lower()
        for item in InputModality:
            if item.value == token:
                return item
    spatial = sum(1 for table in schema.tables if table.is_spatial)
    names = " ".join(table.name.lower() for table in schema.tables)
    if "section" in names:
        return InputModality.CYMDIST
    if spatial and spatial >= max(1, len(schema.tables) // 2):
        return InputModality.SPATIAL
    if any(
        "dbo." in table.name.lower() or table.source_id == "network_db"
        for table in schema.tables
    ):
        return InputModality.DATABASE
    if spatial and spatial < len(schema.tables):
        return InputModality.MIXED
    return InputModality.TABULAR


def apply_strategy(
    mapping: MappingConfig,
    schema: DatasetSchema,
    strategy: ConversionStrategy,
) -> tuple[MappingConfig, str]:
    """Return a mapping variant for the requested conversion strategy."""

    if strategy in {ConversionStrategy.AUTO, ConversionStrategy.FULL_MAPPED}:
        return mapping, "Keep all mapped entities from the decision front."

    dumped = mapping.model_dump(exclude_none=True)
    if strategy is ConversionStrategy.NETWORK_CORE:
        for drop in ("loads", "generators", "switches"):
            dumped.pop(drop, None)
        return (
            MappingConfig.model_validate(dumped),
            "Network core: buses/lines/sources/transformers/substations only.",
        )

    lines = mapping.lines
    if lines is None:
        return mapping, "No lines layer; compact_lines left mapping unchanged."
    lookup = {table.name: table for table in schema.tables}
    current = lookup.get(lines.source)
    if current is not None and current.rows <= COMPACT_LINE_ROW_LIMIT:
        return mapping, f"Lines table {lines.source!r} already compact ({current.rows} rows)."

    alternative = _best_compact_line_table(schema, exclude=lines.source)
    if alternative is None:
        dumped.pop("loads", None)
        return (
            MappingConfig.model_validate(dumped),
            "No compact line alternative; dropped loads for a lighter convert.",
        )

    alt_columns = {column.name for column in alternative.columns}
    new_fields = {
        logical: column
        for logical, column in lines.fields.items()
        if column in alt_columns
    }
    if "id" not in new_fields:
        for candidate in (
            "ID",
            "CODIGO",
            "Codigo",
            "CodTramoAT",
            "CodTramoMT",
            "CodTramoBT",
            "CodTramo",
        ):
            if candidate in alt_columns:
                new_fields["id"] = candidate
                break
        if "id" not in new_fields:
            for column in sorted(alt_columns):
                token = column.lower().replace(" ", "")
                if token.startswith("codtramo") or token in {"id", "codigo", "código"}:
                    new_fields["id"] = column
                    break
    if "id" not in new_fields:
        return mapping, f"Alternate line table {alternative.name!r} lacks an id column."

    dumped["lines"] = LayerMapping(
        source=alternative.name,
        fields=new_fields,
        units=dict(lines.units),
        defaults=dict(lines.defaults),
    ).model_dump()
    dumped.pop("loads", None)
    return (
        MappingConfig.model_validate(dumped),
        f"Switched lines to compact table {alternative.name!r} ({alternative.rows} rows).",
    )


def _best_compact_line_table(
    schema: DatasetSchema,
    *,
    exclude: str,
) -> TableSchema | None:
    candidates: list[TableSchema] = []
    for table in schema.tables:
        if table.name == exclude:
            continue
        token = table.name.lower()
        if "tramo" not in token and "line" not in token and "section" not in token:
            continue
        if table.rows <= COMPACT_LINE_ROW_LIMIT:
            candidates.append(table)
    if not candidates:
        return None
    return min(candidates, key=lambda table: (table.rows, table.name.lower()))


def score_strategy_mapping(
    mapping: MappingConfig,
    schema: DatasetSchema,
) -> dict[str, float]:
    """Proxy multi-criteria scores for a conversion strategy (benefit criteria)."""

    lookup = {table.name: table for table in schema.tables}
    mapped = [
        name
        for name in (
            "buses",
            "lines",
            "loads",
            "sources",
            "transformers",
            "switches",
            "generators",
            "substations",
        )
        if getattr(mapping, name) is not None
    ]
    coverage = len(mapped) / 8.0
    uniqueness_sources = [
        getattr(mapping, name).source
        for name in mapped
        if getattr(mapping, name) is not None
    ]
    uniqueness = (
        len(set(uniqueness_sources)) / len(uniqueness_sources) if uniqueness_sources else 0.0
    )

    lexical = 0.0
    type_consistency = 1.0
    if mapping.lines is not None and mapping.lines.fields:
        lexical = min(1.0, len(mapping.lines.fields) / 5.0)

    connectivity = 0.0
    if mapping.lines is not None:
        fields = mapping.lines.fields
        if fields.get("from_bus") or fields.get("to_bus"):
            connectivity += 0.5
        if mapping.buses is not None:
            connectivity += 0.5

    compactness = 0.5
    if mapping.lines is not None:
        table = lookup.get(mapping.lines.source)
        if table is not None:
            if table.rows <= COMPACT_LINE_ROW_LIMIT:
                compactness = 1.0
            else:
                compactness = max(0.05, COMPACT_LINE_ROW_LIMIT / max(table.rows, 1))
    if mapping.loads is None:
        compactness = min(1.0, compactness + 0.05)

    return {
        "coverage": coverage,
        "lexical": lexical,
        "type_consistency": type_consistency,
        "table_uniqueness": uniqueness,
        "connectivity_readiness": connectivity,
        "compactness": compactness,
    }


def select_conversion_strategy(
    mapping: MappingConfig,
    schema: DatasetSchema,
    *,
    strategy: ConversionStrategy | str | None = None,
    weights: dict[str, float] | None = None,
    modality_hint: str | None = None,
) -> StrategyDecision:
    """Build strategy candidates and pick one with TOPSIS (or an explicit strategy)."""

    requested = parse_strategy(strategy)
    weight_map = normalize_topsis_weights(
        weights if weights is not None else DEFAULT_TOPSIS_WEIGHTS
    )
    input_modality = detect_input_modality(schema, hint=modality_hint)

    variants: list[ConversionStrategy] = [
        ConversionStrategy.FULL_MAPPED,
        ConversionStrategy.NETWORK_CORE,
        ConversionStrategy.COMPACT_LINES,
    ]
    candidates: list[StrategyCandidate] = []
    for name in variants:
        variant_mapping, rationale = apply_strategy(mapping, schema, name)
        objectives = score_strategy_mapping(variant_mapping, schema)
        candidates.append(
            StrategyCandidate(
                name=name,
                mapping=variant_mapping,
                objectives=objectives,
                rationale=rationale,
            )
        )

    if requested is ConversionStrategy.AUTO:
        objective_rows = [
            tuple(item.objectives[name] for name in OBJECTIVE_NAMES) for item in candidates
        ]
        selected_index = topsis_select(objective_rows, weights_tuple(weight_map))
    else:
        selected_index = next(
            (index for index, item in enumerate(candidates) if item.name is requested),
            0,
        )

    selected = candidates[selected_index]
    report = {
        "input_modality": input_modality.value,
        "strategy": selected.name.value,
        "selected_index": selected_index,
        "multicriteria_weights": weight_map,
        "selected_objectives": selected.objectives,
        "rationale": selected.rationale,
        "candidates": [
            {
                "name": item.name.value,
                "objectives": item.objectives,
                "rationale": item.rationale,
                "summary": {
                    key: (
                        None
                        if getattr(item.mapping, key) is None
                        else getattr(item.mapping, key).source
                    )
                    for key in (
                        "buses",
                        "lines",
                        "loads",
                        "sources",
                        "substations",
                        "transformers",
                    )
                },
            }
            for item in candidates
        ],
    }
    return StrategyDecision(
        modality=input_modality,
        selected=selected.name,
        selected_index=selected_index,
        weights=weight_map,
        candidates=tuple(candidates),
        report=report,
    )
