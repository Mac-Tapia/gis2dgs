from __future__ import annotations

import pandas as pd

from .dataset import InputDataset


def enrich_cymdist_tables(dataset: InputDataset) -> InputDataset:
    """Attach network node refs and resolve CYMDIST load ValueType semantics."""

    sections = dataset.tables.get("SECTION")
    if sections is not None and "SectionID" in sections.frame.columns:
        section_frame = sections.frame
        if "ToNodeID" in section_frame.columns:
            lookup = section_frame[["SectionID", "ToNodeID"]].drop_duplicates(
                subset=["SectionID"], keep="first"
            )
            for name in ("CUSTOMER_LOADS", "LOADS"):
                table = dataset.tables.get(name)
                if table is None or "SectionID" not in table.frame.columns:
                    continue
                table.frame = table.frame.merge(lookup, on="SectionID", how="left")

    for name in ("CUSTOMER_LOADS", "LOADS"):
        table = dataset.tables.get(name)
        if table is None:
            continue
        table.frame = _resolve_load_powers(table.frame)

    nodes = dataset.tables.get("NODE")
    sources = dataset.tables.get("SOURCE")
    if (
        nodes is not None
        and sources is not None
        and "NodeID" in nodes.frame.columns
        and "NodeID" in sources.frame.columns
    ):
        src = sources.frame.drop_duplicates(subset=["NodeID"], keep="first")
        merge_cols = ["NodeID"]
        for column in ("DesiredVoltage", "NetworkID"):
            if column in src.columns:
                merge_cols.append(column)
        if len(merge_cols) > 1:
            frame = nodes.frame
            for column in merge_cols[1:]:
                if column in frame.columns and column != "NetworkID":
                    frame = frame.drop(columns=[column])
            merged = frame.merge(src[merge_cols], on="NodeID", how="left", suffixes=("", "_src"))
            if "NetworkID_src" in merged.columns:
                if "NetworkID" in merged.columns:
                    merged["NetworkID"] = merged["NetworkID"].fillna(merged["NetworkID_src"])
                else:
                    merged["NetworkID"] = merged["NetworkID_src"]
                merged = merged.drop(columns=["NetworkID_src"])
            nodes.frame = merged

    # Stamp feeder DesiredVoltage onto SECTION rows (for line nominal voltage).
    sections = dataset.tables.get("SECTION")
    if (
        sections is not None
        and sources is not None
        and "NetworkID" in sections.frame.columns
        and "NetworkID" in sources.frame.columns
        and "DesiredVoltage" in sources.frame.columns
    ):
        feeder_v = (
            sources.frame.dropna(subset=["NetworkID"])
            .drop_duplicates(subset=["NetworkID"], keep="first")[
                ["NetworkID", "DesiredVoltage"]
            ]
        )
        frame = sections.frame
        if "DesiredVoltage" in frame.columns:
            frame = frame.drop(columns=["DesiredVoltage"])
        sections.frame = frame.merge(feeder_v, on="NetworkID", how="left")

    # Propagate feeder voltage to every SECTION endpoint bus.
    nodes = dataset.tables.get("NODE")
    sections = dataset.tables.get("SECTION")
    if (
        nodes is not None
        and sections is not None
        and "DesiredVoltage" in sections.frame.columns
        and "NodeID" in nodes.frame.columns
    ):
        ends: list[pd.DataFrame] = []
        for column in ("FromNodeID", "ToNodeID"):
            if column in sections.frame.columns:
                part = sections.frame[[column, "DesiredVoltage"]].rename(
                    columns={column: "NodeID"}
                )
                ends.append(part.dropna(subset=["NodeID", "DesiredVoltage"]))
        if ends:
            node_v = (
                pd.concat(ends, ignore_index=True)
                .drop_duplicates(subset=["NodeID"], keep="first")
            )
            frame = nodes.frame
            if "DesiredVoltage" in frame.columns:
                existing = frame[["NodeID", "DesiredVoltage"]].rename(
                    columns={"DesiredVoltage": "DesiredVoltage_existing"}
                )
                frame = frame.drop(columns=["DesiredVoltage"])
                merged = frame.merge(node_v, on="NodeID", how="left")
                merged = merged.merge(existing, on="NodeID", how="left")
                merged["DesiredVoltage"] = merged["DesiredVoltage_existing"].fillna(
                    merged["DesiredVoltage"]
                )
                merged = merged.drop(columns=["DesiredVoltage_existing"])
                nodes.frame = merged
            else:
                nodes.frame = frame.merge(node_v, on="NodeID", how="left")
    return dataset


def _resolve_load_powers(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive ActivePower_kW / ReactivePower_kvar from CYMDIST ValueType codes.

    Documented CYMDIST customer-load ValueType meanings:
    - 0: Value1=kW, Value2=kvar
    - 1: Value1=kVA, Value2=power factor (%)
    - 2: Value1=kW, Value2=power factor (%)
    """

    if "Value1" not in frame.columns:
        return frame
    out = frame.copy()
    value_type = (
        pd.to_numeric(out.get("ValueType"), errors="coerce").fillna(0).astype(int)
        if "ValueType" in out.columns
        else pd.Series(0, index=out.index, dtype=int)
    )
    v1 = pd.to_numeric(out["Value1"], errors="coerce").fillna(0.0)
    v2 = (
        pd.to_numeric(out["Value2"], errors="coerce").fillna(0.0)
        if "Value2" in out.columns
        else pd.Series(0.0, index=out.index)
    )

    active = v1.copy()
    reactive = v2.copy()

    mask_kva_pf = value_type == 1
    if mask_kva_pf.any():
        pf = (v2[mask_kva_pf] / 100.0).clip(lower=-1.0, upper=1.0)
        s_kva = v1[mask_kva_pf]
        active.loc[mask_kva_pf] = s_kva * pf
        reactive.loc[mask_kva_pf] = s_kva * _reactive_factor(pf)

    mask_kw_pf = value_type == 2
    if mask_kw_pf.any():
        pf = (v2[mask_kw_pf] / 100.0).clip(lower=-1.0, upper=1.0)
        p_kw = v1[mask_kw_pf]
        active.loc[mask_kw_pf] = p_kw
        # Q = P * tan(acos(pf)) with sign of pf; avoid div-by-zero at pf≈0.
        reactive.loc[mask_kw_pf] = p_kw * _reactive_over_active(pf)

    out["ActivePower_kW"] = active
    out["ReactivePower_kvar"] = reactive
    return out


def _reactive_factor(pf: pd.Series) -> pd.Series:
    abs_pf = pf.abs().clip(upper=1.0)
    magnitude = (1.0 - abs_pf * abs_pf).clip(lower=0.0).pow(0.5)
    return magnitude.where(pf >= 0, -magnitude)


def _reactive_over_active(pf: pd.Series) -> pd.Series:
    abs_pf = pf.abs().clip(lower=1e-9, upper=1.0)
    ratio = ((1.0 - abs_pf * abs_pf).clip(lower=0.0).pow(0.5)) / abs_pf
    return ratio.where(pf >= 0, -ratio)
