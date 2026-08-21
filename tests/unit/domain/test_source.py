import pytest

from gis2dgs.domain import BusId, Source, SourceId


def test_source_rejects_non_positive_voltage() -> None:
    with pytest.raises(ValueError):
        Source(SourceId("SRC1"), "Grid", BusId("B1"), 0.0)
