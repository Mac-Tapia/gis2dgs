from __future__ import annotations

import geopandas as gpd


def has_active_geometry(frame: gpd.GeoDataFrame) -> bool:
    try:
        name = frame.geometry.name
    except (AttributeError, KeyError, ValueError):
        return False
    return bool(name) and name in frame.columns


def safe_frame_crs(frame: gpd.GeoDataFrame) -> object | None:
    """Return CRS when the frame has an active geometry column, else None."""

    if not has_active_geometry(frame):
        return None
    try:
        return frame.crs
    except AttributeError:
        return None
