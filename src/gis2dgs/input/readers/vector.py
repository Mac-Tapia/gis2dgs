from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from ..compact import compact_frame
from ..dataset import InputDataset
from ..exceptions import InputError


class VectorInputReader:
    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        layers: tuple[str, ...] | None = None,
        aliases: dict[str, str] | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.layers = layers
        self.aliases = dict(aliases or {})
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    def _available_layers(self) -> tuple[str, ...]:
        if self.layers is not None:
            return self.layers
        try:
            import pyogrio

            listed = pyogrio.list_layers(self.path)
            names = tuple(str(row[0]) for row in listed)
            if names:
                return names
        except Exception:
            pass
        return (self.path.stem,)

    def read(self) -> InputDataset:
        if not self.path.exists():
            raise InputError(f"Vector input does not exist: {self.path}")
        result = InputDataset()
        available = self._available_layers()
        for layer in available:
            try:
                kwargs: dict[str, object] = {}
                if not (len(available) == 1 and layer == self.path.stem):
                    kwargs["layer"] = layer
                if self.sample_rows is not None and self.sample_rows > 0:
                    kwargs["rows"] = int(self.sample_rows)
                try:
                    frame = gpd.read_file(self.path, **kwargs)
                except TypeError:
                    kwargs.pop("rows", None)
                    frame = gpd.read_file(self.path, **kwargs)
                    if self.sample_rows is not None and self.sample_rows > 0:
                        frame = frame.iloc[: int(self.sample_rows)]
            except Exception as exc:
                raise InputError(
                    f"Unable to read vector layer {layer!r} from {self.path}: {exc}"
                ) from exc
            logical = self.aliases.get(layer, layer)
            if self.compact:
                frame = compact_frame(frame, copy=False)
            result.add_table(
                logical,
                frame,
                source_id=self.source_id,
                metadata={
                    "format": "vector",
                    "path": str(self.path),
                    "layer": layer,
                    "crs": str(frame.crs) if frame.crs is not None else None,
                },
                copy_frame=self.copy_frame,
            )
        return result
