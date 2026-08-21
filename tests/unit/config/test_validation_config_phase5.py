from pathlib import Path

from gis2dgs.config.validation import load_validation_policy


def test_load_validation_policy_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "validation.yaml"
    path.write_text(
        "profile: geographic\nrequire_in_service_source: true\n",
        encoding="utf-8",
    )
    policy = load_validation_policy(path)
    assert policy.name == "geographic"
    assert policy.require_geographic_coordinates is True
    assert policy.require_in_service_source is True
