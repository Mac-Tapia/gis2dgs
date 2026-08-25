from dataclasses import dataclass
from typing import Literal

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

from .exceptions import GisConnectivityError
from .geodataframe_utils import has_active_geometry, safe_frame_crs
from .normalizer import is_missing, normalize_identifier

EndpointName = Literal["from", "to"]


@dataclass(frozen=True, slots=True)
class BusCandidate:
    bus_id: str
    distance_m: float


@dataclass(frozen=True, slots=True)
class EndpointConnectionSuggestion:
    line_id: str
    endpoint: EndpointName
    current_bus_id: str | None
    candidates: tuple[BusCandidate, ...]
    resolved_bus_id: str | None

    @property
    def is_ambiguous(self) -> bool:
        return self.resolved_bus_id is None and len(self.candidates) > 1

    @property
    def has_match(self) -> bool:
        return bool(self.candidates)


@dataclass(frozen=True, slots=True)
class ConnectivityProposal:
    suggestions: tuple[EndpointConnectionSuggestion, ...]

    @property
    def resolved_count(self) -> int:
        return sum(item.resolved_bus_id is not None for item in self.suggestions)

    @property
    def unresolved_count(self) -> int:
        return sum(item.resolved_bus_id is None for item in self.suggestions)


def _require_metric_projected_crs(frame: gpd.GeoDataFrame, layer_name: str) -> CRS:
    frame_crs = safe_frame_crs(frame)
    if frame_crs is None:
        raise GisConnectivityError(f"Layer {layer_name!r} has no CRS.")
    crs = CRS.from_user_input(frame_crs)
    if not crs.is_projected:
        raise GisConnectivityError(
            f"Layer {layer_name!r} must use a projected CRS for metric endpoint matching."
        )
    units = {axis.unit_name.lower() for axis in crs.axis_info if axis.unit_name}
    if not any("metre" in unit or "meter" in unit for unit in units):
        raise GisConnectivityError(
            f"Layer {layer_name!r} must use metre-based projected coordinates."
        )
    return crs


def _validate_bus_geometries(buses: gpd.GeoDataFrame, bus_id_field: str) -> None:
    if bus_id_field not in buses.columns:
        raise GisConnectivityError(f"Bus ID column not found: {bus_id_field}")
    if buses.geometry.name not in buses.columns:
        raise GisConnectivityError("Bus layer has no active geometry column.")
    for index, geometry in buses.geometry.items():
        if not isinstance(geometry, Point) or geometry.is_empty:
            raise GisConnectivityError(
                f"Bus row {index!r} must have a non-empty Point geometry."
            )


def _line_endpoints(geometry: object, line_id: str) -> tuple[Point, Point]:
    if not isinstance(geometry, LineString) or geometry.is_empty:
        raise GisConnectivityError(
            f"Line {line_id!r} must have a non-empty LineString geometry."
        )
    coordinates = list(geometry.coords)
    if len(coordinates) < 2:
        raise GisConnectivityError(f"Line {line_id!r} has fewer than two coordinates.")
    return Point(coordinates[0]), Point(coordinates[-1])


def _candidate_matches(
    endpoint: Point,
    tree: STRtree,
    bus_ids: list[str],
    tolerance_m: float,
) -> tuple[BusCandidate, ...]:
    indexes = tree.query(endpoint.buffer(tolerance_m))
    candidates: list[BusCandidate] = []
    for raw_index in indexes:
        index = int(raw_index)
        geometry = tree.geometries[index]
        distance = float(endpoint.distance(geometry))
        if distance <= tolerance_m:
            candidates.append(BusCandidate(bus_id=bus_ids[index], distance_m=distance))
    return tuple(sorted(candidates, key=lambda item: (item.distance_m, item.bus_id)))


def _resolved_candidate(candidates: tuple[BusCandidate, ...], tie_tolerance_m: float) -> str | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0].bus_id
    if abs(candidates[0].distance_m - candidates[1].distance_m) <= tie_tolerance_m:
        return None
    return candidates[0].bus_id


def propose_line_endpoint_connections(
    lines: gpd.GeoDataFrame,
    buses: gpd.GeoDataFrame,
    *,
    line_id_field: str,
    bus_id_field: str,
    from_bus_field: str,
    to_bus_field: str,
    tolerance_m: float,
    tie_tolerance_m: float = 1e-6,
    missing_only: bool = True,
    repair_invalid_references: bool = True,
) -> ConnectivityProposal:
    """Suggest missing line endpoint references from GIS geometry without mutating data.

    The function intentionally requires a metre-based projected CRS. It returns proposals only;
    applying them is a separate explicit operation so topology repair remains auditable.
    """

    if tolerance_m <= 0:
        raise ValueError("tolerance_m must be greater than zero.")
    if tie_tolerance_m < 0:
        raise ValueError("tie_tolerance_m cannot be negative.")

    lines_crs = _require_metric_projected_crs(lines, "lines")
    buses_crs = _require_metric_projected_crs(buses, "buses")
    if lines_crs != buses_crs:
        raise GisConnectivityError("Line and bus layers must use the same CRS.")

    _validate_bus_geometries(buses, bus_id_field)
    required_line_columns = {line_id_field, from_bus_field, to_bus_field}
    missing_columns = sorted(required_line_columns - set(lines.columns))
    if missing_columns:
        raise GisConnectivityError(
            f"Line columns not found: {', '.join(missing_columns)}"
        )

    bus_ids = [normalize_identifier(value) for value in buses[bus_id_field].tolist()]
    bus_id_set = set(bus_ids)
    if len(bus_id_set) != len(bus_ids):
        raise GisConnectivityError("Bus IDs must be unique for spatial connectivity inference.")

    bus_geometries = list(buses.geometry)
    tree = STRtree(bus_geometries)
    suggestions: list[EndpointConnectionSuggestion] = []

    for _, row in lines.iterrows():
        line_id = normalize_identifier(row[line_id_field])
        from_point, to_point = _line_endpoints(row.geometry, line_id)
        endpoints: tuple[tuple[EndpointName, str, Point], ...] = (
            ("from", from_bus_field, from_point),
            ("to", to_bus_field, to_point),
        )
        for endpoint_name, field_name, point in endpoints:
            current_value = row[field_name]
            current_bus_id = (
                None if is_missing(current_value) else normalize_identifier(current_value)
            )
            current_is_valid = current_bus_id in bus_id_set if current_bus_id is not None else False
            if missing_only and current_is_valid:
                continue
            if missing_only and current_bus_id is not None and not repair_invalid_references:
                continue
            candidates = _candidate_matches(point, tree, bus_ids, tolerance_m)
            suggestions.append(
                EndpointConnectionSuggestion(
                    line_id=line_id,
                    endpoint=endpoint_name,
                    current_bus_id=current_bus_id,
                    candidates=candidates,
                    resolved_bus_id=_resolved_candidate(candidates, tie_tolerance_m),
                )
            )

    return ConnectivityProposal(suggestions=tuple(suggestions))


def apply_connection_proposal(
    lines: gpd.GeoDataFrame,
    proposal: ConnectivityProposal,
    *,
    line_id_field: str,
    from_bus_field: str,
    to_bus_field: str,
) -> gpd.GeoDataFrame:
    """Return a copy with only unambiguous proposed references applied."""

    result = lines.copy()
    for field_name in (from_bus_field, to_bus_field):
        if field_name not in result.columns:
            result[field_name] = pd.Series([pd.NA] * len(result), dtype=object)
        elif not (
            pd.api.types.is_object_dtype(result[field_name])
            or pd.api.types.is_string_dtype(result[field_name])
        ):
            result[field_name] = result[field_name].astype(object)

    index_by_line: dict[str, object] = {}
    for index, value in result[line_id_field].items():
        line_id = normalize_identifier(value)
        if line_id in index_by_line:
            raise GisConnectivityError(f"Duplicate line ID: {line_id}")
        index_by_line[line_id] = index

    for suggestion in proposal.suggestions:
        if suggestion.resolved_bus_id is None:
            continue
        if suggestion.line_id not in index_by_line:
            raise GisConnectivityError(
                f"Proposal references line not present in target layer: {suggestion.line_id}"
            )
        index = index_by_line[suggestion.line_id]
        field_name = from_bus_field if suggestion.endpoint == "from" else to_bus_field
        result.at[index, field_name] = suggestion.resolved_bus_id

    return result


def reconstruct_mapped_line_endpoints(
    dataset: "GisDataset",
    *,
    line_layer: str,
    bus_layer: str,
    line_id_field: str,
    bus_id_field: str,
    from_bus_field: str,
    to_bus_field: str,
    tolerance_m: float = 2.0,
    tie_tolerance_m: float = 1e-6,
    apply_unambiguous: bool = True,
) -> tuple["GisDataset", ConnectivityProposal]:
    """Propose line-bus links from geometry and optionally apply unambiguous matches.

    Proposals are always computed first. Applying them is an explicit second step
    controlled by ``apply_unambiguous``.
    """

    from .dataset import GisDataset

    lines = dataset.layer(line_layer).copy()
    buses = dataset.layer(bus_layer).copy()
    if not has_active_geometry(lines) or not has_active_geometry(buses):
        return dataset, ConnectivityProposal(suggestions=())
    for field_name in (from_bus_field, to_bus_field):
        if field_name not in lines.columns:
            lines[field_name] = None
    proposal = propose_line_endpoint_connections(
        lines,
        buses,
        line_id_field=line_id_field,
        bus_id_field=bus_id_field,
        from_bus_field=from_bus_field,
        to_bus_field=to_bus_field,
        tolerance_m=tolerance_m,
        tie_tolerance_m=tie_tolerance_m,
        missing_only=True,
        repair_invalid_references=True,
    )
    if apply_unambiguous:
        lines = apply_connection_proposal(
            lines,
            proposal,
            line_id_field=line_id_field,
            from_bus_field=from_bus_field,
            to_bus_field=to_bus_field,
        )
    updated = GisDataset()
    for name, frame in dataset.layers.items():
        updated.add_layer(name, lines if name == line_layer else frame)
    return updated, proposal


