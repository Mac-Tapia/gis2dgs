from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..compact import compact_frame
from ..dataset import InputDataset
from ..exceptions import InputError

_SECTION = re.compile(r"^\[(?P<name>[^\]]+)\]\s*$")
_FORMAT = re.compile(r"^FORMAT_(?P<name>[A-Z0-9_]+)=(?P<columns>.+)$")
_KEY_VALUE = re.compile(r"^(?P<key>[A-Za-z0-9_]+)=(?P<value>.*)$")


def is_cymdist_network_export(path: Path) -> bool:
    header = _read_text_header(path)
    return "[GENERAL]" in header and "CYMDIST_VERSION" in header


def is_cymdist_import_config(path: Path) -> bool:
    header = _read_text_header(path)
    return "[IMPORT MODE]" in header


def sniff_cymdist_role(path: Path) -> str:
    if is_cymdist_import_config(path):
        return "equipment_import_config"
    if not is_cymdist_network_export(path):
        return "unknown"
    header = _read_text_header(path, size=8192)
    if "[NODE]" in header or "[SECTION]" in header:
        return "network"
    if "[LOADS]" in header or "[CUSTOMER LOADS]" in header:
        return "loads"
    return "network"


def parse_cymdist_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {"path": str(path)}
    if not path.is_file():
        return metadata
    in_general = False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            section = _SECTION.match(line)
            if section is not None:
                in_general = section.group("name").upper() == "GENERAL"
                if not in_general:
                    break
                continue
            if not in_general:
                continue
            match = _KEY_VALUE.match(line)
            if match is not None:
                metadata[match.group("key").upper()] = match.group("value")
    return metadata


def parse_cymdist_text(path: Path, *, sample_rows: int | None = None) -> tuple[dict[str, str], dict[str, pd.DataFrame]]:
    if not path.exists():
        raise InputError(f"CYMDIST text input does not exist: {path}")

    metadata = parse_cymdist_metadata(path)
    tables: dict[str, pd.DataFrame] = {}
    current_section: str | None = None
    current_columns: list[str] | None = None
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal rows, current_columns, current_section
        if current_section is None or not rows or not current_columns:
            rows = []
            return
        frame = pd.DataFrame(rows, columns=current_columns)
        logical = _normalize_section_name(current_section)
        tables[logical] = frame
        rows = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            stripped = line.strip()
            if not stripped:
                continue

            section = _SECTION.match(stripped)
            if section is not None:
                flush()
                current_section = section.group("name")
                current_columns = None
                rows = []
                continue

            if current_section is None:
                continue

            format_match = _FORMAT.match(stripped)
            if format_match is not None:
                flush()
                current_columns = [
                    column.strip()
                    for column in format_match.group("columns").split(",")
                    if column.strip()
                ]
                rows = []
                continue

            if current_columns is None:
                continue
            if stripped.upper().startswith("FEEDER="):
                continue

            rows.append(_split_row(stripped, len(current_columns)))

    flush()
    if sample_rows is not None and sample_rows > 0:
        for name, frame in list(tables.items()):
            tables[name] = frame.iloc[: int(sample_rows)].copy()
    tables = _enrich_network_tables(tables)
    return metadata, tables


class CymdistTextInputReader:
    """Reader for CYMDIST section-based text exports (network, loads, etc.)."""

    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        table_prefix: str | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.table_prefix = table_prefix
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    def read(self) -> InputDataset:
        if is_cymdist_import_config(self.path):
            raise InputError(
                f"{self.path.name} is a CYMDIST import configuration file, not tabular network data. "
                "Use the companion RED/CARGA export files instead."
            )
        metadata, tables = parse_cymdist_text(self.path, sample_rows=self.sample_rows)
        if not tables:
            raise InputError(f"No tabular CYMDIST sections found in {self.path}")

        prefix = self.table_prefix

        result = InputDataset()
        for section_name, frame in tables.items():
            logical = f"{prefix}__{section_name}" if prefix else section_name
            stored = compact_frame(frame, copy=False) if self.compact else frame
            result.add_table(
                logical,
                stored,
                source_id=self.source_id,
                metadata={
                    "format": "cymdist_text",
                    "path": str(self.path),
                    "section": section_name,
                    "role": sniff_cymdist_role(self.path),
                    **{key.lower(): value for key, value in metadata.items() if key != "PATH"},
                },
                copy_frame=self.copy_frame,
            )
        return result


def parse_cymdist_column_values(
    path: Path,
    *,
    section: str,
    column: str,
) -> set[str]:
    """Stream column values from one CYMDIST section without loading the full file."""

    target = _normalize_section_name(section)
    current_section: str | None = None
    columns: list[str] | None = None
    column_index: int | None = None
    values: set[str] = set()

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            section_match = _SECTION.match(line)
            if section_match is not None:
                current_section = _normalize_section_name(section_match.group("name"))
                columns = None
                column_index = None
                continue
            if current_section != target:
                continue
            if line.startswith("FORMAT_"):
                columns = [
                    part.strip()
                    for part in line.split("=", 1)[1].split(",")
                    if part.strip()
                ]
                column_index = columns.index(column) if column in columns else None
                continue
            if column_index is None or columns is None:
                continue
            if line.upper().startswith("FEEDER="):
                continue
            parts = _split_row(line, len(columns))
            if column_index < len(parts):
                value = parts[column_index].strip()
                if value:
                    values.add(value)
    return values


def _normalize_section_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_").upper()


def _split_row(line: str, expected: int) -> list[str]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < expected:
        parts.extend([""] * (expected - len(parts)))
    return parts[:expected]


def _enrich_network_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    sections = tables.get("SECTION")
    line_cfg = tables.get("LINE_CONFIGURATION")
    if sections is None or line_cfg is None:
        return tables
    if "SectionID" not in sections.columns or "SectionID" not in line_cfg.columns:
        return tables
    merged = sections.merge(
        line_cfg.drop_duplicates(subset=["SectionID"], keep="first"),
        on="SectionID",
        how="left",
        suffixes=("", "_linecfg"),
    )
    tables["SECTION"] = merged
    return tables


def _read_text_header(path: Path, size: int = 4096) -> str:
    if not path.is_file():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(size)
    except OSError:
        return ""
