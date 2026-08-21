from __future__ import annotations

import argparse
import time

from gis2dgs.domain import Bus, Line, NetworkModel, Source
from gis2dgs.domain.identifiers import BusId, LineId, SourceId
from gis2dgs.topology import TopologyAnalyzer


def build_radial_network(size: int) -> NetworkModel:
    if size < 2:
        raise ValueError("size must be >= 2")
    network = NetworkModel()
    for index in range(size):
        network.add_bus(Bus(BusId(f"B{index}"), f"Bus {index}", 10.0))
    for index in range(size - 1):
        network.add_line(
            Line(
                LineId(f"L{index}"),
                f"Line {index}",
                BusId(f"B{index}"),
                BusId(f"B{index + 1}"),
                0.1,
                10.0,
            )
        )
    network.add_source(Source(SourceId("SRC"), "Source", BusId("B0"), 10.0))
    return network


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nodes", "--buses", dest="nodes", type=int, default=50_000)
    args = parser.parse_args()
    network = build_radial_network(args.nodes)
    start = time.perf_counter()
    report = TopologyAnalyzer().analyze(network)
    elapsed = time.perf_counter() - start
    print(
        f"nodes={args.nodes} lines={args.nodes - 1} elapsed_seconds={elapsed:.6f} "
        f"islands={len(report.islands)} energized={len(report.energized_buses)}"
    )


if __name__ == "__main__":
    main()
