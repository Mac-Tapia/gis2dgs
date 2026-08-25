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


def _parent_identifier(value: object) -> str:
    """Normalize parent refs; accept ``977870 - LABEL`` inventory encodings."""

    text = str(value).strip()
    if " - " in text:
        text = text.split(" - ", 1)[0].strip()
    elif " – " in text:
        text = text.split(" – ", 1)[0].strip()
    return normalize_identifier(text)


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
        "codigotramopadre",
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


def _ensure_identifier_column(frame: pd.DataFrame, name: str) -> None:
    """Ensure a column can store normalized string identifiers (not compact float/int)."""

    if name not in frame.columns:
        frame[name] = pd.Series([pd.NA] * len(frame), dtype=object)
        return
    series = frame[name]
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        return
    frame[name] = series.astype(object)


def _column_holds_identifiers(series: pd.Series) -> bool:
    return bool(
        pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
    )


def _is_non_endpoint_column(name: str) -> bool:
    token = _normalize_token(name)
    return any(
        marker in token
        for marker in (
            "distrito",
            "district",
            "jerarquia",
            "localidad",
            "ubicacion",
            "direccion",
            "provincia",
            "departamento",
            "zona",
            "estado",
            "fecha",
            "color",
        )
    )


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
    """Fill line endpoint columns from parent/feeder hierarchy without mutating other columns.

    Resolved endpoints are always written to object-dtype ``from_bus`` / ``to_bus``
    columns when the mapped fields reuse compact numeric inventory columns (float32
    parent codes) or non-endpoint attributes (district, locality, etc.). That avoids
    ``TypeError: Invalid value '…' for dtype 'float32'`` from pandas ``.at`` writes.
    """

    result = lines.copy()
    write_from = from_bus_field
    write_to = to_bus_field

    if from_bus_field in result.columns and (
        from_bus_field == parent_field
        or not _column_holds_identifiers(result[from_bus_field])
        or _is_non_endpoint_column(from_bus_field)
    ):
        write_from = "from_bus"
    if to_bus_field in result.columns and (
        to_bus_field == parent_field
        or to_bus_field == from_bus_field
        or not _column_holds_identifiers(result[to_bus_field])
        or _is_non_endpoint_column(to_bus_field)
    ):
        write_to = "to_bus"
    if write_from == write_to:
        write_from = "from_bus"
        write_to = "to_bus"

    _ensure_identifier_column(result, write_from)
    _ensure_identifier_column(result, write_to)

    for index, row in result.iterrows():
        line_id = normalize_identifier(row[line_id_field])
        # Prefer already-resolved dedicated columns; otherwise read mapped fields.
        from_raw = row.get(write_from) if write_from in row.index else None
        if is_missing(from_raw) and from_bus_field in row.index and write_from != from_bus_field:
            from_raw = row.get(from_bus_field)
        to_raw = row.get(write_to) if write_to in row.index else None
        if is_missing(to_raw) and to_bus_field in row.index and write_to != to_bus_field:
            # Mapped to_bus may be a non-endpoint column; ignore it for distal id.
            if not _is_non_endpoint_column(to_bus_field):
                to_raw = row.get(to_bus_field)
            else:
                to_raw = None
        from_id = None if is_missing(from_raw) else normalize_identifier(from_raw)
        to_id = None if is_missing(to_raw) else normalize_identifier(to_raw)
        if (
            to_id is not None
            and from_id is not None
            and from_id not in root_parent_markers
            and from_id != line_id
            and write_from == from_bus_field
            and write_to == to_bus_field
        ):
            continue

        parent_raw = row[parent_field]
        parent_id = (
            None if is_missing(parent_raw) else _parent_identifier(parent_raw)
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

        result.at[index, write_from] = resolved_from
        result.at[index, write_to] = to_id if to_id is not None else line_id

    result.attrs["hierarchical_from_bus_field"] = write_from
    result.attrs["hierarchical_to_bus_field"] = write_to
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

    buses_table = buses.copy()
    _ensure_identifier_column(buses_table, bus_id_field)

    existing = {
        normalize_identifier(value)
        for value in buses_table[bus_id_field].tolist()
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
        return buses_table

    voltage_field = bus_mapping.fields.get("nominal_voltage_kv")
    default_voltage = bus_mapping.defaults.get("nominal_voltage_kv", 1.0)
    extra_rows: list[dict[str, object]] = []
    for bus_id in sorted(needed):
        row: dict[str, object] = {bus_id_field: bus_id}
        if voltage_field is not None:
            row[voltage_field] = default_voltage
        extra_rows.append(row)

    extension = pd.DataFrame(extra_rows)
    combined = pd.concat(
        [buses_table.drop(columns=["geometry"], errors="ignore"), extension],
        ignore_index=True,
    )
    crs = safe_frame_crs(buses_table)
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
    from_bus_field = str(
        updated_lines.attrs.get("hierarchical_from_bus_field", from_bus_field)
    )
    to_bus_field = str(
        updated_lines.attrs.get("hierarchical_to_bus_field", to_bus_field)
    )
    updated_buses = synthesize_endpoint_buses(
        dataset.layer(bus_layer),
        updated_lines,
        bus_mapping=bus_mapping,
        bus_id_field=bus_id_field,
        from_bus_field=from_bus_field,
        to_bus_field=to_bus_field,
    )

    line_mapping.fields["from_bus"] = from_bus_field
    line_mapping.fields["to_bus"] = to_bus_field

    updated = GisDataset()
    for name, frame in dataset.layers.items():
        if name == line_layer:
            updated.add_layer(name, updated_lines)
        elif name == bus_layer:
            updated.add_layer(name, updated_buses)
        else:
            updated.add_layer(name, frame)
    return updated, True
