from __future__ import annotations

from typing import TYPE_CHECKING

import geopandas as gpd
from geopandas import GeoSeries
from shapely.geometry import LineString, Point

from gis2dgs.assist.scoring import normalize_token
from gis2dgs.gis.geodataframe_utils import has_active_geometry, safe_frame_crs
from gis2dgs.gis.normalizer import (
    is_missing,
    normalize_number,
    parse_xy_from_geometry_text,
)

if TYPE_CHECKING:
    from gis2dgs.config.models import LayerMapping, MappingConfig


def _xy_from_mapped_values(x_value: object, y_value: object) -> Point | None:
    if is_missing(x_value) and is_missing(y_value):
        return None
    for candidate in (x_value, y_value):
        parsed = parse_xy_from_geometry_text(candidate)
        if parsed is not None and (
            is_missing(x_value)
            or is_missing(y_value)
            or str(x_value).strip() == str(y_value).strip()
            or parse_xy_from_geometry_text(y_value) is not None
        ):
            return Point(parsed[0], parsed[1])
    if is_missing(x_value) or is_missing(y_value):
        return None
    try:
        return Point(normalize_number(x_value), normalize_number(y_value))
    except ValueError:
        parsed = parse_xy_from_geometry_text(x_value) or parse_xy_from_geometry_text(
            y_value
        )
        if parsed is None:
            return None
        return Point(parsed[0], parsed[1])


def detect_span_endpoint_columns(columns: tuple[str, ...] | list[str]) -> tuple[str, str, str, str] | None:
    """Return X1/Y1/X2/Y2 column names when a table encodes span endpoints."""

    by_token = {normalize_token(name): name for name in columns}
    required = ("x1", "y1", "x2", "y2")
    if all(token in by_token for token in required):
        return (
            by_token["x1"],
            by_token["y1"],
            by_token["x2"],
            by_token["y2"],
        )
    return None


def infer_inventory_metric_crs(frame: gpd.GeoDataFrame, x_field: str, y_field: str) -> str | None:
    """Assign a metre-based CRS when exports omit EPSG but use projected inventory coordinates."""

    if x_field not in frame.columns or y_field not in frame.columns:
        return None
    sample = frame[[x_field, y_field]].dropna(how="any").head(25)
    if sample.empty:
        return None
    try:
        max_abs = max(
            float(abs(value))
            for column in (x_field, y_field)
            for value in sample[column]
        )
    except (TypeError, ValueError):
        return None
    if max_abs > 1_000.0:
        return "EPSG:32718"
    return None


def materialize_layer_linestrings(
    frame: gpd.GeoDataFrame,
    *,
    default_crs: str | None = None,
) -> gpd.GeoDataFrame:
    """Build LineString geometry from X1/Y1/X2/Y2 columns when geometry is absent."""

    if has_active_geometry(frame) and frame.geometry.notna().any():
        return frame
    endpoints = detect_span_endpoint_columns(tuple(frame.columns))
    if endpoints is None:
        return frame
    x1_field, y1_field, x2_field, y2_field = endpoints
    result = frame.copy()
    geometries: list[LineString | None] = []
    for _, row in result.iterrows():
        try:
            start = (
                normalize_number(row[x1_field]),
                normalize_number(row[y1_field]),
            )
            end = (
                normalize_number(row[x2_field]),
                normalize_number(row[y2_field]),
            )
            geometries.append(LineString([start, end]))
        except (TypeError, ValueError):
            geometries.append(None)
    crs = (
        default_crs
        or safe_frame_crs(frame)
        or infer_inventory_metric_crs(result, x1_field, y1_field)
    )
    return result.set_geometry(GeoSeries(geometries, crs=crs), crs=crs)


def materialize_layer_points(
    frame: gpd.GeoDataFrame,
    mapping: LayerMapping,
    *,
    default_crs: str | None = None,
) -> gpd.GeoDataFrame:
    """Build point geometry from mapped x/y columns when the layer has tabular coordinates only."""

    if _has_point_geometry(frame):
        return frame

    x_field = mapping.fields.get("x")
    y_field = mapping.fields.get("y")
    if not x_field or not y_field:
        return frame
    if x_field not in frame.columns or y_field not in frame.columns:
        return frame

    result = frame.copy()
    geometries = []
    for _, row in result.iterrows():
        point = _xy_from_mapped_values(row[x_field], row[y_field])
        geometries.append(point)
    crs = default_crs if default_crs is not None else safe_frame_crs(frame)
    if crs is None and x_field in frame.columns and y_field in frame.columns:
        crs = infer_inventory_metric_crs(frame, x_field, y_field)
    return result.set_geometry(GeoSeries(geometries, crs=crs), crs=crs)


def materialize_mapped_coordinates(
    dataset: "GisDataset",
    mapping: MappingConfig,
    *,
    default_crs: str | None = None,
) -> "GisDataset":
    """Materialize point/line geometry from mapped or heuristic inventory columns."""

    from .dataset import GisDataset

    shared_crs = mapping.target_crs or default_crs
    updated = GisDataset()
    bus_frame = None
    if mapping.buses is not None and mapping.buses.source in dataset.layers:
        bus_frame = materialize_layer_points(
            dataset.layer(mapping.buses.source),
            mapping.buses,
            default_crs=shared_crs,
        )
        shared_crs = shared_crs or safe_frame_crs(bus_frame)

    for name, frame in dataset.layers.items():
        if mapping.buses is not None and mapping.buses.source == name:
            updated.add_layer(name, bus_frame if bus_frame is not None else frame)
            continue
        if mapping.substations is not None and mapping.substations.source == name:
            updated.add_layer(
                name,
                materialize_layer_points(
                    frame,
                    mapping.substations,
                    default_crs=shared_crs,
                ),
            )
            continue
        if mapping.lines is not None and mapping.lines.source == name:
            updated.add_layer(
                name,
                materialize_layer_linestrings(frame, default_crs=shared_crs),
            )
            continue
        updated.add_layer(name, frame)
    return updated


def _has_point_geometry(frame: gpd.GeoDataFrame) -> bool:
    return has_active_geometry(frame) and frame.geometry.notna().any()
