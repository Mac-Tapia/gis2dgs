from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .readers.cymdist_text import (
    is_cymdist_import_config,
    is_cymdist_network_export,
    parse_cymdist_metadata,
    parse_cymdist_text,
    sniff_cymdist_role,
)

_DATE_TOKEN = re.compile(r"(20\d{6}|\d{6})")
_PROFILE_PATH = Path(__file__).resolve().parents[3] / "config" / "layer_profiles.yaml"
_INVENTORY_SUFFIX = re.compile(r"[_-]([A-Z]{1,3}\d{2,6})$", re.IGNORECASE)


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
    cymdist_roles = roles & {"network", "loads"}
    if cymdist_roles:
        return _cymdist_confidence_score(
            data_reports=data_reports,
            linked=linked,
            cross_ratio=cross_ratio,
            roles=roles,
        )
    return _tabular_confidence_score(data_reports=data_reports, linked=linked)


def _cymdist_confidence_score(
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


def _tabular_confidence_score(
    *,
    data_reports: list[BundleFileReport],
    linked: bool,
) -> float:
    """Score GIS/Excel/CSV inventory packages by electrical role coverage, not CYMDIST."""

    score = 0.15
    if not data_reports:
        return score
    score += 0.15
    roles = _infer_tabular_inventory_roles(data_reports)
    if roles.get("buses"):
        score += 0.2
    if roles.get("lines"):
        score += 0.2
    if roles.get("sources"):
        score += 0.1
    if roles.get("loads"):
        score += 0.1
    if roles.get("transformers"):
        score += 0.05
    if roles.get("buses") and roles.get("lines"):
        score += 0.15
    if linked:
        score += 0.1
    if _shared_inventory_suffix(data_reports):
        score += 0.05
    return min(score, 1.0)


@lru_cache(maxsize=1)
def _load_tabular_role_markers() -> dict[str, tuple[str, ...]]:
    if not _PROFILE_PATH.is_file():
        return {}
    payload = yaml.safe_load(_PROFILE_PATH.read_text(encoding="utf-8")) or {}
    roles = payload.get("roles", {})
    markers: dict[str, tuple[str, ...]] = {}
    if not isinstance(roles, dict):
        return markers
    for role, definition in roles.items():
        if not isinstance(definition, dict):
            continue
        raw = definition.get("name_markers", ())
        if isinstance(raw, list):
            markers[str(role)] = tuple(str(item).casefold() for item in raw)
    return markers


def _normalize_inventory_token(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def _infer_tabular_inventory_roles(
    reports: list[BundleFileReport],
) -> dict[str, bool]:
    markers = _load_tabular_role_markers()
    found = {role: False for role in markers}
    for report in reports:
        if report.role != "tabular":
            continue
        token = _normalize_inventory_token(Path(report.name).stem)
        for role, role_markers in markers.items():
            if any(marker in token for marker in role_markers):
                found[role] = True
    return found


def _shared_inventory_suffix(reports: list[BundleFileReport]) -> bool:
    """Return True when multiple tabular files share a feeder/inventory suffix."""

    suffixes: list[str] = []
    for report in reports:
        if report.role != "tabular":
            continue
        match = _INVENTORY_SUFFIX.search(Path(report.name).stem)
        if match is not None:
            suffixes.append(match.group(1).casefold())
    if len(suffixes) < 2:
        return False
    return len(set(suffixes)) == 1
