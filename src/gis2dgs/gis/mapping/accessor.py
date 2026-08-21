from dataclasses import dataclass
from typing import Any

import pandas as pd

from gis2dgs.config.models import LayerMapping
from gis2dgs.gis.exceptions import GisMappingError
from gis2dgs.gis.normalizer import is_missing


@dataclass(frozen=True, slots=True)
class RowAccessor:
    """Resolve logical domain fields from a configured GIS row."""

    layer_name: str
    row_index: object
    row: pd.Series
    mapping: LayerMapping
    crs: object | None = None

    def get(self, logical_field: str, *, default: Any = None) -> Any:
        source_column = self.mapping.fields.get(logical_field)
        if source_column is not None:
            if source_column not in self.row.index:
                raise GisMappingError(
                    self._message(
                        logical_field,
                        f"configured source column {source_column!r} does not exist",
                    )
                )
            value = self.row[source_column]
            if not is_missing(value):
                return value

        if logical_field in self.mapping.defaults:
            return self.mapping.defaults[logical_field]
        return default

    def require(self, logical_field: str) -> Any:
        value = self.get(logical_field)
        if is_missing(value):
            raise GisMappingError(
                self._message(logical_field, "required value is missing")
            )
        return value

    def unit(self, logical_field: str, canonical_unit: str) -> str:
        return str(self.mapping.units.get(logical_field, canonical_unit))

    def _message(self, logical_field: str, detail: str) -> str:
        return (
            f"Layer {self.layer_name!r}, row {self.row_index!r}, "
            f"field {logical_field!r}: {detail}."
        )
