from gis2dgs.domain import Bus, BusId, Line, LineId, NetworkModel
from gis2dgs.validation.electrical_rules import validate_voltage_consistency


def test_line_voltage_mismatch_is_error() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 22.9))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    issues = validate_voltage_consistency(network)
    assert [issue.code for issue in issues] == ["ELE001"]


def test_transformer_voltage_mismatch_is_error() -> None:
    from gis2dgs.domain import Transformer, TransformerId

    network = NetworkModel()
    network.add_bus(Bus(BusId("HV"), "HV", 22.9))
    network.add_bus(Bus(BusId("LV"), "LV", 0.38))
    network.add_transformer(
        Transformer(
            TransformerId("T1"),
            "T1",
            BusId("HV"),
            BusId("LV"),
            10.0,
            0.38,
            0.5,
        )
    )
    issues = validate_voltage_consistency(network)
    assert "ELE003" in {issue.code for issue in issues}
