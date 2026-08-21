from collections.abc import Iterator

import networkx as nx

from gis2dgs.domain.network import NetworkModel

from .models import EdgeRef

NetworkGraph = nx.MultiGraph


def _add_edge(
    graph: NetworkGraph,
    from_bus: str,
    to_bus: str,
    *,
    key: str,
    object_type: str,
    object_id: str,
    conductive: bool,
    in_service: bool,
) -> None:
    graph.add_edge(
        from_bus,
        to_bus,
        key=key,
        object_type=object_type,
        object_id=object_id,
        conductive=conductive,
        in_service=in_service,
    )


def build_graph(network: NetworkModel) -> NetworkGraph:
    """Build the conductive electrical graph used for tracing and analysis.

    Rules:
    - buses are always represented as nodes;
    - out-of-service elements are excluded;
    - open switches are excluded because they do not conduct;
    - parallel electrical elements are preserved with ``MultiGraph``.
    """

    graph = nx.MultiGraph()

    for bus in network.buses.values():
        graph.add_node(
            str(bus.id),
            object_type="bus",
            nominal_voltage_kv=bus.nominal_voltage_kv,
            feeder_id=str(bus.feeder_id) if bus.feeder_id is not None else None,
        )

    for line in network.lines.values():
        if line.in_service:
            _add_edge(
                graph,
                str(line.from_bus),
                str(line.to_bus),
                key=f"line:{line.id}",
                object_type="line",
                object_id=str(line.id),
                conductive=True,
                in_service=True,
            )

    for switch in network.switches.values():
        if switch.in_service and switch.closed:
            _add_edge(
                graph,
                str(switch.from_bus),
                str(switch.to_bus),
                key=f"switch:{switch.id}",
                object_type="switch",
                object_id=str(switch.id),
                conductive=True,
                in_service=True,
            )

    for transformer in network.transformers.values():
        if transformer.in_service:
            _add_edge(
                graph,
                str(transformer.hv_bus),
                str(transformer.lv_bus),
                key=f"transformer:{transformer.id}",
                object_type="transformer",
                object_id=str(transformer.id),
                conductive=True,
                in_service=True,
            )

    return graph


def build_physical_graph(
    network: NetworkModel,
    *,
    include_out_of_service: bool = False,
) -> NetworkGraph:
    """Build a physical graph that also represents non-conductive switch boundaries.

    This graph is for diagnostics. Algorithms that calculate energized reachability must use
    :func:`build_graph`, not this function.
    """

    graph = nx.MultiGraph()

    for bus in network.buses.values():
        graph.add_node(
            str(bus.id),
            object_type="bus",
            nominal_voltage_kv=bus.nominal_voltage_kv,
            feeder_id=str(bus.feeder_id) if bus.feeder_id is not None else None,
        )

    for line in network.lines.values():
        if line.in_service or include_out_of_service:
            _add_edge(
                graph,
                str(line.from_bus),
                str(line.to_bus),
                key=f"line:{line.id}",
                object_type="line",
                object_id=str(line.id),
                conductive=line.in_service,
                in_service=line.in_service,
            )

    for switch in network.switches.values():
        if switch.in_service or include_out_of_service:
            _add_edge(
                graph,
                str(switch.from_bus),
                str(switch.to_bus),
                key=f"switch:{switch.id}",
                object_type="switch",
                object_id=str(switch.id),
                conductive=switch.in_service and switch.closed,
                in_service=switch.in_service,
            )

    for transformer in network.transformers.values():
        if transformer.in_service or include_out_of_service:
            _add_edge(
                graph,
                str(transformer.hv_bus),
                str(transformer.lv_bus),
                key=f"transformer:{transformer.id}",
                object_type="transformer",
                object_id=str(transformer.id),
                conductive=transformer.in_service,
                in_service=transformer.in_service,
            )

    return graph


def edge_ref(key: str, data: dict[str, object]) -> EdgeRef:
    return EdgeRef(
        object_type=str(data["object_type"]),
        object_id=str(data["object_id"]),
        key=key,
    )


def iter_edge_refs(graph: NetworkGraph) -> Iterator[EdgeRef]:
    refs = [
        edge_ref(str(key), data)
        for _, _, key, data in graph.edges(keys=True, data=True)
    ]
    yield from sorted(refs)


def edge_refs_for_buses(
    graph: NetworkGraph,
    buses: set[str] | frozenset[str],
) -> tuple[EdgeRef, ...]:
    refs: list[EdgeRef] = []
    for from_bus, to_bus, key, data in graph.edges(keys=True, data=True):
        if from_bus in buses and to_bus in buses:
            refs.append(edge_ref(str(key), data))
    return tuple(sorted(refs))
