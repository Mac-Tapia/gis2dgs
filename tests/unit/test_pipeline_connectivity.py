from pathlib import Path

from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.pipeline import _reconstruct_connectivity


def test_reconstruct_connectivity_does_not_mutate_mapping_on_failure(
    tmp_path: Path,
) -> None:
    mapping = MappingConfig(
        buses=LayerMapping(source="buses", fields={"id": "bus_id"}),
        lines=LayerMapping(source="lines", fields={"id": "line_id"}),
    )
    dataset = GisDataset()

    updated = _reconstruct_connectivity(
        dataset,
        mapping,
        report_path=tmp_path / "connectivity.yaml",
    )

    assert updated is dataset
    assert "from_bus" not in mapping.lines.fields
    assert "to_bus" not in mapping.lines.fields
