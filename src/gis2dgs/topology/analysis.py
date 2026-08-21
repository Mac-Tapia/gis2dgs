from collections import defaultdict

import networkx as nx

from gis2dgs.domain.network import NetworkModel

from .graph import NetworkGraph, build_graph, edge_ref, edge_refs_for_buses
from .models import CycleKind, CycleTrace, SourceTrace, TopologyIsland


def connected_components(graph: NetworkGraph) -> list[set[str]]:
    components = [set(component) for component in nx.connected_components(graph)]
    return sorted(components, key=lambda buses: (min(buses), len(buses)))


def isolated_buses(graph: NetworkGraph) -> set[str]:
    return set(nx.isolates(graph))


def trace_from(graph: NetworkGraph, source_bus: str) -> set[str]:
    if source_bus not in graph:
        raise KeyError(f"Source bus does not exist in graph: {source_bus}")
    return set(nx.node_connected_component(graph, source_bus))


def active_source_buses(network: NetworkModel) -> dict[str, str]:
    return {
        str(source.id): str(source.bus_id)
        for source in network.sources.values()
        if source.in_service and network.has_bus(source.bus_id)
    }


def trace_sources(
    network: NetworkModel,
    graph: NetworkGraph | None = None,
) -> tuple[SourceTrace, ...]:
    graph = graph or build_graph(network)
    traces: list[SourceTrace] = []

    for source_id, source_bus in sorted(active_source_buses(network).items()):
        if source_bus not in graph:
            continue
        buses = frozenset(trace_from(graph, source_bus))
        traces.append(
            SourceTrace(
                source_id=source_id,
                source_bus=source_bus,
                buses=buses,
                edges=edge_refs_for_buses(graph, buses),
            )
        )

    return tuple(traces)


def energized_buses(
    network: NetworkModel,
    graph: NetworkGraph | None = None,
) -> frozenset[str]:
    traces = trace_sources(network, graph)
    buses: set[str] = set()
    for trace in traces:
        buses.update(trace.buses)
    return frozenset(buses)


def deenergized_buses(
    network: NetworkModel,
    graph: NetworkGraph | None = None,
) -> frozenset[str]:
    graph = graph or build_graph(network)
    return frozenset(set(graph.nodes) - set(energized_buses(network, graph)))


def _component_is_radial(graph: NetworkGraph, buses: set[str]) -> bool:
    if not buses:
        return True
    subgraph = graph.subgraph(buses)
    return nx.is_connected(subgraph) and subgraph.number_of_edges() == len(buses) - 1


def find_islands(
    network: NetworkModel,
    graph: NetworkGraph | None = None,
) -> tuple[TopologyIsland, ...]:
    graph = graph or build_graph(network)
    source_by_bus: defaultdict[str, list[str]] = defaultdict(list)
    for source_id, bus_id in active_source_buses(network).items():
        source_by_bus[bus_id].append(source_id)

    islands: list[TopologyIsland] = []
    for index, buses in enumerate(connected_components(graph), start=1):
        source_ids = sorted(
            source_id
            for bus_id in buses
            for source_id in source_by_bus.get(bus_id, [])
        )
        edge_count = graph.subgraph(buses).number_of_edges()
        islands.append(
            TopologyIsland(
                island_id=f"ISLAND_{index:04d}",
                buses=frozenset(buses),
                source_ids=tuple(source_ids),
                edge_count=edge_count,
                energized=bool(source_ids),
                radial=_component_is_radial(graph, buses),
            )
        )

    return tuple(islands)


def _canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
    if not nodes:
        return ()
    rotations: list[tuple[str, ...]] = []
    for sequence in (nodes, list(reversed(nodes))):
        for index in range(len(sequence)):
            rotations.append(tuple(sequence[index:] + sequence[:index]))
    return min(rotations)


def find_cycles(graph: NetworkGraph) -> tuple[CycleTrace, ...]:
    cycles: list[CycleTrace] = []

    parallel_groups: list[tuple[str, str, list[tuple[str, dict[str, object]]]]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for from_bus, to_bus in graph.edges():
        pair = tuple(sorted((str(from_bus), str(to_bus))))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edge_data = graph.get_edge_data(*pair, default={})
        items = [(str(key), data) for key, data in edge_data.items()]
        if len(items) > 1:
            parallel_groups.append((pair[0], pair[1], items))

    for from_bus, to_bus, items in sorted(parallel_groups):
        refs = tuple(sorted(edge_ref(key, data) for key, data in items))
        cycles.append(
            CycleTrace(
                cycle_id=f"CYCLE_PARALLEL_{len(cycles) + 1:04d}",
                kind=CycleKind.PARALLEL,
                buses=(from_bus, to_bus),
                edges=refs,
            )
        )

    simple_graph = nx.Graph()
    simple_graph.add_nodes_from(graph.nodes)
    simple_graph.add_edges_from((u, v) for u, v in graph.edges())

    canonical_cycles = sorted(
        {_canonical_cycle([str(node) for node in cycle]) for cycle in nx.cycle_basis(simple_graph)}
    )
    for nodes in canonical_cycles:
        refs = []
        for index, from_bus in enumerate(nodes):
            to_bus = nodes[(index + 1) % len(nodes)]
            edge_data = graph.get_edge_data(from_bus, to_bus, default={})
            if edge_data:
                key = sorted(str(value) for value in edge_data)[0]
                refs.append(edge_ref(key, edge_data[key]))
        cycles.append(
            CycleTrace(
                cycle_id=f"CYCLE_SIMPLE_{len(cycles) + 1:04d}",
                kind=CycleKind.SIMPLE,
                buses=nodes,
                edges=tuple(sorted(refs)),
            )
        )

    return tuple(cycles)
