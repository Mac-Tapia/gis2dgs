from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import geopandas as gpd

from ..dataset import InputDataset


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    dtype: str
    nullable: bool
    non_null_count: int
    unique_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "nullable": self.nullable,
            "non_null_count": self.non_null_count,
            "unique_count": self.unique_count,
        }


@dataclass(frozen=True, slots=True)
class TableSchema:
    name: str
    rows: int
    columns: tuple[ColumnSchema, ...]
    is_spatial: bool
    geometry_column: str | None
    crs: str | None
    source_id: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "rows": self.rows,
            "columns": [column.as_dict() for column in self.columns],
            "is_spatial": self.is_spatial,
            "geometry_column": self.geometry_column,
            "crs": self.crs,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class DatasetSchema:
    tables: tuple[TableSchema, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"tables": [table.as_dict() for table in self.tables]}


def discover_schema(
    dataset: InputDataset,
    *,
    sample_rows: int | None = None,
) -> DatasetSchema:
    tables: list[TableSchema] = []
    for input_table in dataset.tables.values():
        frame = input_table.frame
        profile = frame
        if sample_rows is not None and sample_rows > 0 and len(frame) > sample_rows:
            profile = frame.iloc[:sample_rows]
        columns: list[ColumnSchema] = []
        for column in frame.columns:
            series = profile[column]
            columns.append(
                ColumnSchema(
                    name=str(column),
                    dtype=str(frame[column].dtype),
                    nullable=bool(series.isna().any()),
                    non_null_count=int(series.notna().sum()),
                    unique_count=int(series.nunique(dropna=True)),
                )
            )
        is_spatial = isinstance(frame, gpd.GeoDataFrame) and frame.geometry.name in frame.columns
        geometry_column = frame.geometry.name if is_spatial else None
        crs = str(frame.crs) if is_spatial and frame.crs is not None else None
        tables.append(
            TableSchema(
                name=input_table.name,
                rows=len(frame),
                columns=tuple(columns),
                is_spatial=is_spatial,
                geometry_column=geometry_column,
                crs=crs,
                source_id=input_table.source_id,
            )
        )
    return DatasetSchema(tuple(tables))
