from dataclasses import dataclass, field

import geopandas as gpd

from .exceptions import GisLayerNotFoundError
from .geodataframe_utils import safe_frame_crs


@dataclass(slots=True)
class GisDataset:
    """Raw GIS layers before conversion to the electrical domain model."""

    layers: dict[str, gpd.GeoDataFrame] = field(default_factory=dict)

    def add_layer(self, name: str, frame: gpd.GeoDataFrame) -> None:
        if not name.strip():
            raise ValueError("Layer name cannot be empty.")
        self.layers[name] = frame.copy()

    def layer(self, name: str) -> gpd.GeoDataFrame:
        try:
            return self.layers[name]
        except KeyError as exc:
            raise GisLayerNotFoundError(f"GIS layer not found: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self.layers)

    def reprojected(self, target_crs: str | None) -> "GisDataset":
        """Return a copy of the dataset reprojected when a target CRS is configured."""

        if target_crs is None:
            clone = GisDataset()
            for name, frame in self.layers.items():
                clone.add_layer(name, frame)
            return clone

        projected = GisDataset()
        for name, frame in self.layers.items():
            if safe_frame_crs(frame) is None:
                raise ValueError(
                    f"Layer {name!r} has no CRS and cannot be reprojected to {target_crs}."
                )
            projected.add_layer(name, frame.to_crs(target_crs))
        return projected
