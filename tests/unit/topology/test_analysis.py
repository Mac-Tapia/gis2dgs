from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel
from gis2dgs.topology import build_graph, connected_components, isolated_buses, trace_from


def test_topology_analysis() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    graph = build_graph(network)
    expected = {frozenset({"B1", "B2"}), frozenset({"B3"})}
    assert {frozenset(c) for c in connected_components(graph)} == expected
    assert isolated_buses(graph) == {"B3"}
    assert trace_from(graph, "B1") == {"B1", "B2"}
