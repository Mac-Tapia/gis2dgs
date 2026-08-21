from gis2dgs.domain.network import NetworkModel

from .analysis import (
    deenergized_buses,
    energized_buses,
    find_cycles,
    find_islands,
    trace_sources,
)
from .branches import extract_branches
from .graph import build_graph
from .models import TopologyReport
from .tracing import (
    TracePolicy,
    find_feeder_overlaps,
    find_open_switch_boundaries,
    trace_feeders,
)


class TopologyAnalyzer:
    """Orchestrate Phase 4 topology analysis without mutating the domain model."""

    def __init__(self, *, feeder_policy: TracePolicy | None = None) -> None:
        self.feeder_policy = feeder_policy or TracePolicy()

    def analyze(self, network: NetworkModel) -> TopologyReport:
        graph = build_graph(network)
        energized = energized_buses(network, graph)
        deenergized = deenergized_buses(network, graph)
        source_traces = trace_sources(network, graph)
        feeders = trace_feeders(network, graph, policy=self.feeder_policy)
        open_boundaries = find_open_switch_boundaries(network, energized)
        stop_buses = {
            boundary.from_bus
            for boundary in open_boundaries
        } | {
            boundary.to_bus
            for boundary in open_boundaries
        } | {
            trace.source_bus
            for trace in source_traces
        }

        return TopologyReport(
            islands=find_islands(network, graph),
            source_traces=source_traces,
            feeders=feeders,
            branches=extract_branches(graph, stop_buses=stop_buses),
            cycles=find_cycles(graph),
            open_switch_boundaries=open_boundaries,
            feeder_overlaps=find_feeder_overlaps(feeders),
            energized_buses=energized,
            deenergized_buses=deenergized,
        )
