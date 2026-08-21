from pathlib import Path

import pytest

from gis2dgs.config.loader import load_yaml


def test_load_yaml(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text("a: 1\n", encoding="utf-8")
    assert load_yaml(path) == {"a": 1}


def test_load_yaml_requires_mapping_root(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_yaml(path)
