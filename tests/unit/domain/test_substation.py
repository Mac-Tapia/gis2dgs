import pytest

from gis2dgs.domain import Substation, SubstationId


def test_substation_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        Substation(SubstationId("S1"), " ")
