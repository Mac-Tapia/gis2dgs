import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

from gis2dgs.gis import (
    GisConnectivityError,
    GisDataset,
    apply_connection_proposal,
    propose_line_endpoint_connections,
    reconstruct_mapped_line_endpoints,
)

CRS = "EPSG:32718"


def _buses() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"bus_id": ["B1", "B2"]},
        geometry=[Point(500000.0, 9500000.0), Point(500100.0, 9500000.0)],
        crs=CRS,
    )


def _lines() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "line_id": ["L1"],
            "from_bus": [pd.NA],
            "to_bus": [pd.NA],
        },
        geometry=[LineString([(500000.05, 9500000.0), (500099.95, 9500000.0)])],
        crs=CRS,
    )


def test_spatial_connectivity_proposes_unique_endpoint_matches() -> None:
    proposal = propose_line_endpoint_connections(
        _lines(),
        _buses(),
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert proposal.resolved_count == 2
    assert proposal.unresolved_count == 0
    assert [item.resolved_bus_id for item in proposal.suggestions] == ["B1", "B2"]


def test_apply_connection_proposal_returns_copy_and_fills_references() -> None:
    lines = _lines()
    proposal = propose_line_endpoint_connections(
        lines,
        _buses(),
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    updated = apply_connection_proposal(
        lines,
        proposal,
        line_id_field="line_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
    )

    assert pd.isna(lines.loc[0, "from_bus"])
    assert updated.loc[0, "from_bus"] == "B1"
    assert updated.loc[0, "to_bus"] == "B2"


def test_existing_references_are_not_reproposed_by_default() -> None:
    lines = _lines()
    lines.loc[0, "from_bus"] = "B1"

    proposal = propose_line_endpoint_connections(
        lines,
        _buses(),
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert len(proposal.suggestions) == 1
    assert proposal.suggestions[0].endpoint == "to"


def test_equidistant_candidates_remain_ambiguous() -> None:
    buses = gpd.GeoDataFrame(
        {"bus_id": ["B1", "B2"]},
        geometry=[Point(499999.9, 9500000.0), Point(500000.1, 9500000.0)],
        crs=CRS,
    )
    lines = gpd.GeoDataFrame(
        {"line_id": ["L1"], "from_bus": [pd.NA], "to_bus": ["B2"]},
        geometry=[LineString([(500000.0, 9500000.0), (500000.1, 9500000.0)])],
        crs=CRS,
    )

    proposal = propose_line_endpoint_connections(
        lines,
        buses,
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert proposal.suggestions[0].resolved_bus_id is None
    assert proposal.suggestions[0].is_ambiguous is True
    assert len(proposal.suggestions[0].candidates) == 2


def test_no_bus_inside_tolerance_remains_unresolved() -> None:
    lines = _lines()
    lines.geometry = [LineString([(500010.0, 9500010.0), (500020.0, 9500010.0)])]

    proposal = propose_line_endpoint_connections(
        lines,
        _buses(),
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert proposal.resolved_count == 0
    assert proposal.unresolved_count == 2
    assert all(not item.has_match for item in proposal.suggestions)


def test_geographic_crs_is_rejected_for_metric_matching() -> None:
    lines = _lines().to_crs("EPSG:4326")
    buses = _buses().to_crs("EPSG:4326")

    with pytest.raises(GisConnectivityError, match="projected CRS"):
        propose_line_endpoint_connections(
            lines,
            buses,
            line_id_field="line_id",
            bus_id_field="bus_id",
            from_bus_field="from_bus",
            to_bus_field="to_bus",
            tolerance_m=0.2,
        )


def test_mismatched_crs_is_rejected() -> None:
    lines = _lines()
    buses = _buses().to_crs("EPSG:32717")

    with pytest.raises(GisConnectivityError, match="same CRS"):
        propose_line_endpoint_connections(
            lines,
            buses,
            line_id_field="line_id",
            bus_id_field="bus_id",
            from_bus_field="from_bus",
            to_bus_field="to_bus",
            tolerance_m=0.2,
        )


def test_invalid_existing_reference_can_be_repaired_spatially() -> None:
    lines = _lines()
    lines.loc[0, "from_bus"] = "UNKNOWN"
    lines.loc[0, "to_bus"] = "B2"

    proposal = propose_line_endpoint_connections(
        lines,
        _buses(),
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert len(proposal.suggestions) == 1
    assert proposal.suggestions[0].current_bus_id == "UNKNOWN"
    assert proposal.suggestions[0].resolved_bus_id == "B1"


def test_reconstruct_mapped_line_endpoints_fills_missing_columns() -> None:
    dataset = GisDataset()
    buses = _buses()
    lines = gpd.GeoDataFrame(
        {"line_id": ["L1"]},
        geometry=[LineString([(500000.05, 9500000.0), (500099.95, 9500000.0)])],
        crs=CRS,
    )
    dataset.add_layer("buses", buses)
    dataset.add_layer("lines", lines)

    updated, proposal = reconstruct_mapped_line_endpoints(
        dataset,
        line_layer="lines",
        bus_layer="buses",
        line_id_field="line_id",
        bus_id_field="bus_id",
        from_bus_field="from_bus",
        to_bus_field="to_bus",
        tolerance_m=0.2,
    )

    assert proposal.resolved_count == 2
    frame = updated.layer("lines")
    assert frame.iloc[0]["from_bus"] == "B1"
    assert frame.iloc[0]["to_bus"] == "B2"
