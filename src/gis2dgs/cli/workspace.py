from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import ValidationError

from gis2dgs.assist import MappingSuggestion, mapping_to_yaml_payload, suggest_mapping
from gis2dgs.config import ResolvedProjectConfig, load_project_config
from gis2dgs.dgs import DgsError, inspect_excel_template
from gis2dgs.input import (
    SQL_SCRIPT_ERROR,
    InputError,
    InputKind,
    InputReaderFactory,
    UnsupportedInputError,
    assess_input_bundle,
    detect_input_kind,
    discover_schema,
    enrich_cymdist_tables,
    iter_detectable_paths,
    merge_datasets,
    programmed_file_suffixes,
)
from gis2dgs.input.readers.cymdist_text import is_cymdist_import_config
from gis2dgs.input.compact import env_sample_rows
from gis2dgs.pipeline import (
    ConversionResult,
    ProgressReporter,
    emit_progress,
    run_conversion,
)


class LoadedFileKind(StrEnum):
    PROJECT = "project"
    INPUT = "input"
    DGS_TEMPLATE = "dgs_template"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class LoadedFile:
    path: Path
    kind: LoadedFileKind
    label: str
    detail: str
    members: tuple[Path, ...] = ()
    detections: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    success: bool
    action: str
    message: str
    payload: dict[str, Any]


def classify_file(path: Path) -> LoadedFile:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return LoadedFile(
            resolved,
            LoadedFileKind.UNSUPPORTED,
            "No encontrado",
            f"No existe el archivo: {resolved}",
        )
    if resolved.is_dir():
        return _classify_directory(resolved)

    suffix = resolved.suffix.lower()
    if suffix == ".sql":
        return LoadedFile(
            resolved,
            LoadedFileKind.UNSUPPORTED,
            "Script SQL (no soportado)",
            SQL_SCRIPT_ERROR,
        )
    if suffix in {".yaml", ".yml"}:
        return _classify_yaml(resolved)
    if suffix in {".xlsx", ".xlsm", ".xls"} and _looks_like_dgs_template(resolved):
        return LoadedFile(
            resolved,
            LoadedFileKind.DGS_TEMPLATE,
            "Plantilla DGS",
            "Excel DGS de referencia. Ejecutar inspecciona el esquema de salida.",
        )
    try:
        kind = detect_input_kind(resolved)
    except UnsupportedInputError as exc:
        return LoadedFile(
            resolved,
            LoadedFileKind.UNSUPPORTED,
            "No soportado",
            str(exc),
        )
    if kind is InputKind.MSSQL_BACKUP:
        return LoadedFile(
            resolved,
            LoadedFileKind.INPUT,
            "Backup SQL Server",
            "Copia de seguridad detectada. Ejecutar restaura el .bak en SQL Server "
            "y lee las tablas (SQL Server local o Docker se comprueba al ejecutar). "
            "Para DGS use examples/mssql_backup/project.yaml con mapping.",
            members=(resolved,),
        )
    return LoadedFile(
        resolved,
        LoadedFileKind.INPUT,
        f"Datos de entrada ({kind.value})",
        "Fuente detectada con el detector del conversor "
        f"({kind.value}). Ejecutar inspecciona tablas y campos. "
        f"Formatos programados: {', '.join(sorted(programmed_file_suffixes()))}. "
        "Para generar DGS cargue un project.yaml.",
        members=(resolved,),
    )


def detect_project_sources(project: ResolvedProjectConfig) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for source in project.inputs.sources:
        uri = source.resolved_uri(project.base_dir)
        row: dict[str, Any] = {
            "id": source.id,
            "uri": uri,
            "configured_kind": source.kind,
        }
        remote = bool(urlparse(uri).scheme) and "://" in uri
        if remote:
            row["exists"] = True
        else:
            row["exists"] = Path(uri).exists()
        try:
            detected = detect_input_kind(uri)
            row["detected_kind"] = detected.value
        except UnsupportedInputError as exc:
            row["detected_kind"] = None
            row["error"] = str(exc)
        if not row["exists"]:
            row["status"] = "missing"
        elif row.get("error"):
            row["status"] = "unsupported"
        else:
            row["status"] = "ok"
        rows.append(row)
    return tuple(rows)


def load_and_run(
    source: str | Path,
    *,
    work_dir: Path | None = None,
    sample_rows: int | None = None,
    use_llm: bool = False,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    """Detect type and run inspect → mapping → NetworkModel → validated DGS.

    A project.yaml converts as-is. Any other supported source is scaffolded under
    output/loaded/<name>/ using the universal electrical/DGS templates, then converted.
    """

    text = str(source)
    if "://" in text:
        emit_progress(on_progress, f"=== Inicio: {text} ===")
        return _load_and_run_uri(
            text,
            work_dir=work_dir,
            sample_rows=sample_rows,
            use_llm=use_llm,
            on_progress=on_progress,
        )
    return load_and_run_loaded(
        classify_file(Path(source)),
        work_dir=work_dir,
        sample_rows=sample_rows,
        use_llm=use_llm,
        on_progress=on_progress,
    )


def load_and_run_loaded(
    loaded: LoadedFile,
    *,
    work_dir: Path | None = None,
    sample_rows: int | None = None,
    use_llm: bool = False,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    """Run the integral flow for an already-classified source (single file or bundle)."""

    emit_progress(on_progress, f"=== Inicio: {loaded.path} ===")
    if loaded.kind is LoadedFileKind.UNSUPPORTED:
        emit_progress(on_progress, f"ERROR: {loaded.detail}")
        return ExecutionOutcome(False, "load", loaded.detail, {"path": str(loaded.path)})
    emit_progress(on_progress, f"Tipo detectado: {loaded.label}")
    if loaded.kind is LoadedFileKind.PROJECT:
        return _execute_project(loaded.path, on_progress=on_progress)
    if loaded.kind is LoadedFileKind.DGS_TEMPLATE:
        output = (work_dir or Path("output") / "loaded") / "dgs_schema.yaml"
        return _execute_inspect_dgs(loaded.path, output, on_progress=on_progress)
    return _load_and_run_input(
        loaded,
        work_dir=work_dir,
        sample_rows=sample_rows,
        use_llm=use_llm,
        on_progress=on_progress,
    )


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    marker = Path("examples") / "minimal" / "config" / "validation.yaml"
    for parent in here.parents:
        if (parent / marker).is_file():
            return parent
    return Path.cwd()


def _sanitize_run_name(path: Path) -> str:
    raw = path.stem or path.name or "loaded"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._") or "loaded"
    return cleaned[:80]


def _template_config_dir() -> Path:
    return _repo_root() / "examples" / "minimal" / "config"


def _copy_runtime_templates(config_dir: Path, *, for_discovery: bool = False) -> None:
    source = _template_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "validation.yaml",
        "electrical_library.yaml",
        "powerfactory_mapping.yaml",
        "dgs_mapping.yaml",
    ):
        shutil.copy2(source / name, config_dir / name)
    if for_discovery:
        validation_path = config_dir / "validation.yaml"
        validation_path.write_text(
            yaml.safe_dump(
                {"profile": "import", "require_transformer_type": False},
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        pf_path = config_dir / "powerfactory_mapping.yaml"
        pf_payload = yaml.safe_load(pf_path.read_text(encoding="utf-8")) or {}
        if isinstance(pf_payload, dict):
            pf_payload["require_type_references"] = False
            pf_path.write_text(
                yaml.safe_dump(pf_payload, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
    dgs_path = config_dir / "dgs_mapping.yaml"
    dgs_payload = yaml.safe_load(dgs_path.read_text(encoding="utf-8")) or {}
    if isinstance(dgs_payload, dict):
        dgs_payload["allow_create_without_template"] = True
        dgs_payload["template_path"] = None
        dgs_path.write_text(
            yaml.safe_dump(dgs_payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def _cymdist_seed_mapping() -> dict[str, Any]:
    seed_path = _repo_root() / "examples" / "cymdist_030826" / "config" / "mapping.yaml"
    if not seed_path.is_file():
        return {}
    payload = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _merge_mapping_seed(seed: dict[str, Any], suggested: dict[str, Any]) -> dict[str, Any]:
    merged = dict(seed)
    for key, value in suggested.items():
        if value is None:
            continue
        if key not in merged or merged[key] is None:
            merged[key] = value
    return merged


def _is_cymdist_data_bundle(assessment) -> bool:
    return any(
        item.format == "cymdist_text" and item.role in {"network", "loads"}
        for item in assessment.files
    )


def _bundle_data_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(path for path in paths if not is_cymdist_import_config(path))
    return tuple(path for path in paths if not is_cymdist_import_config(path))


def _format_bundle_summary(assessment) -> str:
    lines = [
        f"Sistema: {assessment.system_kind} | Vinculados: {'sí' if assessment.linked else 'no'} | "
        f"Confianza: {assessment.confidence:.0%}",
    ]
    for item in assessment.files:
        lines.append(
            f"- {item.name} [{item.role}] tablas={item.table_count} "
            f"fecha={item.export_date or item.date_token or '?'}"
        )
    for warning in assessment.warnings:
        lines.append(f"  Aviso: {warning}")
    for error in assessment.errors:
        lines.append(f"  Error: {error}")
    return "\n".join(lines)


def _sources_for_paths(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    used: set[str] = set()
    for path in _bundle_data_paths(paths):
        kind = detect_input_kind(path)
        base = re.sub(r"[^A-Za-z0-9_]+", "_", path.stem) or "source"
        source_id = base
        index = 1
        while source_id in used:
            index += 1
            source_id = f"{base}_{index}"
        used.add(source_id)
        entry: dict[str, Any] = {
            "id": source_id,
            "uri": str(path.resolve()),
            "kind": kind.value,
        }
        if kind is InputKind.CSV:
            entry["options"] = {"table_name": path.stem}
        elif kind is InputKind.MSSQL_BACKUP:
            os.environ["GIS2DGS_MSSQL_BACKUP"] = str(path.resolve())
        sources.append(entry)
    return sources


def _write_loaded_project(
    *,
    run_dir: Path,
    sources: list[dict[str, Any]],
    mapping: dict[str, Any],
    name: str,
) -> Path:
    config_dir = run_dir / "config"
    _copy_runtime_templates(config_dir, for_discovery=True)
    mapping_path = config_dir / "mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(mapping, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    out_dir = run_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "inputs": {"on_conflict": "overwrite", "sources": sources},
        "mapping": "config/mapping.yaml",
        "validation": "config/validation.yaml",
        "electrical_library": "config/electrical_library.yaml",
        "powerfactory_mapping": "config/powerfactory_mapping.yaml",
        "dgs_schema": "config/dgs_mapping.yaml",
        "output_dgs": "output/red_dgs.xlsx",
        "validation_json": "output/validation.json",
        "validation_csv": "output/validation.csv",
        "schema_report": "output/input_schema.yaml",
        "fail_on_validation_errors": True,
    }
    project_path = run_dir / "project.yaml"
    project_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return project_path


def _load_and_run_input(
    loaded: LoadedFile,
    *,
    work_dir: Path | None,
    sample_rows: int | None,
    use_llm: bool,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    run_dir = work_dir or (Path("output") / "loaded" / _sanitize_run_name(loaded.path))
    run_dir.mkdir(parents=True, exist_ok=True)
    emit_progress(on_progress, f"Directorio de trabajo: {run_dir.resolve()}")
    data_paths = _bundle_data_paths(loaded.members or (loaded.path,))
    bundle_assessment = None
    if len(data_paths) > 1:
        emit_progress(on_progress, "[Paquete] Analizando coherencia multi-archivo…")
        bundle_assessment = assess_input_bundle(data_paths)
        emit_progress(on_progress, _format_bundle_summary(bundle_assessment))
        report_path = run_dir / "output" / "bundle_assessment.yaml"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            yaml.safe_dump(
                bundle_assessment.as_dict(), sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        emit_progress(on_progress, f"[Paquete] Informe: {report_path}")
        if bundle_assessment.errors:
            emit_progress(on_progress, "ERROR: paquete incompatible.")
            return ExecutionOutcome(
                False,
                "load",
                "El paquete de archivos no parece del mismo sistema eléctrico:\n"
                + _format_bundle_summary(bundle_assessment),
                {"bundle": bundle_assessment.as_dict()},
            )
    emit_progress(on_progress, "[Inspección] Leyendo entradas y descubriendo esquema…")
    inspect = _execute_inspect_inputs(
        data_paths,
        run_dir / "output" / "input_schema.yaml",
        sample_rows=sample_rows,
        on_progress=on_progress,
    )
    if not inspect.success:
        emit_progress(on_progress, f"ERROR inspección: {inspect.message}")
        return ExecutionOutcome(False, "load", inspect.message, inspect.payload)
    emit_progress(on_progress, inspect.message)
    emit_progress(on_progress, "[Mapping] Proponiendo mapping (NSGA-II + TOPSIS)…")
    suggested = suggest_mapping_for_loaded(
        loaded,
        output=run_dir / "config" / "mapping.yaml",
        sample_rows=sample_rows,
        use_llm=use_llm,
        on_progress=on_progress,
    )
    if not suggested.success:
        emit_progress(on_progress, f"ERROR mapping: {suggested.message}")
        return ExecutionOutcome(False, "load", suggested.message, suggested.payload)
    mapping = suggested.payload.get("mapping")
    if not isinstance(mapping, dict):
        return ExecutionOutcome(
            False,
            "load",
            "No se obtuvo mapping para convertir.",
            suggested.payload,
        )
    if bundle_assessment is not None and _is_cymdist_data_bundle(bundle_assessment):
        emit_progress(on_progress, "[Mapping] Aplicando plantilla CYMDIST…")
        mapping = _merge_mapping_seed(_cymdist_seed_mapping(), mapping)
    emit_progress(on_progress, f"[Proyecto] Escribiendo project.yaml en {run_dir}…")
    sources = _sources_for_paths(data_paths)
    for source in sources:
        emit_progress(
            on_progress,
            f"  fuente {source['id']}: {source['kind']} → {source['uri']}",
        )
    project_path = _write_loaded_project(
        run_dir=run_dir,
        sources=sources,
        mapping=mapping,
        name=_sanitize_run_name(loaded.path),
    )
    emit_progress(on_progress, f"[Proyecto] Creado: {project_path}")
    if mapping.get("buses") is None:
        mapping_path = run_dir / "config" / "mapping.yaml"
        payload = {
            "source": str(loaded.path),
            "detected_kind": loaded.label,
            "project": str(project_path),
            "mapping_path": str(mapping_path),
            "schema": inspect.payload,
            "mapping": mapping,
        }
        return ExecutionOutcome(
            False,
            "load",
            "Inspección y mapping listos, pero no hay barras mapeadas. "
            f"Revise {mapping_path} y complete id, tensión y conectividad "
            "antes de generar DGS. El mapping es una propuesta, no un DGS.",
            payload,
        )
    emit_progress(on_progress, "[Conversión] Iniciando pipeline integral → DGS…")
    converted = _execute_project(project_path, on_progress=on_progress)
    payload = {
        "source": str(loaded.path),
        "detected_kind": loaded.label,
        "project": str(project_path),
        "schema": inspect.payload,
        "mapping": mapping,
        "conversion": converted.payload,
    }
    if not converted.success:
        emit_progress(on_progress, f"ERROR conversión: {converted.message}")
        return ExecutionOutcome(
            False,
            "load",
            "Inspección y mapping listos, pero la conversión falló: "
            f"{converted.message}",
            payload,
        )
    emit_progress(on_progress, f"=== Fin OK: {converted.message} ===")
    return ExecutionOutcome(True, "load", converted.message, payload)


def _load_and_run_uri(
    uri: str,
    *,
    work_dir: Path | None,
    sample_rows: int | None,
    use_llm: bool,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    run_dir = work_dir or (Path("output") / "loaded" / "database")
    run_dir.mkdir(parents=True, exist_ok=True)
    emit_progress(on_progress, f"Directorio de trabajo: {run_dir.resolve()}")
    emit_progress(on_progress, "[Inspección] Base de datos remota…")
    inspect = _execute_inspect_uri(
        uri,
        output=run_dir / "output" / "input_schema.yaml",
        sample_rows=sample_rows,
    )
    if not inspect.success:
        emit_progress(on_progress, f"ERROR inspección: {inspect.message}")
        return ExecutionOutcome(False, "load", inspect.message, inspect.payload)
    emit_progress(on_progress, inspect.message)
    emit_progress(on_progress, "[Mapping] Proponiendo mapping…")
    suggested = suggest_mapping_for_uri(
        uri,
        output=run_dir / "config" / "mapping.yaml",
        sample_rows=sample_rows,
        use_llm=use_llm,
    )
    if not suggested.success:
        emit_progress(on_progress, f"ERROR mapping: {suggested.message}")
        return ExecutionOutcome(False, "load", suggested.message, suggested.payload)
    mapping = suggested.payload.get("mapping")
    if not isinstance(mapping, dict):
        return ExecutionOutcome(False, "load", "No se obtuvo mapping.", suggested.payload)
    emit_progress(on_progress, f"[Proyecto] Escribiendo project.yaml…")
    sources = [{"id": "network_db", "uri": uri, "kind": "database"}]
    project_path = _write_loaded_project(
        run_dir=run_dir,
        sources=sources,
        mapping=mapping,
        name="database",
    )
    if mapping.get("buses") is None:
        mapping_path = run_dir / "config" / "mapping.yaml"
        payload = {
            "source": uri,
            "project": str(project_path),
            "mapping_path": str(mapping_path),
            "schema": inspect.payload,
            "mapping": mapping,
        }
        return ExecutionOutcome(
            False,
            "load",
            "Inspección y mapping listos, pero no hay barras mapeadas. "
            f"Revise {mapping_path} y complete id, tensión y conectividad "
            "antes de generar DGS. El mapping es una propuesta, no un DGS.",
            payload,
        )
    emit_progress(on_progress, "[Conversión] Iniciando pipeline integral → DGS…")
    converted = _execute_project(project_path, on_progress=on_progress)
    payload = {
        "source": uri,
        "project": str(project_path),
        "schema": inspect.payload,
        "mapping": mapping,
        "conversion": converted.payload,
    }
    if not converted.success:
        emit_progress(on_progress, f"ERROR conversión: {converted.message}")
        return ExecutionOutcome(
            False,
            "load",
            f"Inspección y mapping listos, pero la conversión falló: {converted.message}",
            payload,
        )
    emit_progress(on_progress, f"=== Fin OK: {converted.message} ===")
    return ExecutionOutcome(True, "load", converted.message, payload)


def execute_loaded_file(loaded: LoadedFile, output: Path | None = None) -> ExecutionOutcome:
    if loaded.kind is LoadedFileKind.PROJECT:
        return _execute_project(loaded.path)
    if loaded.kind is LoadedFileKind.INPUT:
        paths = loaded.members or (loaded.path,)
        return _execute_inspect_inputs(paths, output)
    if loaded.kind is LoadedFileKind.DGS_TEMPLATE:
        return _execute_inspect_dgs(loaded.path, output)
    return ExecutionOutcome(
        False,
        "unsupported",
        loaded.detail,
        {"path": str(loaded.path)},
    )


def suggest_mapping_for_loaded(
    loaded: LoadedFile,
    output: Path | None = None,
    *,
    sample_rows: int | None = None,
    use_llm: bool = False,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    """Propose mapping YAML from a loaded input or project. Does not write DGS."""

    if loaded.kind is LoadedFileKind.UNSUPPORTED:
        return ExecutionOutcome(False, "suggest-mapping", loaded.detail, {"path": str(loaded.path)})
    if loaded.kind is LoadedFileKind.DGS_TEMPLATE:
        return ExecutionOutcome(
            False,
            "suggest-mapping",
            "Una plantilla DGS no es una fuente de mapping. Cargue tablas GIS o un project.yaml.",
            {"path": str(loaded.path)},
        )
    emit_progress(on_progress, "[Mapping] Analizando esquema para propuesta…")
    budget = sample_rows if sample_rows is not None else env_sample_rows()
    try:
        if loaded.kind is LoadedFileKind.PROJECT:
            project = load_project_config(loaded.path)
            schema = discover_schema(
                _read_project_inputs(project, sample_rows=budget),
                sample_rows=budget,
            )
        else:
            paths = loaded.members or (loaded.path,)
            schema = discover_schema(
                _read_input_paths(paths, sample_rows=budget),
                sample_rows=budget,
            )
        suggestion = suggest_mapping(schema, use_llm=use_llm)
    except (InputError, UnsupportedInputError, OSError, ValueError) as exc:
        emit_progress(on_progress, f"ERROR mapping: {exc}")
        return ExecutionOutcome(
            False,
            "suggest-mapping",
            f"No se pudo proponer mapping: {exc}",
            {"path": str(loaded.path)},
        )
    mapping = mapping_to_yaml_payload(suggestion.mapping)
    for layer in ("buses", "lines", "loads", "sources", "transformers"):
        if layer in mapping and isinstance(mapping[layer], dict):
            emit_progress(
                on_progress,
                f"[Mapping] {layer}: tabla {mapping[layer].get('source', '?')}",
            )
    emit_progress(on_progress, "[Mapping] Propuesta completada.")
    return _outcome_from_suggestion(suggestion, output)


def suggest_mapping_for_uri(
    uri: str,
    output: Path | None = None,
    *,
    kind: InputKind = InputKind.AUTO,
    sample_rows: int | None = None,
    use_llm: bool = False,
) -> ExecutionOutcome:
    budget = sample_rows if sample_rows is not None else env_sample_rows()
    try:
        dataset = InputReaderFactory.create(
            uri,
            kind=kind,
            source_id="source",
            options=_reader_options(budget),
        ).read()
        schema = discover_schema(dataset, sample_rows=budget)
        suggestion = suggest_mapping(schema, use_llm=use_llm)
    except (InputError, UnsupportedInputError, OSError, ValueError) as exc:
        return ExecutionOutcome(
            False,
            "suggest-mapping",
            f"No se pudo proponer mapping: {exc}",
            {"uri": uri},
        )
    return _outcome_from_suggestion(suggestion, output)


def _outcome_from_suggestion(
    suggestion: MappingSuggestion, output: Path | None
) -> ExecutionOutcome:
    mapping_payload = mapping_to_yaml_payload(suggestion.mapping)
    report_payload = {**suggestion.report, "pareto": list(suggestion.pareto)}
    written: dict[str, str] = {}
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(mapping_payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        report_path = output.with_name(f"{output.stem}_report.yaml")
        report_path.write_text(
            yaml.safe_dump(report_payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        written = {"written_to": str(output), "report_to": str(report_path)}
    mapped = [
        name
        for name in (
            "buses",
            "lines",
            "loads",
            "sources",
            "transformers",
            "switches",
            "generators",
            "substations",
        )
        if getattr(suggestion.mapping, name) is not None
    ]
    warnings = suggestion.report.get("warnings") or []
    warning_text = (" " + " ".join(warnings)) if warnings else ""
    return ExecutionOutcome(
        True,
        "suggest-mapping",
        "Mapping propuesto (NSGA-II + TOPSIS). "
        f"Entidades: {', '.join(mapped) or '(ninguna)'}. "
        "Revise el YAML y úselo en project.yaml; la conversión sigue el pipeline "
        f"NetworkModel → validación → DGS.{warning_text}",
        {
            "mapping": mapping_payload,
            "report": suggestion.report,
            "pareto_size": suggestion.report.get("pareto_size"),
            **written,
        },
    )


def classify_paths(
    paths: tuple[Path, ...] | list[Path],
    *,
    display_path: Path | None = None,
) -> LoadedFile:
    """Classify an explicit multi-file data bundle (e.g. RED + CARGA + equipo TXT)."""

    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            resolved.append(path)
    files = tuple(dict.fromkeys(resolved))
    if not files:
        anchor = display_path.expanduser().resolve() if display_path else Path(".")
        programmed = ", ".join(sorted(programmed_file_suffixes()))
        return LoadedFile(
            anchor,
            LoadedFileKind.UNSUPPORTED,
            "Sin archivos de datos",
            f"No hay archivos con las extensiones programadas: {programmed}.",
        )
    if len(files) == 1:
        return classify_file(files[0])

    detections: list[dict[str, Any]] = []
    usable: list[Path] = []
    for file_path in files:
        try:
            kind = detect_input_kind(file_path)
            detections.append(
                {
                    "path": str(file_path),
                    "detected_kind": kind.value,
                    "status": "ok",
                }
            )
            usable.append(file_path)
        except UnsupportedInputError as exc:
            if is_cymdist_import_config(file_path):
                detections.append(
                    {
                        "path": str(file_path),
                        "detected_kind": "cymdist_import_config",
                        "status": "companion",
                        "detail": str(exc),
                    }
                )
                usable.append(file_path)
            else:
                detections.append(
                    {
                        "path": str(file_path),
                        "detected_kind": None,
                        "status": "unsupported",
                        "detail": str(exc),
                    }
                )

    members = tuple(usable)
    if not members:
        anchor = display_path.expanduser().resolve() if display_path else files[0].parent
        return LoadedFile(
            anchor,
            LoadedFileKind.UNSUPPORTED,
            "Paquete no soportado",
            _bundle_detail(files, detections),
            detections=tuple(detections),
        )

    parents = {path.parent for path in members}
    if display_path is not None:
        anchor = display_path.expanduser().resolve()
    elif len(parents) == 1:
        anchor = next(iter(parents))
    else:
        anchor = members[0].parent

    label_prefix = "Carpeta" if display_path is not None and Path(display_path).is_dir() else "Paquete"
    return LoadedFile(
        anchor,
        LoadedFileKind.INPUT,
        f"{label_prefix}: {len(members)} archivo(s)",
        _bundle_detail(files, detections),
        members=members,
        detections=tuple(detections),
    )


def _classify_directory(path: Path) -> LoadedFile:
    if path.suffix.lower() == ".gdb":
        return LoadedFile(
            path,
            LoadedFileKind.INPUT,
            "Datos de entrada (vector)",
            "File Geodatabase detectada. Ejecutar inspecciona capas.",
            members=(path,),
        )
    project_yaml = path / "project.yaml"
    if project_yaml.is_file():
        return _classify_yaml(project_yaml)

    files = iter_detectable_paths(path, recursive=False)
    if not files:
        files = iter_detectable_paths(path, recursive=True)
    if not files:
        programmed = ", ".join(sorted(programmed_file_suffixes()))
        return LoadedFile(
            path,
            LoadedFileKind.UNSUPPORTED,
            "Carpeta sin datos detectables",
            f"No hay archivos con las extensiones programadas: {programmed}.",
        )
    return classify_paths(files, display_path=path)


def _bundle_detail(
    files: tuple[Path, ...] | list[Path],
    detections: list[dict[str, Any]],
) -> str:
    lines = ["Archivos detectados con el detector del conversor:"]
    lines.extend(
        f"- {file_path.name} [{row.get('detected_kind', '?')}]"
        for file_path, row in zip(files, detections, strict=False)
    )
    data_paths = _bundle_data_paths(tuple(files))
    if len(data_paths) > 1:
        lines.append("")
        lines.append("Análisis de paquete (mismo sistema eléctrico):")
        lines.append(_format_bundle_summary(assess_input_bundle(data_paths)))
    return "\n".join(lines)


def _classify_yaml(path: Path) -> LoadedFile:
    try:
        project = load_project_config(path)
    except (ValidationError, yaml.YAMLError, OSError, TypeError, ValueError) as exc:
        return LoadedFile(
            path,
            LoadedFileKind.UNSUPPORTED,
            "YAML no ejecutable",
            "El YAML no es un project.yaml de conversión. "
            f"Detalle: {exc}",
        )
    detections = detect_project_sources(project)
    lines = []
    for row in detections:
        status = row["status"]
        kind = row.get("detected_kind") or row["configured_kind"]
        lines.append(f"- {row['id']} [{kind}] {status}: {row['uri']}")
    missing = sum(1 for row in detections if row["status"] != "ok")
    extra = ""
    if missing:
        extra = f"\nAtención: {missing} fuente(s) no están listas."
    return LoadedFile(
        path,
        LoadedFileKind.PROJECT,
        f"Proyecto: {project.name}",
        "Fuentes del proyecto detectadas como está programado el conversor:\n"
        + "\n".join(lines)
        + extra
        + "\nEjecutar genera el DGS validado.",
        detections=detections,
    )


def _looks_like_dgs_template(path: Path) -> bool:
    try:
        report = inspect_excel_template(path)
    except (DgsError, OSError, ValueError):
        return False
    names = {sheet.sheet for sheet in report.sheets}
    return "General" in names and "ElmNet" in names


def _execute_project(
    path: Path,
    *,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    try:
        emit_progress(on_progress, f"[Proyecto] Cargando {path}…")
        project = load_project_config(path)
        detections = detect_project_sources(project)
        for row in detections:
            emit_progress(
                on_progress,
                f"  fuente {row['id']}: {row.get('detected_kind') or row['configured_kind']} "
                f"({row['status']}) → {row['uri']}",
            )
        readiness_error = _project_sources_readiness_error(detections)
        if readiness_error is not None:
            emit_progress(on_progress, f"ERROR: {readiness_error}")
            return ExecutionOutcome(
                False,
                "convert",
                readiness_error,
                {
                    "path": str(path),
                    "detected_sources": [dict(row) for row in detections],
                },
            )
        result = run_conversion(project, on_progress=on_progress)
    except Exception as exc:
        emit_progress(on_progress, f"ERROR: {type(exc).__name__}: {exc}")
        return ExecutionOutcome(
            False,
            "convert",
            f"La conversión falló: {type(exc).__name__}: {exc}",
            {"path": str(path)},
        )
    payload = result.as_dict()
    payload["detected_sources"] = [dict(row) for row in detections]
    message = _conversion_message(result)
    emit_progress(on_progress, message)
    return ExecutionOutcome(
        True,
        "convert",
        message,
        payload,
    )


def _reader_options(sample_rows: int | None) -> dict[str, Any]:
    options: dict[str, Any] = {"copy_frame": False, "compact": True}
    if sample_rows is not None and sample_rows > 0:
        options["sample_rows"] = int(sample_rows)
    return options


def _read_input_paths(paths: tuple[Path, ...], *, sample_rows: int | None) -> Any:
    datasets = [
        InputReaderFactory.create(
            str(path),
            kind=InputKind.AUTO,
            source_id=path.stem,
            options=_reader_options(sample_rows),
        ).read()
        for path in _bundle_data_paths(paths)
    ]
    return enrich_cymdist_tables(
        merge_datasets(datasets, on_conflict="overwrite")
    )


def _read_project_inputs(project: ResolvedProjectConfig, *, sample_rows: int | None) -> Any:
    datasets = []
    for source in project.inputs.sources:
        options = dict(source.options)
        options.update(_reader_options(sample_rows))
        datasets.append(
            InputReaderFactory.create(
                source.resolved_uri(project.base_dir),
                kind=InputKind(source.kind),
                source_id=source.id,
                options=options,
            ).read()
        )
    return enrich_cymdist_tables(
        merge_datasets(datasets, on_conflict=project.inputs.on_conflict)
    )


def _execute_inspect_inputs(
    paths: tuple[Path, ...],
    output: Path | None,
    *,
    sample_rows: int | None = None,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    budget = sample_rows if sample_rows is not None else env_sample_rows()
    for path in _bundle_data_paths(paths):
        emit_progress(on_progress, f"  leyendo {path.name}…")
    try:
        schema = discover_schema(
            _read_input_paths(paths, sample_rows=budget),
            sample_rows=budget,
        )
    except (InputError, UnsupportedInputError, OSError, ValueError) as exc:
        return ExecutionOutcome(
            False,
            "inspect-input",
            f"No se pudo inspeccionar la entrada: {exc}",
            {"paths": [str(path) for path in paths]},
        )
    payload: dict[str, Any] = schema.as_dict()
    payload["detected_files"] = [str(path) for path in paths]
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        payload = {**payload, "written_to": str(output)}
    tables = ", ".join(table.name for table in schema.tables) or "(ninguna)"
    return ExecutionOutcome(
        True,
        "inspect-input",
        f"Detectados {len(paths)} archivo(s). Tablas: {tables}. "
        "Para generar DGS use un project.yaml con mapping.",
        payload,
    )


def _execute_inspect_uri(
    uri: str,
    *,
    output: Path | None,
    sample_rows: int | None = None,
) -> ExecutionOutcome:
    from gis2dgs.input.mssql_ensure import prepare_mssql_environment

    prepare_mssql_environment()
    budget = sample_rows if sample_rows is not None else env_sample_rows()
    try:
        dataset = InputReaderFactory.create(
            uri,
            kind=InputKind.AUTO,
            source_id="source",
            options=_reader_options(budget),
        ).read()
        schema = discover_schema(dataset, sample_rows=budget)
    except (InputError, UnsupportedInputError, OSError, ValueError) as exc:
        return ExecutionOutcome(
            False,
            "inspect-input",
            f"No se pudo inspeccionar la entrada: {exc}",
            {"uri": uri},
        )
    payload: dict[str, Any] = schema.as_dict()
    payload["detected_uri"] = uri
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        payload = {**payload, "written_to": str(output)}
    tables = ", ".join(table.name for table in schema.tables) or "(ninguna)"
    return ExecutionOutcome(
        True,
        "inspect-input",
        f"Detectada fuente de base de datos. Tablas: {tables}.",
        payload,
    )


def _project_sources_readiness_error(
    detections: tuple[dict[str, Any], ...],
) -> str | None:
    not_ready = [row for row in detections if row.get("status") != "ok"]
    if not not_ready:
        return None
    details = "; ".join(
        f"{row.get('id')}: {row.get('status')} ({row.get('uri')})" for row in not_ready
    )
    return (
        "El project.yaml no es ejecutable porque hay fuentes sin conectividad o no "
        f"soportadas: {details}. Corrija rutas/conexiones y vuelva a ejecutar."
    )


def _execute_inspect_dgs(
    path: Path,
    output: Path | None,
    *,
    on_progress: ProgressReporter = None,
) -> ExecutionOutcome:
    emit_progress(on_progress, f"[DGS] Inspeccionando plantilla {path}…")
    try:
        report = inspect_excel_template(path)
    except DgsError as exc:
        return ExecutionOutcome(
            False,
            "inspect-template",
            f"No se pudo inspeccionar el DGS: {exc}",
            {"path": str(path)},
        )
    payload = report.as_dict()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        payload = {**payload, "written_to": str(output)}
    sheets = ", ".join(sheet.sheet for sheet in report.sheets)
    version = report.dgs_format_version or "sin versión declarada"
    return ExecutionOutcome(
        True,
        "inspect-template",
        f"Plantilla DGS revisión {version}. Hojas: {sheets}.",
        payload,
    )


def _conversion_message(result: ConversionResult) -> str:
    network = result.as_dict()["network"]
    assert isinstance(network, dict)
    return (
        "Conversión completada. "
        f"DGS: {result.output_dgs}. "
        f"Barras={network['buses']}, líneas={network['lines']}, "
        f"cargas={network['loads']}, fuentes={network['sources']}."
    )
