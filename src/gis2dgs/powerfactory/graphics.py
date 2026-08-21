"""Build per-feeder single-line graphics (IntGrfnet / IntGrf / IntGrfcon)."""

from __future__ import annotations

from collections import defaultdict, deque

from gis2dgs.domain import NetworkModel
from gis2dgs.domain.identifiers import BusId, SourceId
from gis2dgs.domain.source import Source

from .classes import PowerFactoryClass
from .ids import ForeignKeyFactory
from .model import PowerFactoryModel, PowerFactoryObject, PowerFactoryReference
from .policy import PowerFactoryMappingPolicy

_SYM_BUS = "TermStrip"
_SYM_LINE = "d_lin"
_SYM_SOURCE = "d_sym"
_SYM_LOAD = "d_load"
_SYM_TRANSFORMER = "d_tr2"
_SPACING_X = 80.0
_SPACING_Y = 40.0


def ensure_feeder_head_sources(network: NetworkModel) -> int:
    """Attach an ElmXnet-equivalent Source at each feeder head bus if missing.

    Returns the number of sources created. Only acts on explicit feeder heads
    (bus id == feeder_id), not on generic topology roots.
    """

    heads = _feeder_head_buses(network, allow_topology_fallback=False)
    existing = {source.bus_id for source in network.sources.values()}
    created = 0
    for head_id in heads:
        if head_id in existing:
            continue
        bus = network.buses[head_id]
        code = str(head_id)
        network.add_source(
            Source(
                id=SourceId(code),
                name=code,
                bus_id=head_id,
                nominal_voltage_kv=bus.nominal_voltage_kv,
            )
        )
        existing.add(head_id)
        created += 1
    return created


def attach_feeder_graphics(
    model: PowerFactoryModel,
    network: NetworkModel,
    *,
    keys: ForeignKeyFactory,
    policy: PowerFactoryMappingPolicy,
    network_key: str | None = None,
    network_keys: dict[str, str] | None = None,
    default_network_key: str | None = None,
) -> int:
    """Create one IntGrfnet diagram per feeder with symbols labeled by operational code."""

    if not policy.create_feeder_graphics and not policy.create_feeder_objects:
        return 0

    membership = _feeder_membership(network)
    if not membership:
        return 0

    by_feeder: dict[str, set[str]] = defaultdict(set)
    for bus_id, feeder_id in membership.items():
        by_feeder[feeder_id].add(bus_id)

    default_key = default_network_key or network_key
    if default_key is None:
        raise ValueError("default_network_key or network_key is required")

    pages = 0
    for feeder_id, bus_ids in sorted(by_feeder.items()):
        parent_key = _diagram_parent_key(
            network, bus_ids, network_keys=network_keys, default_key=default_key
        )
        diagram_key = keys.make("grfnet", feeder_id)
        if policy.create_feeder_graphics:
            pages += 1
            model.add(
                PowerFactoryObject(
                    class_name=str(PowerFactoryClass.GRAPHIC_NET),
                    foreign_key=diagram_key,
                    name=_safe_name(feeder_id),
                    attributes={"snap_on": 0, "ortho_on": 0},
                    references={"data_folder": PowerFactoryReference(parent_key)},
                    parent=PowerFactoryReference(parent_key),
                    source_kind="feeder_diagram",
                    source_id=feeder_id,
                )
            )
        if policy.create_feeder_objects:
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

        positions = _layout_feeder(network, feeder_id, bus_ids)
        for bus_id in sorted(bus_ids):
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
                    symbol=_SYM_BUS,
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
                    symbol=_SYM_SOURCE,
                    x=bus_pos[0] - _SPACING_X,
                    y=bus_pos[1],
                    source_id=code,
                )
            )

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
                    symbol=_SYM_LOAD,
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
            if membership.get(from_id) != feeder_id and membership.get(to_id) != feeder_id:
                continue
            line_key = keys.make("line", line.id)
            if line_key not in model.objects:
                continue
            code = _operational_code(model.objects[line_key], str(line.id))
            x1, y1 = positions.get(from_id, (0.0, 0.0))
            x2, y2 = positions.get(to_id, (_SPACING_X, 0.0))
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            grf_key = keys.make("grf", f"line:{line.id}")
            model.add(
                _graphic(
                    foreign_key=grf_key,
                    name=code,
                    diagram_key=diagram_key,
                    data_key=line_key,
                    symbol=_SYM_LINE,
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
                        name=f"{code}_{index + 1}",
                        attributes={
                            "r_x0": px,
                            "r_y0": py,
                            "r_x1": mid_x,
                            "r_y1": mid_y,
                            "size_row": 2,
                        },
                        parent=PowerFactoryReference(grf_key),
                        source_kind="graphic_connection",
                        source_id=f"{code}:{index + 1}",
                    )
                )

        for transformer in network.transformers.values():
            hv = str(transformer.hv_bus)
            lv = str(transformer.lv_bus)
            if membership.get(hv) != feeder_id and membership.get(lv) != feeder_id:
                continue
            # Place each transformer once, on the HV-side feeder diagram.
            if membership.get(hv, feeder_id) != feeder_id:
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
                    symbol=_SYM_TRANSFORMER,
                    x=(x1 + x2) / 2.0,
                    y=(y1 + y2) / 2.0,
                    source_id=code,
                )
            )

    return pages


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
        # Fall back to a terminal on the feeder when no source exists.
        for bus_id in sorted(bus_ids):
            term_key = keys.make("bus", bus_id)
            if term_key in model.objects:
                head_source_key = term_key
                break
    if head_source_key is None:
        return

    cubicle_key = keys.cubicle(head_source_key, "1")
    obj_key = cubicle_key if cubicle_key in model.objects else head_source_key
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
    return tuple(BusId(bus_id) for bus_id in sorted(roots) if BusId(bus_id) in network.buses)


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
            membership[bus_key] = "NETWORK"
    return membership


def _layout_feeder(
    network: NetworkModel,
    feeder_id: str,
    bus_ids: set[str],
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    has_coords = False
    for bus_id in bus_ids:
        bus = network.buses.get(BusId(bus_id))
        if bus is None or bus.x is None or bus.y is None:
            continue
        positions[bus_id] = (float(bus.x), float(bus.y))
        has_coords = True
    if has_coords and len(positions) >= max(1, len(bus_ids) // 2):
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
    cleaned = value.strip() or "UNNAMED"
    return cleaned[:40]


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
