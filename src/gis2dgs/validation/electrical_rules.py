from math import isclose

from gis2dgs.domain.network import NetworkModel

from .policy import ValidationPolicy
from .result import Severity, ValidationCategory, ValidationIssue

VOLTAGE_TOLERANCE_KV = 1e-6


def _same_voltage(first: float, second: float, tolerance_kv: float) -> bool:
    return isclose(first, second, rel_tol=0.0, abs_tol=tolerance_kv)


def validate_voltage_consistency(
    network: NetworkModel,
    *,
    tolerance_kv: float = VOLTAGE_TOLERANCE_KV,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for line in network.lines.values():
        for bus_id in (line.from_bus, line.to_bus):
            bus = network.buses.get(bus_id)
            if bus is not None and not _same_voltage(
                bus.nominal_voltage_kv,
                line.nominal_voltage_kv,
                tolerance_kv,
            ):
                issues.append(
                    ValidationIssue(
                        code="ELE001",
                        severity=Severity.ERROR,
                        category=ValidationCategory.ELECTRICAL,
                        object_type="Line",
                        object_id=str(line.id),
                        message=(
                            f"Line {line.id}: voltage {line.nominal_voltage_kv} kV "
                            f"does not match bus {bus.id} voltage "
                            f"{bus.nominal_voltage_kv} kV."
                        ),
                    )
                )

    for source in network.sources.values():
        bus = network.buses.get(source.bus_id)
        if bus is not None and not _same_voltage(
            bus.nominal_voltage_kv,
            source.nominal_voltage_kv,
            tolerance_kv,
        ):
            issues.append(
                ValidationIssue(
                    code="ELE002",
                    severity=Severity.ERROR,
                    category=ValidationCategory.ELECTRICAL,
                    object_type="Source",
                    object_id=str(source.id),
                    message=(
                        f"Source {source.id}: voltage {source.nominal_voltage_kv} kV "
                        f"does not match bus {bus.id} voltage {bus.nominal_voltage_kv} kV."
                    ),
                )
            )

    for transformer in network.transformers.values():
        hv_bus = network.buses.get(transformer.hv_bus)
        lv_bus = network.buses.get(transformer.lv_bus)

        if hv_bus is not None and not _same_voltage(
            hv_bus.nominal_voltage_kv,
            transformer.hv_voltage_kv,
            tolerance_kv,
        ):
            issues.append(
                ValidationIssue(
                    code="ELE003",
                    severity=Severity.ERROR,
                    category=ValidationCategory.ELECTRICAL,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: HV voltage "
                        f"{transformer.hv_voltage_kv} kV does not match bus "
                        f"{hv_bus.id} voltage {hv_bus.nominal_voltage_kv} kV."
                    ),
                )
            )

        if lv_bus is not None and not _same_voltage(
            lv_bus.nominal_voltage_kv,
            transformer.lv_voltage_kv,
            tolerance_kv,
        ):
            issues.append(
                ValidationIssue(
                    code="ELE004",
                    severity=Severity.ERROR,
                    category=ValidationCategory.ELECTRICAL,
                    object_type="Transformer",
                    object_id=str(transformer.id),
                    message=(
                        f"Transformer {transformer.id}: LV voltage "
                        f"{transformer.lv_voltage_kv} kV does not match bus "
                        f"{lv_bus.id} voltage {lv_bus.nominal_voltage_kv} kV."
                    ),
                )
            )

    for switch in network.switches.values():
        from_bus = network.buses.get(switch.from_bus)
        to_bus = network.buses.get(switch.to_bus)
        if (
            from_bus is not None
            and to_bus is not None
            and not _same_voltage(
                from_bus.nominal_voltage_kv,
                to_bus.nominal_voltage_kv,
                tolerance_kv,
            )
        ):
            issues.append(
                ValidationIssue(
                    code="ELE005",
                    severity=Severity.ERROR,
                    category=ValidationCategory.ELECTRICAL,
                    object_type="Switch",
                    object_id=str(switch.id),
                    message=(
                        f"Switch {switch.id}: buses {from_bus.id} and {to_bus.id} "
                        "have different nominal voltages."
                    ),
                )
            )

    return issues


def validate_electrical_consistency(
    network: NetworkModel,
    policy: ValidationPolicy,
) -> list[ValidationIssue]:
    return validate_voltage_consistency(
        network,
        tolerance_kv=policy.voltage_tolerance_kv,
    )
