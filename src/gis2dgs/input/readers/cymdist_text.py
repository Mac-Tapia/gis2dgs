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
    current_logical: str | None = None
    current_columns: list[str] | None = None
    current_network_id: str | None = None
    rows: list[list[str]] = []

    def flush() -> None:
        nonlocal rows, current_columns, current_section, current_logical
        if current_logical is None or not rows or not current_columns:
            rows = []
            return
        frame = pd.DataFrame(rows, columns=current_columns)
        if (
            current_logical == "SECTION"
            and current_network_id
            and "NetworkID" not in frame.columns
        ):
            frame = frame.copy()
            frame["NetworkID"] = current_network_id
        _store_table(tables, current_logical, frame)
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
                current_logical = _normalize_section_name(current_section)
                current_columns = None
                current_network_id = None
                rows = []
                continue

            if current_section is None:
                continue

            format_match = _FORMAT.match(stripped)
            if format_match is not None:
                flush()
                format_name = _normalize_section_name(format_match.group("name"))
                # FORMAT_FEEDER appears inside [SECTION]; keep feeders as their own table.
                current_logical = (
                    "FEEDER" if format_name == "FEEDER" else _normalize_section_name(current_section)
                )
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
                # Flush pending SECTION rows with the *previous* NetworkID before
                # switching feeder context (FEEDER= often precedes the next FORMAT_).
                flush()
                payload = stripped.split("=", 1)[1]
                feeder_cols = (
                    current_columns
                    if current_logical == "FEEDER" and current_columns
                    else [
                        "NetworkID",
                        "HeadNodeID",
                        "CoordSet",
                        "Year",
                        "Description",
                        "Color",
                        "LoadFactor",
                    ]
                )
                feeder_parts = _split_row(payload, len(feeder_cols))
                if feeder_parts and feeder_parts[0]:
                    current_network_id = feeder_parts[0]
                _store_table(
                    tables,
                    "FEEDER",
                    pd.DataFrame([feeder_parts], columns=feeder_cols),
                )
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


def _store_table(tables: dict[str, pd.DataFrame], logical: str, frame: pd.DataFrame) -> None:
    """Accumulate rows when the same logical section is flushed more than once.

    CYMDIST exports repeat ``FORMAT_SECTION`` once per feeder; overwriting would
    keep only the last feeder's topology.
    """

    existing = tables.get(logical)
    if existing is None or existing.empty:
        tables[logical] = frame
        return
    if frame.empty:
        return
    if list(existing.columns) == list(frame.columns):
        tables[logical] = pd.concat([existing, frame], ignore_index=True)
        return
    all_cols = list(dict.fromkeys([*existing.columns, *frame.columns]))
    tables[logical] = pd.concat(
        [existing.reindex(columns=all_cols), frame.reindex(columns=all_cols)],
        ignore_index=True,
    )


def _enrich_network_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    sections = tables.get("SECTION")
    line_cfg = tables.get("LINE_CONFIGURATION")
    if sections is not None and line_cfg is not None:
        if "SectionID" in sections.columns and "SectionID" in line_cfg.columns:
            merged = sections.merge(
                line_cfg.drop_duplicates(subset=["SectionID"], keep="first"),
                on="SectionID",
                how="left",
                suffixes=("", "_linecfg"),
            )
            tables["SECTION"] = merged
            sections = tables["SECTION"]

    nodes = tables.get("NODE")
    headnodes = tables.get("HEADNODES")
    if nodes is not None:
        if (
            headnodes is not None
            and "NodeID" in nodes.columns
            and "NodeID" in headnodes.columns
            and "NetworkID" in headnodes.columns
        ):
            head = headnodes.drop_duplicates(subset=["NodeID"], keep="first")[
                [column for column in ("NodeID", "NetworkID") if column in headnodes.columns]
            ]
            if "NetworkID" in nodes.columns:
                nodes = nodes.drop(columns=["NetworkID"])
            nodes = nodes.merge(head, on="NodeID", how="left")
        if "NetworkID" not in nodes.columns:
            nodes = nodes.copy()
            nodes["NetworkID"] = pd.NA
        nodes = _fill_network_id_from_sources(nodes, tables.get("SOURCE"), sections)
        tables["NODE"] = nodes

    if sections is not None:
        if "NetworkID" not in sections.columns:
            sections = sections.copy()
            sections["NetworkID"] = pd.NA
        sections = _fill_section_network_id(sections, tables.get("NODE"))
        tables["SECTION"] = sections
    return tables


def _fill_network_id_from_sources(
    nodes: pd.DataFrame,
    sources: pd.DataFrame | None,
    sections: pd.DataFrame | None,
) -> pd.DataFrame:
    """Stamp NetworkID on nodes from SOURCE heads, then walk SECTION connectivity.

    Minimal exports often omit [HEADNODES] / FEEDER= and only put NetworkID on SOURCE.
    """

    if "NodeID" not in nodes.columns or "NetworkID" not in nodes.columns:
        return nodes
    result = nodes.copy()
    assigned: dict[str, str] = {}
    for _, row in result.iterrows():
        node_id = str(row["NodeID"]).strip() if pd.notna(row["NodeID"]) else ""
        net = row["NetworkID"]
        if node_id and pd.notna(net) and str(net).strip():
            assigned[node_id] = str(net).strip()

    if sources is not None and {"NodeID", "NetworkID"}.issubset(sources.columns):
        for _, row in sources.iterrows():
            node_id = str(row["NodeID"]).strip() if pd.notna(row["NodeID"]) else ""
            net = str(row["NetworkID"]).strip() if pd.notna(row["NetworkID"]) else ""
            if node_id and net and node_id not in assigned:
                assigned[node_id] = net

    if sections is not None and {"FromNodeID", "ToNodeID"}.issubset(sections.columns):
        edges: list[tuple[str, str]] = []
        for _, row in sections.iterrows():
            a = str(row["FromNodeID"]).strip() if pd.notna(row["FromNodeID"]) else ""
            b = str(row["ToNodeID"]).strip() if pd.notna(row["ToNodeID"]) else ""
            if a and b:
                edges.append((a, b))
        changed = True
        while changed:
            changed = False
            for a, b in edges:
                if a in assigned and b not in assigned:
                    assigned[b] = assigned[a]
                    changed = True
                elif b in assigned and a not in assigned:
                    assigned[a] = assigned[b]
                    changed = True

    if not assigned:
        return result
    result["NetworkID"] = [
        assigned.get(str(node).strip(), net if pd.notna(net) else pd.NA)
        if pd.notna(node)
        else (net if pd.notna(net) else pd.NA)
        for node, net in zip(result["NodeID"], result["NetworkID"], strict=False)
    ]
    return result


def _fill_section_network_id(
    sections: pd.DataFrame,
    nodes: pd.DataFrame | None,
) -> pd.DataFrame:
    if nodes is None or "NetworkID" not in sections.columns:
        return sections
    if not {"NodeID", "NetworkID"}.issubset(nodes.columns):
        return sections
    lookup = {
        str(row["NodeID"]).strip(): str(row["NetworkID"]).strip()
        for _, row in nodes.iterrows()
        if pd.notna(row["NodeID"])
        and pd.notna(row["NetworkID"])
        and str(row["NetworkID"]).strip()
    }
    if not lookup:
        return sections
    result = sections.copy()

    def _net_for(row: pd.Series) -> object:
        current = row.get("NetworkID")
        if pd.notna(current) and str(current).strip():
            return current
        for key in ("FromNodeID", "ToNodeID"):
            raw = row.get(key)
            if pd.isna(raw):
                continue
            found = lookup.get(str(raw).strip())
            if found:
                return found
        return current

    result["NetworkID"] = result.apply(_net_for, axis=1)
    return result


def _read_text_header(path: Path, size: int = 4096) -> str:
    if not path.is_file():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(size)
    except OSError:
        return ""
