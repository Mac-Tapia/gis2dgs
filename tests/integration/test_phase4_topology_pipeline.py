from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    Load,
    LoadId,
    NetworkModel,
    Source,
    SourceId,
    Switch,
    SwitchId,
)
from gis2dgs.topology import TopologyAnalyzer
from gis2dgs.validation import NetworkValidator


def test_phase4_analysis_integrates_with_existing_validation_pipeline() -> None:
    network = NetworkModel()
    for bus_id in ("SET", "F1", "F2", "OFF"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("SET"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("SET"), BusId("F1"), 0.2, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("F1"), BusId("F2"), 0.2, 10.0))
    network.add_switch(
        Switch(SwitchId("SW_OPEN"), "SW_OPEN", BusId("F2"), BusId("OFF"), closed=False)
    )
    network.add_load(Load(LoadId("LD1"), "Load", BusId("F2"), 0.5, 0.1))

    report = TopologyAnalyzer().analyze(network)
    validation = NetworkValidator().validate(network)

    assert report.energized_buses == frozenset({"SET", "F1", "F2"})
    assert report.deenergized_buses == frozenset({"OFF"})
    assert report.open_switch_boundaries[0].switch_id == "SW_OPEN"
    assert validation.is_valid is True
