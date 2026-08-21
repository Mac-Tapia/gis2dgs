from pathlib import Path

import pytest

from gis2dgs.config import (
    DgsMappingConfig,
    DgsSchemaConfig,
    load_dgs_mapping_profile,
    load_dgs_schema,
)


def test_repository_schema_loads_without_claiming_universal_columns() -> None:
    path = Path("config/dgs_mapping.yaml")
    schema = load_dgs_schema(path)
    assert schema.configured is False
    expected = (path.parent / "../data/reference/dgs_reference.xlsx").resolve()
    assert schema.template_path == expected


def test_configured_schema_requires_class_mapping() -> None:
    with pytest.raises(ValueError):
        DgsSchemaConfig(configured=True)


def test_old_config_api_remains_compatible() -> None:
    assert DgsMappingConfig is DgsSchemaConfig
    assert load_dgs_mapping_profile(Path("config/dgs_mapping.yaml")) == load_dgs_schema(
        Path("config/dgs_mapping.yaml")
    )
