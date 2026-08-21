from gis2dgs.domain.network import NetworkModel

from .result import Severity, ValidationCategory, ValidationIssue


def validate_references(network: NetworkModel) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for line in network.lines.values():
        for role, bus_id in (("from_bus", line.from_bus), ("to_bus", line.to_bus)):
            if not network.has_bus(bus_id):
                issues.append(
                    ValidationIssue(
                        code="NET001",
                        severity=Severity.ERROR,
                        category=ValidationCategory.STRUCTURE,
                        object_type="Line",
                        message=f"Line {line.id}: {role} {bus_id} does not exist.",
                        object_id=str(line.id),
                    )
                )

    for transformer in network.transformers.values():
        for role, bus_id in (
            ("hv_bus", transformer.hv_bus),
            ("lv_bus", transformer.lv_bus),
        ):
            if not network.has_bus(bus_id):
                issues.append(
                    ValidationIssue(
                        code="NET002",
                        severity=Severity.ERROR,
                        category=ValidationCategory.STRUCTURE,
                        object_type="Transformer",
                        message=(
                            f"Transformer {transformer.id}: {role} {bus_id} does not exist."
                        ),
                        object_id=str(transformer.id),
                    )
                )

    for switch in network.switches.values():
        for role, bus_id in (("from_bus", switch.from_bus), ("to_bus", switch.to_bus)):
            if not network.has_bus(bus_id):
                issues.append(
                    ValidationIssue(
                        code="NET003",
                        severity=Severity.ERROR,
                        category=ValidationCategory.STRUCTURE,
                        object_type="Switch",
                        message=f"Switch {switch.id}: {role} {bus_id} does not exist.",
                        object_id=str(switch.id),
                    )
                )

    for load in network.loads.values():
        if not network.has_bus(load.bus_id):
            issues.append(
                ValidationIssue(
                    code="NET004",
                    severity=Severity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    object_type="Load",
                    message=f"Load {load.id}: bus {load.bus_id} does not exist.",
                    object_id=str(load.id),
                )
            )

    for source in network.sources.values():
        if not network.has_bus(source.bus_id):
            issues.append(
                ValidationIssue(
                    code="NET005",
                    severity=Severity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    object_type="Source",
                    message=f"Source {source.id}: bus {source.bus_id} does not exist.",
                    object_id=str(source.id),
                )
            )

    for generator in network.generators.values():
        if not network.has_bus(generator.bus_id):
            issues.append(
                ValidationIssue(
                    code="NET007",
                    severity=Severity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    object_type="Generator",
                    message=(
                        f"Generator {generator.id}: bus {generator.bus_id} does not exist."
                    ),
                    object_id=str(generator.id),
                )
            )

    for bus in network.buses.values():
        if bus.substation_id is not None and bus.substation_id not in network.substations:
            issues.append(
                ValidationIssue(
                    code="NET008",
                    severity=Severity.ERROR,
                    category=ValidationCategory.STRUCTURE,
                    object_type="Bus",
                    object_id=str(bus.id),
                    message=(
                        f"Bus {bus.id}: substation {bus.substation_id} does not exist."
                    ),
                )
            )
    return issues


def validate_minimum_structure(network: NetworkModel) -> list[ValidationIssue]:
    if network.buses:
        return []
    return [
        ValidationIssue(
            code="NET006",
            severity=Severity.ERROR,
            category=ValidationCategory.STRUCTURE,
            object_type="NetworkModel",
            message="The network does not contain any buses.",
        )
    ]
