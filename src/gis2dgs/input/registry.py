from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import InputReader
from .detector import InputKind, detect_input_kind
from .exceptions import UnsupportedInputError
from .readers import (
    CsvInputReader,
    CymdistTextInputReader,
    ExcelInputReader,
    MssqlBackupReader,
    ParquetInputReader,
    SqlAlchemyInputReader,
    VectorInputReader,
)


class InputReaderFactory:
    @staticmethod
    def create(
        uri: str | Path,
        *,
        kind: InputKind = InputKind.AUTO,
        source_id: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> InputReader:
        resolved = detect_input_kind(uri) if kind == InputKind.AUTO else kind
        opts = dict(options or {})
        if resolved == InputKind.EXCEL:
            return ExcelInputReader(Path(uri), source_id=source_id, **opts)
        if resolved == InputKind.CSV:
            return CsvInputReader(Path(uri), source_id=source_id, **opts)
        if resolved == InputKind.VECTOR:
            return VectorInputReader(Path(uri), source_id=source_id, **opts)
        if resolved == InputKind.PARQUET:
            return ParquetInputReader(Path(uri), source_id=source_id, **opts)
        if resolved == InputKind.DATABASE:
            return SqlAlchemyInputReader(uri, source_id=source_id, **opts)
        if resolved == InputKind.MSSQL_BACKUP:
            return MssqlBackupReader(Path(uri), source_id=source_id, **opts)
        if resolved == InputKind.CYMDIST_TEXT:
            return CymdistTextInputReader(Path(uri), source_id=source_id, **opts)
        raise UnsupportedInputError(f"Unsupported input kind: {resolved}")
