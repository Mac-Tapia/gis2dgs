from pathlib import Path

import geopandas as gpd
import pandas as pd

from .base import GisReader
from .dataset import GisDataset
from .exceptions import GisSchemaError


class CsvPointReader(GisReader):
    """Read a CSV point layer using explicit X/Y columns and a CRS."""

    def __init__(
        self,
        path: Path,
        *,
        x_column: str,
        y_column: str,
        crs: str,
        layer_name: str | None = None,
    ) -> None:
        self.path = path
        self.x_column = x_column
        self.y_column = y_column
        self.crs = crs
        self.layer_name = layer_name or path.stem

    def read(self) -> GisDataset:
        if not self.path.exists():
            raise FileNotFoundError(self.path)

        frame = pd.read_csv(self.path)
        missing = {self.x_column, self.y_column} - set(frame.columns)
        if missing:
            raise GisSchemaError(f"Missing coordinate columns: {sorted(missing)}")

        if frame[[self.x_column, self.y_column]].isna().any().any():
            raise GisSchemaError("Coordinate columns cannot contain null values.")

        try:
            x_values = pd.to_numeric(frame[self.x_column], errors="raise")
            y_values = pd.to_numeric(frame[self.y_column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise GisSchemaError("Coordinate columns must be numeric.") from exc

        geometry = gpd.points_from_xy(x_values, y_values)
        geoframe = gpd.GeoDataFrame(frame, geometry=geometry, crs=self.crs)
        dataset = GisDataset()
        dataset.add_layer(self.layer_name, geoframe)
        return dataset
