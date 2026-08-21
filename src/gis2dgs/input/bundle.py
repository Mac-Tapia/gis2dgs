from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .readers.cymdist_text import (
    is_cymdist_import_config,
    is_cymdist_network_export,
    parse_cymdist_metadata,
    parse_cymdist_text,
    sniff_cymdist_role,
)

_DATE_TOKEN = re.compile(r"(20\d{6}|\d{6})")


@dataclass(frozen=True, slots=True)
class BundleFileReport:
    path: str
    name: str
    role: str
    format: str
    export_date: str | None
    cymdist_version: str | None
    date_token: str | None
    table_count: int
    key_tables: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InputBundleAssessment:
    files: tuple[BundleFileReport, ...]
    linked: bool
    system_kind: str
    confidence: float
    shared_date_tokens: tuple[str, ...]
    shared_export_dates: tuple[str, ...]
    cross_reference_ratio: float | None
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "linked": self.linked,
            "system_kind": self.system_kind,
            "confidence": self.confidence,
            "shared_date_tokens": list(self.shared_date_tokens),
            "shared_export_dates": list(self.shared_export_dates),
            "cross_reference_ratio": self.cross_reference_ratio,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "files": [
                {
                    "path": item.path,
                    "name": item.name,
                    "role": item.role,
                    "format": item.format,
                    "export_date": item.export_date,
                    "cymdist_version": item.cymdist_version,
                    "date_token": item.date_token,
                    "table_count": item.table_count,
                    "key_tables": list(item.key_tables),
                }
                for item in self.files
            ],
        }


def assess_input_bundle(paths: tuple[Path, ...] | list[Path]) -> InputBundleAssessment:
    reports = [_inspect_file(path) for path in paths]
    data_reports = [item for item in reports if item.role not in {"unsupported", "equipment_import_config"}]
    warnings: list[str] = []
    errors: list[str] = []

    for item in reports:
        if item.role == "equipment_import_config":
            warnings.append(
                f"{item.name} es configuración de importación CYMDIST (no aporta tablas de red)."
            )
        if item.role == "unsupported":
            errors.append(f"{item.name} no es un formato de datos reconocido para el paquete.")

    tokens = {item.date_token for item in data_reports if item.date_token}
    export_dates = {item.export_date for item in data_reports if item.export_date}
    roles = {item.role for item in data_reports}
    cymdist_roles = roles & {"network", "loads"}

    cross_ratio = (
        _cross_reference_loads_to_network(paths, reports)
        if cymdist_roles == {"network", "loads"}
        else None
    )

    linked = bool(data_reports) and not errors
    if len(tokens) > 1:
        linked = False
        errors.append(
            "Los archivos parecen pertenecer a fechas distintas: "
            + ", ".join(sorted(tokens))
        )
    if len(export_dates) > 1:
        linked = False
        errors.append(
            "Las fechas de exportación CYMDIST no coinciden: "
            + ", ".join(sorted(export_dates))
        )
    if cymdist_roles and "network" not in roles:
        warnings.append("No se detectó archivo de red (RED) con nodos/tramos.")
    if cymdist_roles and "loads" not in roles:
        warnings.append("No se detectó archivo de cargas (CARGA).")

    system_kind = _infer_system_kind(paths, reports) if cymdist_roles else "tabular"
    confidence = _confidence_score(
        data_reports=data_reports,
        linked=linked,
        cross_ratio=cross_ratio,
        roles=roles,
    )

    if cross_ratio is not None and cross_ratio < 0.5:
        warnings.append(
            f"Solo {cross_ratio:.0%} de cargas referencia tramos presentes en la red."
        )

    return InputBundleAssessment(
        files=tuple(reports),
        linked=linked and len(errors) == 0,
        system_kind=system_kind,
        confidence=confidence,
        shared_date_tokens=tuple(sorted(tokens)),
        shared_export_dates=tuple(sorted(export_dates)),
        cross_reference_ratio=cross_ratio,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _inspect_file(path: Path) -> BundleFileReport:
    resolved = path.expanduser().resolve()
    name = resolved.name
    if is_cymdist_import_config(resolved):
        return BundleFileReport(
            path=str(resolved),
            name=name,
            role="equipment_import_config",
            format="cymdist_import_config",
            export_date=None,
            cymdist_version=None,
            date_token=_extract_date_token(name),
            table_count=0,
            key_tables=(),
        )
    if is_cymdist_network_export(resolved):
        metadata = parse_cymdist_metadata(resolved)
        _, tables = parse_cymdist_text(resolved, sample_rows=200)
        role = sniff_cymdist_role(resolved)
        key_tables = tuple(
            table
            for table in ("NODE", "SECTION", "SOURCE", "LOADS", "CUSTOMER_LOADS")
            if table in tables
        )
        return BundleFileReport(
            path=str(resolved),
            name=name,
            role=role,
            format="cymdist_text",
            export_date=metadata.get("DATE"),
            cymdist_version=metadata.get("CYMDIST_VERSION"),
            date_token=_extract_date_token(name),
            table_count=len(tables),
            key_tables=key_tables,
        )
    try:
        from .detector import detect_input_kind

        kind = detect_input_kind(resolved)
    except Exception:
        return BundleFileReport(
            path=str(resolved),
            name=name,
            role="unsupported",
            format="unknown",
            export_date=None,
            cymdist_version=None,
            date_token=_extract_date_token(name),
            table_count=0,
            key_tables=(),
        )
    return BundleFileReport(
        path=str(resolved),
        name=name,
        role="tabular",
        format=kind.value,
        export_date=None,
        cymdist_version=None,
        date_token=_extract_date_token(name),
        table_count=1,
        key_tables=(resolved.stem,),
    )


def _extract_date_token(name: str) -> str | None:
    match = _DATE_TOKEN.search(name.upper())
    return match.group(1) if match is not None else None


def _cross_reference_loads_to_network(
    paths: tuple[Path, ...] | list[Path],
    reports: list[BundleFileReport],
) -> float | None:
    from .readers.cymdist_text import parse_cymdist_column_values

    network_sections: set[str] = set()
    load_sections: set[str] = set()
    for path, report in zip(paths, reports, strict=False):
        if report.format != "cymdist_text":
            continue
        if report.role == "network":
            network_sections.update(
                parse_cymdist_column_values(
                    path, section="SECTION", column="SectionID"
                )
            )
        if report.role == "loads":
            for table_name, column in (
                ("CUSTOMER LOADS", "SectionID"),
                ("LOADS", "SectionID"),
            ):
                load_sections.update(
                    parse_cymdist_column_values(path, section=table_name, column=column)
                )
    if not load_sections or not network_sections:
        return None
    matched = load_sections & network_sections
    return len(matched) / len(load_sections)


def _infer_system_kind(
    paths: tuple[Path, ...] | list[Path],
    reports: list[BundleFileReport],
) -> str:
    voltages: list[float] = []
    for path, report in zip(paths, reports, strict=False):
        if report.role != "network":
            continue
        _, tables = parse_cymdist_text(path, sample_rows=2000)
        sources = tables.get("SOURCE")
        if sources is None or "DesiredVoltage" not in sources.columns:
            continue
        for value in sources["DesiredVoltage"].tolist():
            try:
                voltages.append(float(str(value).strip()))
            except (TypeError, ValueError):
                continue
    if not voltages:
        return "unknown"
    max_kv = max(voltages)
    if max_kv >= 69.0:
        return "transmission"
    if max_kv <= 35.0:
        return "distribution"
    return "mixed"


def _confidence_score(
    *,
    data_reports: list[BundleFileReport],
    linked: bool,
    cross_ratio: float | None,
    roles: set[str],
) -> float:
    score = 0.2
    if data_reports:
        score += 0.2
    if linked:
        score += 0.25
    if "network" in roles:
        score += 0.15
    if "loads" in roles:
        score += 0.1
    if cross_ratio is not None:
        score += 0.1 * cross_ratio
    return min(score, 1.0)
