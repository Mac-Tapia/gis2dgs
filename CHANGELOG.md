# Changelog

## 1.0.0 — universal audited release

### Added

- Universal input layer based on physical format/database connectivity rather than
  GIS product names.
- Excel, CSV/TSV, vector, Parquet, SQLite and SQLAlchemy database readers.
- Automatic input-kind detection, multi-source merge and schema discovery.
- Project-level conversion pipeline and executable CLI.
- Typed DGS header parser and DGS format-revision inspection.
- Real-reference integration hooks for `SALIDA_DGS.xlsx` and `M_ALIMENTAD.xlsx`.
- End-to-end minimal project and performance benchmark.
- Documentation for architecture, supported inputs, operation, security,
  acceptance and research basis.

### Changed

- DGS remains structurally driven and never selects a PowerFactory product version.
- `StaCubic` carries an explicit connection index; optional `StaSwitch` objects can
  be created at cubicles.
- Dataset merge implementation avoids repeated full-dataset copying.
- Vector I/O backend `pyogrio` is declared as a core dependency.

### Compatibility

- Legacy `gis/` adapters and Phase 0–8 public APIs are retained where practical.
- `DgsMappingProfile` remains an alias for `DgsSchema`.

## 0.8.1 — audited Phase 0–8 release

- Version-neutral DGS architecture using `DgsSchema`.
- Audited Phase 0–8 baseline.
