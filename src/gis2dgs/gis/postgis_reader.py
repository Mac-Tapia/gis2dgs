from collections.abc import Mapping

import geopandas as gpd
from sqlalchemy.engine import Connection, Engine

from .base import GisReader
from .dataset import GisDataset
from .exceptions import GisError


class PostGisReader(GisReader):
    """Read configured PostGIS SQL statements into named GIS layers."""

    def __init__(
        self,
        connectable: Engine | Connection,
        queries: Mapping[str, str],
        *,
        geom_column: str = "geometry",
    ) -> None:
        self.connectable = connectable
        self.queries = dict(queries)
        self.geom_column = geom_column

    def read(self) -> GisDataset:
        dataset = GisDataset()
        try:
            for layer_name, query in self.queries.items():
                frame = gpd.read_postgis(
                    query, self.connectable, geom_col=self.geom_column
                )
                dataset.add_layer(layer_name, frame)
        except Exception as exc:
            raise GisError("Unable to read one or more PostGIS layers.") from exc
        return dataset
