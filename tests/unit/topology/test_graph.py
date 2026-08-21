from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel, Switch, SwitchId
from gis2dgs.topology import build_graph


def test_build_graph_preserves_parallel_elements() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.2, 10.0))
    graph = build_graph(network)
    assert graph.number_of_edges("B1", "B2") == 2


def test_open_switch_does_not_create_conductive_edge() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_switch(Switch(SwitchId("S1"), "S1", BusId("B1"), BusId("B2"), closed=False))
    graph = build_graph(network)
    assert not graph.has_edge("B1", "B2")
