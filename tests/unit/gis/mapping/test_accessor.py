import pandas as pd
import pytest

from gis2dgs.config.models import LayerMapping
from gis2dgs.gis.exceptions import GisMappingError
from gis2dgs.gis.mapping.accessor import RowAccessor


def test_accessor_reads_configured_column() -> None:
    mapping = LayerMapping(source="nodes", fields={"id": "node_id"})
    row = pd.Series({"node_id": "N1"})
    accessor = RowAccessor("nodes", 3, row, mapping)

    assert accessor.require("id") == "N1"


def test_accessor_uses_default_for_missing_value() -> None:
    mapping = LayerMapping(source="nodes", defaults={"name": "unnamed"})
    row = pd.Series({"other": 1})
    accessor = RowAccessor("nodes", 0, row, mapping)

    assert accessor.get("name") == "unnamed"


def test_accessor_reports_missing_configured_source_column() -> None:
    mapping = LayerMapping(source="nodes", fields={"id": "node_id"})
    row = pd.Series({"wrong": "N1"})
    accessor = RowAccessor("nodes", 7, row, mapping)

    with pytest.raises(GisMappingError, match="node_id"):
        accessor.require("id")
