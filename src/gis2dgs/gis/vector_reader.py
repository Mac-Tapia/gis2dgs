from pathlib import Path

import geopandas as gpd

from .base import GisReader
from .dataset import GisDataset
from .exceptions import GisError


class VectorFileReader(GisReader):
    """Read vector layers from SHP, GPKG, GeoJSON and compatible formats."""

    def __init__(self, path: Path, layers: list[str] | None = None) -> None:
        self.path = path
        self.layers = layers

    def _layer_names(self) -> list[str]:
        if self.layers is not None:
            return self.layers

        try:
            available = gpd.list_layers(self.path)
            names = available["name"].astype(str).tolist()
            return names or [self.path.stem]
        except Exception:
            # Some single-layer drivers do not expose layer enumeration.
            return [self.path.stem]

    def read(self) -> GisDataset:
        if not self.path.exists():
            raise FileNotFoundError(self.path)

        dataset = GisDataset()
        try:
            for layer_name in self._layer_names():
                read_layer = None if layer_name == self.path.stem else layer_name
                frame = gpd.read_file(self.path, layer=read_layer)
                dataset.add_layer(layer_name, frame)
        except Exception as exc:
            raise GisError(f"Unable to read vector GIS source: {self.path}") from exc
        return dataset
