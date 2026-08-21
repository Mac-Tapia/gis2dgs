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


def test_analyzer_builds_complete_topology_report() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_switch(
        Switch(SwitchId("SW1"), "SW1", BusId("B2"), BusId("B3"), closed=False)
    )

    report = TopologyAnalyzer().analyze(network)

    assert report.energized_buses == frozenset({"B1", "B2"})
    assert report.deenergized_buses == frozenset({"B3"})
    assert len(report.islands) == 2
    assert len(report.feeders) == 1
    assert len(report.open_switch_boundaries) == 1
    assert report.cycles == ()
    assert report.is_radial is True
