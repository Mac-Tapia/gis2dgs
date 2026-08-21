from pathlib import Path

import pytest

from gis2dgs.dgs import (
    DgsClassMapping,
    DgsIdentityMapping,
    DgsMappingProfile,
    DgsSchema,
    DgsSchemaNotConfiguredError,
    DgsValueMapping,
)


def test_schema_rejects_unconfigured_use() -> None:
    with pytest.raises(DgsSchemaNotConfiguredError):
        DgsSchema().require_configured()


def test_schema_is_canonical_and_old_profile_name_is_compatible_alias() -> None:
    assert DgsMappingProfile is DgsSchema


def test_schema_contains_no_powerfactory_version_selector() -> None:
    fields = set(DgsSchema.__dataclass_fields__)
    assert "version" not in fields
    assert "powerfactory_version" not in fields
    assert "digsilent_version" not in fields


def test_value_mapping_is_structural_not_version_driven() -> None:
    mapping = DgsValueMapping("current_ka", scale=0.001)
    assert mapping.transform(500.0) == pytest.approx(0.5)


def test_class_mapping_collects_declared_schema_columns() -> None:
    mapping = DgsClassMapping(
        table="ElmTerm",
        identity=DgsIdentityMapping("FID", "loc_name", "parent"),
        attributes={"nominal_voltage_kv": DgsValueMapping("uknom")},
        static_values={"OP": "I"},
        required_columns=("FID", "extra"),
    )
    assert mapping.all_columns() == (
        "FID",
        "loc_name",
        "parent",
        "uknom",
        "OP",
        "extra",
    )
