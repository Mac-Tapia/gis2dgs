import pytest

from gis2dgs.validation import ValidationPolicy


def test_power_flow_profile_enables_required_checks() -> None:
    policy = ValidationPolicy.power_flow()
    assert policy.require_in_service_source
    assert policy.require_line_type
    assert policy.require_transformer_type
    assert policy.require_electrical_library
    assert policy.require_all_buses_energized


def test_short_circuit_profile_requires_zero_sequence() -> None:
    policy = ValidationPolicy.short_circuit()
    assert policy.require_electrical_library
    assert policy.require_zero_sequence_data


def test_import_profile_keeps_first_pass_checks_lightweight() -> None:
    policy = ValidationPolicy.import_profile()
    assert policy.name == "import"
    assert not policy.require_in_service_source
    assert not policy.require_line_type
    assert not policy.require_electrical_library
    assert not policy.require_all_buses_energized


def test_profile_settings_can_be_overridden() -> None:
    policy = ValidationPolicy.from_mapping(
        {"profile": "power_flow", "require_line_type": False}
    )
    assert policy.name == "power_flow"
    assert not policy.require_line_type
    assert policy.require_electrical_library


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown validation profile"):
        ValidationPolicy.from_mapping({"profile": "invalid"})


def test_unknown_setting_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown validation setting"):
        ValidationPolicy.from_mapping({"not_a_setting": True})
