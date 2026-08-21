from collections.abc import Iterable

from .graph import NetworkGraph, edge_ref
from .models import BranchTrace, EdgeRef

EdgeIdentity = tuple[str, str, str]


def _identity(from_bus: str, to_bus: str, key: str) -> EdgeIdentity:
    pair = tuple(sorted((from_bus, to_bus)))
    return pair[0], pair[1], key


def _ref(graph: NetworkGraph, identity: EdgeIdentity) -> EdgeRef:
    from_bus, to_bus, key = identity
    data = graph.get_edge_data(from_bus, to_bus, key)
    if data is None:
        raise KeyError(f"Graph edge does not exist: {identity}")
    return edge_ref(key, data)


def _structural_boundaries(
    graph: NetworkGraph,
    stop_buses: set[str],
    split_element_types: set[str],
) -> set[str]:
    boundaries = set(stop_buses)
    for node in graph.nodes:
        neighbors = set(str(neighbor) for neighbor in graph.neighbors(node))
        if graph.degree(node) != 2 or len(neighbors) != 2:
            boundaries.add(str(node))

    for from_bus, to_bus, _, data in graph.edges(keys=True, data=True):
        if str(data.get("object_type")) in split_element_types:
            boundaries.add(str(from_bus))
            boundaries.add(str(to_bus))

    return boundaries


def _incident_unvisited(
    graph: NetworkGraph,
    node: str,
    visited: set[EdgeIdentity],
) -> list[tuple[str, str, dict[str, object]]]:
    candidates: list[tuple[str, str, dict[str, object]]] = []
    for _, neighbor, key, data in graph.edges(node, keys=True, data=True):
        neighbor = str(neighbor)
        key = str(key)
        if _identity(node, neighbor, key) not in visited:
            candidates.append((neighbor, key, data))
    return sorted(candidates, key=lambda item: item[1])


def _walk_branch(
    graph: NetworkGraph,
    start: str,
    first_neighbor: str,
    first_key: str,
    boundaries: set[str],
    visited: set[EdgeIdentity],
) -> tuple[list[str], list[EdgeIdentity], bool]:
    buses = [start, first_neighbor]
    edges = [_identity(start, first_neighbor, first_key)]
    visited.add(edges[0])
    previous = start
    current = first_neighbor
    has_cycle = current == start

    while not has_cycle and current not in boundaries:
        candidates = []
        for neighbor, key, _ in _incident_unvisited(graph, current, visited):
            if neighbor == previous and len(candidates) == 0:
                continue
            candidates.append((neighbor, key))
        if not candidates:
            break

        neighbor, key = candidates[0]
        identity = _identity(current, neighbor, key)
        visited.add(identity)
        edges.append(identity)
        buses.append(neighbor)
        previous, current = current, neighbor
        if current == start:
            has_cycle = True

    return buses, edges, has_cycle


def extract_branches(
    graph: NetworkGraph,
    *,
    stop_buses: Iterable[str] = (),
    split_element_types: Iterable[str] = ("switch", "transformer"),
) -> tuple[BranchTrace, ...]:
    """Split a conductive network into maximal edge paths between structural boundaries."""

    boundaries = _structural_boundaries(
        graph,
        set(stop_buses),
        set(split_element_types),
    )
    visited: set[EdgeIdentity] = set()
    raw_branches: list[tuple[list[str], list[EdgeIdentity], bool]] = []

    for start in sorted(boundaries):
        if start not in graph:
            continue
        for neighbor, key, _ in _incident_unvisited(graph, start, visited):
            raw_branches.append(
                _walk_branch(graph, start, neighbor, key, boundaries, visited)
            )

    all_edges = sorted(
        {
            _identity(str(from_bus), str(to_bus), str(key))
            for from_bus, to_bus, key in graph.edges(keys=True)
        }
    )
    for identity in all_edges:
        if identity in visited:
            continue
        start, neighbor, key = identity
        raw_branches.append(
            _walk_branch(graph, start, neighbor, key, boundaries | {start}, visited)
        )

    branches = []
    for index, (buses, identities, has_cycle) in enumerate(raw_branches, start=1):
        refs = tuple(_ref(graph, identity) for identity in identities)
        branches.append(
            BranchTrace(
                branch_id=f"BRANCH_{index:04d}",
                start_bus=buses[0],
                end_bus=buses[-1],
                buses=tuple(buses),
                edges=refs,
                has_cycle=has_cycle,
            )
        )

    return tuple(branches)
