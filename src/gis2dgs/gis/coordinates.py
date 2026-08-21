from __future__ import annotations

from typing import TYPE_CHECKING

import geopandas as gpd
from geopandas import GeoSeries
from shapely.geometry import Point

from gis2dgs.gis.geodataframe_utils import has_active_geometry, safe_frame_crs
from gis2dgs.gis.normalizer import is_missing, normalize_number

if TYPE_CHECKING:
    from gis2dgs.config.models import LayerMapping, MappingConfig


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
        x_value = row[x_field]
        y_value = row[y_field]
        if is_missing(x_value) or is_missing(y_value):
            geometries.append(None)
            continue
        geometries.append(
            Point(normalize_number(x_value), normalize_number(y_value))
        )
    crs = default_crs if default_crs is not None else safe_frame_crs(frame)
    return result.set_geometry(GeoSeries(geometries, crs=crs), crs=crs)


def materialize_mapped_coordinates(
    dataset: "GisDataset",
    mapping: MappingConfig,
    *,
    default_crs: str | None = None,
) -> "GisDataset":
    """Return a dataset copy with point geometry materialized for mapped bus/substation layers."""

    from .dataset import GisDataset

    updated = GisDataset()
    for name, frame in dataset.layers.items():
        layer_mapping = None
        if mapping.buses is not None and mapping.buses.source == name:
            layer_mapping = mapping.buses
        elif mapping.substations is not None and mapping.substations.source == name:
            layer_mapping = mapping.substations
        if layer_mapping is None:
            updated.add_layer(name, frame)
            continue
        updated.add_layer(
            name,
            materialize_layer_points(
                frame,
                layer_mapping,
                default_crs=mapping.target_crs or default_crs,
            ),
        )
    return updated


def _has_point_geometry(frame: gpd.GeoDataFrame) -> bool:
    if not has_active_geometry(frame):
        return False
    return frame.geometry.notna().any()
