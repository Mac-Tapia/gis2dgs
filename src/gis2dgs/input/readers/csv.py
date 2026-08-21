from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..compact import compact_frame
from ..dataset import InputDataset
from ..exceptions import InputError


class CsvInputReader:
    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        table_name: str | None = None,
        delimiter: str | None = None,
        encoding: str = "utf-8",
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.table_name = table_name or path.stem
        self.delimiter = delimiter
        self.encoding = encoding
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    def read(self) -> InputDataset:
        if not self.path.exists():
            raise InputError(f"CSV input does not exist: {self.path}")
        separator = self.delimiter
        if separator is None:
            separator = "\t" if self.path.suffix.lower() == ".tsv" else ","
        kwargs: dict[str, object] = {"sep": separator, "encoding": self.encoding}
        if self.sample_rows is not None and self.sample_rows > 0:
            kwargs["nrows"] = int(self.sample_rows)
        try:
            frame = pd.read_csv(self.path, **kwargs)
        except (OSError, UnicodeError, pd.errors.ParserError) as exc:
            raise InputError(f"Unable to read CSV input {self.path}: {exc}") from exc
        if self.compact:
            frame = compact_frame(frame, copy=False)
        result = InputDataset()
        result.add_table(
            self.table_name,
            frame,
            source_id=self.source_id,
            metadata={"format": "csv", "path": str(self.path)},
            copy_frame=self.copy_frame,
        )
        return result
