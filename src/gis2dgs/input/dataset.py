from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import pandas as pd

from gis2dgs.gis.dataset import GisDataset

from .exceptions import DatasetConflictError


@dataclass(slots=True)
class InputTable:
    name: str
    frame: pd.DataFrame
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> InputTable:
        return InputTable(
            name=self.name,
            frame=self.frame.copy(),
            source_id=self.source_id,
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class InputDataset:
    """Universal collection of tabular and geospatial source tables.

    The electrical domain is intentionally not exposed here. Readers only turn
    files/databases into pandas/GeoPandas frames. Mapping into NetworkModel is a
    separate concern.
    """

    tables: dict[str, InputTable] = field(default_factory=dict)

    def add_table(
        self,
        name: str,
        frame: pd.DataFrame,
        *,
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        on_conflict: str = "error",
        copy_frame: bool = True,
    ) -> None:
        logical_name = name.strip()
        if not logical_name:
            raise ValueError("Input table name cannot be empty.")
        if logical_name in self.tables:
            if on_conflict == "error":
                raise DatasetConflictError(f"Duplicate input table: {logical_name}")
            if on_conflict == "overwrite":
                pass
            else:
                raise ValueError(f"Unknown table conflict policy: {on_conflict}")
        stored = frame.copy() if copy_frame else frame
        self.tables[logical_name] = InputTable(
            name=logical_name,
            frame=stored,
            source_id=source_id,
            metadata=dict(metadata or {}),
        )

    def table(self, name: str) -> InputTable:
        try:
            return self.tables[name]
        except KeyError as exc:
            raise KeyError(f"Input table not found: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self.tables)

    def merged(self, other: InputDataset, *, on_conflict: str = "error") -> InputDataset:
        result = self.copy()
        for table in other.tables.values():
            result.add_table(
                table.name,
                table.frame,
                source_id=table.source_id,
                metadata=table.metadata,
                on_conflict=on_conflict,
                copy_frame=False,
            )
        return result

    def copy(self) -> InputDataset:
        result = InputDataset()
        for table in self.tables.values():
            result.tables[table.name] = table.copy()
        return result

    def to_gis_dataset(self) -> GisDataset:
        """Bridge universal input tables to the legacy Phase 3 mapper boundary.

        Plain tables are wrapped as GeoDataFrames without inventing geometry.
        Existing GeoDataFrames retain geometry and CRS.
        """

        dataset = GisDataset()
        for table in self.tables.values():
            frame = table.frame
            if isinstance(frame, gpd.GeoDataFrame):
                geo = frame.copy()
            else:
                geo = gpd.GeoDataFrame(frame.copy())
            dataset.add_layer(table.name, geo)
        return dataset
