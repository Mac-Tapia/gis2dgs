from gis2dgs.powerfactory import (
    MappingSeverity,
    PowerFactoryModel,
    PowerFactoryObject,
    PowerFactoryReference,
    validate_powerfactory_model,
)


def test_mapping_validation_detects_missing_parent_and_reference() -> None:
    model = PowerFactoryModel()
    model.add(
        PowerFactoryObject(
            "StaCubic",
            "C1",
            "Cubicle",
            references={"connected_element": PowerFactoryReference("MISSING-ELEMENT")},
            parent=PowerFactoryReference("MISSING-BUS"),
        )
    )
    report = validate_powerfactory_model(model)
    assert report.is_valid is False
    assert {issue.code for issue in report.errors} == {"PFM001", "PFM002"}
    assert all(issue.severity == MappingSeverity.ERROR for issue in report.errors)
