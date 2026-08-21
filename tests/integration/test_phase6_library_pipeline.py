from gis2dgs.domain import (
    Bus,
    BusId,
    Line,
    LineId,
    NetworkModel,
    Source,
    SourceId,
    Transformer,
    TransformerId,
)
from gis2dgs.electrical import ElectricalLibrary, LineType, TransformerType
from gis2dgs.validation import NetworkValidator, ValidationPolicy


def test_power_flow_readiness_with_resolved_type_library() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "MV source", 10.0))
    network.add_bus(Bus(BusId("B2"), "MV load", 10.0))
    network.add_bus(Bus(BusId("B3"), "LV bus", 0.4))
    network.add_source(Source(SourceId("GRID"), "Grid", BusId("B1"), 10.0))
    network.add_line(
        Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.5, 10.0, "LT1")
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

    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT1", "Synthetic line", 10.0, 0.4, 0.3, 200.0)],
        transformer_types=[
            TransformerType(
                "TT1",
                "Synthetic transformer",
                1.0,
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

    report = NetworkValidator(
        ValidationPolicy.power_flow(),
        electrical_library=library,
    ).validate(network)

    assert report.is_valid
    assert report.error_count == 0
    assert report.profile == "power_flow"
