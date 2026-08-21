from pathlib import Path

import pytest

from gis2dgs.config import DgsMappingConfig, load_dgs_mapping_profile


def test_unconfigured_repository_profile_loads_without_claiming_target_schema() -> None:
    path = Path("config/dgs_mapping.yaml")
    profile = load_dgs_mapping_profile(path)
    assert profile.configured is False
    expected = (
        path.parent / "../data/reference/dgs_reference.xlsx"
    ).resolve()
    assert profile.template_path == expected


def test_configured_profile_requires_classes() -> None:
    with pytest.raises(ValueError):
        DgsMappingConfig(configured=True)
