from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from ..compact import compact_frame
from ..dataset import InputDataset
from ..exceptions import InputDependencyError, InputError


class ParquetInputReader:
    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        table_name: str | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.table_name = table_name or path.stem
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    def read(self) -> InputDataset:
        if not self.path.exists():
            raise InputError(f"Parquet input does not exist: {self.path}")
        try:
            frame = self._read_frame()
        except ImportError as exc:
            raise InputDependencyError(
                "Parquet support requires pyarrow. Install the optional 'parquet' dependencies."
            ) from exc
        if self.compact:
            frame = compact_frame(frame, copy=False)
        result = InputDataset()
        result.add_table(
            self.table_name,
            frame,
            source_id=self.source_id,
            metadata={"format": "parquet", "path": str(self.path)},
            copy_frame=self.copy_frame,
        )
        return result

    def _read_frame(self) -> pd.DataFrame:
        if self.sample_rows is not None and self.sample_rows > 0:
            try:
                import pyarrow.parquet as pq

                parquet_file = pq.ParquetFile(self.path)
                batch = next(parquet_file.iter_batches(batch_size=int(self.sample_rows)))
                return batch.to_pandas()
            except StopIteration:
                return pd.DataFrame()
            except Exception:
                pass
        try:
            frame = gpd.read_parquet(self.path)
        except (ValueError, TypeError):
            frame = pd.read_parquet(self.path)
        if self.sample_rows is not None and self.sample_rows > 0:
            return frame.iloc[: int(self.sample_rows)]
        return frame
