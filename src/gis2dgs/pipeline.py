from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from gis2dgs.config import (
    ResolvedProjectConfig,
    load_dgs_schema,
    load_electrical_library,
    load_mapping_config,
    load_powerfactory_mapping_policy,
    load_validation_policy,
)
from gis2dgs.dgs import DgsMapper, DgsWriter
from gis2dgs.gis.connectivity import reconstruct_mapped_line_endpoints
from gis2dgs.gis.coordinates import materialize_mapped_coordinates
from gis2dgs.gis.exceptions import GisConnectivityError, GisLayerNotFoundError
from gis2dgs.gis.hierarchical import prepare_hierarchical_connectivity
from gis2dgs.gis.mapping.domain_mapper import GisToDomainMapper
from gis2dgs.gis.voltage_lookup import detect_voltage_lookup
from gis2dgs.input import InputKind, InputReaderFactory, discover_schema, merge_datasets
from gis2dgs.input.cymdist_enrich import enrich_cymdist_tables
from gis2dgs.powerfactory import PowerFactoryMapper
from gis2dgs.validation import NetworkValidator, ValidationReportWriter

ProgressReporter = Callable[[str], None] | None


def emit_progress(reporter: ProgressReporter, message: str) -> None:
    if reporter is not None:
        reporter(message)


class ConversionFailedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConversionResult:
    output_dgs: Path
    validation_json: Path
    validation_csv: Path
    input_schema_report: Path
    input_tables: int
    buses: int
    lines: int
    transformers: int
    switches: int
    loads: int
    generators: int
    sources: int

    def as_dict(self) -> dict[str, object]:
        return {
            "output_dgs": str(self.output_dgs),
            "validation_json": str(self.validation_json),
            "validation_csv": str(self.validation_csv),
            "input_schema_report": str(self.input_schema_report),
            "input_tables": self.input_tables,
            "network": {
                "buses": self.buses,
                "lines": self.lines,
                "transformers": self.transformers,
                "switches": self.switches,
                "loads": self.loads,
                "generators": self.generators,
                "sources": self.sources,
            },
        }


def _load_inputs(
    project: ResolvedProjectConfig,
    *,
    on_progress: ProgressReporter = None,
):
    datasets = []
    for source in project.inputs.sources:
        uri = source.resolved_uri(project.base_dir)
        emit_progress(
            on_progress,
            f"[Entrada] Leyendo fuente {source.id!r} ({source.kind}) → {uri}",
        )
        reader = InputReaderFactory.create(
            uri,
            kind=InputKind(source.kind),
            source_id=source.id,
            options=source.options,
        )
        dataset = reader.read()
        emit_progress(
            on_progress,
            f"[Entrada] Fuente {source.id!r}: {len(dataset.tables)} tabla(s).",
        )
        datasets.append(dataset)
    merged = enrich_cymdist_tables(
        merge_datasets(datasets, on_conflict=project.inputs.on_conflict)
    )
    emit_progress(
        on_progress,
        f"[Entrada] Total combinado: {len(merged.tables)} tabla(s).",
    )
    return merged


def run_conversion(
    project: ResolvedProjectConfig,
    *,
    on_progress: ProgressReporter = None,
) -> ConversionResult:
    emit_progress(on_progress, "[1/8] Cargando fuentes de datos…")
    inputs = _load_inputs(project, on_progress=on_progress)
    emit_progress(on_progress, "[2/8] Descubriendo esquema de entrada…")
    discovered = discover_schema(inputs)
    project.schema_report.parent.mkdir(parents=True, exist_ok=True)
    project.schema_report.write_text(
        yaml.safe_dump(discovered.as_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    emit_progress(
        on_progress,
        f"[2/8] Esquema guardado: {len(discovered.tables)} tabla(s) → {project.schema_report}",
    )

    emit_progress(on_progress, "[3/8] Aplicando mapping y conectividad GIS…")
    mapping = load_mapping_config(project.mapping)
    gis_dataset = inputs.to_gis_dataset()
    if mapping.target_crs is not None:
        emit_progress(
            on_progress,
            f"[3/8] Reproyectando capas a {mapping.target_crs}…",
        )
        gis_dataset = gis_dataset.reprojected(mapping.target_crs)
    gis_dataset = _prepare_line_connectivity(
        gis_dataset,
        mapping,
        report_path=project.schema_report.with_name("connectivity.yaml"),
    )
    emit_progress(on_progress, "[4/8] Construyendo NetworkModel (dominio eléctrico)…")
    network = GisToDomainMapper(
        mapping,
        voltage_lookup=detect_voltage_lookup(gis_dataset),
    ).map(gis_dataset)
    summary = network.summary()
    emit_progress(
        on_progress,
        "[4/8] NetworkModel: "
        f"barras={summary['buses']}, líneas={summary['lines']}, "
        f"cargas={summary['loads']}, fuentes={summary['sources']}.",
    )
    emit_progress(on_progress, "[5/8] Validando red…")
    library = load_electrical_library(project.electrical_library)
    validation_policy = load_validation_policy(project.validation)
    validation = NetworkValidator(
        validation_policy,
        electrical_library=library,
    ).validate(network)
    ValidationReportWriter.write_json(validation, project.validation_json)
    ValidationReportWriter.write_csv(validation, project.validation_csv)
    emit_progress(
        on_progress,
        f"[5/8] Validación: válida={validation.is_valid}, "
        f"errores={validation.error_count}, avisos={validation.warning_count}. "
        f"Informe: {project.validation_json}",
    )
    if project.fail_on_validation_errors and not validation.is_valid:
        raise ConversionFailedError(
            f"Network validation failed with {validation.error_count} error(s). "
            f"See {project.validation_json}."
        )

    emit_progress(on_progress, "[6/8] Mapeando a modelo PowerFactory…")
    pf_policy = load_powerfactory_mapping_policy(project.powerfactory_mapping)
    pf_model = PowerFactoryMapper(pf_policy).map(network, library)
    emit_progress(on_progress, "[7/8] Generando documento DGS…")
    dgs_schema = load_dgs_schema(project.dgs_schema)
    dgs_document = DgsMapper(dgs_schema).map_powerfactory_model(pf_model)
    output = DgsWriter(dgs_schema).write(dgs_document, project.output_dgs)
    emit_progress(on_progress, f"[8/8] DGS escrito: {output}")

    return ConversionResult(
        output_dgs=output,
        validation_json=project.validation_json,
        validation_csv=project.validation_csv,
        input_schema_report=project.schema_report,
        input_tables=len(inputs.tables),
        buses=len(network.buses),
        lines=len(network.lines),
        transformers=len(network.transformers),
        switches=len(network.switches),
        loads=len(network.loads),
        generators=len(network.generators),
        sources=len(network.sources),
    )


def _prepare_line_connectivity(dataset, mapping, *, report_path: Path):
    if mapping.buses is None or mapping.lines is None:
        return dataset
    if (
        mapping.lines.source not in dataset.layers
        or mapping.buses.source not in dataset.layers
    ):
        return dataset

    dataset = materialize_mapped_coordinates(dataset, mapping)
    dataset, hierarchical_applied = prepare_hierarchical_connectivity(
        dataset,
        line_layer=mapping.lines.source,
        bus_layer=mapping.buses.source,
        line_mapping=mapping.lines,
        bus_mapping=mapping.buses,
    )

    bus_id = mapping.buses.fields.get("id")
    line_id = mapping.lines.fields.get("id")
    if not bus_id or not line_id:
        return dataset
    from_bus = mapping.lines.fields.setdefault("from_bus", "from_bus")
    to_bus = mapping.lines.fields.setdefault("to_bus", "to_bus")
    try:
        updated, proposal = reconstruct_mapped_line_endpoints(
            dataset,
            line_layer=mapping.lines.source,
            bus_layer=mapping.buses.source,
            line_id_field=line_id,
            bus_id_field=bus_id,
            from_bus_field=from_bus,
            to_bus_field=to_bus,
            tolerance_m=mapping.connectivity.tolerance_m,
            tie_tolerance_m=mapping.connectivity.tie_tolerance_m,
            apply_unambiguous=mapping.connectivity.apply_unambiguous,
        )
    except (GisConnectivityError, GisLayerNotFoundError, KeyError, ValueError, AttributeError):
        updated = dataset
        proposal = None
    else:
        dataset = updated

    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "hierarchical_applied": hierarchical_applied,
    }
    if proposal is not None:
        payload.update(
            {
                "resolved": proposal.resolved_count,
                "unresolved": proposal.unresolved_count,
                "suggestions": [
                    {
                        "line_id": item.line_id,
                        "endpoint": item.endpoint,
                        "current_bus_id": item.current_bus_id,
                        "resolved_bus_id": item.resolved_bus_id,
                        "candidates": [
                            {
                                "bus_id": candidate.bus_id,
                                "distance_m": candidate.distance_m,
                            }
                            for candidate in item.candidates
                        ],
                    }
                    for item in proposal.suggestions
                ],
            }
        )
    report_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return dataset


def _reconstruct_connectivity(dataset, mapping, *, report_path: Path):
    return _prepare_line_connectivity(dataset, mapping, report_path=report_path)
