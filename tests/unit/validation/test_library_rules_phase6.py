from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    NetworkModel,
    Transformer,
    TransformerId,
)
from gis2dgs.electrical import ElectricalLibrary, LineType, TransformerType
from gis2dgs.validation import ValidationPolicy, validate_electrical_library
from gis2dgs.validation.result import Severity


def _network() -> NetworkModel:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0))
    network.add_bus(Bus(BusId("B3"), "B3", 0.4))
    network.add_line(
        Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 1.0, 10.0, "LT1")
    )
    network.add_transformer(
        Transformer(
            TransformerId("T1"),
            "T1",
            BusId("B2"),
            BusId("B3"),
            10.0,
            0.4,
            1.0,
            "TT1",
        )
    )
    return network


def _library(*, line_voltage: float = 10.0, transformer_power: float = 1.0) -> ElectricalLibrary:
    return ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "LT1", line_voltage, 0.4, 0.3, 200.0)],
        transformer_types=[
            TransformerType(
                "TT1",
                "TT1",
                transformer_power,
                10.0,
                0.4,
                6.0,
                10.0,
                2.0,
                1.0,
                "Dyn11",
            )
        ],
    )


def test_required_library_missing_is_error() -> None:
    issues = validate_electrical_library(_network(), None, ValidationPolicy.power_flow())
    assert [issue.code for issue in issues] == ["LIB001"]


def test_unknown_type_ids_are_reported() -> None:
    issues = validate_electrical_library(
        _network(), ElectricalLibrary(), ValidationPolicy.standard()
    )
    assert {issue.code for issue in issues} == {"LIB101", "LIB201"}
    assert all(issue.severity == Severity.WARNING for issue in issues)


def test_type_instance_mismatches_are_reported() -> None:
    issues = validate_electrical_library(
        _network(),
        _library(line_voltage=22.9, transformer_power=2.0),
        ValidationPolicy.standard(),
    )
    assert {issue.code for issue in issues} == {"LIB102", "LIB204"}


def test_matching_library_has_no_issues() -> None:
    assert validate_electrical_library(
        _network(), _library(), ValidationPolicy.power_flow()
    ) == []


def test_short_circuit_profile_requires_zero_sequence_data() -> None:
    issues = validate_electrical_library(
        _network(), _library(), ValidationPolicy.short_circuit()
    )
    assert {issue.code for issue in issues} == {"LIB103", "LIB205"}


def test_transformer_voltage_mismatches_are_reported() -> None:
    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "LT1", 10.0, 0.4, 0.3, 200.0)],
        transformer_types=[
            TransformerType(
                "TT1",
                "TT1",
                1.0,
                22.9,
                0.23,
                6.0,
                10.0,
                2.0,
                1.0,
                "Dyn11",
            )
        ],
    )
    issues = validate_electrical_library(_network(), library, ValidationPolicy.standard())
    assert {issue.code for issue in issues} == {"LIB202", "LIB203"}


def test_out_of_service_elements_do_not_require_library_resolution() -> None:
    network = _network()
    line = network.lines.pop(next(iter(network.lines)))
    transformer = network.transformers.pop(next(iter(network.transformers)))
    network.add_line(
        Line(
            line.id,
            line.name,
            line.from_bus,
            line.to_bus,
            line.length_km,
            line.nominal_voltage_kv,
            line.type_id,
            False,
        )
    )
    network.add_transformer(
        Transformer(
            transformer.id,
            transformer.name,
            transformer.hv_bus,
            transformer.lv_bus,
            transformer.hv_voltage_kv,
            transformer.lv_voltage_kv,
            transformer.rated_power_mva,
            transformer.type_id,
            False,
        )
    )
    assert validate_electrical_library(
        network, ElectricalLibrary(), ValidationPolicy.standard()
    ) == []
