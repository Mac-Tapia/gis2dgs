from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

import geopandas as gpd
import pandas as pd
from geopandas import GeoSeries

from gis2dgs.gis.geodataframe_utils import safe_frame_crs
from gis2dgs.gis.normalizer import is_missing, normalize_identifier

if TYPE_CHECKING:
    from gis2dgs.config.models import LayerMapping

ROOT_PARENT_MARKERS = frozenset({"0", ""})
_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _normalize_token(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_only = "".join(char for char in folded if not unicodedata.combining(char))
    return _TOKEN_SPLIT.sub("", ascii_only)


def detect_parent_column(columns: tuple[str, ...] | list[str]) -> str | None:
    """Return a line-table column that encodes a parent segment reference, if any."""

    best_name: str | None = None
    aliases = (
        "from_bus",
        "nodo_i",
        "bus1",
        "origen",
        "padre",
        "codtramobtpadre",
        "codtramomtpadre",
        "tramopadre",
    )
    for name in columns:
        token = _normalize_token(name)
        if "padre" in token and ("tramo" in token or "segment" in token):
            return name
        if token in {_normalize_token(alias) for alias in aliases}:
            return name
        if any(_normalize_token(alias) in token for alias in aliases if len(alias) >= 4):
            best_name = name
    return best_name


def detect_feeder_column(columns: tuple[str, ...] | list[str]) -> str | None:
    """Return a feeder/salida column used as the upstream endpoint for root segments."""

    best_name: str | None = None
    aliases = (
        "codsalidabt",
        "codsalidamt",
        "salida",
        "feeder",
        "alimentador",
    )
    for name in columns:
        token = _normalize_token(name)
        if "salida" in token:
            return name
        if token in {_normalize_token(alias) for alias in aliases}:
            return name
    return best_name


def apply_hierarchical_line_endpoints(
    lines: gpd.GeoDataFrame,
    *,
    line_id_field: str,
    parent_field: str,
    feeder_field: str | None,
    from_bus_field: str = "from_bus",
    to_bus_field: str = "to_bus",
    root_parent_markers: frozenset[str] = ROOT_PARENT_MARKERS,
) -> gpd.GeoDataFrame:
    """Fill line endpoint columns from parent/feeder hierarchy without mutating other columns."""

    result = lines.copy()
    if from_bus_field not in result.columns:
        result[from_bus_field] = pd.NA
    if to_bus_field not in result.columns:
        result[to_bus_field] = pd.NA

    for index, row in result.iterrows():
        line_id = normalize_identifier(row[line_id_field])
        from_raw = row.get(from_bus_field)
        to_raw = row.get(to_bus_field)
        from_id = (
            None if is_missing(from_raw) else normalize_identifier(from_raw)
        )
        to_id = None if is_missing(to_raw) else normalize_identifier(to_raw)
        if (
            to_id is not None
            and from_id is not None
            and from_id not in root_parent_markers
            and from_id != line_id
        ):
            continue

        parent_raw = row[parent_field]
        parent_id = (
            None
            if is_missing(parent_raw)
            else normalize_identifier(parent_raw)
        )
        feeder_id = None
        if feeder_field is not None and feeder_field in row.index:
            feeder_raw = row[feeder_field]
            if not is_missing(feeder_raw):
                feeder_id = normalize_identifier(feeder_raw)

        resolved_from = from_id if from_id is not None else parent_id
        if (
            resolved_from is None
            or resolved_from in root_parent_markers
            or resolved_from == line_id
        ):
            resolved_from = feeder_id
        if resolved_from is None:
            continue

        result.at[index, from_bus_field] = resolved_from
        result.at[index, to_bus_field] = to_id if to_id is not None else line_id

    return result


def synthesize_endpoint_buses(
    buses: gpd.GeoDataFrame,
    lines: gpd.GeoDataFrame,
    *,
    bus_mapping: LayerMapping,
    bus_id_field: str,
    from_bus_field: str,
    to_bus_field: str,
) -> gpd.GeoDataFrame:
    """Append placeholder bus rows for line endpoints missing from the configured bus layer."""

    existing = {
        normalize_identifier(value)
        for value in buses[bus_id_field].tolist()
        if not is_missing(value)
    }
    needed: set[str] = set()
    for field_name in (from_bus_field, to_bus_field):
        if field_name not in lines.columns:
            continue
        for value in lines[field_name].tolist():
            if is_missing(value):
                continue
            bus_id = normalize_identifier(value)
            if bus_id not in existing:
                needed.add(bus_id)

    if not needed:
        return buses

    voltage_field = bus_mapping.fields.get("nominal_voltage_kv")
    default_voltage = bus_mapping.defaults.get("nominal_voltage_kv", 1.0)
    extra_rows: list[dict[str, object]] = []
    for bus_id in sorted(needed):
        row: dict[str, object] = {bus_id_field: bus_id}
        if voltage_field is not None:
            row[voltage_field] = default_voltage
        extra_rows.append(row)

    extension = pd.DataFrame(extra_rows)
    combined = pd.concat([buses.drop(columns=["geometry"], errors="ignore"), extension], ignore_index=True)
    crs = safe_frame_crs(buses)
    return gpd.GeoDataFrame(combined).set_geometry(
        GeoSeries([None] * len(combined), crs=crs),
        crs=crs,
    )


def prepare_hierarchical_connectivity(
    dataset: "GisDataset",
    *,
    line_layer: str,
    bus_layer: str,
    line_mapping: LayerMapping,
    bus_mapping: LayerMapping,
) -> tuple["GisDataset", bool]:
    """Infer line endpoints and synthesize buses when explicit connectivity columns are absent."""

    from .dataset import GisDataset

    if line_layer not in dataset.layers or bus_layer not in dataset.layers:
        return dataset, False

    line_id_field = line_mapping.fields.get("id")
    bus_id_field = bus_mapping.fields.get("id")
    if not line_id_field or not bus_id_field:
        return dataset, False

    lines = dataset.layer(line_layer)
    parent_field = line_mapping.fields.get("from_bus") or detect_parent_column(
        tuple(lines.columns)
    )
    if parent_field is None:
        return dataset, False

    feeder_field = line_mapping.fields.get("feeder_id")
    if feeder_field is None:
        feeder_field = detect_feeder_column(tuple(lines.columns))

    from_bus_field = line_mapping.fields.get("from_bus", "from_bus")
    to_bus_field = line_mapping.fields.get("to_bus", "to_bus")
    if line_mapping.fields.get("from_bus") is None:
        from_bus_field = "from_bus"
    if line_mapping.fields.get("to_bus") is None:
        to_bus_field = "to_bus"

    updated_lines = apply_hierarchical_line_endpoints(
        lines,
        line_id_field=line_id_field,
        parent_field=parent_field,
        feeder_field=feeder_field,
        from_bus_field=from_bus_field,
        to_bus_field=to_bus_field,
    )
    updated_buses = synthesize_endpoint_buses(
        dataset.layer(bus_layer),
        updated_lines,
        bus_mapping=bus_mapping,
        bus_id_field=bus_id_field,
        from_bus_field=from_bus_field,
        to_bus_field=to_bus_field,
    )

    line_mapping.fields.setdefault("from_bus", from_bus_field)
    line_mapping.fields.setdefault("to_bus", to_bus_field)

    updated = GisDataset()
    for name, frame in dataset.layers.items():
        if name == line_layer:
            updated.add_layer(name, updated_lines)
        elif name == bus_layer:
            updated.add_layer(name, updated_buses)
        else:
            updated.add_layer(name, frame)
    return updated, True
