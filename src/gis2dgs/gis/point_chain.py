"""Rebuild aerial-cable start/end points from an ordered point chain (structures/towers).

Inventory Excel exports often store line GEOMETRÍA as ``Linea:  N Coordenadas`` without
XY, while tower/structure tables keep ``Nodo: X- … Y- …``. This module:

1. Orders those points by feeder/line key + sequence
2. Walks hierarchical tramos along each feeder by cumulative length
3. Snaps each cable start/end to the nearest chain node (same coordinates)
4. Writes LineString geometry and from_bus/to_bus to those node ids
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from gis2dgs.gis.normalizer import (
    is_missing,
    normalize_identifier,
    normalize_number,
    parse_xy_from_geometry_text,
)


@dataclass(frozen=True, slots=True)
class PointChainLinkResult:
    feeders_linked: int
    lines_updated: int
    lines_skipped: int


def _point_xy(
    row: pd.Series, x_field: str | None, y_field: str | None
) -> tuple[float, float] | None:
    geometry = row.geometry if "geometry" in row.index else None
    if isinstance(geometry, Point) and not geometry.is_empty:
        return float(geometry.x), float(geometry.y)
    if x_field and y_field and x_field in row.index and y_field in row.index:
        for candidate in (row[x_field], row[y_field]):
            parsed = parse_xy_from_geometry_text(candidate)
            if parsed is not None:
                return parsed
        try:
            if not is_missing(row[x_field]) and not is_missing(row[y_field]):
                return normalize_number(row[x_field]), normalize_number(row[y_field])
        except ValueError:
            return None
    return None


def _ordered_chain(
    points: gpd.GeoDataFrame,
    *,
    id_field: str,
    key_field: str,
    sequence_field: str | None,
    x_field: str | None,
    y_field: str | None,
) -> dict[str, list[tuple[str, float, float]]]:
    buckets: dict[str, list[tuple[Any, str, float, float]]] = defaultdict(list)
    for _, row in points.iterrows():
        key_raw = row.get(key_field)
        if is_missing(key_raw):
            continue
        key = normalize_identifier(key_raw)
        bus_id = normalize_identifier(row.get(id_field))
        if not bus_id:
            continue
        xy = _point_xy(row, x_field, y_field)
        if xy is None:
            continue
        seq: Any = 0
        if (
            sequence_field
            and sequence_field in row.index
            and not is_missing(row[sequence_field])
        ):
            try:
                seq = normalize_number(row[sequence_field])
            except ValueError:
                seq = str(row[sequence_field])
        buckets[key].append((seq, bus_id, xy[0], xy[1]))

    ordered: dict[str, list[tuple[str, float, float]]] = {}
    for key, rows in buckets.items():
        rows.sort(key=lambda item: (item[0] is None, item[0], item[1]))
        chain: list[tuple[str, float, float]] = []
        for _, bus_id, x, y in rows:
            if chain and abs(chain[-1][1] - x) < 1e-6 and abs(chain[-1][2] - y) < 1e-6:
                continue
            chain.append((bus_id, x, y))
        if len(chain) >= 2:
            ordered[key] = chain
    return ordered


def _tramo_order(
    lines: gpd.GeoDataFrame,
    *,
    line_id_field: str,
    parent_field: str | None,
    feeder_field: str,
) -> dict[str, list[str]]:
    """Return feeder → line ids in root-to-leaf order (parent hierarchy)."""

    by_feeder: dict[str, list[str]] = defaultdict(list)
    parent_of: dict[str, str | None] = {}
    for _, row in lines.iterrows():
        line_id = normalize_identifier(row.get(line_id_field))
        if not line_id:
            continue
        feeder_raw = row.get(feeder_field)
        if is_missing(feeder_raw):
            continue
        feeder = normalize_identifier(feeder_raw)
        by_feeder[feeder].append(line_id)
        parent = None
        if parent_field and parent_field in row.index and not is_missing(row[parent_field]):
            parent = normalize_identifier(row[parent_field])
            if parent in {"0", ""}:
                parent = None
        parent_of[line_id] = parent

    ordered: dict[str, list[str]] = {}
    for feeder, members in by_feeder.items():
        children: dict[str | None, list[str]] = defaultdict(list)
        member_set = set(members)
        for line_id in members:
            parent = parent_of.get(line_id)
            if parent not in member_set:
                parent = None
            children[parent].append(line_id)
        for bucket in children.values():
            bucket.sort()
        sequence: list[str] = []
        stack = list(reversed(children.get(None, [])))
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            sequence.append(current)
            stack.extend(reversed(children.get(current, [])))
        for line_id in sorted(members):
            if line_id not in seen:
                sequence.append(line_id)
        ordered[feeder] = sequence
    return ordered


def _nearest_chain_index(
    chain: list[tuple[str, float, float]],
    distance_along: float,
    cumulative: list[float],
) -> int:
    if distance_along <= 0:
        return 0
    total = cumulative[-1] if cumulative else 0.0
    if distance_along >= total:
        return len(chain) - 1
    for index in range(1, len(cumulative)):
        if distance_along <= cumulative[index]:
            before = cumulative[index - 1]
            after = cumulative[index]
            if abs(distance_along - before) <= abs(after - distance_along):
                return index - 1
            return index
    return len(chain) - 1


def assign_line_endpoints_from_point_chain(
    lines: gpd.GeoDataFrame,
    points: gpd.GeoDataFrame,
    *,
    line_id_field: str,
    point_id_field: str,
    line_key_field: str,
    point_key_field: str,
    sequence_field: str | None = None,
    parent_field: str | None = None,
    length_field: str | None = None,
    length_unit_is_metres: bool = True,
    from_bus_field: str = "from_bus",
    to_bus_field: str = "to_bus",
    point_x_field: str | None = None,
    point_y_field: str | None = None,
) -> tuple[gpd.GeoDataFrame, PointChainLinkResult]:
    """Snap each cable's start/end to chain nodes that share the path coordinates."""

    chains = _ordered_chain(
        points,
        id_field=point_id_field,
        key_field=point_key_field,
        sequence_field=sequence_field,
        x_field=point_x_field,
        y_field=point_y_field,
    )
    if not chains:
        return lines, PointChainLinkResult(0, 0, len(lines))

    order = _tramo_order(
        lines,
        line_id_field=line_id_field,
        parent_field=parent_field,
        feeder_field=line_key_field,
    )

    result = lines.copy()
    result[from_bus_field] = (
        result[from_bus_field].astype(object)
        if from_bus_field in result.columns
        else pd.Series([pd.NA] * len(result), dtype=object, index=result.index)
    )
    result[to_bus_field] = (
        result[to_bus_field].astype(object)
        if to_bus_field in result.columns
        else pd.Series([pd.NA] * len(result), dtype=object, index=result.index)
    )

    id_to_label: dict[str, Any] = {}
    for label, row in result.iterrows():
        line_id = normalize_identifier(row.get(line_id_field))
        if line_id:
            id_to_label[line_id] = label

    new_geometry: dict[Any, LineString] = {}
    feeders_linked = 0
    lines_updated = 0
    lines_skipped = 0

    for feeder, line_ids in order.items():
        chain = chains.get(feeder)
        if chain is None or len(chain) < 2:
            lines_skipped += len(line_ids)
            continue
        feeders_linked += 1
        cumulative = [0.0]
        for index in range(1, len(chain)):
            x0, y0 = chain[index - 1][1], chain[index - 1][2]
            x1, y1 = chain[index][1], chain[index][2]
            cumulative.append(
                cumulative[-1] + ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            )
        path_length = cumulative[-1]
        cursor = 0.0
        for line_id in line_ids:
            label = id_to_label.get(line_id)
            if label is None:
                lines_skipped += 1
                continue
            row = result.loc[label]
            segment_m = 0.0
            if (
                length_field
                and length_field in row.index
                and not is_missing(row[length_field])
            ):
                try:
                    raw = normalize_number(row[length_field])
                    segment_m = (
                        float(raw) if length_unit_is_metres else float(raw) * 1000.0
                    )
                except ValueError:
                    segment_m = 0.0
            if segment_m <= 0 and path_length > 0 and line_ids:
                segment_m = path_length / max(len(line_ids), 1)

            start_idx = _nearest_chain_index(chain, cursor, cumulative)
            end_dist = min(path_length, cursor + max(segment_m, 0.0))
            end_idx = _nearest_chain_index(chain, end_dist, cumulative)
            if end_idx <= start_idx and start_idx < len(chain) - 1:
                end_idx = start_idx + 1
            if end_idx == start_idx and start_idx > 0:
                start_idx -= 1

            start_id, x0, y0 = chain[start_idx]
            end_id, x1, y1 = chain[end_idx]
            result.at[label, from_bus_field] = start_id
            result.at[label, to_bus_field] = end_id
            new_geometry[label] = LineString([(x0, y0), (x1, y1)])
            lines_updated += 1
            cursor = end_dist

    if new_geometry:
        geometries = []
        for label in result.index:
            if label in new_geometry:
                geometries.append(new_geometry[label])
            elif hasattr(result, "geometry"):
                geometries.append(result.geometry.loc[label])
            else:
                geometries.append(None)
        result = result.set_geometry(geometries, crs=getattr(result, "crs", None))

    result.attrs["hierarchical_from_bus_field"] = from_bus_field
    result.attrs["hierarchical_to_bus_field"] = to_bus_field
    result.attrs["point_chain_applied"] = True
    return result, PointChainLinkResult(feeders_linked, lines_updated, lines_skipped)
