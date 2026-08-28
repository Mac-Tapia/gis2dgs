from gis2dgs.domain import Bus, Line, NetworkModel, Source, Transformer
from gis2dgs.domain.identifiers import (
    BusId,
    ElectricalSystemId,
    FeederId,
    LineId,
    SourceId,
    TransformerId,
)
from gis2dgs.electrical import ElectricalLibrary, LineType
from gis2dgs.powerfactory import PowerFactoryMapper, validate_powerfactory_model
from gis2dgs.powerfactory.graphics import (
    ensure_feeder_head_sources,
)
from gis2dgs.powerfactory.policy import PowerFactoryMappingPolicy
import pytest


def _two_feeder_network() -> NetworkModel:
    network = NetworkModel()
    network.add_bus(Bus(BusId("F1"), "F1", 1.0, feeder_id=FeederId("F1")))
    network.add_bus(Bus(BusId("L1"), "L1", 1.0, feeder_id=FeederId("F1")))
    network.add_bus(Bus(BusId("F2"), "F2", 1.0, feeder_id=FeederId("F2")))
    network.add_bus(Bus(BusId("L2"), "L2", 1.0, feeder_id=FeederId("F2")))
    network.add_line(Line(LineId("T1"), "T1", BusId("F1"), BusId("L1"), 0.1, 1.0))
    network.add_line(Line(LineId("T2"), "T2", BusId("F2"), BusId("L2"), 0.1, 1.0))
    return network


def test_ensure_feeder_head_sources_creates_equivalent_per_feeder() -> None:
    network = _two_feeder_network()
    created = ensure_feeder_head_sources(network)
    assert created == 2
    assert {str(source.bus_id) for source in network.sources.values()} == {"F1", "F2"}
    assert {str(source.id) for source in network.sources.values()} == {"F1", "F2"}
    assert all(str(source.name).startswith("Equiv_") for source in network.sources.values())


def test_ensure_feeder_head_sources_uses_topology_roots() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("H"), "H", 10.0))
    network.add_bus(Bus(BusId("A"), "A", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("H"), BusId("A"), 0.1, 10.0))
    created = ensure_feeder_head_sources(network)
    assert created == 1
    source = next(iter(network.sources.values()))
    assert str(source.bus_id) == "H"
    assert source.name.startswith("Equiv_")


def test_ensure_feeder_head_sources_creates_one_equivalent_for_geo_inventory() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("NMT1"), "NMT1", 1.0, x=0.0, y=0.0))
    for index in range(4):
        geo_id = f"GEO_{index}_{index}"
        network.add_bus(Bus(BusId(geo_id), geo_id, 1.0, x=float(index), y=float(index)))
        network.add_line(
            Line(
                LineId(f"L{index}"),
                f"L{index}",
                BusId(geo_id),
                BusId("NMT1"),
                0.01,
                1.0,
            )
        )
    created = ensure_feeder_head_sources(network)
    assert created == 1
    source = next(iter(network.sources.values()))
    assert str(source.bus_id) == "NMT1"


def test_mapper_builds_one_diagram_per_feeder_with_source_and_codes() -> None:
    network = _two_feeder_network()
    library = ElectricalLibrary.from_types(
        line_types=[LineType("LT", "LT", 1.0, 0.2, 0.1, 200.0)]
    )
    for line_id in ("T1", "T2"):
        network.lines[LineId(line_id)] = Line(
            LineId(line_id),
            line_id,
            network.lines[LineId(line_id)].from_bus,
            network.lines[LineId(line_id)].to_bus,
            0.1,
            1.0,
            "LT",
        )

    model = PowerFactoryMapper().map(network, library)
    assert validate_powerfactory_model(model).is_valid

    diagrams = model.find_by_class("IntGrfnet")
    assert len(diagrams) == 2
    assert {obj.name for obj in diagrams} == {"F1", "F2"}

    sources = model.find_by_class("ElmXnet")
    assert len(sources) == 2
    assert {obj.name for obj in sources} == {"Equiv_F1", "Equiv_F2"}

    feeders = model.find_by_class("ElmFeeder")
    assert len(feeders) == 2
    assert {obj.name for obj in feeders} == {"F1", "F2"}

    graphics = model.find_by_class("IntGrf")
    assert any(obj.name == "L_T1" for obj in graphics)
    assert any(obj.name == "F1" for obj in graphics)
    assert any(obj.attributes.get("symbol_name") == "d_sym" for obj in graphics)
    assert any(obj.attributes.get("symbol_name") == "Term" for obj in graphics)
    assert all(
        obj.attributes.get("usage") == 1
        for obj in model.find_by_class("ElmTerm")
    )


def test_attach_feeder_graphics_can_be_disabled() -> None:
    network = _two_feeder_network()
    policy = PowerFactoryMappingPolicy(
        create_feeder_graphics=False,
        create_feeder_objects=False,
        require_type_references=False,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    assert model.find_by_class("IntGrfnet") == ()
    assert len(model.find_by_class("ElmXnet")) == 2


def test_single_grid_policy_produces_one_elmnet() -> None:
    network = _two_feeder_network()
    network.buses[BusId("F1")] = Bus(
        BusId("F1"),
        "F1",
        1.0,
        feeder_id=FeederId("F1"),
        system_id=ElectricalSystemId("SE0019"),
        x=100.0,
        y=200.0,
    )
    network.buses[BusId("L1")] = Bus(
        BusId("L1"), "L1", 1.0, feeder_id=FeederId("F1"), x=150.0, y=200.0
    )
    network.buses[BusId("F2")] = Bus(
        BusId("F2"),
        "F2",
        1.0,
        feeder_id=FeederId("F2"),
        system_id=ElectricalSystemId("SE0234"),
        x=300.0,
        y=400.0,
    )
    network.buses[BusId("L2")] = Bus(
        BusId("L2"), "L2", 1.0, feeder_id=FeederId("F2"), x=350.0, y=400.0
    )
    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=False,
        create_feeder_graphics=True,
        create_feeder_objects=False,
        include_coordinates=True,
        diagram_layout="gis",
    )
    model = PowerFactoryMapper(policy).map(network, None)
    assert len(model.find_by_class("ElmNet")) == 1
    assert len(model.find_by_class("IntGrfnet")) == 1
    assert model.find_by_class("ElmFeeder") == ()
    graphics = model.find_by_class("IntGrf")
    assert graphics
    # Relative GIS placement: F1 at origin after normalization, L1 50m east.
    bus_graphics = {
        obj.source_id: (obj.attributes["center_x"], obj.attributes["center_y"])
        for obj in graphics
        if obj.attributes.get("symbol_name") == "Term"
    }
    assert bus_graphics["F1"] == pytest.approx((0.0, 0.0))
    assert bus_graphics["L1"] == pytest.approx((50.0, 0.0))
    assert bus_graphics["F2"] == pytest.approx((200.0, 200.0))


def test_crushed_gis_auto_falls_back_to_topology_with_visible_edges() -> None:
    """Whole-network GIS scaled into 4000u collapses local tramos; auto uses SLD."""

    network = NetworkModel()
    # One origin + many near neighbours across a huge UTM span → short median edge.
    network.add_bus(
        Bus(BusId("H"), "H", 10.0, feeder_id=FeederId("F1"), x=0.0, y=0.0)
    )
    for index in range(8):
        bus_id = f"N{index}"
        network.add_bus(
            Bus(
                BusId(bus_id),
                bus_id,
                10.0,
                feeder_id=FeederId("F1"),
                x=500_000.0 + index * 40.0,
                y=200_000.0,
            )
        )
        prev = "H" if index == 0 else f"N{index - 1}"
        network.add_line(
            Line(LineId(f"L{index}"), f"L{index}", BusId(prev), BusId(bus_id), 0.04, 10.0)
        )

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=False,
        create_feeder_graphics=True,
        create_feeder_objects=False,
        diagram_layout="auto",
        diagram_min_edge_length=20.0,
        diagram_target_extent=4000.0,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    cons = model.find_by_class("IntGrfcon")
    assert cons
    lengths = []
    for obj in cons:
        dx = float(obj.attributes["r_x1"]) - float(obj.attributes["r_x0"])
        dy = float(obj.attributes["r_y1"]) - float(obj.attributes["r_y0"])
        lengths.append((dx * dx + dy * dy) ** 0.5)
    assert min(lengths) >= 20.0 * 0.45  # half of topology spacing toward midpoint


def test_utm_coords_with_origin_bus_are_fitted_into_diagram_extent() -> None:
    """Regression: one bus at (0,0) used to skip normalisation and blank PF NETWORK."""

    network = NetworkModel()
    network.add_bus(
        Bus(BusId("ORIGIN"), "ORIGIN", 10.0, feeder_id=FeederId("F1"), x=0.0, y=0.0)
    )
    network.add_bus(
        Bus(
            BusId("EAST"),
            "EAST",
            10.0,
            feeder_id=FeederId("F1"),
            x=317_614.0,
            y=274_438.0,
        )
    )
    network.add_bus(
        Bus(
            BusId("NORTH"),
            "NORTH",
            10.0,
            feeder_id=FeederId("F1"),
            x=317_614.0,
            y=274_538.0,
        )
    )
    network.add_line(Line(LineId("L1"), "L1", BusId("ORIGIN"), BusId("EAST"), 1.0, 10.0))
    network.add_line(Line(LineId("L2"), "L2", BusId("EAST"), BusId("NORTH"), 0.1, 10.0))
    network.add_source(Source(SourceId("ORIGIN"), "ORIGIN", BusId("ORIGIN"), 10.0))

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=False,
        create_feeder_graphics=True,
        create_feeder_objects=False,
        diagram_layout="gis",
        diagram_target_extent=4000.0,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    bus_graphics = {
        obj.source_id: (obj.attributes["center_x"], obj.attributes["center_y"])
        for obj in model.find_by_class("IntGrf")
        if obj.attributes.get("symbol_name") == "Term"
    }
    xs = [xy[0] for xy in bus_graphics.values()]
    ys = [xy[1] for xy in bus_graphics.values()]
    assert min(xs) == pytest.approx(0.0)
    assert min(ys) == pytest.approx(0.0)
    assert max(xs) <= 4000.0 + 1e-6
    assert max(ys) <= 4000.0 + 1e-6
    assert max(xs) > 100.0

    cons = model.find_by_class("IntGrfcon")
    assert cons
    assert all(obj.attributes.get("r_x_sizerow") == 2 for obj in cons)
    assert all(obj.attributes.get("r_y_sizerow") == 2 for obj in cons)


def test_fit_diagram_coordinates_scales_projected_metres() -> None:
    from gis2dgs.powerfactory.graphics import _fit_diagram_coordinates

    fitted = _fit_diagram_coordinates(
        {"a": (0.0, 0.0), "b": (100_000.0, 50_000.0)},
        target_extent=4000.0,
    )
    assert fitted["a"] == pytest.approx((0.0, 0.0))
    assert fitted["b"][0] == pytest.approx(4000.0)
    assert fitted["b"][1] == pytest.approx(2000.0)


def test_orphan_feeder_does_not_create_network_diagram_page() -> None:
    """Regression: orphan bucket named NETWORK opened a blank PF diagram."""

    network = NetworkModel()
    network.add_bus(Bus(BusId("H"), "H", 10.0, feeder_id=FeederId("F1")))
    network.add_bus(Bus(BusId("A"), "A", 10.0, feeder_id=FeederId("F1")))
    network.add_bus(Bus(BusId("ISO"), "ISO", 10.0))
    network.add_line(Line(LineId("L1"), "L1", BusId("H"), BusId("A"), 0.1, 10.0))
    network.add_source(Source(SourceId("H"), "H", BusId("H"), 10.0))

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=True,
        create_feeder_objects=False,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    diagrams = {obj.name for obj in model.find_by_class("IntGrfnet")}
    assert "NETWORK" not in diagrams
    assert "F1" in diagrams
    assert "__ORPHAN__" not in diagrams


def test_geo_endpoint_inventory_uses_single_inventario_diagram() -> None:
    """Many GEO_* span endpoints must not become one IntGrfnet per topology root."""

    network = NetworkModel()
    for index in range(12):
        from_id = f"GEO_{index * 100}_{index * 100}"
        to_id = f"GEO_{index * 100 + 50}_{index * 100 + 50}"
        network.add_bus(
            Bus(BusId(from_id), from_id, 1.0, x=float(index * 100), y=float(index * 100))
        )
        network.add_bus(
            Bus(
                BusId(to_id),
                to_id,
                1.0,
                x=float(index * 100 + 50),
                y=float(index * 100 + 50),
            )
        )
        network.add_line(
            Line(
                LineId(f"L{index}"),
                f"L{index}",
                BusId(from_id),
                BusId(to_id),
                0.01,
                1.0,
            )
        )

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=True,
        create_feeder_objects=False,
        diagram_layout="auto",
        diagram_min_edge_length=20.0,
    )
    model = PowerFactoryMapper(policy).map(network, None)

    diagrams = {obj.name for obj in model.find_by_class("IntGrfnet")}
    assert diagrams == {"INVENTARIO"}
    assert len(model.find_by_class("ElmXnet")) == 1
    graphics = model.find_by_class("IntGrf")
    term_graphics = [
        obj for obj in graphics if obj.attributes.get("symbol_name") == "Term"
    ]
    assert len(term_graphics) == 0
    assert len(graphics) == len(network.lines) + 1
    xs = [obj.attributes["center_x"] for obj in graphics]
    ys = [obj.attributes["center_y"] for obj in graphics]
    assert max(xs) - min(xs) > 100.0
    assert max(ys) - min(ys) > 100.0
    diagram_keys = {obj.foreign_key for obj in model.find_by_class("IntGrfnet")}
    assert all(
        obj.parent is not None and obj.parent.target_key in diagram_keys
        for obj in model.find_by_class("IntGrf")
    )


def test_bus_only_inventory_creates_inventory_diagram_with_terminals() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 1.0, x=100.0, y=200.0))
    network.add_bus(Bus(BusId("B2"), "B2", 1.0, x=150.0, y=250.0))

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=False,
        diagrams_per_feeder=True,
        create_feeder_objects=False,
        diagram_layout="gis",
    )
    model = PowerFactoryMapper(policy).map(network, None)

    diagrams = {obj.name for obj in model.find_by_class("IntGrfnet")}
    assert diagrams == {"INVENTARIO"}
    assert len(model.find_by_class("IntGrf")) == 3
    assert len(model.find_by_class("ElmXnet")) == 1


def test_elm_feeder_never_references_terminal() -> None:
    network = NetworkModel()
    network.add_bus(Bus(BusId("B1"), "B1", 10.0, feeder_id=FeederId("NETWORK")))
    network.add_bus(Bus(BusId("B2"), "B2", 10.0, feeder_id=FeederId("NETWORK")))
    network.add_line(Line(LineId("L1"), "L1", BusId("B1"), BusId("B2"), 0.1, 10.0))
    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        create_feeder_graphics=False,
        create_feeder_objects=True,
        ensure_feeder_sources=False,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    # No source cubicle → no ElmFeeder (must not fall back to ElmTerm).
    assert model.find_by_class("ElmFeeder") == ()


def test_mapper_splits_grids_by_electrical_system_and_diagrams_by_feeder() -> None:
    network = NetworkModel()
    network.add_bus(
        Bus(
            BusId("L14231"),
            "0101",
            10.0,
            feeder_id=FeederId("0101"),
            system_id=ElectricalSystemId("SE0019"),
        )
    )
    network.add_bus(
        Bus(
            BusId("T0101"),
            "T0101",
            10.0,
            feeder_id=FeederId("0101"),
            system_id=ElectricalSystemId("SE0019"),
        )
    )
    network.add_bus(
        Bus(
            BusId("SED0101"),
            "0101065E",
            0.4,
            feeder_id=FeederId("0101"),
            system_id=ElectricalSystemId("SE0019"),
        )
    )
    network.add_bus(
        Bus(
            BusId("L14232"),
            "0102",
            10.0,
            feeder_id=FeederId("0102"),
            system_id=ElectricalSystemId("SE0019"),
        )
    )
    network.add_bus(
        Bus(
            BusId("L999"),
            "0201",
            10.0,
            feeder_id=FeederId("0201"),
            system_id=ElectricalSystemId("SE0234"),
        )
    )
    network.add_line(
        Line(LineId("MT1"), "MT1", BusId("L14231"), BusId("T0101"), 0.05, 10.0)
    )
    network.add_transformer(
        Transformer(
            TransformerId("SED1"),
            "0101065E",
            BusId("L14231"),
            BusId("SED0101"),
            10.0,
            0.4,
            0.25,
        )
    )
    network.add_source(Source(SourceId("L14231"), "0101", BusId("L14231"), 10.0))
    network.add_source(Source(SourceId("L14232"), "0102", BusId("L14232"), 10.0))
    network.add_source(Source(SourceId("L999"), "0201", BusId("L999"), 10.0))

    policy = PowerFactoryMappingPolicy(
        require_type_references=False,
        split_networks_by_system=True,
    )
    model = PowerFactoryMapper(policy).map(network, None)
    assert validate_powerfactory_model(model).is_valid

    grids = model.find_by_class("ElmNet")
    assert {obj.name for obj in grids} == {"SE0019", "SE0234"}

    diagrams = model.find_by_class("IntGrfnet")
    assert {obj.name for obj in diagrams} == {"0101", "0102", "0201"}

    parent_by_feeder = {
        obj.name: str(obj.parent.target_key) if obj.parent is not None else None
        for obj in diagrams
    }
    se0019 = next(obj.foreign_key for obj in grids if obj.name == "SE0019")
    se0234 = next(obj.foreign_key for obj in grids if obj.name == "SE0234")
    assert parent_by_feeder["0101"] == se0019
    assert parent_by_feeder["0102"] == se0019
    assert parent_by_feeder["0201"] == se0234

    graphics = model.find_by_class("IntGrf")
    assert any(obj.name == "0101065E" for obj in graphics)
    assert any(obj.attributes.get("symbol_name") == "d_tr2" for obj in graphics)
