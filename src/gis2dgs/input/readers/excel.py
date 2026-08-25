from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..compact import compact_frame
from ..dataset import InputDataset
from ..exceptions import InputDependencyError, InputError


class ExcelInputReader:
    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        sheets: tuple[str, ...] | None = None,
        aliases: dict[str, str] | None = None,
        table_name: str | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.sheets = sheets
        self.aliases = dict(aliases or {})
        self.table_name = table_name
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    def read(self) -> InputDataset:
        if not self.path.exists():
            raise InputError(f"Excel input does not exist: {self.path}")
        excel_kwargs: dict[str, object] = {}
        if self.sample_rows is not None and self.sample_rows > 0:
            excel_kwargs["nrows"] = int(self.sample_rows)
        try:
            if self.sheets is None:
                frames = pd.read_excel(self.path, sheet_name=None, **excel_kwargs)
            else:
                frames = {
                    sheet: pd.read_excel(self.path, sheet_name=sheet, **excel_kwargs)
                    for sheet in self.sheets
                }
        except ImportError as exc:
            raise InputDependencyError(
                "Reading this Excel format requires an additional pandas engine. "
                "For legacy .xls files install the optional 'excel-legacy' dependencies."
            ) from exc
        except ValueError as exc:
            raise InputError(f"Unable to read Excel input {self.path}: {exc}") from exc

        result = InputDataset()
        single_sheet = len(frames) == 1
        for sheet, frame in frames.items():
            if self.table_name and single_sheet:
                logical = self.table_name
            else:
                logical = self.aliases.get(sheet, sheet)
            if self.compact:
                frame = compact_frame(frame, copy=False)
            result.add_table(
                logical,
                frame,
                source_id=self.source_id,
                metadata={"format": "excel", "path": str(self.path), "sheet": sheet},
                copy_frame=self.copy_frame,
            )
        return result
