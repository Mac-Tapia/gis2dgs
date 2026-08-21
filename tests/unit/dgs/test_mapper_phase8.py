import pytest

from gis2dgs.dgs import (
    DgsClassMapping,
    DgsIdentityMapping,
    DgsMapper,
    DgsMappingError,
    DgsMappingProfile,
    DgsReferenceMapping,
    DgsValueMapping,
    UnmappedPolicy,
)
from gis2dgs.powerfactory import PowerFactoryModel, PowerFactoryObject, PowerFactoryReference


def _profile(**overrides) -> DgsMappingProfile:
    classes = {
        "ElmTerm": DgsClassMapping(
            table="ElmTerm",
            identity=DgsIdentityMapping("FID", "loc_name", "parent"),
            attributes={
                "nominal_voltage_kv": DgsValueMapping("uknom"),
                "in_service": DgsValueMapping(
                    "outserv",
                    value_map={"true": 0, "false": 1},
                ),
            },
        ),
        "ElmLne": DgsClassMapping(
            table="ElmLne",
            identity=DgsIdentityMapping("FID", "loc_name", "parent"),
            attributes={"length_km": DgsValueMapping("dline")},
            references={
                "terminal_1_cubicle": DgsReferenceMapping("bus1"),
                "terminal_2_cubicle": DgsReferenceMapping("bus2"),
            },
        ),
        "StaCubic": DgsClassMapping(
            table="StaCubic",
            identity=DgsIdentityMapping("FID", "loc_name", "parent"),
        ),
    }
    params = {
        "configured": True,
        "allow_create_without_template": True,
        "classes": classes,
    }
    params.update(overrides)
    return DgsMappingProfile(**params)


def test_mapper_maps_identity_attributes_parent_and_references() -> None:
    model = PowerFactoryModel()
    model.add(
        PowerFactoryObject(
            "ElmTerm",
            "BUS1",
            "Bus 1",
            {"nominal_voltage_kv": 10.0, "in_service": True},
        )
    )
    model.add(
        PowerFactoryObject(
            "ElmLne",
            "L1",
            "Line 1",
            {"length_km": 0.5},
            {
                "terminal_1_cubicle": PowerFactoryReference("C1"),
                "terminal_2_cubicle": PowerFactoryReference("C2"),
            },
            parent=PowerFactoryReference("NET"),
        )
    )
    model.add(PowerFactoryObject("StaCubic", "C1", "Cubicle 1"))
    model.add(PowerFactoryObject("StaCubic", "C2", "Cubicle 2"))

    document = DgsMapper(_profile()).map_powerfactory_model(model)

    bus = document.get_table("ElmTerm").rows[0]
    assert bus.values == {
        "FID": "BUS1",
        "loc_name": "Bus 1",
        "parent": None,
        "uknom": 10.0,
        "outserv": 0,
    }
    line = document.get_table("ElmLne").rows[0]
    assert line.values["FID"] == "L1"
    assert line.values["parent"] == "NET"
    assert line.values["bus1"] == "C1"
    assert line.values["bus2"] == "C2"


def test_mapper_rejects_unmapped_semantic_attribute_in_strict_mode() -> None:
    model = PowerFactoryModel()
    model.add(PowerFactoryObject("ElmTerm", "B1", "B1", {"coordinate_x": 1.0}))

    with pytest.raises(DgsMappingError, match="unmapped semantic attributes"):
        DgsMapper(_profile()).map_powerfactory_model(model)


def test_mapper_can_skip_unmapped_powerfactory_class() -> None:
    model = PowerFactoryModel()
    model.add(PowerFactoryObject("ElmXnet", "GRID", "Grid"))
    profile = _profile(unmapped_class_policy=UnmappedPolicy.SKIP)

    document = DgsMapper(profile).map_powerfactory_model(model)

    assert document.summary()["rows"] == 0


def test_mapper_rejects_dangling_cubicle_reference() -> None:
    model = PowerFactoryModel()
    model.add(
        PowerFactoryObject(
            "ElmLne",
            "L1",
            "Line 1",
            {"length_km": 0.5},
            {
                "terminal_1_cubicle": PowerFactoryReference("MISSING"),
                "terminal_2_cubicle": PowerFactoryReference("C2"),
            },
        )
    )
    model.add(PowerFactoryObject("StaCubic", "C2", "Cubicle 2"))

    with pytest.raises(DgsMappingError, match="Dangling DGS reference"):
        DgsMapper(_profile()).map_powerfactory_model(model)
