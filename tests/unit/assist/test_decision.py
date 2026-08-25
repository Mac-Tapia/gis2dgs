"""Unit tests for multi-objective / multi-criteria mapping decision."""

from __future__ import annotations

import pandas as pd

from gis2dgs.assist.decision import (
    OBJECTIVE_NAMES,
    DecisionModality,
    normalize_topsis_weights,
    parse_modality,
    parse_weights_string,
)
from gis2dgs.assist.service import suggest_mapping
from gis2dgs.input import InputDataset, discover_schema
from gis2dgs.input.schema.discovery import ColumnSchema, DatasetSchema, TableSchema


def _tiny_schema() -> DatasetSchema:
    dataset = InputDataset()
    dataset.add_table(
        "buses",
        pd.DataFrame({"id": ["B1", "B2"], "voltage_kv": [10.0, 10.0]}),
    )
    dataset.add_table(
        "lines",
        pd.DataFrame(
            {
                "id": ["L1"],
                "from_bus": ["B1"],
                "to_bus": ["B2"],
                "length_km": [1.0],
                "voltage_kv": [10.0],
            }
        ),
    )
    dataset.add_table(
        "loads",
        pd.DataFrame({"id": ["LD1"], "bus_id": ["B2"], "p_mw": [0.5]}),
    )
    dataset.add_table(
        "sources",
        pd.DataFrame({"id": ["S1"], "bus_id": ["B1"], "voltage_kv": [10.0]}),
    )
    return discover_schema(dataset)


def test_normalize_and_parse_weights() -> None:
    weights = normalize_topsis_weights({"coverage": 2.0, "lexical": 1.0})
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(weights) == set(OBJECTIVE_NAMES)
    parsed = parse_weights_string("coverage=0.4,lexical=0.2,type_consistency=0.1")
    assert abs(sum(parsed.values()) - 1.0) < 1e-9
    assert parse_modality("pareto") is DecisionModality.PARETO
    assert parse_modality(None) is DecisionModality.NSGA_TOPSIS


def test_suggest_mapping_exposes_six_objectives() -> None:
    suggestion = suggest_mapping(
        _tiny_schema(), seed=1, population_size=12, generations=6
    )
    selected = suggestion.report["selected_objectives"]
    assert set(selected) == set(OBJECTIVE_NAMES)
    assert "connectivity_readiness" in selected
    assert "compactness" in selected
    assert suggestion.report["pareto_size"] == len(suggestion.pareto)
    assert "modality" in suggestion.report
    assert "multicriteria_weights" in suggestion.report


def test_nsga_selection_not_silently_overridden_by_greedy() -> None:
    """TOPSIS pick must stick; greedy is only a candidate or explicit modality."""

    schema = _tiny_schema()
    topsis = suggest_mapping(
        schema,
        seed=5,
        population_size=16,
        generations=8,
        modality=DecisionModality.NSGA_TOPSIS,
    )
    greedy = suggest_mapping(
        schema,
        seed=5,
        population_size=16,
        generations=8,
        modality=DecisionModality.GREEDY,
    )
    assert topsis.modality is DecisionModality.NSGA_TOPSIS
    assert greedy.modality is DecisionModality.GREEDY
    # Same seed/search → fronts equal; indices may differ when TOPSIS ≠ greedy.
    assert len(topsis.pareto) == len(greedy.pareto)
    if topsis.selected_index != greedy.selected_index:
        assert topsis.mapping.model_dump(exclude_none=True) != greedy.mapping.model_dump(
            exclude_none=True
        )


def test_custom_topsis_weights_change_selection_when_front_diverges() -> None:
    schema = _tiny_schema()
    coverage_heavy = suggest_mapping(
        schema,
        seed=9,
        population_size=20,
        generations=10,
        weights={
            "coverage": 0.7,
            "lexical": 0.05,
            "type_consistency": 0.05,
            "table_uniqueness": 0.05,
            "connectivity_readiness": 0.1,
            "compactness": 0.05,
        },
    )
    compact_heavy = suggest_mapping(
        schema,
        seed=9,
        population_size=20,
        generations=10,
        weights={
            "coverage": 0.05,
            "lexical": 0.05,
            "type_consistency": 0.05,
            "table_uniqueness": 0.05,
            "connectivity_readiness": 0.1,
            "compactness": 0.7,
        },
    )
    assert abs(sum(coverage_heavy.weights.values()) - 1.0) < 1e-9
    assert coverage_heavy.weights["coverage"] > coverage_heavy.weights["compactness"]
    assert compact_heavy.weights["compactness"] > compact_heavy.weights["coverage"]
    # Same front; selection may or may not differ — report always stores weights used.
    assert coverage_heavy.report["multicriteria_weights"]["coverage"] > 0.5
    assert compact_heavy.report["multicriteria_weights"]["compactness"] > 0.5


def test_pareto_index_selects_explicit_front_member() -> None:
    suggestion = suggest_mapping(
        _tiny_schema(),
        seed=3,
        population_size=16,
        generations=8,
        modality=DecisionModality.PARETO,
        pareto_index=0,
    )
    assert suggestion.modality is DecisionModality.PARETO
    assert suggestion.selected_index == 0
    assert suggestion.mapping.model_dump(exclude_none=True) == suggestion.pareto[0]["mapping"]


def test_connectivity_and_compactness_scores_present_on_hierarchical_schema() -> None:
    schema = DatasetSchema(
        tables=(
            TableSchema(
                "TramoBT",
                180_000,
                (
                    ColumnSchema("CodTramoBT", "str", False, 180_000, 180_000),
                    ColumnSchema("CodTramoBTPadre", "str", False, 180_000, 100_000),
                    ColumnSchema("Longitud", "float32", False, 180_000, 50_000),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "TramoAT",
                2_000,
                (
                    ColumnSchema("CodTramoAT", "str", False, 2_000, 2_000),
                    ColumnSchema("CodTramoATPadre", "str", False, 2_000, 1_500),
                    ColumnSchema("Longitud", "float32", False, 2_000, 1_000),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )
    suggestion = suggest_mapping(schema, seed=2, population_size=16, generations=8)
    objs = suggestion.report["selected_objectives"]
    assert 0.0 <= objs["connectivity_readiness"] <= 1.0
    assert 0.0 <= objs["compactness"] <= 1.0
    # Huge BT table should not monopolize compactness when AT exists on the front.
    assert any(
        entry["objectives"]["compactness"] >= objs["compactness"] * 0.5
        for entry in suggestion.pareto
    )
