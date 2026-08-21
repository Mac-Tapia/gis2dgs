from math import nan

from gis2dgs.domain import Bus, BusId, NetworkModel
from gis2dgs.validation import ValidationPolicy
from gis2dgs.validation.data_quality_rules import validate_data_quality


def test_partial_coordinates_are_error() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0, x=1.0, y=None))
    issues = validate_data_quality(network, ValidationPolicy.standard())
    assert [issue.code for issue in issues] == ["DAT002"]


def test_geographic_profile_requires_coordinates() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    issues = validate_data_quality(network, ValidationPolicy.geographic())
    assert any(issue.code == "DAT003" for issue in issues)


def test_non_finite_bus_voltage_is_detected() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", nan))
    issues = validate_data_quality(network, ValidationPolicy.standard())
    assert any(issue.code == "DAT001" for issue in issues)


def test_non_finite_values_are_detected_across_domain_objects() -> None:
    from gis2dgs.domain import (
        Generator,
        GeneratorId,
        Line,
        LineId,
        Load,
        LoadId,
        Source,
        SourceId,
        Transformer,
        TransformerId,
    )

    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), nan, 10.0))
    network.add_transformer(
        Transformer(
            TransformerId("T1"),
            "T1",
            BusId("B1"),
            BusId("B2"),
            10.0,
            0.4,
            nan,
        )
    )
    network.add_load(Load(LoadId("LD1"), "LD1", BusId("B1"), 0.1, nan))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B1"), nan))
    network.add_generator(
        Generator(GeneratorId("G1"), "PV", BusId("B1"), 0.1, nan, technology="PV")
    )

    issues = validate_data_quality(network, ValidationPolicy.standard())
    assert sum(issue.code == "DAT001" for issue in issues) == 5
