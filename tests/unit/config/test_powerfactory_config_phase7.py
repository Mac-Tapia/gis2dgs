from pathlib import Path

from gis2dgs.config.powerfactory import (
    PowerFactoryMappingConfig,
    load_powerfactory_mapping_policy,
)


def test_powerfactory_config_converts_to_policy() -> None:
    config = PowerFactoryMappingConfig(network_id="N1", network_name="Network 1")
    policy = config.to_policy()
    assert policy.network_id == "N1"
    assert policy.classes.line == "ElmLne"


def test_project_powerfactory_mapping_yaml_loads() -> None:
    policy = load_powerfactory_mapping_policy(Path("config/powerfactory_mapping.yaml"))
    assert policy.classes.cubicle == "StaCubic"
    assert policy.classes.generator == "ElmGenstat"
