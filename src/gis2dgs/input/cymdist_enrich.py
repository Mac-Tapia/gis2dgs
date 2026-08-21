from __future__ import annotations

from .dataset import InputDataset


def enrich_cymdist_tables(dataset: InputDataset) -> InputDataset:
    """Attach network node references to CYMDIST load tables when possible."""

    sections = dataset.tables.get("SECTION")
    if sections is None or "SectionID" not in sections.frame.columns:
        return dataset
    section_frame = sections.frame
    if "ToNodeID" not in section_frame.columns:
        return dataset
    lookup = section_frame[["SectionID", "ToNodeID"]].drop_duplicates(
        subset=["SectionID"], keep="first"
    )
    for name in ("CUSTOMER_LOADS", "LOADS"):
        table = dataset.tables.get(name)
        if table is None or "SectionID" not in table.frame.columns:
            continue
        merged = table.frame.merge(lookup, on="SectionID", how="left")
        table.frame = merged
    return dataset
