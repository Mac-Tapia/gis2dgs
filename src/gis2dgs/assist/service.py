from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Any

from gis2dgs.assist.catalog import ENTITIES, EntitySpec, FieldSpec
from gis2dgs.assist.decision import (
    DEFAULT_TOPSIS_WEIGHTS,
    DecisionModality,
    OBJECTIVE_NAMES,
    MappingDecision,
    normalize_topsis_weights,
    objectives_as_dict,
    parse_modality,
    weights_from_env,
    weights_tuple,
)
from gis2dgs.assist.layer_classifier import (
    LayerClassificationReport,
    classify_dataset_layers,
    entity_assignment_allowed,
    entity_assignment_boost,
)
from gis2dgs.assist.llm import refine_mapping_with_llm
from gis2dgs.assist.nsga import nsga_ii
from gis2dgs.assist.scoring import is_numeric_dtype, lexical_score, normalize_token
from gis2dgs.assist.topsis import topsis_select
from gis2dgs.config.models import MappingConfig
from gis2dgs.gis.hierarchical import (
    detect_feeder_column,
    detect_parent_column,
    sanitize_line_endpoint_fields,
)
from gis2dgs.input.schema.discovery import ColumnSchema, DatasetSchema, TableSchema

UNIT_HINTS: dict[str, str] = {
    "nominal_voltage_kv": "kV",
    "hv_voltage_kv": "kV",
    "lv_voltage_kv": "kV",
    "length_km": "km",
    "active_power_mw": "MW",
    "reactive_power_mvar": "Mvar",
    "rated_power_mva": "MVA",
}


def _infer_length_unit(column_name: str) -> str:
    """Infer length unit from inventory column labels (often metres)."""

    token = normalize_token(column_name)
    if "km" in token:
        return "km"
    raw = column_name.lower()
    if "(m)" in raw or token.endswith("m") or "metro" in token:
        return "m"
    return "km"


def _infer_active_power_unit(column_name: str) -> str:
    """Infer active-power unit from inventory labels (distribution P is usually kW)."""

    token = normalize_token(column_name)
    raw = column_name.lower()
    if "mw" in token and "kw" not in token:
        return "MW"
    if "kw" in token or "(kw)" in raw:
        return "kW"
    if token in {"w", "watt", "watts"} or token.endswith("_w"):
        return "W"
    # PAC / potencia / demanda without an explicit MW tag → kW (service connections).
    if any(marker in token for marker in ("pac", "potencia", "demanda", "dmax", "pact")):
        return "kW"
    return "MW"


def _infer_reactive_power_unit(column_name: str) -> str:
    """Infer reactive-power unit from inventory labels."""

    token = normalize_token(column_name)
    raw = column_name.lower()
    if "mvar" in token or "mvar" in raw.replace(" ", ""):
        return "Mvar"
    if "kvar" in token or "kvar" in raw:
        return "kvar"
    if token.endswith("var") or token == "var":
        return "var"
    if token in {"q", "qac"} or "reactiva" in token:
        return "kvar"
    return "Mvar"

# Backward-compatible 4-tuple used by older tests; full defaults live in decision.py.
TOPSIS_WEIGHTS = (
    DEFAULT_TOPSIS_WEIGHTS["coverage"],
    DEFAULT_TOPSIS_WEIGHTS["lexical"],
    DEFAULT_TOPSIS_WEIGHTS["type_consistency"],
    DEFAULT_TOPSIS_WEIGHTS["table_uniqueness"],
)
TOP_K_TABLES = 6
TOP_K_COLUMNS = 8
TABLE_SCORE_MIN = 0.62
COLUMN_SCORE_MIN = 0.34
NUMERIC_COLUMN_SCORE_MIN = 0.55
CONNECTIVITY_COLUMN_SCORE_MIN = 0.65
VOLTAGE_DEFAULT_KV = 1.0
COMPACT_LINE_ROW_LIMIT = 50_000
CONNECTIVITY_FIELDS = frozenset({"from_bus", "to_bus", "bus_id", "hv_bus", "lv_bus"})
_NON_ENDPOINT_MARKERS = frozenset(
    {
        "distrito",
        "district",
        "jerarquia",
        "localidad",
        "ubicacion",
        "direccion",
        "address",
        "provincia",
        "departamento",
        "zona",
        "color",
        "rol",
        "estado",
        "fecha",
        "fec",
        "descripcion",
        "description",
        "observacion",
        "telefono",
        "voltaje",
        "tension",
    }
)
_COORDINATE_MARKERS = frozenset(
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
        "geometria",
        "geometry",
        "utm",
        "longitud",
        "lon",
        "lat",
        "latitud",
    }
)
# Ownership / taxonomy columns are not operational service state (REE GIS: ESTADO ≠ PROPIETARIO;
# LatAm inventories use DISTRIBUIDOR/TERCEROS as owner codes, not EN SERVICIO / FUERA DE SERVICIO).
_IN_SERVICE_NEGATIVE_MARKERS = (
    "propietar",
    "proprietar",
    "owner",
    "titular",
    "mantenedor",
    "ejecutor",
    "rol",
    "role",
    "color",
    "localidad",
    "distrito",
    "sistema",
    "descripcion",
    "description",
    "nombre",
    "name",
    "codigo",
    "code",
)
_IN_SERVICE_POSITIVE_MARKERS = (
    "estado",
    "service",
    "servic",
    "outserv",
    "activo",
    "inactiv",
    "operativ",
    "status",
    "instalacion",
    "suministro",
)


@dataclass(frozen=True, slots=True)
class MappingSuggestion:
    mapping: MappingConfig
    report: dict[str, Any]
    pareto: tuple[dict[str, Any], ...]
    modality: DecisionModality = DecisionModality.NSGA_TOPSIS
    selected_index: int = 0
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_TOPSIS_WEIGHTS))

    def as_decision(self) -> MappingDecision:
        return MappingDecision(
            mapping=self.mapping,
            report=self.report,
            pareto=self.pareto,
            modality=self.modality,
            selected_index=self.selected_index,
            weights=dict(self.weights),
        )


@dataclass(slots=True)
class _SearchSpace:
    tables: tuple[TableSchema, ...]
    table_choices: dict[str, list[int]]
    column_choices: dict[tuple[str, str], list[int]]
    table_scores: dict[tuple[str, int], float]
    column_scores: dict[tuple[str, str, int], float]
    offsets: list[tuple[str, str | None]]
    layer_report: LayerClassificationReport
    length: int = 0
    greedy: list[int] = field(default_factory=list)


def suggest_mapping(
    schema: DatasetSchema,
    *,
    seed: int = 42,
    use_llm: bool = False,
    population_size: int = 32,
    generations: int = 24,
    modality: DecisionModality | str | None = None,
    weights: dict[str, float] | tuple[float, ...] | list[float] | None = None,
    pareto_index: int | None = None,
) -> MappingSuggestion:
    """Propose MappingConfig from discovered schema. Never writes DGS.

    Multi-objective NSGA-II explores the Pareto front; multi-criteria TOPSIS
    (or an explicit modality) selects one candidate. Never silently overlays
    a greedy mapping on top of the selected chromosome.
    """

    chosen_modality = parse_modality(modality)
    if use_llm and chosen_modality is DecisionModality.NSGA_TOPSIS:
        # Legacy ``use_llm=True`` requests LLM refinement after TOPSIS.
        pass
    weight_map = normalize_topsis_weights(weights if weights is not None else weights_from_env())
    weight_vec = weights_tuple(weight_map)

    space = _build_space(schema)
    if space.length == 0:
        empty = MappingConfig()
        report = {
            "method": "nsga-ii+topsis",
            "modality": chosen_modality.value,
            "multicriteria_weights": weight_map,
            "pareto_size": 0,
            "selected_index": 0,
            "selected_objectives": objectives_as_dict((0.0,) * len(OBJECTIVE_NAMES)),
            "llm_used": False,
            "warnings": _warnings(empty, schema),
            "note": (
                "This YAML is a mapping proposal. Conversion still requires NetworkModel "
                "and validation via project.yaml; it does not write DGS by itself."
            ),
        }
        return MappingSuggestion(
            empty,
            report,
            (),
            modality=chosen_modality,
            selected_index=0,
            weights=weight_map,
        )

    def evaluate(chromosome: list[int]) -> tuple[float, ...]:
        return _objectives(space, chromosome)

    def randomize(rng: Random) -> list[int]:
        if rng.random() < 0.35:
            return list(space.greedy)
        chromosome = [0] * space.length
        for position, (entity_name, field_name) in enumerate(space.offsets):
            if field_name is None:
                choices = space.table_choices[entity_name]
            else:
                choices = space.column_choices[(entity_name, field_name)]
            chromosome[position] = rng.randrange(len(choices))
        return chromosome

    def crossover(rng: Random, first: list[int], second: list[int]) -> list[int]:
        point = rng.randrange(1, max(2, len(first)))
        return first[:point] + second[point:]

    def mutate(rng: Random, chromosome: list[int]) -> list[int]:
        child = list(chromosome)
        position = rng.randrange(len(child))
        entity_name, field_name = space.offsets[position]
        if field_name is None:
            width = len(space.table_choices[entity_name])
        else:
            width = len(space.column_choices[(entity_name, field_name)])
        child[position] = rng.randrange(width)
        return child

    result = nsga_ii(
        evaluate,
        randomize,
        crossover,
        mutate,
        population_size=population_size,
        generations=generations,
        seed=seed,
    )
    front = result.fronts[0] if result.fronts else list(range(len(result.population)))
    candidates = [result.population[index] for index in front]
    candidate_obj = [result.objectives[index] for index in front]
    if space.greedy not in candidates:
        candidates.append(list(space.greedy))
        candidate_obj.append(evaluate(space.greedy))

    greedy_index = next(
        (index for index, chromosome in enumerate(candidates) if chromosome == space.greedy),
        0,
    )

    if chosen_modality is DecisionModality.GREEDY:
        selected_offset = greedy_index
    elif chosen_modality is DecisionModality.PARETO:
        if pareto_index is None:
            raise ValueError("pareto_index is required when modality=pareto")
        if pareto_index < 0 or pareto_index >= len(candidates):
            raise ValueError(
                f"pareto_index {pareto_index} out of range for front size {len(candidates)}"
            )
        selected_offset = int(pareto_index)
    else:
        selected_offset = topsis_select(candidate_obj, weight_vec)
        # Convert requires buses; never prefer a bus-less TOPSIS pick when the
        # front already contains a candidate with a buses layer.
        selected_offset = _prefer_candidate_with_buses(
            space, candidates, candidate_obj, selected_offset, weight_vec
        )

    selected = candidates[selected_offset]
    mapping = _decode(space, selected)

    llm_used = False
    if chosen_modality is DecisionModality.LLM or use_llm:
        refined = refine_mapping_with_llm(
            _schema_payload(schema),
            mapping.model_dump(exclude_none=True),
        )
        if refined:
            mapping = _merge_llm(schema, mapping, refined)
            llm_used = True
            if chosen_modality is DecisionModality.LLM and not llm_used:
                pass
        elif chosen_modality is DecisionModality.LLM:
            # Fail-open: keep TOPSIS/NSGA selection when LLM is unavailable.
            chosen_modality = DecisionModality.NSGA_TOPSIS

    pareto_payload = tuple(
        {
            "objectives": objectives_as_dict(objectives),
            "mapping": _decode(space, chromosome).model_dump(exclude_none=True),
            "summary": _mapping_summary(_decode(space, chromosome)),
        }
        for chromosome, objectives in zip(candidates, candidate_obj, strict=True)
    )
    report = {
        "method": "nsga-ii+topsis",
        "modality": chosen_modality.value,
        "multicriteria_weights": weight_map,
        "pareto_size": len(candidates),
        "selected_index": selected_offset,
        "selected_objectives": objectives_as_dict(candidate_obj[selected_offset]),
        "llm_used": llm_used,
        "warnings": _warnings(mapping, schema),
        "layer_classification": space.layer_report.as_dict(),
        "note": (
            "This YAML is a mapping proposal. Conversion still requires NetworkModel "
            "and validation via project.yaml; it does not write DGS by itself."
        ),
    }
    return MappingSuggestion(
        mapping,
        report,
        pareto_payload,
        modality=chosen_modality,
        selected_index=selected_offset,
        weights=weight_map,
    )


def _mapping_summary(mapping: MappingConfig) -> dict[str, str | None]:
    summary: dict[str, str | None] = {}
    for name in (
        "buses",
        "lines",
        "loads",
        "sources",
        "transformers",
        "switches",
        "generators",
        "substations",
    ):
        layer = getattr(mapping, name)
        summary[name] = None if layer is None else str(layer.source)
    return summary


def mapping_to_yaml_payload(mapping: MappingConfig) -> dict[str, Any]:
    dumped = mapping.model_dump(exclude_none=True)
    dumped.setdefault("target_crs", None)
    default_connectivity = MappingConfig().connectivity.model_dump()
    if dumped.get("connectivity") == default_connectivity:
        dumped.pop("connectivity", None)
    return dumped


def _build_space(schema: DatasetSchema) -> _SearchSpace:
    tables = schema.tables
    layer_report = classify_dataset_layers(tables)
    table_choices: dict[str, list[int]] = {}
    column_choices: dict[tuple[str, str], list[int]] = {}
    table_scores: dict[tuple[str, int], float] = {}
    column_scores: dict[tuple[str, str, int], float] = {}
    offsets: list[tuple[str, str | None]] = []

    for entity in ENTITIES:
        ranked_tables = _rank_tables(entity, tables, layer_report=layer_report)
        table_choices[entity.name] = ranked_tables
        for table_index in ranked_tables:
            table_scores[(entity.name, table_index)] = (
                0.0
                if table_index < 0
                else _combined_table_score(
                    entity, table_index, tables, layer_report=layer_report
                )
            )
        offsets.append((entity.name, None))
        for spec in entity.fields:
            ranked_columns = _rank_columns(spec, tables)
            column_choices[(entity.name, spec.name)] = ranked_columns
            for encoded in ranked_columns:
                column_scores[(entity.name, spec.name, encoded)] = _encoded_column_score(
                    spec, tables, encoded
                )
            offsets.append((entity.name, spec.name))

    space = _SearchSpace(
        tables=tables,
        table_choices=table_choices,
        column_choices=column_choices,
        table_scores=table_scores,
        column_scores=column_scores,
        offsets=offsets,
        layer_report=layer_report,
        length=len(offsets),
    )
    space.greedy = _greedy(space)
    return space


def _field_accept_threshold(spec: FieldSpec) -> float:
    if spec.name in CONNECTIVITY_FIELDS:
        return CONNECTIVITY_COLUMN_SCORE_MIN
    if spec.required and spec.numeric:
        return NUMERIC_COLUMN_SCORE_MIN
    return COLUMN_SCORE_MIN


def _column_match_score(spec: FieldSpec, column: ColumnSchema) -> float:
    raw = lexical_score(column.name, spec.aliases)
    score = raw
    token = normalize_token(column.name)
    dtype = column.dtype.lower()
    if spec.numeric and is_numeric_dtype(column.dtype):
        score = min(1.0, raw + 0.08)
    elif spec.numeric and not is_numeric_dtype(column.dtype):
        if raw >= 0.95:
            score = raw * 0.85
        elif raw < 0.99:
            score *= 0.45
    if column.non_null_count == 0:
        score *= 0.05
    if spec.name in CONNECTIVITY_FIELDS:
        if any(marker in token for marker in _NON_ENDPOINT_MARKERS):
            score *= 0.05
        if any(
            marker in token
            for marker in ("fase", "phase", "norma", "conductor", "calibre")
        ):
            score *= 0.10
        if (
            "datetime" in dtype
            or "timestamp" in dtype
            or dtype in {"date", "datetime64[ns]", "datetime64[us]"}
        ):
            score *= 0.05
        # Segment/line code columns are not endpoint references unless they encode parent.
        if (
            spec.name in {"from_bus", "to_bus"}
            and any(marker in token for marker in ("tramo", "segment", "line", "conductor"))
            and "padre" not in token
            and "parent" not in token
            and not any(
                marker in token
                for marker in ("nodo", "bus", "origen", "destino", "from", "to", "salid")
            )
        ):
            score *= 0.20
        if (
            spec.name == "from_bus"
            and "padre" not in token
            and "parent" not in token
            and token.endswith("tramo")
        ):
            score *= 0.20
    if spec.name in {"x", "y"}:
        if not any(marker in token for marker in _COORDINATE_MARKERS):
            score *= 0.05
        elif token in {"cantfase", "cantfases", "fase", "fasesqtd"}:
            score *= 0.02
        elif "voltaje" in token or "tension" in token:
            score *= 0.05
    if spec.name == "nominal_voltage_kv":
        if token in {"descripcion", "description", "nombre", "name"}:
            score *= 0.02
        if "kv" in token or token.endswith("kv"):
            score = min(1.0, score + 0.12)
    if spec.name == "type_id":
        if any(
            marker in token
            for marker in ("tipored", "tipocircuito", "tiposervicio", "tiposistema")
        ):
            score *= 0.25
        elif "norma" in token or "conductor" in token:
            score = min(1.0, score + 0.15)
        elif token in {"codigo", "code", "id", "fid"}:
            score *= 0.15
    if spec.name == "in_service":
        if (
            "datetime" in dtype
            or "timestamp" in dtype
            or dtype in {"date", "datetime64[ns]", "datetime64[us]"}
        ):
            score *= 0.05
        if any(
            marker in token
            for marker in (
                "fec",
                "fecha",
                "date",
                "datetime",
                "timestamp",
                "existe",
                "desde",
                "puesta",
                "commission",
            )
        ):
            score *= 0.05
        if any(marker in token for marker in _IN_SERVICE_NEGATIVE_MARKERS):
            score *= 0.05
        elif not any(marker in token for marker in _IN_SERVICE_POSITIVE_MARKERS):
            # Reject fuzzy-only matches (e.g. SequenceMatcher on PROPRIETARIO ≈ estado*).
            score *= 0.25
    if spec.name == "name":
        if (
            "datetime" in dtype
            or "timestamp" in dtype
            or dtype in {"date", "datetime64[ns]", "datetime64[us]"}
        ):
            score *= 0.05
        if "padre" in token or token.endswith("parent"):
            score *= 0.05
        elif any(
            marker in token
            for marker in (
                "frombus",
                "tobus",
                "nodo_i",
                "nodo_f",
                "bus1",
                "bus2",
                "origen",
                "destino",
            )
        ):
            score *= 0.10
        elif token in {"phase", "fase"}:
            score *= 0.05
        elif any(
            marker in token
            for marker in ("fec", "fecha", "date", "datetime", "timestamp")
        ):
            score *= 0.05
        elif "norma" in token:
            score *= 0.10
        if column.non_null_count > 1:
            uniqueness = column.unique_count / column.non_null_count
            if uniqueness < 0.85:
                score *= max(0.05, uniqueness)
    return score


def _best_field_score_on_table(spec: FieldSpec, table: TableSchema) -> float:
    return max(
        (_column_match_score(spec, column) for column in table.columns),
        default=0.0,
    )


def _field_is_plausible(spec: FieldSpec, table: TableSchema) -> bool:
    return _best_field_score_on_table(spec, table) >= _field_accept_threshold(spec)


def _bus_topology_signature(table: TableSchema) -> float:
    """Score tables that look like point nodes from column shape alone."""

    entity = next(item for item in ENTITIES if item.name == "buses")
    specs = {spec.name: spec for spec in entity.fields}
    id_score = _best_field_score_on_table(specs["id"], table)
    if id_score < COLUMN_SCORE_MIN:
        return 0.0
    x_score = _best_field_score_on_table(specs["x"], table)
    y_score = _best_field_score_on_table(specs["y"], table)
    if x_score >= COLUMN_SCORE_MIN and y_score >= COLUMN_SCORE_MIN:
        signature = min(1.0, (id_score + x_score + y_score) / 3.0)
    else:
        signature = id_score * 0.5
    name_score = lexical_score(
        table.name,
        next(item.table_aliases for item in ENTITIES if item.name == "buses"),
    )
    if name_score < 0.55:
        row_factor = min(1.0, table.rows / 10.0)
        signature *= max(0.05, row_factor)
    return signature


def _line_geometry_signature(table: TableSchema) -> float:
    """Score span tables with endpoint coordinates (X1/Y1/X2/Y2 style exports)."""

    entity = next(item for item in ENTITIES if item.name == "lines")
    id_spec = next(spec for spec in entity.fields if spec.name == "id")
    id_score = _best_field_score_on_table(id_spec, table)
    if id_score < COLUMN_SCORE_MIN:
        return 0.0

    def endpoint_score(prefix: str) -> float:
        best = 0.0
        for column in table.columns:
            token = normalize_token(column.name)
            if token == prefix or token.startswith(prefix):
                if any(marker in token for marker in _COORDINATE_MARKERS):
                    best = max(best, 1.0 if token == prefix else 0.92)
        return best

    x1 = endpoint_score("x1")
    y1 = endpoint_score("y1")
    x2 = endpoint_score("x2")
    y2 = endpoint_score("y2")
    if min(x1, y1, x2, y2) < 0.85:
        return 0.0
    return min(1.0, (id_score + x1 + y1 + x2 + y2) / 5.0)


def _combined_table_score(
    entity: EntitySpec,
    table_index: int,
    tables: tuple[TableSchema, ...],
    *,
    layer_report: LayerClassificationReport | None = None,
) -> float:
    table = tables[table_index]
    name_score = lexical_score(table.name, entity.table_aliases)
    required_specs = [spec for spec in entity.fields if spec.required]
    id_spec = next((spec for spec in entity.fields if spec.name == "id"), None)
    if not required_specs:
        return name_score
    column_scores = [_best_field_score_on_table(spec, table) for spec in required_specs]
    column_score = sum(column_scores) / len(column_scores)
    combined = max(name_score, column_score * 0.92)
    if entity.name == "buses":
        bus_signature = _bus_topology_signature(table)
        if bus_signature >= 0.62:
            combined = max(combined, bus_signature * 0.96)
        if name_score < 0.55 and table.rows < 10:
            combined *= max(0.05, table.rows / 10.0)
    elif entity.name == "lines":
        line_signature = _line_geometry_signature(table)
        if line_signature >= 0.62:
            combined = max(combined, line_signature * 0.94)
    if id_spec is not None:
        combined = max(combined, _best_field_score_on_table(id_spec, table) * 0.98)
    if name_score < 0.50:
        signature = (
            _bus_topology_signature(table)
            if entity.name == "buses"
            else _line_geometry_signature(table)
            if entity.name == "lines"
            else 0.0
        )
        if signature < 0.62:
            combined = min(combined, name_score + 0.18)
    # Prefer distribution (BT) line inventories and MT feeder sources over AT trunks.
    prefix = _table_voltage_prefix(table.name)
    if entity.name == "lines" and prefix == "bt":
        combined = min(1.0, combined + 0.08)
    elif entity.name == "lines" and prefix == "at":
        combined *= 0.92
    if entity.name == "sources" and prefix == "mt":
        combined = min(1.0, combined + 0.06)
    elif entity.name == "sources" and prefix == "at":
        combined *= 0.90
    if entity.name == "lines" and detect_parent_column(
        [column.name for column in table.columns]
    ):
        combined = min(1.0, combined + 0.04)
    if layer_report is not None:
        role_boost = entity_assignment_boost(
            table,
            entity.name,
            report=layer_report,
        )
        if role_boost >= 0.55:
            combined = max(combined, role_boost * 0.97)
    return combined


def _table_qualifies_for_entity(
    entity: EntitySpec,
    table: TableSchema,
    *,
    layer_report: LayerClassificationReport | None = None,
) -> bool:
    spec_by_name = {spec.name: spec for spec in entity.fields}
    id_spec = spec_by_name.get("id")
    if id_spec is not None and not _field_is_plausible(id_spec, table):
        return False
    if entity.name == "buses":
        name_score = lexical_score(table.name, entity.table_aliases)
        token = normalize_token(table.name)
        if layer_report is not None and not entity_assignment_allowed(
            table,
            entity.name,
            report=layer_report,
        ):
            return False
        if name_score < 0.55 and _bus_topology_signature(table) < 0.62:
            return False
        if (
            name_score < 0.55
            and table.rows < 3
            and _bus_topology_signature(table) < 0.90
        ):
            return False
        if any(
            marker in token
            for marker in ("generacion", "generador", "generator", "centrogeneracion")
        ):
            return False
        voltage_spec = spec_by_name.get("nominal_voltage_kv")
        if voltage_spec is not None and id_spec is not None:
            id_score = _best_field_score_on_table(id_spec, table)
            voltage_score = _best_field_score_on_table(voltage_spec, table)
            if voltage_score >= 0.90 and id_score < 0.72:
                return False
    if entity.name == "lines":
        name_score = lexical_score(table.name, entity.table_aliases)
        if layer_report is not None and not entity_assignment_allowed(
            table,
            entity.name,
            report=layer_report,
        ):
            return False
        if name_score < 0.55 and _line_geometry_signature(table) < 0.62:
            return False
    if entity.name == "substations":
        name_score = lexical_score(table.name, entity.table_aliases)
        token = normalize_token(table.name)
        if name_score < 0.55:
            return False
        if any(
            marker in token
            for marker in (
                "section",
                "tramo",
                "segment",
                "line",
                "carga",
                "load",
                "customer",
                "node",
                "nodo",
            )
        ):
            return False
    return True


def _rank_tables(
    entity: EntitySpec,
    tables: tuple[TableSchema, ...],
    *,
    layer_report: LayerClassificationReport | None = None,
) -> list[int]:
    scored = [
        (
            _combined_table_score(
                entity, index, tables, layer_report=layer_report
            ),
            index,
        )
        for index, table in enumerate(tables)
        if _table_qualifies_for_entity(
            entity, table, layer_report=layer_report
        )
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen = [index for score, index in scored[:TOP_K_TABLES] if score >= TABLE_SCORE_MIN]
    return [-1, *chosen]


def _rank_columns(spec: FieldSpec, tables: tuple[TableSchema, ...]) -> list[int]:
    scored: list[tuple[float, int]] = []
    for table_index, table in enumerate(tables):
        for column_index, column in enumerate(table.columns):
            score = _column_match_score(spec, column)
            scored.append((score, _encode_column(table_index, column_index)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen = [encoded for score, encoded in scored[:TOP_K_COLUMNS] if score >= COLUMN_SCORE_MIN]
    per_table: dict[int, list[tuple[float, int]]] = {}
    for score, encoded in scored:
        if score < COLUMN_SCORE_MIN:
            continue
        table_index, _ = _decode_column(encoded)
        bucket = per_table.setdefault(table_index, [])
        if len(bucket) < 2:
            bucket.append((score, encoded))
    for bucket in per_table.values():
        for _score, encoded in bucket:
            if encoded not in chosen:
                chosen.append(encoded)
    return [-1, *chosen]


def _encode_column(table_index: int, column_index: int) -> int:
    return table_index * 10_000 + column_index


def _decode_column(encoded: int) -> tuple[int, int]:
    return encoded // 10_000, encoded % 10_000


def _encoded_column_score(
    spec: FieldSpec, tables: tuple[TableSchema, ...], encoded: int
) -> float:
    if encoded < 0:
        return 0.0
    table_index, column_index = _decode_column(encoded)
    column = tables[table_index].columns[column_index]
    return _column_match_score(spec, column)


def _table_name_leaders(
    tables: tuple[TableSchema, ...],
) -> dict[int, tuple[float, str]]:
    leaders: dict[int, tuple[float, str]] = {}
    for table_index, table in enumerate(tables):
        for entity in ENTITIES:
            name_score = lexical_score(table.name, entity.table_aliases)
            current = leaders.get(table_index)
            if current is None or name_score > current[0]:
                leaders[table_index] = (name_score, entity.name)
    return leaders


def _greedy(space: _SearchSpace) -> list[int]:
    chromosome = [0] * space.length
    leaders = _table_name_leaders(space.tables)
    ranked: list[tuple[float, float, str, int, int]] = []
    for entity in ENTITIES:
        for choice, table_index in enumerate(space.table_choices[entity.name]):
            if table_index < 0:
                continue
            ranked.append(
                (
                    space.table_scores[(entity.name, table_index)],
                    lexical_score(space.tables[table_index].name, entity.table_aliases),
                    entity.name,
                    choice,
                    table_index,
                )
            )
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    table_choice_by_entity: dict[str, int] = {}
    used_tables: set[int] = set()
    for score, _name_score, entity_name, choice, table_index in ranked:
        if entity_name in table_choice_by_entity or table_index in used_tables:
            continue
        if score < TABLE_SCORE_MIN:
            continue
        leader_score, leader_entity = leaders.get(table_index, (0.0, ""))
        if leader_score >= 0.72 and leader_entity != entity_name:
            continue
        table_choice_by_entity[entity_name] = choice
        used_tables.add(table_index)

    for position, (entity_name, field_name) in enumerate(space.offsets):
        if field_name is None:
            chromosome[position] = table_choice_by_entity.get(entity_name, 0)
            continue
        table_pos = next(
            index
            for index, item in enumerate(space.offsets)
            if item == (entity_name, None)
        )
        table_index = space.table_choices[entity_name][chromosome[table_pos]]
        best_choice = 0
        best_score = -1.0
        for choice, encoded in enumerate(space.column_choices[(entity_name, field_name)]):
            if encoded < 0:
                score = 0.0
            else:
                encoded_table, _ = _decode_column(encoded)
                if table_index >= 0 and encoded_table != table_index:
                    continue
                score = space.column_scores[(entity_name, field_name, encoded)]
            if score > best_score:
                best_score = score
                best_choice = choice
        chromosome[position] = best_choice
    return chromosome


def _decode(space: _SearchSpace, chromosome: list[int]) -> MappingConfig:
    table_name_leader = _table_name_leaders(space.tables)

    pending: list[tuple[float, float, str, dict[str, Any], int]] = []
    for entity in ENTITIES:
        table_pos = space.offsets.index((entity.name, None))
        table_width = len(space.table_choices[entity.name])
        table_choice = chromosome[table_pos] % table_width if table_width else 0
        table_index = space.table_choices[entity.name][table_choice]
        if table_index < 0:
            continue
        table = space.tables[table_index]
        leader_score, leader_entity = table_name_leader.get(table_index, (0.0, ""))
        if leader_score >= 0.72 and leader_entity != entity.name:
            continue
        if not _table_qualifies_for_entity(entity, table):
            continue
        table_score = space.table_scores.get((entity.name, table_index), 0.0)
        name_score = lexical_score(table.name, entity.table_aliases)
        if table_score < TABLE_SCORE_MIN:
            continue
        fields: dict[str, str] = {}
        units: dict[str, str] = {}
        defaults: dict[str, Any] = {}
        used_columns: set[str] = set()
        spec_by_name = {spec.name: spec for spec in entity.fields}
        ordered_fields = [spec for spec in entity.fields if spec.required] + [
            spec for spec in entity.fields if not spec.required
        ]
        for spec in ordered_fields:
            best_encoded = -1
            best_score = -1.0
            for encoded in space.column_choices[(entity.name, spec.name)]:
                if encoded < 0:
                    continue
                encoded_table, column_index = _decode_column(encoded)
                if encoded_table != table_index:
                    continue
                column_name = space.tables[table_index].columns[column_index].name
                if column_name in used_columns:
                    continue
                score = space.column_scores[(entity.name, spec.name, encoded)]
                if score > best_score:
                    best_score = score
                    best_encoded = encoded
            if best_score < _field_accept_threshold(spec):
                best_encoded = -1
            if best_encoded < 0:
                continue
            _, column_index = _decode_column(best_encoded)
            column_name = space.tables[table_index].columns[column_index].name
            used_columns.add(column_name)
            fields[spec.name] = column_name
            if spec.name == "length_km":
                units[spec.name] = _infer_length_unit(column_name)
            elif spec.name == "active_power_mw":
                units[spec.name] = _infer_active_power_unit(column_name)
            elif spec.name == "reactive_power_mvar":
                units[spec.name] = _infer_reactive_power_unit(column_name)
            elif spec.name in UNIT_HINTS:
                units[spec.name] = UNIT_HINTS[spec.name]
        table = space.tables[table_index]
        required = _required_fields(entity, table)
        unresolved = [name for name in required if name not in fields]
        satisfied = True
        for name in unresolved:
            spec = spec_by_name[name]
            if spec.numeric:
                defaults[name] = VOLTAGE_DEFAULT_KV
                units.setdefault(name, UNIT_HINTS.get(name, "kV"))
            else:
                satisfied = False
                break
        if not satisfied:
            continue
        if entity.name == "lines":
            _apply_hierarchical_line_defaults(table, fields)
            sanitize_line_endpoint_fields(
                [column.name for column in table.columns],
                fields,
            )
        _sanitize_display_name_field(table, fields)
        _sanitize_coordinate_fields(table, fields)
        _sanitize_voltage_field(table, fields)
        if entity.name in {"lines", "switches", "loads", "generators", "sources", "transformers"}:
            _sanitize_in_service_field(table, fields)
        if entity.name == "buses":
            _sanitize_bus_id_field(table, fields)
        if entity.name == "loads":
            _sanitize_load_power_fields(table, fields)
            if "active_power_mw" in fields:
                defaults.setdefault("active_power_mw", 0.0)
                # Re-infer after sanitize in case the column survived with a wrong default unit.
                units["active_power_mw"] = _infer_active_power_unit(fields["active_power_mw"])
            if "reactive_power_mvar" in fields:
                defaults.setdefault("reactive_power_mvar", 0.0)
                units["reactive_power_mvar"] = _infer_reactive_power_unit(
                    fields["reactive_power_mvar"]
                )
        for name in _required_fields(entity, table):
            if name in fields:
                continue
            spec = spec_by_name[name]
            if spec.numeric:
                defaults[name] = VOLTAGE_DEFAULT_KV
                units.setdefault(name, UNIT_HINTS.get(name, "kV"))
            elif name not in {"from_bus", "to_bus"}:
                satisfied = False
                break
        if not satisfied:
            continue
        if entity.name == "loads" and "active_power_mw" not in fields:
            continue
        layer: dict[str, Any] = {
            "source": table.name,
            "fields": fields,
            "units": units,
        }
        if defaults:
            layer["defaults"] = defaults
        pending.append(
            (
                table_score,
                name_score,
                entity.name,
                layer,
                table_index,
            )
        )

    payload: dict[str, Any] = {"target_crs": None}
    pending.sort(key=lambda item: (-item[1], -item[0], item[2]))
    line_candidates = [item for item in pending if item[2] == "lines"]
    if line_candidates:
        preferred_line = min(
            line_candidates,
            key=lambda item: (
                _line_convert_cost(space.tables[item[4]]),
                _line_voltage_rank(item[3]["source"]),
                -item[1],
                -item[0],
            ),
        )
        pending = [preferred_line] + [
            item for item in pending if item is not preferred_line
        ]
    bus_candidates = [item for item in pending if item[2] == "buses"]
    if len(bus_candidates) > 1:
        preferred_bus = max(
            bus_candidates,
            key=lambda item: (space.tables[item[4]].rows, item[0], item[1]),
        )
        pending = [preferred_bus] + [
            item for item in pending if item is not preferred_bus
        ]
    line_prefix: str | None = None
    for _table_score, _name_score, entity_name, layer, table_index in pending:
        if entity_name == "lines":
            line_prefix = _table_voltage_prefix(layer["source"])
            break
    claimed: dict[int, str] = {}
    for _table_score, _name_score, entity_name, layer, table_index in pending:
        if (
            entity_name == "buses"
            and line_prefix is not None
            and _table_voltage_prefix(layer["source"]) not in {line_prefix, None}
        ):
            continue
        if entity_name == "substations":
            lines_layer = payload.get("lines")
            if lines_layer is not None and lines_layer.get("source") == layer.get("source"):
                continue
        current = claimed.get(table_index)
        if current is not None and current != entity_name:
            shared_connectivity_layer = {current, entity_name} <= {"buses", "lines"}
            table_columns = [column.name for column in space.tables[table_index].columns]
            hierarchical = detect_parent_column(table_columns) is not None
            if not (shared_connectivity_layer and hierarchical):
                continue
        if table_index not in claimed:
            claimed[table_index] = entity_name
        payload[entity_name] = layer
    return MappingConfig.model_validate(payload)


def _table_voltage_prefix(table_name: str) -> str | None:
    token = normalize_token(table_name)
    for prefix in ("bt", "mt", "at"):
        if (
            token.startswith(prefix)
            or token.endswith(prefix)
            or f"tramo{prefix}" in token
            or f"{prefix}tramo" in token
            or f"salida{prefix}" in token
            or f"{prefix}salida" in token
        ):
            return prefix
    return None


def _line_voltage_rank(table_name: str) -> int:
    """Prefer distribution inventories (BT) over transmission (AT) for line mapping."""

    return {"bt": 0, "mt": 1, "at": 2}.get(_table_voltage_prefix(table_name) or "", 3)


def _line_convert_cost(table: TableSchema) -> int:
    """Prefer compact line tables so GUI auto-convert finishes in minutes, not hours."""

    return 1 if table.rows > 50_000 else 0


def _apply_hierarchical_line_defaults(table: TableSchema, fields: dict[str, str]) -> None:
    """When a line table exposes a parent tramo column, default the distal endpoint to its id."""

    line_id = fields.get("id")
    if not line_id:
        return
    parent_field = fields.get("from_bus")
    if parent_field is None:
        parent_field = detect_parent_column([column.name for column in table.columns])
        if parent_field is not None:
            fields.setdefault("from_bus", parent_field)
    if parent_field is None:
        return
    if "padre" not in normalize_token(parent_field):
        return
    to_bus = fields.get("to_bus")
    if to_bus is None:
        fields["to_bus"] = line_id
        return
    token = normalize_token(to_bus)
    if any(marker in token for marker in _NON_ENDPOINT_MARKERS) or to_bus == parent_field:
        fields["to_bus"] = line_id


def _sanitize_coordinate_fields(table: TableSchema, fields: dict[str, str]) -> None:
    """Drop x/y mappings that are not coordinate-like columns."""

    lookup = {column.name: column for column in table.columns}
    for axis in ("x", "y"):
        column_name = fields.get(axis)
        if not column_name:
            continue
        column = lookup.get(column_name)
        token = normalize_token(column_name)
        if column is None or column.non_null_count == 0:
            fields.pop(axis, None)
            continue
        if not any(marker in token for marker in _COORDINATE_MARKERS):
            fields.pop(axis, None)
            continue
        if any(
            marker in token
            for marker in ("cantfase", "voltaje", "tension", "fase")
        ):
            fields.pop(axis, None)


def _sanitize_voltage_field(table: TableSchema, fields: dict[str, str]) -> None:
    """Drop voltage mappings that point at empty description/name columns."""

    column_name = fields.get("nominal_voltage_kv")
    if not column_name:
        return
    lookup = {column.name: column for column in table.columns}
    column = lookup.get(column_name)
    if column is None:
        return
    token = normalize_token(column_name)
    if column.non_null_count == 0 or token in {
        "descripcion",
        "description",
        "nombre",
        "name",
        "codigo",
        "code",
    }:
        fields.pop("nominal_voltage_kv", None)
        return
    if not is_numeric_dtype(column.dtype) and not any(
        marker in token for marker in ("tension", "volt", "kv", "nominal", "tennom")
    ):
        fields.pop("nominal_voltage_kv", None)


def _sanitize_in_service_field(table: TableSchema, fields: dict[str, str]) -> None:
    """Drop in_service mappings that point at GIS lifecycle/edit columns."""

    column_name = fields.get("in_service")
    if not column_name:
        return
    token = normalize_token(column_name)
    if token.startswith("estadog") or "estado_g" in column_name.casefold():
        fields.pop("in_service", None)
        return
    if any(
        marker in token
        for marker in ("geometr", "edicion", "edit", "cambio", "modific", "correg")
    ):
        fields.pop("in_service", None)


def _sanitize_bus_id_field(table: TableSchema, fields: dict[str, str]) -> None:
    """Prefer business ``codigo`` over surrogate numeric ``id`` for bus keys.

    GIS inventories often expose both an internal ID and a stable code (SED/SET).
    Loads and feeders typically reference the code, not the surrogate.
    """

    current = fields.get("id")
    if current is None:
        return
    if normalize_token(current) != "id":
        return
    best: ColumnSchema | None = None
    best_score = -1.0
    for column in table.columns:
        token = normalize_token(column.name)
        if token not in {"codigo", "code", "cod"} and not token.startswith("cod"):
            continue
        if any(
            marker in token
            for marker in ("norma", "catalogo", "catalogue", "armado", "oficina")
        ):
            continue
        if column.non_null_count <= 0:
            continue
        if is_numeric_dtype(column.dtype):
            continue
        uniqueness = column.unique_count / max(1, column.non_null_count)
        if uniqueness < 0.95:
            continue
        score = uniqueness + (0.05 if token in {"codigo", "code"} else 0.0)
        if score > best_score:
            best_score = score
            best = column
    if best is not None:
        fields["id"] = best.name


def _prefer_candidate_with_buses(
    space: _SearchSpace,
    candidates: list[list[int]],
    candidate_obj: list[tuple[float, ...]],
    selected_offset: int,
    weight_vec: tuple[float, ...],
) -> int:
    """If the front has any buses mapping, avoid selecting a bus-less chromosome."""

    selected_mapping = _decode(space, candidates[selected_offset])
    if selected_mapping.buses is not None:
        return selected_offset
    with_buses = [
        index
        for index, chromosome in enumerate(candidates)
        if _decode(space, chromosome).buses is not None
    ]
    if not with_buses:
        return selected_offset
    restricted = [candidate_obj[index] for index in with_buses]
    local = topsis_select(restricted, weight_vec)
    return with_buses[local]


def _voltage_column_type_ok(column: ColumnSchema) -> bool:
    """String kV columns (e.g. ``22,9``) still count as voltage-typed."""

    if is_numeric_dtype(column.dtype):
        return True
    token = normalize_token(column.name)
    return (
        "kv" in token
        or "tension" in token
        or "voltaje" in token
        or "voltage" in token
    )


_LOAD_POWER_REJECT_MARKERS = frozenset(
    {
        "kwh",
        "energia",
        "energy",
        "medidor",
        "meter",
        "nis",
        "cliente",
        "nombre",
        "direccion",
        "address",
        "fecha",
        "estado",
        "ubicacion",
        "geografica",
        "geografico",
        "distrito",
        "jerarquia",
        "coordenada",
        "coord",
        "utm",
        "este",
        "norte",
        "longitud",
        "latitud",
    }
)


def _sanitize_load_power_fields(table: TableSchema, fields: dict[str, str]) -> None:
    """Drop load power mappings that are energy counters or non-numeric inventory fields."""

    lookup = {column.name: column for column in table.columns}
    for logical in ("active_power_mw", "reactive_power_mvar"):
        column_name = fields.get(logical)
        if not column_name:
            continue
        column = lookup.get(column_name)
        token = normalize_token(column_name)
        if column is None or column.non_null_count == 0:
            fields.pop(logical, None)
            continue
        if any(marker in token for marker in _LOAD_POWER_REJECT_MARKERS):
            fields.pop(logical, None)
            continue
        if not is_numeric_dtype(column.dtype) and "demanda" not in token and "potencia" not in token:
            fields.pop(logical, None)


def _sanitize_display_name_field(table: TableSchema, fields: dict[str, str]) -> None:
    """Drop display-name mappings that would collide or are not object labels."""

    name_column = fields.get("name")
    if not name_column:
        return
    reserved = {
        column
        for key, column in fields.items()
        if key in {"id", "from_bus", "to_bus", "type_id", "bus_id", "hv_bus", "lv_bus"}
        and column
    }
    if name_column in reserved:
        fields.pop("name", None)
        return
    lookup = {column.name: column for column in table.columns}
    column = lookup.get(name_column)
    if column is None:
        return
    token = normalize_token(column.name)
    dtype = column.dtype.lower()
    if column.non_null_count == 0:
        fields.pop("name", None)
        return
    if (
        "datetime" in dtype
        or "timestamp" in dtype
        or dtype in {"date"}
        or any(
            marker in token
            for marker in (
                "fec",
                "fecha",
                "date",
                "datetime",
                "timestamp",
                "padre",
                "color",
                "rgb",
                "colour",
            )
        )
        or "norma" in token
    ):
        fields.pop("name", None)
        return
    if column.non_null_count > 1 and (column.unique_count / column.non_null_count) < 0.85:
        fields.pop("name", None)


def _required_fields(entity: EntitySpec, table: TableSchema) -> list[str]:
    spec_by_name = {spec.name: spec for spec in entity.fields}
    required = [spec.name for spec in entity.fields if spec.required]
    if entity.name == "lines" and table.is_spatial:
        return [name for name in required if name not in {"from_bus", "to_bus", "length_km"}]
    if entity.name == "lines":
        return [
            name
            for name in required
            if name not in {"from_bus", "to_bus"}
            or _field_is_plausible(spec_by_name[name], table)
        ]
    return required


def _objectives(space: _SearchSpace, chromosome: list[int]) -> tuple[float, ...]:
    mapping = _decode(space, chromosome)
    required_total = 0
    required_hit = 0
    lexical_values: list[float] = []
    type_hits = 0
    type_total = 0
    used_tables: list[str] = []
    lookup = {table.name: table for table in space.tables}
    plausible = {
        entity.name
        for entity in ENTITIES
        if any(index >= 0 for index in space.table_choices[entity.name])
    }

    for entity in ENTITIES:
        if entity.name not in plausible:
            continue
        layer = getattr(mapping, entity.name)
        required = [spec for spec in entity.fields if spec.required]
        required_total += len(required)
        if layer is None:
            continue
        used_tables.append(layer.source)
        table = lookup.get(layer.source)
        required_hit += sum(1 for spec in required if spec.name in layer.fields)
        for spec in entity.fields:
            column_name = layer.fields.get(spec.name)
            if not column_name or table is None:
                continue
            column = next((item for item in table.columns if item.name == column_name), None)
            if column is None:
                continue
            lexical_values.append(lexical_score(column.name, spec.aliases))
            if spec.numeric:
                type_total += 1
                if spec.name == "nominal_voltage_kv":
                    if _voltage_column_type_ok(column):
                        type_hits += 1
                elif is_numeric_dtype(column.dtype):
                    type_hits += 1

    coverage = required_hit / required_total if required_total else 0.0
    lexical = sum(lexical_values) / len(lexical_values) if lexical_values else 0.0
    types = type_hits / type_total if type_total else 1.0
    uniqueness = len(set(used_tables)) / len(used_tables) if used_tables else 0.0
    connectivity = _connectivity_readiness(mapping, lookup)
    compactness = _compactness_score(mapping, lookup)
    return (coverage, lexical, types, uniqueness, connectivity, compactness)


def _connectivity_readiness(
    mapping: MappingConfig,
    lookup: dict[str, TableSchema],
) -> float:
    """Higher when line endpoints can be resolved via parent/feeder or explicit buses."""

    if mapping.lines is None:
        return 0.0
    table = lookup.get(mapping.lines.source)
    if table is None:
        return 0.0
    columns = [column.name for column in table.columns]
    score = 0.0
    fields = mapping.lines.fields
    if fields.get("from_bus") or detect_parent_column(columns):
        score += 0.45
    if fields.get("to_bus") or fields.get("id"):
        score += 0.25
    if fields.get("feeder_id") or detect_feeder_column(columns):
        score += 0.20
    if mapping.buses is not None and mapping.buses.fields.get("id"):
        score += 0.10
    return min(1.0, score)


def _compactness_score(
    mapping: MappingConfig,
    lookup: dict[str, TableSchema],
) -> float:
    """Prefer manageable line inventories so GUI auto-convert finishes promptly."""

    if mapping.lines is None:
        return 0.5
    table = lookup.get(mapping.lines.source)
    if table is None:
        return 0.5
    rows = max(0, int(table.rows))
    if rows <= 0:
        return 1.0
    if rows <= COMPACT_LINE_ROW_LIMIT:
        return 1.0
    # Soft penalty above the compact threshold.
    return max(0.05, COMPACT_LINE_ROW_LIMIT / rows)


def _schema_payload(schema: DatasetSchema) -> dict[str, Any]:
    return {
        "tables": [
            {
                "name": table.name,
                "columns": [column.name for column in table.columns],
            }
            for table in schema.tables
        ]
    }


def _merge_llm(
    schema: DatasetSchema,
    seed: MappingConfig,
    proposed: dict[str, Any],
) -> MappingConfig:
    names = {table.name for table in schema.tables}
    columns = {
        table.name: {column.name for column in table.columns} for table in schema.tables
    }
    merged = seed.model_dump(exclude_none=True)
    for entity in ENTITIES:
        block = proposed.get(entity.name)
        if not isinstance(block, dict):
            continue
        source = str(block.get("source", "")).strip()
        fields = block.get("fields")
        if source not in names or not isinstance(fields, dict):
            continue
        cleaned: dict[str, str] = {}
        allowed = {spec.name for spec in entity.fields}
        for logical, column in fields.items():
            if logical not in allowed:
                continue
            column_name = str(column).strip()
            if column_name in columns[source]:
                cleaned[str(logical)] = column_name
        if not cleaned:
            continue
        units = {name: UNIT_HINTS[name] for name in cleaned if name in UNIT_HINTS}
        merged[entity.name] = {"source": source, "fields": cleaned, "units": units}
    return MappingConfig.model_validate(merged)


def _warnings(mapping: MappingConfig, schema: DatasetSchema) -> list[str]:
    warnings: list[str] = []
    mapped = [
        entity.name
        for entity in ENTITIES
        if getattr(mapping, entity.name) is not None
    ]
    if "buses" not in mapped:
        warnings.append("No buses mapping met required fields (id, nominal_voltage_kv).")
    elif mapping.buses is not None and mapping.buses.defaults.get("nominal_voltage_kv") is not None:
        warnings.append(
            "Buses use defaults.nominal_voltage_kv as placeholder; resolve via Tensiones "
            "lookup or edit the YAML before generating DGS."
        )
    if "lines" not in mapped:
        warnings.append("No lines mapping met required fields.")
    elif mapping.lines is not None:
        missing_connectivity = [
            field
            for field in ("from_bus", "to_bus")
            if field not in mapping.lines.fields
        ]
        if missing_connectivity:
            warnings.append(
                "Lines lack "
                + "/".join(missing_connectivity)
                + "; enable connectivity.apply_unambiguous and ensure bus x/y are mapped."
            )
    unused = []
    mapped_sources = {
        getattr(mapping, entity.name).source
        for entity in ENTITIES
        if getattr(mapping, entity.name) is not None
    }
    for table in schema.tables:
        if table.name not in mapped_sources:
            unused.append(table.name)
    if unused:
        warnings.append("Unmapped tables: " + ", ".join(unused[:12]))
    return warnings
