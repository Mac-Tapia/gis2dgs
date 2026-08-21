from math import isfinite

from gis2dgs.domain.network import NetworkModel

from .policy import ValidationPolicy
from .result import Severity, ValidationCategory, ValidationIssue


def _finite_issue(
    *,
    code: str,
    object_type: str,
    object_id: object,
    field_name: str,
    value: float,
) -> ValidationIssue | None:
    if isfinite(value):
        return None
    return ValidationIssue(
        code=code,
        severity=Severity.ERROR,
        category=ValidationCategory.DATA_QUALITY,
        object_type=object_type,
        object_id=str(object_id),
        message=(
            f"{object_type} {object_id}: field {field_name} must be finite; "
            f"received {value!r}."
        ),
    )


def _coordinate_issues(
    *,
    object_type: str,
    object_id: object,
    x: float | None,
    y: float | None,
    required: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if (x is None) != (y is None):
        issues.append(
            ValidationIssue(
                code="DAT002",
                severity=Severity.ERROR,
                category=ValidationCategory.DATA_QUALITY,
                object_type=object_type,
                object_id=str(object_id),
                message=(
                    f"{object_type} {object_id}: coordinates must contain both x and y "
                    "or neither."
                ),
            )
        )
        return issues

    if x is None and y is None:
        if required:
            issues.append(
                ValidationIssue(
                    code="DAT003",
                    severity=Severity.ERROR,
                    category=ValidationCategory.DATA_QUALITY,
                    object_type=object_type,
                    object_id=str(object_id),
                    message=(
                        f"{object_type} {object_id}: geographic coordinates are required "
                        "by the active validation profile."
                    ),
                )
            )
        return issues

    assert x is not None and y is not None
    for field_name, value in (("x", x), ("y", y)):
        issue = _finite_issue(
            code="DAT001",
            object_type=object_type,
            object_id=object_id,
            field_name=field_name,
            value=value,
        )
        if issue is not None:
            issues.append(issue)
    return issues


def validate_data_quality(
    network: NetworkModel,
    policy: ValidationPolicy,
) -> list[ValidationIssue]:
    """Validate canonical values without depending on GIS implementation details."""
    issues: list[ValidationIssue] = []

    for bus in network.buses.values():
        issue = _finite_issue(
            code="DAT001",
            object_type="Bus",
            object_id=bus.id,
            field_name="nominal_voltage_kv",
            value=bus.nominal_voltage_kv,
        )
        if issue is not None:
            issues.append(issue)
        issues.extend(
            _coordinate_issues(
                object_type="Bus",
                object_id=bus.id,
                x=bus.x,
                y=bus.y,
                required=policy.require_geographic_coordinates,
            )
        )

    for substation in network.substations.values():
        issues.extend(
            _coordinate_issues(
                object_type="Substation",
                object_id=substation.id,
                x=substation.x,
                y=substation.y,
                required=policy.require_geographic_coordinates,
            )
        )

    for line in network.lines.values():
        for field_name, value in (
            ("length_km", line.length_km),
            ("nominal_voltage_kv", line.nominal_voltage_kv),
        ):
            issue = _finite_issue(
                code="DAT001",
                object_type="Line",
                object_id=line.id,
                field_name=field_name,
                value=value,
            )
            if issue is not None:
                issues.append(issue)

    for transformer in network.transformers.values():
        for field_name, value in (
            ("hv_voltage_kv", transformer.hv_voltage_kv),
            ("lv_voltage_kv", transformer.lv_voltage_kv),
            ("rated_power_mva", transformer.rated_power_mva),
        ):
            issue = _finite_issue(
                code="DAT001",
                object_type="Transformer",
                object_id=transformer.id,
                field_name=field_name,
                value=value,
            )
            if issue is not None:
                issues.append(issue)

    for load in network.loads.values():
        for field_name, value in (
            ("active_power_mw", load.active_power_mw),
            ("reactive_power_mvar", load.reactive_power_mvar),
        ):
            issue = _finite_issue(
                code="DAT001",
                object_type="Load",
                object_id=load.id,
                field_name=field_name,
                value=value,
            )
            if issue is not None:
                issues.append(issue)

    for generator in network.generators.values():
        for field_name, value in (
            ("active_power_mw", generator.active_power_mw),
            ("reactive_power_mvar", generator.reactive_power_mvar),
        ):
            issue = _finite_issue(
                code="DAT001",
                object_type="Generator",
                object_id=generator.id,
                field_name=field_name,
                value=value,
            )
            if issue is not None:
                issues.append(issue)

    for source in network.sources.values():
        issue = _finite_issue(
            code="DAT001",
            object_type="Source",
            object_id=source.id,
            field_name="nominal_voltage_kv",
            value=source.nominal_voltage_kv,
        )
        if issue is not None:
            issues.append(issue)

    return issues
