from gis2dgs.domain.network import NetworkModel
from gis2dgs.topology import TopologyReport

from .policy import ValidationPolicy
from .result import Severity, ValidationCategory, ValidationIssue


def validate_readiness(
    network: NetworkModel,
    topology: TopologyReport | None,
    policy: ValidationPolicy,
) -> list[ValidationIssue]:
    """Validate requirements that are profile-dependent rather than universally invalid."""
    issues: list[ValidationIssue] = []

    if policy.require_in_service_source:
        active_sources = [source for source in network.sources.values() if source.in_service]
        if not active_sources:
            issues.append(
                ValidationIssue(
                    code="RDY001",
                    severity=Severity.ERROR,
                    category=ValidationCategory.READINESS,
                    object_type="NetworkModel",
                    message=(
                        "The active validation profile requires at least one in-service source."
                    ),
                )
            )

    if policy.require_line_type:
        for line in network.lines.values():
            if line.in_service and not (line.type_id and line.type_id.strip()):
                issues.append(
                    ValidationIssue(
                        code="RDY002",
                        severity=Severity.ERROR,
                        category=ValidationCategory.READINESS,
                        object_type="Line",
                        object_id=str(line.id),
                        message=(
                            f"Line {line.id}: an electrical type reference is required by "
                            "the active validation profile."
                        ),
                    )
                )

    if policy.require_transformer_type:
        for transformer in network.transformers.values():
            if transformer.in_service and not (
                transformer.type_id and transformer.type_id.strip()
            ):
                issues.append(
                    ValidationIssue(
                        code="RDY003",
                        severity=Severity.ERROR,
                        category=ValidationCategory.READINESS,
                        object_type="Transformer",
                        object_id=str(transformer.id),
                        message=(
                            f"Transformer {transformer.id}: an electrical type reference is "
                            "required by the active validation profile."
                        ),
                    )
                )

    if topology is None:
        return issues

    if policy.require_all_buses_energized:
        for bus_id in sorted(topology.deenergized_buses):
            issues.append(
                ValidationIssue(
                    code="RDY004",
                    severity=Severity.ERROR,
                    category=ValidationCategory.READINESS,
                    object_type="Bus",
                    object_id=bus_id,
                    message=(
                        f"Bus {bus_id} must be reachable from an in-service source for "
                        "the active validation profile."
                    ),
                )
            )

    if policy.require_radial_network and not topology.is_radial:
        issues.append(
            ValidationIssue(
                code="RDY005",
                severity=Severity.ERROR,
                category=ValidationCategory.READINESS,
                object_type="NetworkModel",
                message="The active validation profile requires an energized radial network.",
            )
        )

    if policy.forbid_feeder_overlaps:
        for overlap in topology.feeder_overlaps:
            issues.append(
                ValidationIssue(
                    code="RDY006",
                    severity=Severity.ERROR,
                    category=ValidationCategory.READINESS,
                    object_type="Bus",
                    object_id=overlap.bus_id,
                    message=(
                        f"Bus {overlap.bus_id} belongs to multiple feeder traces, which is "
                        "forbidden by the active validation profile."
                    ),
                )
            )

    return issues
