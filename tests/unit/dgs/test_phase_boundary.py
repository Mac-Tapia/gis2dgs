from pathlib import Path

import pytest

from gis2dgs.dgs import DgsMapper, DgsSchemaNotConfiguredError, DgsWriter
from gis2dgs.domain import NetworkModel


def test_mapper_fails_explicitly_without_reference_schema() -> None:
    with pytest.raises(DgsSchemaNotConfiguredError):
        DgsMapper().map_network(NetworkModel())


def test_writer_fails_explicitly_without_reference_schema(tmp_path: Path) -> None:
    with pytest.raises(DgsSchemaNotConfiguredError):
        DgsWriter().write([], tmp_path / "network.dgs")


def test_phase8_mapper_rejects_powerfactory_model_without_reference_schema() -> None:
    from gis2dgs.powerfactory import PowerFactoryModel

    with pytest.raises(DgsSchemaNotConfiguredError):
        DgsMapper().map_powerfactory_model(PowerFactoryModel())
