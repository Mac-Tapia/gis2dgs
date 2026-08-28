"""Declarative electrical-layer classification from table schema.

Classifies inventory tables by column signatures and optional name hints.
Vendor-neutral: works for CYMDIST sections, GIS Excel exports, CSV packages, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from gis2dgs.assist.catalog import ENTITIES, EntitySpec, FieldSpec
from gis2dgs.assist.scoring import lexical_score, normalize_token
from gis2dgs.input.schema.discovery import TableSchema

_PROFILE_PATH = Path(__file__).resolve().parents[3] / "config" / "layer_profiles.yaml"
_ASSIGNMENT_MARGIN = 0.12
_FIELD_ACCEPT = 0.34
_ENDPOINT_MARKERS = frozenset(
    {
        "x",
        "y",
        "este",
        "east",
        "norte",
        "north",
        "coord",
        "coordenada",
        "coordenadas",
        "geometr",
        "utm",
        "lon",
        "lat",
    }
)


@dataclass(frozen=True, slots=True)
class TableLayerDecision:
    table: str
    role: str
    score: float
    rationale: str
    role_scores: dict[str, float]


@dataclass(frozen=True, slots=True)
class LayerClassificationReport:
    tables: tuple[TableLayerDecision, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "tables": [
                {
                    "table": item.table,
                    "role": item.role,
                    "score": round(item.score, 4),
                    "rationale": item.rationale,
                    "role_scores": {
                        role: round(score, 4) for role, score in item.role_scores.items()
                    },
                }
                for item in self.tables
            ]
        }

    def primary_role(self, table_name: str) -> str | None:
        for item in self.tables:
            if item.table == table_name:
                return item.role
        return None

    def role_score(self, table_name: str, role: str) -> float:
        for item in self.tables:
            if item.table == table_name:
                return item.role_scores.get(role, 0.0)
        return 0.0


def classify_dataset_layers(
    tables: tuple[TableSchema, ...] | list[TableSchema],
    *,
    profiles: dict[str, Any] | None = None,
) -> LayerClassificationReport:
    payload = profiles if profiles is not None else _load_profiles()
    role_defs = payload.get("roles", {})
    decisions: list[TableLayerDecision] = []
    for table in tables:
        role_scores = {
            role: _score_table_for_role(table, str(role), dict(defn))
            for role, defn in role_defs.items()
        }
        lexical_scores = {
            entity.name: lexical_score(table.name, entity.table_aliases)
            for entity in ENTITIES
            if entity.name in role_scores
        }
        for role, lexical in lexical_scores.items():
            role_scores[role] = max(role_scores.get(role, 0.0), lexical * 0.88)
        best_role = max(role_scores, key=lambda role: role_scores[role])
        best_score = role_scores[best_role]
        decisions.append(
            TableLayerDecision(
                table=table.name,
                role=best_role if best_score >= 0.45 else "unassigned",
                score=best_score,
                rationale=_rationale(table, best_role, best_score, role_scores),
                role_scores=role_scores,
            )
        )
    return LayerClassificationReport(tuple(decisions))


def entity_assignment_allowed(
    table: TableSchema,
    entity_name: str,
    *,
    report: LayerClassificationReport | None = None,
) -> bool:
    """Return False when schema evidence strongly prefers another electrical role."""

    classification = report or classify_dataset_layers((table,))
    primary = classification.primary_role(table.name)
    if primary in {None, "unassigned"}:
        return True
    if primary == entity_name:
        return True
    primary_score = classification.role_score(table.name, primary)
    entity_score = classification.role_score(table.name, entity_name)
    if entity_score + _ASSIGNMENT_MARGIN >= primary_score:
        return True
    return entity_score >= 0.80 and primary_score < 0.65


def entity_assignment_boost(
    table: TableSchema,
    entity_name: str,
    *,
    report: LayerClassificationReport | None = None,
) -> float:
    classification = report or classify_dataset_layers((table,))
    return classification.role_score(table.name, entity_name)


@lru_cache(maxsize=1)
def _load_profiles() -> dict[str, Any]:
    if not _PROFILE_PATH.is_file():
        return {"version": 1, "roles": {}}
    payload = yaml.safe_load(_PROFILE_PATH.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {"version": 1, "roles": {}}


def _entity_spec(entity_name: str) -> EntitySpec | None:
    for entity in ENTITIES:
        if entity.name == entity_name:
            return entity
    return None


def _field_score(spec: FieldSpec, table: TableSchema) -> float:
    best = 0.0
    for column in table.columns:
        token = normalize_token(column.name)
        raw = lexical_score(column.name, spec.aliases)
        score = raw
        if column.non_null_count == 0:
            score *= 0.05
        if spec.name in {"x", "y"} and not any(marker in token for marker in _ENDPOINT_MARKERS):
            score *= 0.05
        best = max(best, score)
    return best


def _endpoint_geometry_score(table: TableSchema) -> float:
    def endpoint(prefix: str) -> float:
        best = 0.0
        for column in table.columns:
            token = normalize_token(column.name)
            if token == prefix or token.startswith(prefix):
                if any(marker in token for marker in _ENDPOINT_MARKERS):
                    best = max(best, 1.0 if token == prefix else 0.92)
        return best

    return min(
        _field_score(next(spec for spec in _entity_spec("lines").fields if spec.name == "id"), table),
        endpoint("x1"),
        endpoint("y1"),
        endpoint("x2"),
        endpoint("y2"),
    )


def _signature_score(
    table: TableSchema,
    entity: EntitySpec,
    field_names: list[str],
    *,
    endpoint_geometry: bool = False,
) -> float:
    if endpoint_geometry:
        geometry = _endpoint_geometry_score(table)
        if geometry < 0.85:
            return 0.0
        id_spec = next((spec for spec in entity.fields if spec.name == "id"), None)
        if id_spec is None:
            return geometry * 0.9
        return min(1.0, (geometry + _field_score(id_spec, table)) / 2.0)

    specs = {spec.name: spec for spec in entity.fields}
    scores: list[float] = []
    for name in field_names:
        spec = specs.get(name)
        if spec is None:
            return 0.0
        scores.append(_field_score(spec, table))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _score_table_for_role(table: TableSchema, role: str, definition: dict[str, Any]) -> float:
    entity = _entity_spec(role)
    if entity is None:
        return 0.0

    markers = tuple(definition.get("name_markers", ()))
    name_score = lexical_score(table.name, markers) if markers else 0.0

    signature_scores: list[float] = []
    signatures = definition.get("signatures", {})
    if isinstance(signatures, dict):
        for spec in signatures.values():
            if not isinstance(spec, dict):
                continue
            fields = spec.get("fields", [])
            if not isinstance(fields, list):
                continue
            weight = float(spec.get("weight", 1.0))
            score = _signature_score(
                table,
                entity,
                [str(item) for item in fields],
                endpoint_geometry=bool(spec.get("endpoint_geometry", False)),
            )
            if score >= _FIELD_ACCEPT:
                signature_scores.append(score * weight)

    signature_score = max(signature_scores) if signature_scores else 0.0
    combined = max(name_score * 0.9, signature_score)

    min_rows = definition.get("min_rows")
    if isinstance(min_rows, int) and table.rows < min_rows and signature_score < 0.90:
        combined *= max(0.05, table.rows / max(min_rows, 1))

    max_rows = definition.get("max_rows")
    if isinstance(max_rows, int) and table.rows > max_rows:
        if name_score >= 0.65:
            combined = min(1.0, combined + 0.08)
        else:
            combined *= max(0.15, max_rows / max(table.rows, 1))

    if role == "buses" and _endpoint_geometry_score(table) >= 0.85:
        combined *= 0.12
    if role == "lines" and _endpoint_geometry_score(table) >= 0.85:
        combined = min(1.0, max(combined, _endpoint_geometry_score(table) * 0.98))

    return min(1.0, combined)


def _rationale(
    table: TableSchema,
    role: str,
    score: float,
    role_scores: dict[str, float],
) -> str:
    ordered = sorted(role_scores.items(), key=lambda item: -item[1])
    runner_up = ordered[1][0] if len(ordered) > 1 else "none"
    return (
        f"rows={table.rows}; primary={role} ({score:.2f}); "
        f"runner_up={runner_up}"
    )
