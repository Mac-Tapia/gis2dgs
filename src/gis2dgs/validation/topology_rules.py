from gis2dgs.domain.network import NetworkModel
from gis2dgs.topology import CycleKind, TopologyAnalyzer, TopologyReport

from .policy import ValidationPolicy
from .result import Severity, ValidationCategory, ValidationIssue


def validate_topology(
    network: NetworkModel,
    report: TopologyReport | None = None,
    policy: ValidationPolicy | None = None,
) -> list[ValidationIssue]:
    active_policy = policy or ValidationPolicy.standard()
    topology = report or TopologyAnalyzer().analyze(network)
    issues: list[ValidationIssue] = []

    degree_zero_buses = {
        bus_id
        for island in topology.islands
        if island.bus_count == 1 and island.edge_count == 0
        for bus_id in island.buses
    }
    for bus_id in sorted(degree_zero_buses):
        issues.append(
            ValidationIssue(
                code="TOP001",
                severity=Severity.WARNING,
                category=ValidationCategory.TOPOLOGY,
                object_type="Bus",
                object_id=bus_id,
                message=f"Bus {bus_id} is electrically isolated.",
            )
        )

    if network.sources:
        for bus_id in sorted(topology.deenergized_buses):
            issues.append(
                ValidationIssue(
                    code="TOP002",
                    severity=Severity.WARNING,
                    category=ValidationCategory.TOPOLOGY,
                    object_type="Bus",
                    object_id=bus_id,
                    message=f"Bus {bus_id} is not reachable from an in-service source.",
                )
            )

    for cycle in topology.cycles:
        if cycle.kind == CycleKind.SIMPLE:
            issues.append(
                ValidationIssue(
                    code="TOP003",
                    severity=Severity.WARNING,
                    category=ValidationCategory.TOPOLOGY,
                    object_type="Cycle",
                    object_id=cycle.cycle_id,
                    message=(
                        f"Cycle {cycle.cycle_id} forms a closed electrical loop through "
                        f"{len(cycle.buses)} buses."
                    ),
                )
            )
        else:
            issues.append(
                ValidationIssue(
                    code="TOP004",
                    severity=Severity.INFO,
                    category=ValidationCategory.TOPOLOGY,
                    object_type="Cycle",
                    object_id=cycle.cycle_id,
                    message=(
                        f"Cycle {cycle.cycle_id} represents parallel conductive elements "
                        "between the same buses."
                    ),
                )
            )

    for overlap in topology.feeder_overlaps:
        issues.append(
            ValidationIssue(
                code="TOP005",
                severity=Severity.WARNING,
                category=ValidationCategory.TOPOLOGY,
                object_type="Bus",
                object_id=overlap.bus_id,
                message=(
                    f"Bus {overlap.bus_id} is reached by multiple feeder traces: "
                    + ", ".join(overlap.feeder_ids)
                    + "."
                ),
            )
        )

    for island in topology.islands:
        if len(island.source_ids) > 1:
            issues.append(
                ValidationIssue(
                    code="TOP006",
                    severity=Severity.INFO,
                    category=ValidationCategory.TOPOLOGY,
                    object_type="TopologyIsland",
                    object_id=island.island_id,
                    message=(
                        f"Island {island.island_id} contains {len(island.source_ids)} "
                        "in-service sources: " + ", ".join(island.source_ids) + "."
                    ),
                )
            )

    if active_policy.report_open_switch_boundaries:
        for boundary in topology.open_switch_boundaries:
            if not boundary.separates_energized_from_deenergized:
                continue
            issues.append(
                ValidationIssue(
                    code="TOP007",
                    severity=Severity.INFO,
                    category=ValidationCategory.TOPOLOGY,
                    object_type="Switch",
                    object_id=boundary.switch_id,
                    message=(
                        f"Open switch {boundary.switch_id} separates an energized side "
                        "from a de-energized side."
                    ),
                )
            )

    return issues
