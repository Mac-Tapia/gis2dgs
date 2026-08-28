"""Materialize electrical lines from GIS span geometry when tables lack bus endpoints."""

from __future__ import annotations

from math import hypot

from gis2dgs.config.models import MappingConfig
from gis2dgs.domain.bus import Bus
from gis2dgs.domain.bus import BusId
from gis2dgs.domain.identifiers import LineId
from gis2dgs.domain.line import Line
from gis2dgs.domain.network import NetworkModel
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.geodataframe_utils import has_active_geometry
from gis2dgs.gis.normalizer import is_missing, normalize_identifier, normalize_number


def augment_network_lines_from_geometry(
    network: NetworkModel,
    dataset: GisDataset,
    mapping: MappingConfig,
) -> int:
    """Add lines from mapped span geometry using nearest buses for connectivity.

    Inventory exports (e.g. EQPM with X1/Y1/X2/Y2) often omit explicit bus ids.
    Graphics and studies still need ElmLne objects; endpoints snap to the nearest
    mapped bus so IntGrf can draw each span at its GIS coordinates.
    """

    if mapping.lines is None or mapping.buses is None:
        return 0
    if mapping.lines.source not in dataset.layers:
        return 0

    frame = dataset.layer(mapping.lines.source)
    if not has_active_geometry(frame) or frame.geometry.isna().all():
        return 0

    line_id_field = mapping.lines.fields.get("id")
    if not line_id_field or line_id_field not in frame.columns:
        return 0

    default_voltage = float(mapping.lines.defaults.get("nominal_voltage_kv", 1.0))
    default_length_km = float(mapping.lines.defaults.get("length_km", 0.001))
    snap_tolerance_m = float(mapping.connectivity.tolerance_m)
    created = 0

    for row_index, row in frame.iterrows():
        geometry = row.geometry
        if geometry is None or geometry.is_empty:
            continue
        raw_id = row.get(line_id_field)
        if is_missing(raw_id):
            continue
        line_id = LineId(normalize_identifier(raw_id))
        if line_id in network.lines:
            continue
        coords = list(geometry.coords)
        if len(coords) < 2:
            continue
        x1, y1 = normalize_number(coords[0][0]), normalize_number(coords[0][1])
        x2, y2 = normalize_number(coords[-1][0]), normalize_number(coords[-1][1])
        from_bus = _endpoint_bus(
            network,
            x1,
            y1,
            default_voltage,
            snap_tolerance_m=snap_tolerance_m,
        )
        to_bus = _endpoint_bus(
            network,
            x2,
            y2,
            default_voltage,
            snap_tolerance_m=snap_tolerance_m,
        )
        if from_bus == to_bus:
            continue
        length_km = max(float(geometry.length) / 1000.0, default_length_km)
        network.add_line(
            Line(
                id=line_id,
                name=str(raw_id),
                from_bus=from_bus,
                to_bus=to_bus,
                length_km=length_km,
                nominal_voltage_kv=default_voltage,
            )
        )
        created += 1
    return created


def _endpoint_bus(
    network: NetworkModel,
    x: float,
    y: float,
    nominal_voltage_kv: float,
    *,
    snap_tolerance_m: float,
) -> BusId:
    """Reuse the nearest mapped bus or create a GIS endpoint bus."""

    nearest = _nearest_bus(network, x, y, exclude_geo=True)
    if nearest is not None:
        bus = network.buses[nearest]
        if bus.x is not None and bus.y is not None:
            if hypot(float(bus.x) - x, float(bus.y) - y) <= snap_tolerance_m:
                return nearest
    bus_id = BusId(f"GEO_{int(round(x))}_{int(round(y))}")
    if bus_id not in network.buses:
        network.add_bus(
            Bus(
                id=bus_id,
                name=str(bus_id),
                nominal_voltage_kv=nominal_voltage_kv,
                x=x,
                y=y,
            )
        )
    return bus_id


def _nearest_bus(
    network: NetworkModel,
    x: float,
    y: float,
    *,
    exclude_geo: bool = False,
) -> BusId | None:
    best_id: BusId | None = None
    best_distance = float("inf")
    for bus in network.buses.values():
        if exclude_geo and str(bus.id).startswith("GEO_"):
            continue
        if bus.x is None or bus.y is None:
            continue
        distance = hypot(float(bus.x) - x, float(bus.y) - y)
        if distance < best_distance:
            best_distance = distance
            best_id = bus.id
    return best_id
