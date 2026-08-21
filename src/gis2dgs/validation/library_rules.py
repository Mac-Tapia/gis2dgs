from __future__ import annotations

from math import isclose

from gis2dgs.domain.network import NetworkModel
from gis2dgs.electrical import ElectricalLibrary

from .policy import ValidationPolicy
from .result import Severity, ValidationCategory, ValidationIssue


def validate_electrical_library(
    network: NetworkModel,
    library: ElectricalLibrary | None,
    policy: ValidationPolicy,
) -> list[ValidationIssue]:
    """Resolve type references and verify instance/type electrical consistency."""
    issues: list[ValidationIssue] = []

    if library is None:
        if policy.require_electrical_library:
            issues.append(
                ValidationIssue(
                    code="LIB001",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="ElectricalLibrary",
                    message=(
                        "The active validation profile requires an electrical type library."
                    ),
                )
            )
        return issues

    unknown_type_severity = (
        Severity.ERROR
        if policy.require_electrical_library or policy.require_line_type
        else Severity.WARNING
    )

    for line in network.lines.values():
        if not line.in_service or not line.type_id:
            continue
        line_type = library.find_line_type(line.type_id)
        if line_type is None:
            issues.append(
                ValidationIssue(
                    code="LIB101",
                    severity=unknown_type_severity,
                    category=ValidationCategory.LIBRARY,
                    object_type="Line",
                    object_id=str(line.id),
                    message=(
                        f"Line {line.id}: type_id {line.type_id!r} does not exist in "
                        "the electrical line-type library."
                    ),
                )
            )
            continue

        if abs(line.nominal_voltage_kv - line_type.nominal_voltage_kv) > (
            policy.voltage_tolerance_kv
        ):
            issues.append(
                ValidationIssue(
                    code="LIB102",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Line",
                    object_id=str(line.id),
                    message=(
                        f"Line {line.id}: nominal voltage {line.nominal_voltage_kv:g} kV "
                        f"does not match type {line_type.id} rated voltage "
                        f"{line_type.nominal_voltage_kv:g} kV."
                    ),
                )
            )

        if policy.require_zero_sequence_data and not line_type.has_zero_sequence_data:
            issues.append(
                ValidationIssue(
                    code="LIB103",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Line",
                    object_id=str(line.id),
                    message=(
                        f"Line {line.id}: type {line_type.id} lacks complete zero-sequence "
                        "parameters required by the active profile."
                    ),
                )
            )

    for transformer in network.transformers.values():
        if not transformer.in_service or not transformer.type_id:
            continue
        transformer_type = library.find_transformer_type(transformer.type_id)
        if transformer_type is None:
            issues.append(
                ValidationIssue(
                    code="LIB201",
                    severity=unknown_type_severity,
                    category=ValidationCategory.LIBRARY,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: type_id {transformer.type_id!r} "
                        "does not exist in the transformer-type library."
                    ),
                )
            )
            continue

        if abs(transformer.hv_voltage_kv - transformer_type.hv_voltage_kv) > (
            policy.voltage_tolerance_kv
        ):
            issues.append(
                ValidationIssue(
                    code="LIB202",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: HV voltage "
                        f"{transformer.hv_voltage_kv:g} kV does not match type "
                        f"{transformer_type.id} HV voltage "
                        f"{transformer_type.hv_voltage_kv:g} kV."
                    ),
                )
            )

        if abs(transformer.lv_voltage_kv - transformer_type.lv_voltage_kv) > (
            policy.voltage_tolerance_kv
        ):
            issues.append(
                ValidationIssue(
                    code="LIB203",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: LV voltage "
                        f"{transformer.lv_voltage_kv:g} kV does not match type "
                        f"{transformer_type.id} LV voltage "
                        f"{transformer_type.lv_voltage_kv:g} kV."
                    ),
                )
            )

        if not isclose(
            transformer.rated_power_mva,
            transformer_type.rated_power_mva,
            rel_tol=policy.transformer_power_relative_tolerance,
            abs_tol=0.0,
        ):
            issues.append(
                ValidationIssue(
                    code="LIB204",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: rated power "
                        f"{transformer.rated_power_mva:g} MVA does not match type "
                        f"{transformer_type.id} rated power "
                        f"{transformer_type.rated_power_mva:g} MVA."
                    ),
                )
            )

        if policy.require_zero_sequence_data and not transformer_type.has_zero_sequence_data:
            issues.append(
                ValidationIssue(
                    code="LIB205",
                    severity=Severity.ERROR,
                    category=ValidationCategory.LIBRARY,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: type {transformer_type.id} lacks "
                        "zero-sequence impedance parameters required by the active profile."
                    ),
                )
            )

    return issues
