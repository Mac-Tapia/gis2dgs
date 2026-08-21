from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    NetworkModel,
    Source,
    SourceId,
    Switch,
    SwitchId,
)
from gis2dgs.topology import TopologyAnalyzer
from gis2dgs.validation import ValidationPolicy
from gis2dgs.validation.topology_rules import validate_topology


def test_cycle_is_reported() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B2"), BusId("B3"), 0.1, 10.0))
    network.add_line(Line(LineId("L3"), "L3", BusId("B3"), BusId("B1"), 0.1, 10.0))

    topology = TopologyAnalyzer().analyze(network)
    issues = validate_topology(network, topology, ValidationPolicy.standard())
    assert any(issue.code == "TOP003" for issue in issues)


def test_open_switch_boundary_is_informational() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B1"), BusId("B2"), closed=False)
    )

    topology = TopologyAnalyzer().analyze(network)
    issues = validate_topology(network, topology, ValidationPolicy.standard())
    assert any(issue.code == "TOP007" for issue in issues)


def test_parallel_elements_are_reported_as_information() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B1"), BusId("B2"), 0.1, 10.0))
    topology = TopologyAnalyzer().analyze(network)
    issues = validate_topology(network, topology, ValidationPolicy.standard())
    assert any(issue.code == "TOP004" for issue in issues)


def test_multiple_sources_in_same_island_are_reported_as_information() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_source(Source(SourceId("S1"), "S1", BusId("B1"), 10.0))
    network.add_source(Source(SourceId("S2"), "S2", BusId("B2"), 10.0))
    topology = TopologyAnalyzer().analyze(network)
    issues = validate_topology(network, topology, ValidationPolicy.standard())
    assert any(issue.code == "TOP006" for issue in issues)
