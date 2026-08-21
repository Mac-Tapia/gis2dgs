from gis2dgs.domain import Bus, NetworkModel
from gis2dgs.domain.identifiers import BusId
from gis2dgs.powerfactory import PowerFactoryMapper
from gis2dgs.powerfactory.model import PowerFactoryModel, PowerFactoryObject, PowerFactoryReference
from gis2dgs.powerfactory.validation import (
    MappingSeverity,
    ensure_unique_display_names,
    validate_powerfactory_model,
)


def _network(foreign_key: str, name: str) -> PowerFactoryObject:
    return PowerFactoryObject(
        class_name="ElmNet",
        foreign_key=foreign_key,
        name=name,
    )


def _line(
    name: str,
    *,
    foreign_key: str,
    parent: str = "GIS2DGS:net:NET",
    source_id: str | None = None,
) -> PowerFactoryObject:
    return PowerFactoryObject(
        class_name="ElmLne",
        foreign_key=foreign_key,
        name=name,
        parent=PowerFactoryReference(parent),
        source_kind="line",
        source_id=source_id,
    )


def test_validate_powerfactory_model_detects_duplicate_display_names() -> None:
    model = PowerFactoryModel()
    model.add(_network("GIS2DGS:net:NET", "Network"))
    model.add(_line("L99996", foreign_key="GIS2DGS:line:L100002"))
    model.add(_line("L99996", foreign_key="GIS2DGS:line:L100003"))

    report = validate_powerfactory_model(model)

    assert not report.is_valid
    duplicate_errors = [issue for issue in report.errors if issue.code == "PFM003"]
    assert len(duplicate_errors) == 1
    assert duplicate_errors[0].severity == MappingSeverity.ERROR


def test_validate_powerfactory_model_allows_same_name_in_different_parents() -> None:
    model = PowerFactoryModel()
    model.add(_network("GIS2DGS:net:NET_A", "Network A"))
    model.add(_network("GIS2DGS:net:NET_B", "Network B"))
    model.add(
        _line("L1", foreign_key="GIS2DGS:line:L1", parent="GIS2DGS:net:NET_A")
    )
    model.add(
        _line("L1", foreign_key="GIS2DGS:line:L1B", parent="GIS2DGS:net:NET_B")
    )

    report = validate_powerfactory_model(model)

    assert report.is_valid


def test_ensure_unique_display_names_replaces_colliding_names_with_source_ids() -> None:
    model = PowerFactoryModel()
    model.add(_network("GIS2DGS:net:NET", "Network"))
    model.add(
        _line(
            "2000-01-01 00:00:00",
            foreign_key="GIS2DGS:line:L1",
            source_id="L1",
        )
    )
    model.add(
        _line(
            "2000-01-01 00:00:00",
            foreign_key="GIS2DGS:line:L2",
            source_id="L2",
        )
    )

    ensure_unique_display_names(model)
    report = validate_powerfactory_model(model)

    assert report.is_valid
    names = {obj.name for obj in model.find_by_class("ElmLne")}
    assert names == {"L1", "L2"}


def test_mapper_uses_source_ids_when_bus_display_names_collide() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("L1093594"), "2000-01-01 00:00:00", 1.0))
    network.add_bus(Bus(BusId("L1093595"), "2000-01-01 00:00:00", 1.0))

    model = PowerFactoryMapper().map(network)
    names = {obj.name for obj in model.find_by_class("ElmTerm")}

    assert names == {"L1093594", "L1093595"}
