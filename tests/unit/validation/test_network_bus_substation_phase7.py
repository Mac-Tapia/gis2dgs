from gis2dgs.domain import Bus, NetworkModel
from gis2dgs.domain.identifiers import BusId, SubstationId
from gis2dgs.validation.network_rules import validate_references


def test_missing_bus_substation_is_reported() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0, substation_id=SubstationId("S404")))
    issues = validate_references(network)
    assert any(issue.code == "NET008" for issue in issues)
