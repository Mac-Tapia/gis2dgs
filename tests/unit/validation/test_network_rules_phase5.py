from gis2dgs.domain import (
    BusId,
    Generator,
    GeneratorId,
    Load,
    LoadId,
    NetworkModel,
    Source,
    SourceId,
    Switch,
    SwitchId,
    Transformer,
    TransformerId,
)
from gis2dgs.validation.network_rules import validate_minimum_structure, validate_references


def test_reference_rules_cover_all_supported_connected_objects() -> None:
    network = NetworkModel()
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
    network.add_switch(Switch(SwitchId("S1"), "S1", BusId("B1"), BusId("B2")))
    network.add_load(Load(LoadId("LD1"), "LD1", BusId("B3"), 0.1, 0.02))
    network.add_source(Source(SourceId("SRC"), "Grid", BusId("B4"), 10.0))
    network.add_generator(
        Generator(GeneratorId("G1"), "PV", BusId("B5"), 0.1, technology="PV")
    )

    codes = [issue.code for issue in validate_references(network)]
    assert codes.count("NET002") == 2
    assert codes.count("NET003") == 2
    assert codes.count("NET004") == 1
    assert codes.count("NET005") == 1
    assert codes.count("NET007") == 1


def test_empty_network_fails_minimum_structure() -> None:
    issues = validate_minimum_structure(NetworkModel())
    assert len(issues) == 1
    assert issues[0].code == "NET006"
