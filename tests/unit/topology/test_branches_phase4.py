from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel, Switch, SwitchId
from gis2dgs.topology import build_graph, extract_branches


def test_extract_branches_splits_at_junction() -> None:
    network = NetworkModel()
    for bus_id in ("B0", "B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B0"), BusId("B1"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L3"), "L3", BusId("B1"), BusId("B3"), 0.1, 10.0))

    branches = extract_branches(build_graph(network))

    assert len(branches) == 3
    assert {branch.start_bus for branch in branches} | {branch.end_bus for branch in branches} >= {
        "B1"
    }
    assert sum(len(branch.edges) for branch in branches) == 3


def test_extract_branches_splits_at_closed_switch() -> None:
    network = NetworkModel()
    for bus_id in ("B0", "B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B0"), BusId("B1"), 0.1, 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B1"), BusId("B2"), closed=True)
    )
    network.add_line(Line(LineId("L2"), "L2", BusId("B2"), BusId("B3"), 0.1, 10.0))

    branches = extract_branches(build_graph(network))

    assert len(branches) == 3
    assert {branch.edges[0].object_type for branch in branches} == {"line", "switch"}


def test_extract_branches_handles_closed_cycle_without_losing_edges() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B2"), BusId("B3"), 0.1, 10.0))
    network.add_line(Line(LineId("L3"), "L3", BusId("B3"), BusId("B1"), 0.1, 10.0))

    branches = extract_branches(build_graph(network))

    assert sum(len(branch.edges) for branch in branches) == 3
    assert len({edge.object_id for branch in branches for edge in branch.edges}) == 3
