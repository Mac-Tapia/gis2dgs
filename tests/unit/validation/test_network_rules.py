from gis2dgs.domain.identifiers import BusId, LineId
from gis2dgs.domain.line import Line
from gis2dgs.domain.network import NetworkModel
from gis2dgs.validation.network_rules import validate_references


def test_missing_line_bus_is_reported() -> None:
    network = NetworkModel()
    network.add_line(
        Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0)
    )

    issues = validate_references(network)

    assert len(issues) == 2
    assert all(issue.code == "NET001" for issue in issues)
