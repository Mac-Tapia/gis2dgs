from gis2dgs.domain.network import NetworkModel
from gis2dgs.electrical import ElectricalLibrary
from gis2dgs.topology import TopologyAnalyzer, TopologyReport

from .data_quality_rules import validate_data_quality
from .electrical_rules import validate_electrical_consistency
from .library_rules import validate_electrical_library
from .network_rules import validate_minimum_structure, validate_references
from .policy import ValidationPolicy
from .readiness_rules import validate_readiness
from .result import Severity, ValidationIssue, ValidationReport
from .topology_rules import validate_topology


class NetworkValidator:
    """Orchestrate validation while computing topology only once."""

    def __init__(
        self,
        policy: ValidationPolicy | None = None,
        topology_analyzer: TopologyAnalyzer | None = None,
        electrical_library: ElectricalLibrary | None = None,
    ) -> None:
        self.policy = policy or ValidationPolicy.standard()
        self.topology_analyzer = topology_analyzer or TopologyAnalyzer()
        self.electrical_library = electrical_library

    def validate(self, network: NetworkModel) -> ValidationReport:
        issues: list[ValidationIssue] = []
        issues.extend(validate_minimum_structure(network))
        issues.extend(validate_references(network))
        issues.extend(validate_data_quality(network, self.policy))
        issues.extend(validate_electrical_consistency(network, self.policy))
        issues.extend(
            validate_electrical_library(
                network,
                self.electrical_library,
                self.policy,
            )
        )

        has_reference_errors = any(
            issue.severity == Severity.ERROR and issue.code.startswith("NET")
            for issue in issues
        )

        topology: TopologyReport | None = None
        if not has_reference_errors and network.buses:
            topology = self.topology_analyzer.analyze(network)
            issues.extend(validate_topology(network, topology, self.policy))

        issues.extend(validate_readiness(network, topology, self.policy))
        issues.sort(key=_issue_sort_key)

        return ValidationReport(
            issues=issues,
            topology=topology,
            profile=self.policy.name,
        )


def _issue_sort_key(issue: ValidationIssue) -> tuple[int, str, str, str, str]:
    severity_order = {
        Severity.ERROR: 0,
        Severity.WARNING: 1,
        Severity.INFO: 2,
    }
    return (
        severity_order[issue.severity],
        issue.category.value,
        issue.code,
        issue.object_type or "",
        issue.object_id or "",
    )


__all__ = ["NetworkValidator", "ValidationReport"]
