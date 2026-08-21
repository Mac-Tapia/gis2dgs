from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    NetworkModel,
    Source,
    SourceId,
)
from gis2dgs.topology import TopologyAnalyzer
from gis2dgs.validation import ValidationPolicy
from gis2dgs.validation.readiness_rules import validate_readiness


def test_power_flow_profile_requires_source_and_line_type() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    topology = TopologyAnalyzer().analyze(network)

    issues = validate_readiness(network, topology, ValidationPolicy.power_flow())
    codes = {issue.code for issue in issues}
    assert "RDY001" in codes
    assert "RDY002" in codes
    assert "RDY004" in codes


def test_line_type_requirement_is_satisfied_when_type_exists() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(
        Line(
            LineId("L1"),
            "L1",
            BusId("B1"),
            BusId("B2"),
            0.1,
            10.0,
            type_id="AAAC70",
        )
    )
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    topology = TopologyAnalyzer().analyze(network)

    issues = validate_readiness(network, topology, ValidationPolicy.power_flow())
    assert all(issue.code != "RDY002" for issue in issues)


def test_transformer_type_is_required_by_power_flow_profile() -> None:
    from gis2dgs.domain import Transformer, TransformerId

    network = NetworkModel()
    network.add_bus(Bus(BusId("BH"), "BH", 10.0))
    network.add_bus(Bus(BusId("BL"), "BL", 0.4))
    network.add_transformer(
        Transformer(
            TransformerId("T1"),
            "T1",
            BusId("BH"),
            BusId("BL"),
            10.0,
            0.4,
            0.63,
        )
    )
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("BH"), 10.0))
    topology = TopologyAnalyzer().analyze(network)
    issues = validate_readiness(network, topology, ValidationPolicy.power_flow())
    assert any(issue.code == "RDY003" for issue in issues)


def test_radial_profile_rejects_meshed_network() -> None:
    network = NetworkModel()
    for bus_id in ("B1", "B2", "B3"):
        network.add_bus(Bus(BusId(bus_id), bus_id, 10.0))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("B2"), BusId("B3"), 0.1, 10.0))
    network.add_line(Line(LineId("L3"), "L3", BusId("B3"), BusId("B1"), 0.1, 10.0))
    topology = TopologyAnalyzer().analyze(network)
    issues = validate_readiness(
        network,
        topology,
        ValidationPolicy.radial_distribution(),
    )
    assert any(issue.code == "RDY005" for issue in issues)
