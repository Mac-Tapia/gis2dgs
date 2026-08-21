from pathlib import Path

import pytest

from gis2dgs.dgs import (
    DgsClassMapping,
    DgsIdentityMapping,
    DgsMappingProfile,
    DgsSchemaNotConfiguredError,
    DgsValueMapping,
)


def test_value_mapping_scales_numeric_values() -> None:
    mapping = DgsValueMapping("current_ka", scale=0.001)
    assert mapping.transform(500.0) == pytest.approx(0.5)


def test_value_mapping_maps_boolean() -> None:
    mapping = DgsValueMapping("outserv", value_map={"true": 0, "false": 1})
    assert mapping.transform(True) == 0
    assert mapping.transform(False) == 1


def test_profile_rejects_unconfigured_use() -> None:
    with pytest.raises(DgsSchemaNotConfiguredError):
        DgsMappingProfile().require_configured()


def test_class_mapping_preserves_column_order_without_duplicates() -> None:
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
