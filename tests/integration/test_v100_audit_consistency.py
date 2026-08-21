from pathlib import Path
import tomllib

import yaml

import gis2dgs
from gis2dgs.config import DgsSchemaConfig, MappingConfig, load_dgs_schema, load_yaml
from gis2dgs.dgs import DgsSchema


ROOT = Path(__file__).resolve().parents[2]


def test_versions_are_consistent_across_package_project_and_settings() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    settings = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
    versions = {
        gis2dgs.__version__,
        pyproject["project"]["version"],
        settings["project"]["version"],
    }
    assert versions == {"1.0.0"}


def test_dgs_schema_is_version_neutral_by_contract() -> None:
    forbidden = {"version", "powerfactory_version", "digsilent_version", "dgs_version"}
    assert forbidden.isdisjoint(DgsSchema.__dataclass_fields__)
    assert forbidden.isdisjoint(DgsSchemaConfig.model_fields)


def test_repository_dgs_schema_is_safe_and_unconfigured() -> None:
    schema = load_dgs_schema(ROOT / "config/dgs_mapping.yaml")
    assert schema.configured is False
    assert schema.classes == {}
    assert schema.template_path == (ROOT / "data/reference/dgs_reference.xlsx").resolve()


def test_electrical_library_example_does_not_recommend_invalid_zero_uk0() -> None:
    text = (ROOT / "config/electrical_library.yaml").read_text(encoding="utf-8")
    assert "uk0_percent: 0.0" not in text


def test_production_mapping_config_includes_generators() -> None:
    config = MappingConfig.model_validate(load_yaml(ROOT / "config/mapping.yaml"))
    assert config.generators is not None
    assert config.generators.source == "generators"
