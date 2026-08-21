import pytest

from gis2dgs.powerfactory import PowerFactoryMappingPolicy


def test_policy_defaults_are_valid() -> None:
    policy = PowerFactoryMappingPolicy()
    assert policy.classes.terminal == "ElmTerm"
    assert policy.classes.cubicle == "StaCubic"


def test_policy_rejects_blank_identity() -> None:
    with pytest.raises(ValueError):
        PowerFactoryMappingPolicy(network_id="")
