"""Unit tests for multimodal conversion strategies."""

from __future__ import annotations

from gis2dgs.assist.strategies import (
    ConversionStrategy,
    apply_strategy,
    detect_input_modality,
    select_conversion_strategy,
)
from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.input.schema.discovery import ColumnSchema, DatasetSchema, TableSchema


def _column(name: str, dtype: str = "str", unique: int = 100, rows: int = 100) -> ColumnSchema:
    return ColumnSchema(name, dtype, False, rows, unique)


def _schema_with_huge_bt_and_suministros() -> DatasetSchema:
    return DatasetSchema(
        tables=(
            TableSchema(
                "Nodos",
                5_000,
                (_column("Codigo", unique=5_000, rows=5_000), _column("Tension", "float64", 3, 5_000)),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "TramoBT",
                180_000,
                (
                    _column("CodTramoBT", unique=180_000, rows=180_000),
                    _column("NodoI", unique=50_000, rows=180_000),
                    _column("NodoF", unique=50_000, rows=180_000),
                    _column("Longitud", "float32", 80_000, 180_000),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "TramoAT",
                3_000,
                (
                    _column("CodTramoAT", unique=3_000, rows=3_000),
                    _column("NodoI", unique=2_000, rows=3_000),
                    _column("NodoF", unique=2_000, rows=3_000),
                    _column("Longitud", "float32", 2_000, 3_000),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "Suministros",
                50_000,
                (
                    _column("Medidor", unique=50_000, rows=50_000),
                    _column("KWH", "float64", 40_000, 50_000),
                    _column("Distrito", unique=20, rows=50_000),
                ),
                False,
                None,
                None,
                None,
            ),
            TableSchema(
                "Alimentadores",
                40,
                (
                    _column("Codigo", unique=40, rows=40),
                    _column("Conexion", unique=40, rows=40),
                    _column("Tension", "float64", 2, 40),
                ),
                False,
                None,
                None,
                None,
            ),
        )
    )


def _full_mapping() -> MappingConfig:
    return MappingConfig(
        buses=LayerMapping(source="Nodos", fields={"id": "Codigo", "nominal_voltage_kv": "Tension"}),
        lines=LayerMapping(
            source="TramoBT",
            fields={
                "id": "CodTramoBT",
                "from_bus": "NodoI",
                "to_bus": "NodoF",
                "length_km": "Longitud",
            },
        ),
        loads=LayerMapping(
            source="Suministros",
            fields={"id": "Medidor", "bus_id": "Distrito", "p_mw": "KWH"},
        ),
        sources=LayerMapping(
            source="Alimentadores",
            fields={"id": "Codigo", "bus_id": "Conexion", "nominal_voltage_kv": "Tension"},
        ),
    )


def test_detect_input_modality_tabular() -> None:
    assert detect_input_modality(_schema_with_huge_bt_and_suministros()) is not None


def test_network_core_drops_loads() -> None:
    mapping, rationale = apply_strategy(
        _full_mapping(),
        _schema_with_huge_bt_and_suministros(),
        ConversionStrategy.NETWORK_CORE,
    )
    assert mapping.loads is None
    assert mapping.buses is not None
    assert mapping.lines is not None
    assert mapping.sources is not None
    assert "core" in rationale.lower() or "Network core" in rationale


def test_compact_lines_prefers_smaller_tramo_table() -> None:
    mapping, rationale = apply_strategy(
        _full_mapping(),
        _schema_with_huge_bt_and_suministros(),
        ConversionStrategy.COMPACT_LINES,
    )
    assert mapping.lines is not None
    assert mapping.lines.source == "TramoAT"
    assert mapping.loads is None
    assert "TramoAT" in rationale


def test_auto_strategy_prefers_network_core_when_loads_are_weak() -> None:
    """Suministros mapped as loads with weak connectivity → network_core should beat full."""

    schema = _schema_with_huge_bt_and_suministros()
    decision = select_conversion_strategy(
        _full_mapping(),
        schema,
        strategy=ConversionStrategy.AUTO,
        weights={
            "coverage": 0.1,
            "lexical": 0.05,
            "type_consistency": 0.05,
            "table_uniqueness": 0.1,
            "connectivity_readiness": 0.35,
            "compactness": 0.35,
        },
    )
    names = [item.name for item in decision.candidates]
    assert ConversionStrategy.NETWORK_CORE in names
    assert ConversionStrategy.FULL_MAPPED in names
    assert ConversionStrategy.COMPACT_LINES in names
    # With compactness + connectivity heavy, full_mapped (huge BT + weak loads) loses.
    assert decision.selected in {
        ConversionStrategy.NETWORK_CORE,
        ConversionStrategy.COMPACT_LINES,
    }
    assert decision.report["strategy"] == decision.selected.value
    core = next(c for c in decision.candidates if c.name is ConversionStrategy.NETWORK_CORE)
    full = next(c for c in decision.candidates if c.name is ConversionStrategy.FULL_MAPPED)
    assert core.mapping.loads is None
    assert full.mapping.loads is not None


def test_explicit_strategy_override() -> None:
    decision = select_conversion_strategy(
        _full_mapping(),
        _schema_with_huge_bt_and_suministros(),
        strategy="full_mapped",
    )
    assert decision.selected is ConversionStrategy.FULL_MAPPED
    assert decision.candidates[decision.selected_index].mapping.loads is not None
