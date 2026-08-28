"""Build per-feeder single-line graphics (IntGrfnet / IntGrf / IntGrfcon)."""

from __future__ import annotations

from collections import defaultdict, deque
from math import hypot

from gis2dgs.domain import NetworkModel
from gis2dgs.domain.identifiers import BusId, SourceId
from gis2dgs.domain.source import Source

from .classes import PowerFactoryClass
from .ids import ForeignKeyFactory, sanitize_loc_name
from .model import PowerFactoryModel, PowerFactoryObject, PowerFactoryReference
from .policy import PowerFactoryMappingPolicy

_SPACING_X = 80.0
_SPACING_Y = 40.0
# Buses unreachable from feeder heads; must not reuse policy.network_id ("NETWORK")
# or PowerFactory opens an almost-empty diagram instead of a real feeder SLD.
_ORPHAN_FEEDER_ID = "__ORPHAN__"
_ORPHAN_DIAGRAM_NAME = "INVENTARIO"
# PowerFactory SLD viewport is diagram-units, not GIS metres. Cap axis span so
# symbols stay visible after import (Fit page / default zoom near origin).
_DIAGRAM_TARGET_EXTENT = 4000.0
_INTGRFCON_POINT_COUNT = 2
_GEO_BUS_PREFIX = "GEO_"


def ensure_feeder_head_sources(network: NetworkModel) -> int:
    """Attach an infinite-bus equivalent (ElmXnet) at each feeder / network head.

    Uses explicit feeder heads when present; otherwise topology roots (from-only
    buses). Every radial network must start with a technical equivalent.
    Geometry inventories (GEO_* endpoint buses, no real feeders) receive one
    equivalent at a single seed bus instead of one per span endpoint.
    """

    if _is_geometry_inventory_network(network):
        heads = _inventory_equivalent_heads(network)
    else:
        heads = _feeder_head_buses(network, allow_topology_fallback=True)
    existing = {source.bus_id for source in network.sources.values()}
    existing_ids = {str(source.id) for source in network.sources.values()}
    created = 0
    for head_id in heads:
        if head_id in existing:
            continue
        bus = network.buses[head_id]
        code = str(head_id)
        source_id = code if code not in existing_ids else f"EQ_{code}"
        network.add_source(
            Source(
                id=SourceId(source_id),
                name=f"Equiv_{code}"[:40],
                bus_id=head_id,
                nominal_voltage_kv=bus.nominal_voltage_kv,
            )
        )
        existing.add(head_id)
        existing_ids.add(source_id)
        created += 1
    return created


def collect_line_geometry_endpoints(
    dataset: object | None,
    *,
    line_layer: str | None,
    line_id_field: str | None,
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Return GIS span endpoints keyed by line id for diagram placement."""

    if dataset is None or not line_layer or not line_id_field:
        return {}
    from gis2dgs.gis.dataset import GisDataset
    from gis2dgs.gis.geodataframe_utils import has_active_geometry
    from gis2dgs.gis.normalizer import is_missing, normalize_identifier, normalize_number

    if not isinstance(dataset, GisDataset):
        return {}
    if line_layer not in dataset.layers:
        return {}
    frame = dataset.layer(line_layer)
    if not has_active_geometry(frame) or line_id_field not in frame.columns:
        return {}

    endpoints: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for _, row in frame.iterrows():
        geometry = row.geometry
        raw_id = row.get(line_id_field)
        if geometry is None or geometry.is_empty or is_missing(raw_id):
            continue
        coords = list(geometry.coords)
        if len(coords) < 2:
            continue
        start = (
            normalize_number(coords[0][0]),
            normalize_number(coords[0][1]),
        )
        end = (
            normalize_number(coords[-1][0]),
            normalize_number(coords[-1][1]),
        )
        endpoints[normalize_identifier(raw_id)] = (start, end)
    return endpoints


def attach_feeder_graphics(
    model: PowerFactoryModel,
    network: NetworkModel,
    *,
    keys: ForeignKeyFactory,
    policy: PowerFactoryMappingPolicy,
    network_key: str | None = None,
    network_keys: dict[str, str] | None = None,
    default_network_key: str | None = None,
    line_geometry_endpoints: dict[str, tuple[tuple[float, float], tuple[float, float]]]
    | None = None,
) -> int:
    """Create IntGrfnet diagram(s) with readable SLD placement.

    GIS coordinates are used when they remain readable after fit; otherwise the
    layout falls back to a topology single-line diagram so lines/equipment stay
    visible. With ``diagrams_per_feeder=True`` (default), each feeder gets its
    own diagram page even under a single ElmNet.
    """

    if not policy.create_feeder_graphics and not policy.create_feeder_objects:
        return 0

    membership = _feeder_membership(network)
    if not membership:
        return 0

    default_key = default_network_key or network_key
    if default_key is None:
        raise ValueError("default_network_key or network_key is required")

    collapse_diagrams = _is_geometry_inventory_network(network)
    if (
        not collapse_diagrams
        and policy.diagrams_per_feeder
        and not _has_real_feeder_membership(network)
    ):
        pseudo_feeders = {
            feeder_id
            for feeder_id in set(membership.values())
            if feeder_id not in {_ORPHAN_FEEDER_ID, policy.network_id}
        }
        if len(pseudo_feeders) > 1:
            collapse_diagrams = True

    if collapse_diagrams:
        by_feeder = {_ORPHAN_FEEDER_ID: set(membership.keys())}
    elif policy.diagrams_per_feeder or policy.split_networks_by_system:
        by_feeder: dict[str, set[str]] = defaultdict(set)
        for bus_id, feeder_id in membership.items():
            by_feeder[feeder_id].add(bus_id)
    else:
        by_feeder = {policy.network_id: set(membership.keys())}

    symbols = policy.graphic_symbols
    skip_loads = len(network.loads) > 5_000
    pages = 0
    geometry_endpoints = line_geometry_endpoints or {}
    feeder_items = sorted(
        by_feeder.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    has_real_feeders = any(feeder_id != _ORPHAN_FEEDER_ID for feeder_id in by_feeder)
    for feeder_id, bus_ids in feeder_items:
        if feeder_id == _ORPHAN_FEEDER_ID and has_real_feeders:
            continue
        diagram_name = (
            _ORPHAN_DIAGRAM_NAME if feeder_id == _ORPHAN_FEEDER_ID else feeder_id
        )
        parent_key = _diagram_parent_key(
            network, bus_ids, network_keys=network_keys, default_key=default_key
        )
        diagram_key = keys.make("grfnet", diagram_name)
        if policy.create_feeder_graphics:
            pages += 1
            model.add(
                PowerFactoryObject(
                    class_name=str(PowerFactoryClass.GRAPHIC_NET),
                    foreign_key=diagram_key,
                    name=_safe_name(diagram_name),
                    attributes={"snap_on": 0, "ortho_on": 0},
                    references={"data_folder": PowerFactoryReference(parent_key)},
                    parent=PowerFactoryReference(parent_key),
                    source_kind="feeder_diagram",
                    source_id=feeder_id,
                )
            )
        if (
            policy.create_feeder_objects
            and not collapse_diagrams
            and (policy.split_networks_by_system or policy.diagrams_per_feeder)
        ):
            _add_feeder_object(
                model,
                network=network,
                keys=keys,
                policy=policy,
                feeder_id=feeder_id,
                bus_ids=bus_ids,
                parent_key=parent_key,
            )
        if not policy.create_feeder_graphics:
            continue

        edges = _feeder_edges(network, bus_ids)
        positions = _resolve_diagram_positions(
            network,
            feeder_id,
            bus_ids,
            edges=edges,
            policy=policy,
            geometry_endpoints=geometry_endpoints,
        )
        for bus_id in sorted(bus_ids):
            if collapse_diagrams and str(bus_id).startswith(_GEO_BUS_PREFIX):
                continue
            term_key = keys.make("bus", bus_id)
            if term_key not in model.objects:
                continue
            code = _operational_code(model.objects[term_key], bus_id)
            x, y = positions.get(bus_id, (0.0, 0.0))
            model.add(
                _graphic(
                    foreign_key=keys.make("grf", f"bus:{bus_id}"),
                    name=code,
                    diagram_key=diagram_key,
                    data_key=term_key,
                    symbol=symbols.terminal,
                    x=x,
                    y=y,
                    source_id=code,
                )
            )

        for source in network.sources.values():
            if str(source.bus_id) not in bus_ids:
                continue
            source_key = keys.make("source", source.id)
            if source_key not in model.objects:
                continue
            code = _operational_code(model.objects[source_key], str(source.id))
            bus_pos = positions.get(str(source.bus_id), (0.0, 0.0))
            model.add(
                _graphic(
                    foreign_key=keys.make("grf", f"source:{source.id}"),
                    name=code,
                    diagram_key=diagram_key,
                    data_key=source_key,
                    symbol=symbols.source,
                    x=bus_pos[0] - _SPACING_X,
                    y=bus_pos[1],
                    source_id=code,
                )
            )

        if not skip_loads:
            for load in network.loads.values():
                if str(load.bus_id) not in bus_ids:
                    continue
                load_key = keys.make("load", load.id)
                if load_key not in model.objects:
                    continue
                code = _operational_code(model.objects[load_key], str(load.id))
                bus_pos = positions.get(str(load.bus_id), (0.0, 0.0))
                model.add(
                    _graphic(
                        foreign_key=keys.make("grf", f"load:{load.id}"),
                        name=code,
                        diagram_key=diagram_key,
                        data_key=load_key,
                        symbol=symbols.load,
                        x=bus_pos[0] + _SPACING_X * 0.35,
                        y=bus_pos[1] + _SPACING_Y * 0.35,
                        source_id=code,
                    )
                )

        for line in network.lines.values():
            from_id = str(line.from_bus)
            to_id = str(line.to_bus)
            if from_id not in bus_ids and to_id not in bus_ids:
                continue
            if (
                (policy.split_networks_by_system or policy.diagrams_per_feeder)
                and membership.get(from_id) != feeder_id
                and membership.get(to_id) != feeder_id
            ):
                continue
            line_key = keys.make("line", line.id)
            if line_key not in model.objects:
                continue
            code = _operational_code(model.objects[line_key], str(line.id))
            geom = geometry_endpoints.get(str(line.id))
            if geom is not None:
                (gx1, gy1), (gx2, gy2) = geom
                x1, y1 = positions.get(f"geom:{line.id}:0", (gx1, gy1))
                x2, y2 = positions.get(f"geom:{line.id}:1", (gx2, gy2))
            else:
                x1, y1 = positions.get(from_id, (0.0, 0.0))
                x2, y2 = positions.get(to_id, (_SPACING_X, 0.0))
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            grf_key = keys.make("grf", f"line:{line.id}")
            model.add(
                _graphic(
                    foreign_key=grf_key,
                    name=f"L_{code}"[:40],
                    diagram_key=diagram_key,
                    data_key=line_key,
                    symbol=symbols.line,
                    x=mid_x,
                    y=mid_y,
                    source_id=code,
                )
            )
            for index, (px, py) in enumerate(((x1, y1), (x2, y2))):
                model.add(
                    PowerFactoryObject(
                        class_name=str(PowerFactoryClass.GRAPHIC_CON),
                        foreign_key=keys.make("grfcon", f"line:{line.id}:{index}"),
                        name=f"C_{code}_{index + 1}"[:40],
                        attributes={
                            "r_x0": px,
                            "r_y0": py,
                            "r_x1": mid_x,
                            "r_y1": mid_y,
                            "r_x_sizerow": _INTGRFCON_POINT_COUNT,
                            "r_y_sizerow": _INTGRFCON_POINT_COUNT,
                        },
                        parent=PowerFactoryReference(grf_key),
                        source_kind="graphic_connection",
                        source_id=f"{code}:{index + 1}",
                    )
                )

        for transformer in network.transformers.values():
            hv = str(transformer.hv_bus)
            lv = str(transformer.lv_bus)
            if policy.split_networks_by_system or policy.diagrams_per_feeder:
                if membership.get(hv) != feeder_id and membership.get(lv) != feeder_id:
                    continue
                # Place each transformer once, on the HV-side feeder diagram.
                if membership.get(hv, feeder_id) != feeder_id:
                    continue
            elif hv not in bus_ids and lv not in bus_ids:
                continue
            tr_key = keys.make("trafo", transformer.id)
            if tr_key not in model.objects:
                continue
            grf_key = keys.make("grf", f"trafo:{transformer.id}")
            if grf_key in model.objects:
                continue
            code = _operational_code(model.objects[tr_key], str(transformer.id))
            x1, y1 = positions.get(hv, (0.0, 0.0))
            x2, y2 = positions.get(lv, (_SPACING_X, 0.0))
            model.add(
                _graphic(
                    foreign_key=grf_key,
                    name=code,
                    diagram_key=diagram_key,
                    data_key=tr_key,
                    symbol=symbols.transformer,
                    x=(x1 + x2) / 2.0,
                    y=(y1 + y2) / 2.0,
                    source_id=code,
                )
            )

    return pages


def _resolve_diagram_positions(
    network: NetworkModel,
    feeder_id: str,
    bus_ids: set[str],
    *,
    edges: list[tuple[str, str]],
    policy: PowerFactoryMappingPolicy,
    geometry_endpoints: dict[str, tuple[tuple[float, float], tuple[float, float]]]
    | None = None,
) -> dict[str, tuple[float, float]]:
    geometry_endpoints = geometry_endpoints or {}
    inventory = _is_geometry_inventory_network(network)
    layout = "gis" if inventory else (policy.diagram_layout if network.lines else "gis")
    if layout == "topology":
        positions = _layout_feeder(network, feeder_id, bus_ids, force_topology=True)
        return _fit_positions_with_geometry(
            positions,
            geometry_endpoints,
            target_extent=policy.diagram_target_extent,
        )

    positions = _layout_feeder(network, feeder_id, bus_ids, force_topology=False)
    fitted = _fit_positions_with_geometry(
        positions,
        geometry_endpoints,
        target_extent=policy.diagram_target_extent,
    )
    bus_fitted = {bus_id: fitted[bus_id] for bus_id in bus_ids if bus_id in fitted}
    if layout == "gis":
        return fitted

    if _median_edge_length(bus_fitted, edges) < policy.diagram_min_edge_length:
        positions = _layout_feeder(network, feeder_id, bus_ids, force_topology=True)
        return _fit_positions_with_geometry(
            positions,
            geometry_endpoints,
            target_extent=policy.diagram_target_extent,
        )
    return fitted


def _fit_positions_with_geometry(
    positions: dict[str, tuple[float, float]],
    geometry_endpoints: dict[str, tuple[tuple[float, float], tuple[float, float]]],
    *,
    target_extent: float,
) -> dict[str, tuple[float, float]]:
    anchor = dict(positions)
    for line_id, (start, end) in geometry_endpoints.items():
        anchor[f"geom:{line_id}:0"] = start
        anchor[f"geom:{line_id}:1"] = end
    return _fit_diagram_coordinates(anchor, target_extent=target_extent)


def _feeder_edges(network: NetworkModel, bus_ids: set[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for line in network.lines.values():
        a, b = str(line.from_bus), str(line.to_bus)
        if a in bus_ids and b in bus_ids:
            edges.append((a, b))
    for transformer in network.transformers.values():
        a, b = str(transformer.hv_bus), str(transformer.lv_bus)
        if a in bus_ids and b in bus_ids:
            edges.append((a, b))
    return edges


def _median_edge_length(
    positions: dict[str, tuple[float, float]],
    edges: list[tuple[str, str]],
) -> float:
    lengths: list[float] = []
    for a, b in edges:
        if a not in positions or b not in positions:
            continue
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        lengths.append(hypot(x2 - x1, y2 - y1))
    if not lengths:
        return float("inf")
    lengths.sort()
    return lengths[len(lengths) // 2]


def _fit_diagram_coordinates(
    positions: dict[str, tuple[float, float]],
    *,
    target_extent: float = _DIAGRAM_TARGET_EXTENT,
) -> dict[str, tuple[float, float]]:
    """Shift to origin and scale GIS/UTM extents into PowerFactory diagram units.

    A single bus at (0,0) mixed with projected metres must not skip normalisation:
    that left symbols at ~1e5–1e6 units and produced a blank NETWORK viewport after
    an otherwise successful DGS import.
    """

    if not positions:
        return positions
    xs = [xy[0] for xy in positions.values()]
    ys = [xy[1] for xy in positions.values()]
    min_x, min_y = min(xs), min(ys)
    span = max(max(xs) - min_x, max(ys) - min_y)
    shifted = {key: (x - min_x, y - min_y) for key, (x, y) in positions.items()}
    if span <= 0.0 or target_extent <= 0.0 or span <= target_extent:
        return shifted
    scale = target_extent / span
    return {key: (x * scale, y * scale) for key, (x, y) in shifted.items()}


# Backwards-compatible alias for callers/tests that still import the old name.
def _normalize_diagram_origin(
    positions: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    return _fit_diagram_coordinates(positions)


def _add_feeder_object(
    model: PowerFactoryModel,
    *,
    network: NetworkModel,
    keys: ForeignKeyFactory,
    policy: PowerFactoryMappingPolicy,
    feeder_id: str,
    bus_ids: set[str],
    parent_key: str,
) -> None:
    """Create DigSILENT ElmFeeder pointing at the feeder-head source cubicle."""

    head_source_key: str | None = None
    for source in network.sources.values():
        if str(source.bus_id) not in bus_ids:
            continue
        source_key = keys.make("source", source.id)
        if source_key in model.objects:
            head_source_key = source_key
            break
    if head_source_key is None:
        return

    cubicle_key = keys.cubicle(head_source_key, "1")
    if cubicle_key not in model.objects:
        # ElmFeeder.obj_id must reference StaCubic*, never ElmTerm.
        return
    obj_key = cubicle_key
    feeder_key = keys.make("feeder", feeder_id)
    if feeder_key in model.objects:
        return
    model.add(
        PowerFactoryObject(
            class_name=str(getattr(policy.classes, "feeder", PowerFactoryClass.FEEDER)),
            foreign_key=feeder_key,
            name=_safe_name(feeder_id),
            attributes={},
            references={"head_object": PowerFactoryReference(obj_key)},
            parent=PowerFactoryReference(parent_key),
            source_kind="feeder",
            source_id=feeder_id,
        )
    )


def _is_geometry_inventory_network(network: NetworkModel) -> bool:
    """True for GIS span inventories with GEO_* buses and no operational feeders."""

    geo_count = sum(
        1 for bus in network.buses.values() if str(bus.id).startswith(_GEO_BUS_PREFIX)
    )
    if geo_count == 0:
        return False
    return not _has_real_feeder_membership(network)


def _has_real_feeder_membership(network: NetworkModel) -> bool:
    """True when feeder_id groups multiple buses (real feeder topology)."""

    counts: dict[str, int] = defaultdict(int)
    for bus in network.buses.values():
        if bus.feeder_id is not None:
            counts[str(bus.feeder_id)] += 1
    return any(count >= 2 for count in counts.values())


def _inventory_equivalent_heads(network: NetworkModel) -> tuple[BusId, ...]:
    """Pick one seed bus for a geometry inventory equivalent source."""

    if network.sources:
        return ()
    for bus in sorted(network.buses.values(), key=lambda item: str(item.id)):
        if not str(bus.id).startswith(_GEO_BUS_PREFIX):
            return (bus.id,)
    return (min(network.buses.keys(), key=str),)


def _feeder_head_buses(
    network: NetworkModel,
    *,
    allow_topology_fallback: bool = True,
) -> tuple[BusId, ...]:
    heads: set[BusId] = set()
    # Explicit external equivalents mark feeder heads (e.g. MT salida 0101).
    for source in network.sources.values():
        if source.bus_id in network.buses:
            heads.add(source.bus_id)
    for bus in network.buses.values():
        if bus.feeder_id is not None and str(bus.id) == str(bus.feeder_id):
            heads.add(bus.id)
    feeder_ids = {
        str(bus.feeder_id)
        for bus in network.buses.values()
        if bus.feeder_id is not None
    }
    for feeder_id in feeder_ids:
        bus_id = BusId(feeder_id)
        if bus_id in network.buses:
            heads.add(bus_id)
    if heads:
        return tuple(sorted(heads, key=str))
    if not allow_topology_fallback:
        return ()

    as_from = {str(line.from_bus) for line in network.lines.values()}
    as_to = {str(line.to_bus) for line in network.lines.values()}
    roots = as_from - as_to
    topology_heads = tuple(
        BusId(bus_id) for bus_id in sorted(roots) if BusId(bus_id) in network.buses
    )
    if topology_heads:
        return topology_heads
    if network.buses:
        # Bus-only GIS inventories still need one head for ElmXnet / diagram seeding.
        first = min(network.buses.keys(), key=str)
        return (first,)
    return ()


def _diagram_parent_key(
    network: NetworkModel,
    bus_ids: set[str],
    *,
    network_keys: dict[str, str] | None,
    default_key: str,
) -> str:
    if not network_keys:
        return default_key
    systems: set[str] = set()
    for bus_id in bus_ids:
        bus = network.buses.get(BusId(bus_id))
        if bus is not None and bus.system_id is not None:
            systems.add(str(bus.system_id))
    if len(systems) == 1:
        system_id = next(iter(systems))
        return network_keys.get(system_id, default_key)
    return default_key


def _feeder_membership(network: NetworkModel) -> dict[str, str]:
    if _is_geometry_inventory_network(network):
        return {
            str(bus.id): _ORPHAN_FEEDER_ID for bus in network.buses.values()
        }

    adjacency: dict[str, set[str]] = defaultdict(set)
    for line in network.lines.values():
        a = str(line.from_bus)
        b = str(line.to_bus)
        adjacency[a].add(b)
        adjacency[b].add(a)
    for transformer in network.transformers.values():
        a = str(transformer.hv_bus)
        b = str(transformer.lv_bus)
        adjacency[a].add(b)
        adjacency[b].add(a)

    if not adjacency:
        return {
            str(bus.id): _ORPHAN_FEEDER_ID for bus in network.buses.values()
        }

    heads = _feeder_head_buses(network, allow_topology_fallback=True)
    membership: dict[str, str] = {}
    for head in heads:
        bus = network.buses[head]
        feeder_id = str(bus.feeder_id) if bus.feeder_id is not None else str(head)
        queue: deque[str] = deque([str(head)])
        while queue:
            current = queue.popleft()
            if current in membership:
                continue
            membership[current] = feeder_id
            for neighbor in adjacency.get(current, ()):
                if neighbor not in membership:
                    queue.append(neighbor)

    for bus in network.buses.values():
        bus_key = str(bus.id)
        if bus_key in membership:
            continue
        if bus.feeder_id is not None:
            membership[bus_key] = str(bus.feeder_id)
        else:
            membership[bus_key] = _ORPHAN_FEEDER_ID
    return membership


def _layout_feeder(
    network: NetworkModel,
    feeder_id: str,
    bus_ids: set[str],
    *,
    force_topology: bool = False,
) -> dict[str, tuple[float, float]]:
    if not force_topology:
        positions: dict[str, tuple[float, float]] = {}
        has_coords = False
        for bus_id in bus_ids:
            bus = network.buses.get(BusId(bus_id))
            if bus is None or bus.x is None or bus.y is None:
                continue
            positions[bus_id] = (float(bus.x), float(bus.y))
            has_coords = True
        if has_coords and len(positions) >= max(1, len(bus_ids) // 2):
            # Fill buses without GIS coords near a connected neighbour that has one.
            adjacency: dict[str, set[str]] = defaultdict(set)
            for line in network.lines.values():
                a = str(line.from_bus)
                b = str(line.to_bus)
                if a in bus_ids and b in bus_ids:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
            missing = [bus_id for bus_id in bus_ids if bus_id not in positions]
            changed = True
            while missing and changed:
                changed = False
                still: list[str] = []
                for bus_id in missing:
                    neighbour_xy = [
                        positions[n]
                        for n in adjacency.get(bus_id, ())
                        if n in positions
                    ]
                    if neighbour_xy:
                        xs = [xy[0] for xy in neighbour_xy]
                        ys = [xy[1] for xy in neighbour_xy]
                        positions[bus_id] = (sum(xs) / len(xs), sum(ys) / len(ys))
                        changed = True
                    else:
                        still.append(bus_id)
                missing = still
            if missing:
                # Isolated nodes without coords: place east of the GIS extent.
                max_x = max((xy[0] for xy in positions.values()), default=0.0)
                max_y = max((xy[1] for xy in positions.values()), default=0.0)
                for index, bus_id in enumerate(sorted(missing)):
                    positions[bus_id] = (max_x + _SPACING_X * (index + 1), max_y)
            return positions

    adjacency: dict[str, set[str]] = defaultdict(set)
    for line in network.lines.values():
        a = str(line.from_bus)
        b = str(line.to_bus)
        if a in bus_ids and b in bus_ids:
            adjacency[a].add(b)
            adjacency[b].add(a)

    head = feeder_id if feeder_id in bus_ids else next(iter(sorted(bus_ids)))
    for bus_id in bus_ids:
        bus = network.buses.get(BusId(bus_id))
        if bus is not None and bus.feeder_id is not None and str(bus.id) == str(bus.feeder_id):
            head = bus_id
            break

    depth: dict[str, int] = {head: 0}
    queue: deque[str] = deque([head])
    order: dict[int, list[str]] = defaultdict(list)
    order[0].append(head)
    while queue:
        current = queue.popleft()
        for neighbor in sorted(adjacency.get(current, ())):
            if neighbor in depth:
                continue
            depth[neighbor] = depth[current] + 1
            order[depth[neighbor]].append(neighbor)
            queue.append(neighbor)

    for bus_id in sorted(bus_ids):
        if bus_id not in depth:
            depth[bus_id] = max(depth.values(), default=0) + 1
            order[depth[bus_id]].append(bus_id)

    laid: dict[str, tuple[float, float]] = {}
    for level, nodes in sorted(order.items()):
        for index, bus_id in enumerate(nodes):
            laid[bus_id] = (level * _SPACING_X, index * _SPACING_Y)
    return laid


def _operational_code(obj: PowerFactoryObject, fallback: str) -> str:
    # Prefer mapped display name (operational label) over internal ids.
    code = (obj.name or obj.source_id or fallback).strip()
    return _safe_name(code or fallback)


def _safe_name(value: str) -> str:
    return sanitize_loc_name(value, fallback="UNNAMED")


def _graphic(
    *,
    foreign_key: str,
    name: str,
    diagram_key: str,
    data_key: str,
    symbol: str,
    x: float,
    y: float,
    source_id: str,
) -> PowerFactoryObject:
    return PowerFactoryObject(
        class_name=str(PowerFactoryClass.GRAPHIC),
        foreign_key=foreign_key,
        name=name,
        attributes={
            "symbol_name": symbol,
            "center_x": x,
            "center_y": y,
        },
        references={"data_object": PowerFactoryReference(data_key)},
        parent=PowerFactoryReference(diagram_key),
        source_kind="graphic",
        source_id=source_id,
    )
