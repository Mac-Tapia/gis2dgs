import pytest

from gis2dgs.domain import (
    Bus,
    Generator,
    Line,
    Load,
    NetworkModel,
    Source,
    Substation,
    Switch,
    Transformer,
)
from gis2dgs.domain.identifiers import (
    BusId,
    GeneratorId,
    LineId,
    LoadId,
    SourceId,
    SubstationId,
    SwitchId,
    TransformerId,
)
from gis2dgs.electrical import ElectricalLibrary, LineType, TransformerType
from gis2dgs.powerfactory import (
    PowerFactoryClass,
    PowerFactoryMapper,
    PowerFactoryMappingError,
    PowerFactoryMappingPolicy,
    validate_powerfactory_model,
)


def sample_network() -> tuple[NetworkModel, ElectricalLibrary]:
    n = NetworkModel()
    n.add_substation(Substation(SubstationId("S1"), "Substation 1", -73.2, -3.7))
    n.add_bus(
        Bus(
            BusId("B1"),
            "Bus 1",
            10.0,
            -73.20,
            -3.70,
            substation_id=SubstationId("S1"),
        )
    )
    n.add_bus(Bus(BusId("B2"), "Bus 2", 10.0, -73.21, -3.71))
    n.add_bus(Bus(BusId("B3"), "Bus 3", 0.4))
    n.add_line(Line(LineId("L1"), "Line 1", BusId("B1"), BusId("B2"), 1.2, 10.0, "LT1"))
    n.add_transformer(
        Transformer(
            TransformerId("T1"),
            "Transformer 1",
            BusId("B2"),
            BusId("B3"),
            10.0,
            0.4,
            0.63,
            "TT1",
        )
    )
    n.add_switch(Switch(SwitchId("SW1"), "Switch 1", BusId("B1"), BusId("B2"), False))
    n.add_load(Load(LoadId("LD1"), "Load 1", BusId("B3"), 0.1, 0.02))
    n.add_generator(Generator(GeneratorId("G1"), "PV 1", BusId("B3"), 0.05, technology="PV"))
    n.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))

    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "Line type 1", 10.0, 0.2, 0.1, 200.0)],
        transformer_types=[
            TransformerType(
                "TT1",
                "Transformer type 1",
                0.63,
                10.0,
                0.4,
                6.0,
                6.0,
                1.0,
                0.5,
                "Dyn11",
            )
        ],
    )
    return n, library


def test_mapper_creates_expected_powerfactory_classes() -> None:
    network, library = sample_network()
    model = PowerFactoryMapper().map(network, library)

    counts = model.class_counts()
    assert counts[PowerFactoryClass.NETWORK] == 1
    assert counts[PowerFactoryClass.SUBSTATION] == 1
    assert counts[PowerFactoryClass.TERMINAL] == 3
    assert counts[PowerFactoryClass.LINE] == 1
    assert counts[PowerFactoryClass.LINE_TYPE] == 1
    assert counts[PowerFactoryClass.TRANSFORMER] == 1
    assert counts[PowerFactoryClass.TRANSFORMER_TYPE] == 1
    assert counts[PowerFactoryClass.SWITCH] == 1
    assert counts[PowerFactoryClass.LOAD] == 1
    assert counts[PowerFactoryClass.GENERATOR] == 1
    assert counts[PowerFactoryClass.EXTERNAL_GRID] == 1
    assert counts[PowerFactoryClass.CUBICLE] == 9
    assert validate_powerfactory_model(model).is_valid


def test_bus_with_substation_is_parented_to_substation() -> None:
    network, library = sample_network()
    model = PowerFactoryMapper().map(network, library)
    bus = model.get("GIS2DGS:bus:B1")
    assert bus.parent is not None
    assert bus.parent.target_key == "GIS2DGS:sub:S1"


def test_two_terminal_element_has_two_cubicles() -> None:
    network, library = sample_network()
    model = PowerFactoryMapper().map(network, library)
    line = model.get("GIS2DGS:line:L1")
    c1 = line.references["terminal_1_cubicle"].target_key
    c2 = line.references["terminal_2_cubicle"].target_key
    assert c1 != c2
    assert model.get(c1).parent.target_key == "GIS2DGS:bus:B1"  # type: ignore[union-attr]
    assert model.get(c2).parent.target_key == "GIS2DGS:bus:B2"  # type: ignore[union-attr]
    assert model.get(c1).references["connected_element"].target_key == line.foreign_key


def test_mapper_preserves_open_switch_state() -> None:
    network, library = sample_network()
    model = PowerFactoryMapper().map(network, library)
    switch = model.get("GIS2DGS:switch:SW1")
    assert switch.attributes["closed"] is False


def test_mapper_can_exclude_out_of_service_elements() -> None:
    network, library = sample_network()
    network.add_load(Load(LoadId("LD2"), "Off", BusId("B3"), 0.01, 0.0, False))
    policy = PowerFactoryMappingPolicy(include_out_of_service=False)
    model = PowerFactoryMapper(policy).map(network, library)
    assert "GIS2DGS:load:LD2" not in model.objects


def test_mapper_requires_line_type_when_policy_is_strict() -> None:
    network, _ = sample_network()
    with pytest.raises(PowerFactoryMappingError, match="line type"):
        PowerFactoryMapper().map(network, ElectricalLibrary())


def test_mapper_can_map_without_types_when_policy_allows_it() -> None:
    network, _ = sample_network()
    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        fallback_line_types_by_voltage=False,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    assert model.get("GIS2DGS:line:L1").references.get("type") is None


def test_mapper_assigns_voltage_fallback_when_library_type_missing() -> None:
    network, library = sample_network()
    network.lines[LineId("L1")] = Line(
        LineId("L1"),
        "Line 1",
        BusId("B1"),
        BusId("B2"),
        1.2,
        10.0,
        "MISSING_CODE",
    )
    policy = PowerFactoryMappingPolicy(require_type_references=False)
    model = PowerFactoryMapper(policy).map(network, library)
    line = model.get("GIS2DGS:line:L1")
    assert line.references["type"].target_key == "GIS2DGS:ltype:LT1"


def test_mapper_rejects_unknown_bus() -> None:
    network, library = sample_network()
    network.lines[LineId("L1")] = Line(
        LineId("L1"), "Line 1", BusId("B1"), BusId("MISSING"), 1.2, 10.0, "LT1"
    )
    with pytest.raises(PowerFactoryMappingError, match="unknown bus"):
        PowerFactoryMapper().map(network, library)
