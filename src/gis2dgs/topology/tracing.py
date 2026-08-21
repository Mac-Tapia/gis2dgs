from collections import defaultdict, deque
from dataclasses import dataclass

from gis2dgs.domain.network import NetworkModel

from .analysis import active_source_buses
from .graph import NetworkGraph, build_graph, edge_ref
from .models import EdgeRef, FeederOverlap, FeederTrace, OpenSwitchBoundary


@dataclass(frozen=True, slots=True)
class TracePolicy:
    """Rules controlling feeder tracing at electrical boundaries."""

    cross_transformers: bool = False
    stop_at_other_sources: bool = True


def _edge_allowed(data: dict[str, object], policy: TracePolicy) -> bool:
    if data.get("object_type") == "transformer" and not policy.cross_transformers:
        return False
    return True


def _reachable_downstream(
    graph: NetworkGraph,
    *,
    source_bus: str,
    root_bus: str,
    root_key: str,
    other_source_buses: set[str],
    policy: TracePolicy,
) -> tuple[set[str], set[tuple[str, str, str]], set[str]]:
    buses: set[str] = {source_bus, root_bus}
    expanded: set[str] = set()
    visited_edges: set[tuple[str, str, str]] = set()
    boundaries: set[str] = {source_bus}
    queue: deque[str] = deque([root_bus])

    root_pair = tuple(sorted((source_bus, root_bus)))
    visited_edges.add((root_pair[0], root_pair[1], root_key))

    while queue:
        current = queue.popleft()
        if current in expanded:
            continue
        expanded.add(current)
        if policy.stop_at_other_sources and current in other_source_buses:
            boundaries.add(current)
            continue

        for _, neighbor, key, data in graph.edges(current, keys=True, data=True):
            neighbor = str(neighbor)
            key = str(key)
            pair = tuple(sorted((current, neighbor)))
            identity = (pair[0], pair[1], key)
            if identity in visited_edges:
                continue
            if current == root_bus and neighbor == source_bus and key == root_key:
                continue
            if neighbor == source_bus:
                boundaries.add(current)
                continue
            if not _edge_allowed(data, policy):
                boundaries.add(current)
                continue

            visited_edges.add(identity)
            buses.add(neighbor)
            if policy.stop_at_other_sources and neighbor in other_source_buses:
                boundaries.add(neighbor)
                continue
            if neighbor not in expanded:
                queue.append(neighbor)

    return buses, visited_edges, boundaries


def _edges_from_identities(
    graph: NetworkGraph,
    identities: set[tuple[str, str, str]],
) -> tuple[EdgeRef, ...]:
    refs: list[EdgeRef] = []
    for from_bus, to_bus, key in identities:
        data = graph.get_edge_data(from_bus, to_bus, key)
        if data is not None:
            refs.append(edge_ref(key, data))
    return tuple(sorted(refs))


def trace_feeders(
    network: NetworkModel,
    graph: NetworkGraph | None = None,
    *,
    policy: TracePolicy | None = None,
) -> tuple[FeederTrace, ...]:
    """Trace each conductive root element leaving each active source bus.

    By default transformer edges are boundaries, so a feeder remains on the source voltage level.
    Open switches are already boundaries because they are absent from the conductive graph.
    """

    graph = graph or build_graph(network)
    policy = policy or TracePolicy()
    sources = active_source_buses(network)
    source_bus_values = set(sources.values())
    traces: list[FeederTrace] = []

    for source_id, source_bus in sorted(sources.items()):
        if source_bus not in graph:
            continue
        other_sources = source_bus_values - {source_bus}
        incident = sorted(
            graph.edges(source_bus, keys=True, data=True),
            key=lambda item: str(item[2]),
        )
        for _, neighbor, key, data in incident:
            if not _edge_allowed(data, policy):
                continue
            root_bus = str(neighbor)
            key = str(key)
            buses, identities, boundaries = _reachable_downstream(
                graph,
                source_bus=source_bus,
                root_bus=root_bus,
                root_key=key,
                other_source_buses=other_sources,
                policy=policy,
            )
            refs = _edges_from_identities(graph, identities)
            edge_count = len(refs)
            has_cycle = edge_count >= len(buses)
            feeder_label = graph.nodes[root_bus].get("feeder_id")
            object_type = str(data["object_type"])
            object_id = str(data["object_id"])
            feeder_id = f"{source_id}:{object_type}:{object_id}"
            traces.append(
                FeederTrace(
                    feeder_id=feeder_id,
                    source_id=source_id,
                    source_bus=source_bus,
                    root_bus=root_bus,
                    root_edge=edge_ref(key, data),
                    label=str(feeder_label) if feeder_label is not None else None,
                    buses=frozenset(buses),
                    edges=refs,
                    boundary_buses=frozenset(boundaries),
                    has_cycle=has_cycle,
                )
            )

    return tuple(traces)


def find_feeder_overlaps(feeders: tuple[FeederTrace, ...]) -> tuple[FeederOverlap, ...]:
    by_bus: defaultdict[str, set[str]] = defaultdict(set)
    source_buses = {feeder.source_bus for feeder in feeders}

    for feeder in feeders:
        for bus_id in feeder.buses:
            if bus_id not in source_buses:
                by_bus[bus_id].add(feeder.feeder_id)

    overlaps = [
        FeederOverlap(bus_id=bus_id, feeder_ids=tuple(sorted(feeder_ids)))
        for bus_id, feeder_ids in by_bus.items()
        if len(feeder_ids) > 1
    ]
    return tuple(sorted(overlaps, key=lambda item: item.bus_id))


def find_open_switch_boundaries(
    network: NetworkModel,
    energized: frozenset[str] | set[str],
) -> tuple[OpenSwitchBoundary, ...]:
    boundaries = []
    for switch in sorted(network.switches.values(), key=lambda item: str(item.id)):
        if not switch.in_service or switch.closed:
            continue
        from_bus = str(switch.from_bus)
        to_bus = str(switch.to_bus)
        boundaries.append(
            OpenSwitchBoundary(
                switch_id=str(switch.id),
                from_bus=from_bus,
                to_bus=to_bus,
                from_energized=from_bus in energized,
                to_energized=to_bus in energized,
            )
        )
    return tuple(boundaries)
