from __future__ import annotations

from dataclasses import replace
from typing import Any

from gis2dgs.domain import NetworkModel
from gis2dgs.electrical import ElectricalLibrary

from .exceptions import PowerFactoryMappingError
from .graphics import attach_feeder_graphics, ensure_feeder_head_sources
from .ids import ForeignKeyFactory
from .model import PowerFactoryModel, PowerFactoryObject, PowerFactoryReference
from .policy import PowerFactoryMappingPolicy
from .validation import ensure_unique_display_names, validate_powerfactory_model


class PowerFactoryMapper:
    """Map canonical domain/electrical objects to a node-breaker PowerFactory model.

    Phase 7 intentionally stops before exact DGS column serialization. The output
    uses real PowerFactory class names but semantic attributes/references. Phase 8
    is responsible for applying a configured, version-neutral DGS schema.
    """

    def __init__(self, policy: PowerFactoryMappingPolicy | None = None) -> None:
        self.policy = policy or PowerFactoryMappingPolicy()
        self.keys = ForeignKeyFactory(self.policy.foreign_key_prefix)

    def map(
        self,
        network: NetworkModel,
        library: ElectricalLibrary | None = None,
    ) -> PowerFactoryModel:
        policy = self.policy
        if (
            len(network.buses) > policy.max_buses_for_feeder_graphics
            and (policy.create_feeder_graphics or policy.create_feeder_objects)
        ):
            policy = replace(
                policy,
                create_feeder_graphics=False,
                create_feeder_objects=False,
            )
        if policy.ensure_feeder_sources:
            ensure_feeder_head_sources(network)
        _propagate_system_ids(network)

        model = PowerFactoryModel()
        net_keys = self._create_networks(model, network)
        default_net = next(iter(net_keys.values()))

        self._map_substations(model, network, net_keys, default_net)
        self._map_terminals(model, network, net_keys, default_net)
        self._map_types(model, library)
        self._map_lines(model, network, library, net_keys, default_net)
        self._map_transformers(model, network, library, net_keys, default_net)
        self._map_switches(model, network, net_keys, default_net)
        self._map_loads(model, network, net_keys, default_net)
        self._map_generators(model, network, net_keys, default_net)
        self._map_sources(model, network, net_keys, default_net)
        attach_feeder_graphics(
            model,
            network,
            keys=self.keys,
            policy=policy,
            network_keys=net_keys,
            default_network_key=default_net,
        )

        ensure_unique_display_names(model)
        report = validate_powerfactory_model(model)
        if not report.is_valid:
            first = report.errors[0]
            raise PowerFactoryMappingError(first.message)
        return model

    def _create_networks(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
    ) -> dict[str, str]:
        systems: list[str]
        if self.policy.split_networks_by_system:
            systems = sorted(
                {
                    str(bus.system_id)
                    for bus in network.buses.values()
                    if bus.system_id is not None
                }
            )
        else:
            systems = []
        if not systems:
            systems = [self.policy.network_id]

        net_keys: dict[str, str] = {}
        for system_id in systems:
            key = self.keys.make("net", system_id)
            net_keys[system_id] = key
            display = (
                self.policy.network_name
                if system_id == self.policy.network_id
                else system_id
            )
            model.add(
                self._object(
                    self.policy.classes.network,
                    key,
                    display,
                    source_kind="network",
                    source_id=system_id,
                )
            )
        return net_keys

    def _network_key_for_bus(
        self,
        network: NetworkModel,
        bus_id: object,
        net_keys: dict[str, str],
        default_net: str,
    ) -> str:
        bus = network.buses.get(bus_id)  # type: ignore[arg-type]
        if bus is not None and bus.system_id is not None:
            return net_keys.get(str(bus.system_id), default_net)
        return default_net

    def _map_substations(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for substation in network.substations.values():
            if not self._include(True):
                continue
            attrs = self._coordinates(substation.x, substation.y)
            model.add(
                self._object(
                    self.policy.classes.substation,
                    self.keys.make("sub", substation.id),
                    substation.name,
                    attrs,
                    parent=default_net,
                    source_kind="substation",
                    source_id=str(substation.id),
                )
            )

    def _map_terminals(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for bus in network.buses.values():
            attrs: dict[str, Any] = {"nominal_voltage_kv": bus.nominal_voltage_kv}
            attrs.update(self._coordinates(bus.x, bus.y))
            if bus.feeder_id is not None:
                attrs["feeder_id"] = str(bus.feeder_id)
            if bus.system_id is not None:
                attrs["system_id"] = str(bus.system_id)

            parent = self._network_key_for_bus(network, bus.id, net_keys, default_net)
            if bus.substation_id is not None:
                if bus.substation_id not in network.substations:
                    if self.policy.require_substation_references:
                        raise PowerFactoryMappingError(
                            f"Bus {bus.id} references unknown substation {bus.substation_id}."
                        )
                else:
                    parent = self.keys.make("sub", bus.substation_id)

            model.add(
                self._object(
                    self.policy.classes.terminal,
                    self.keys.make("bus", bus.id),
                    bus.name,
                    attrs,
                    parent=parent,
                    source_kind="bus",
                    source_id=str(bus.id),
                )
            )

    def _map_types(
        self,
        model: PowerFactoryModel,
        library: ElectricalLibrary | None,
    ) -> None:
        if library is None:
            return
        for line_type in library.line_types.values():
            model.add(
                self._object(
                    self.policy.classes.line_type,
                    self.keys.make("ltype", line_type.id),
                    line_type.name,
                    {
                        "nominal_voltage_kv": line_type.nominal_voltage_kv,
                        "r1_ohm_per_km": line_type.r1_ohm_per_km,
                        "x1_ohm_per_km": line_type.x1_ohm_per_km,
                        "c1_nf_per_km": line_type.c1_nf_per_km,
                        "rated_current_a": line_type.rated_current_a,
                        "r0_ohm_per_km": line_type.r0_ohm_per_km,
                        "x0_ohm_per_km": line_type.x0_ohm_per_km,
                        "c0_nf_per_km": line_type.c0_nf_per_km,
                        "phases": line_type.phases,
                    },
                    source_kind="line_type",
                    source_id=line_type.id,
                )
            )
        for transformer_type in library.transformer_types.values():
            model.add(
                self._object(
                    self.policy.classes.transformer_type,
                    self.keys.make("ttype", transformer_type.id),
                    transformer_type.name,
                    {
                        "rated_power_mva": transformer_type.rated_power_mva,
                        "hv_voltage_kv": transformer_type.hv_voltage_kv,
                        "lv_voltage_kv": transformer_type.lv_voltage_kv,
                        "uk_percent": transformer_type.uk_percent,
                        "copper_loss_kw": transformer_type.copper_loss_kw,
                        "no_load_loss_kw": transformer_type.no_load_loss_kw,
                        "no_load_current_percent": transformer_type.no_load_current_percent,
                        "vector_group": transformer_type.vector_group,
                        "phase_shift_deg": transformer_type.phase_shift_deg,
                        "uk0_percent": transformer_type.uk0_percent,
                        "ur0_percent": transformer_type.ur0_percent,
                    },
                    source_kind="transformer_type",
                    source_id=transformer_type.id,
                )
            )

    def _map_lines(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        library: ElectricalLibrary | None,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for line in network.lines.values():
            if not self._include(line.in_service):
                continue
            element_key = self.keys.make("line", line.id)
            refs: dict[str, PowerFactoryReference] = {}
            if line.type_id is not None:
                if library is not None and library.find_line_type(line.type_id) is not None:
                    refs["type"] = PowerFactoryReference(
                        self.keys.make("ltype", line.type_id)
                    )
                elif self.policy.require_type_references:
                    self._require_line_type(line.type_id, library, line.id)
            elif self.policy.require_type_references:
                raise PowerFactoryMappingError(f"Line {line.id} has no type_id.")

            side_a, side_b = self._add_two_terminal_cubicles(
                model,
                network,
                element_key,
                "line",
                line.id,
                line.from_bus,
                line.to_bus,
            )
            refs["terminal_1_cubicle"] = PowerFactoryReference(side_a)
            refs["terminal_2_cubicle"] = PowerFactoryReference(side_b)
            parent = self._network_key_for_bus(
                network, line.from_bus, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.line,
                    element_key,
                    line.name,
                    {
                        "length_km": line.length_km,
                        "nominal_voltage_kv": line.nominal_voltage_kv,
                        "in_service": line.in_service,
                    },
                    refs,
                    parent=parent,
                    source_kind="line",
                    source_id=str(line.id),
                )
            )

    def _map_transformers(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        library: ElectricalLibrary | None,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for transformer in network.transformers.values():
            if not self._include(transformer.in_service):
                continue
            element_key = self.keys.make("trafo", transformer.id)
            refs: dict[str, PowerFactoryReference] = {}
            if transformer.type_id is not None:
                if (
                    library is not None
                    and library.find_transformer_type(transformer.type_id) is not None
                ):
                    refs["type"] = PowerFactoryReference(
                        self.keys.make("ttype", transformer.type_id)
                    )
                elif self.policy.require_type_references:
                    self._require_transformer_type(
                        transformer.type_id,
                        library,
                        transformer.id,
                    )
            elif self.policy.require_type_references:
                raise PowerFactoryMappingError(
                    f"Transformer {transformer.id} has no type_id."
                )

            hv_cub, lv_cub = self._add_two_terminal_cubicles(
                model,
                network,
                element_key,
                "transformer",
                transformer.id,
                transformer.hv_bus,
                transformer.lv_bus,
                side_names=("hv", "lv"),
            )
            refs["hv_cubicle"] = PowerFactoryReference(hv_cub)
            refs["lv_cubicle"] = PowerFactoryReference(lv_cub)
            parent = self._network_key_for_bus(
                network, transformer.hv_bus, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.transformer,
                    element_key,
                    transformer.name,
                    {
                        "hv_voltage_kv": transformer.hv_voltage_kv,
                        "lv_voltage_kv": transformer.lv_voltage_kv,
                        "rated_power_mva": transformer.rated_power_mva,
                        "in_service": transformer.in_service,
                    },
                    refs,
                    parent=parent,
                    source_kind="transformer",
                    source_id=str(transformer.id),
                )
            )

    def _map_switches(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for switch in network.switches.values():
            if not self._include(switch.in_service):
                continue
            element_key = self.keys.make("switch", switch.id)
            side_a, side_b = self._add_two_terminal_cubicles(
                model,
                network,
                element_key,
                "switch",
                switch.id,
                switch.from_bus,
                switch.to_bus,
            )
            parent = self._network_key_for_bus(
                network, switch.from_bus, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.switch,
                    element_key,
                    switch.name,
                    {"closed": switch.closed, "in_service": switch.in_service},
                    {
                        "terminal_1_cubicle": PowerFactoryReference(side_a),
                        "terminal_2_cubicle": PowerFactoryReference(side_b),
                    },
                    parent=parent,
                    source_kind="switch",
                    source_id=str(switch.id),
                )
            )

    def _map_loads(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for load in network.loads.values():
            if not self._include(load.in_service):
                continue
            element_key = self.keys.make("load", load.id)
            cubicle = self._add_single_terminal_cubicle(
                model,
                network,
                element_key,
                "load",
                load.id,
                load.bus_id,
            )
            parent = self._network_key_for_bus(
                network, load.bus_id, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.load,
                    element_key,
                    load.name,
                    {
                        "active_power_mw": load.active_power_mw,
                        "reactive_power_mvar": load.reactive_power_mvar,
                        "in_service": load.in_service,
                    },
                    {"cubicle": PowerFactoryReference(cubicle)},
                    parent=parent,
                    source_kind="load",
                    source_id=str(load.id),
                )
            )

    def _map_generators(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for generator in network.generators.values():
            if not self._include(generator.in_service):
                continue
            element_key = self.keys.make("gen", generator.id)
            cubicle = self._add_single_terminal_cubicle(
                model,
                network,
                element_key,
                "generator",
                generator.id,
                generator.bus_id,
            )
            attrs: dict[str, Any] = {
                "active_power_mw": generator.active_power_mw,
                "reactive_power_mvar": generator.reactive_power_mvar,
                "in_service": generator.in_service,
            }
            if generator.technology is not None:
                attrs["technology"] = generator.technology
            parent = self._network_key_for_bus(
                network, generator.bus_id, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.generator,
                    element_key,
                    generator.name,
                    attrs,
                    {"cubicle": PowerFactoryReference(cubicle)},
                    parent=parent,
                    source_kind="generator",
                    source_id=str(generator.id),
                )
            )

    def _map_sources(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        net_keys: dict[str, str],
        default_net: str,
    ) -> None:
        for source in network.sources.values():
            if not self._include(source.in_service):
                continue
            element_key = self.keys.make("source", source.id)
            cubicle = self._add_single_terminal_cubicle(
                model,
                network,
                element_key,
                "source",
                source.id,
                source.bus_id,
            )
            parent = self._network_key_for_bus(
                network, source.bus_id, net_keys, default_net
            )
            model.add(
                self._object(
                    self.policy.classes.source,
                    element_key,
                    source.name,
                    {
                        "nominal_voltage_kv": source.nominal_voltage_kv,
                        "in_service": source.in_service,
                    },
                    {"cubicle": PowerFactoryReference(cubicle)},
                    parent=parent,
                    source_kind="source",
                    source_id=str(source.id),
                )
            )

    def _add_two_terminal_cubicles(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        element_key: str,
        source_kind: str,
        source_id: object,
        bus_a: object,
        bus_b: object,
        *,
        side_names: tuple[str, str] = ("1", "2"),
    ) -> tuple[str, str]:
        self._require_bus(network, bus_a, source_kind, source_id)
        self._require_bus(network, bus_b, source_kind, source_id)
        cub_a = self.keys.cubicle(element_key, side_names[0])
        cub_b = self.keys.cubicle(element_key, side_names[1])
        self._add_cubicle(
            model, cub_a, element_key, bus_a, source_kind, source_id, connection_index=0
        )
        self._add_cubicle(
            model, cub_b, element_key, bus_b, source_kind, source_id, connection_index=1
        )
        return cub_a, cub_b

    def _add_single_terminal_cubicle(
        self,
        model: PowerFactoryModel,
        network: NetworkModel,
        element_key: str,
        source_kind: str,
        source_id: object,
        bus_id: object,
    ) -> str:
        self._require_bus(network, bus_id, source_kind, source_id)
        cubicle = self.keys.cubicle(element_key, "1")
        self._add_cubicle(
            model, cubicle, element_key, bus_id, source_kind, source_id, connection_index=0
        )
        return cubicle

    def _add_cubicle(
        self,
        model: PowerFactoryModel,
        cubicle_key: str,
        element_key: str,
        bus_id: object,
        source_kind: str,
        source_id: object,
        *,
        connection_index: int,
    ) -> None:
        model.add(
            self._object(
                self.policy.classes.cubicle,
                cubicle_key,
                f"{source_kind} {source_id} cubicle",
                attributes={"connection_index": connection_index},
                references={"connected_element": PowerFactoryReference(element_key)},
                parent=self.keys.make("bus", bus_id),
                source_kind=f"{source_kind}_cubicle",
                source_id=str(source_id),
            )
        )
        if self.policy.create_cubicle_switches:
            switch_key = self.keys.make("cubsw", cubicle_key)
            model.add(
                self._object(
                    self.policy.classes.cubicle_switch,
                    switch_key,
                    f"{source_kind} {source_id} connection switch",
                    attributes={"closed": True},
                    parent=cubicle_key,
                    source_kind=f"{source_kind}_cubicle_switch",
                    source_id=str(source_id),
                )
            )

    def _require_bus(
        self,
        network: NetworkModel,
        bus_id: object,
        source_kind: str,
        source_id: object,
    ) -> None:
        if bus_id not in network.buses:
            raise PowerFactoryMappingError(
                f"{source_kind.capitalize()} {source_id} references unknown bus {bus_id}."
            )

    def _require_line_type(
        self,
        type_id: str,
        library: ElectricalLibrary | None,
        line_id: object,
    ) -> None:
        if library is None or library.find_line_type(type_id) is None:
            raise PowerFactoryMappingError(
                f"Line {line_id} references line type {type_id!r} that is not available."
            )

    def _require_transformer_type(
        self,
        type_id: str,
        library: ElectricalLibrary | None,
        transformer_id: object,
    ) -> None:
        if library is None or library.find_transformer_type(type_id) is None:
            raise PowerFactoryMappingError(
                f"Transformer {transformer_id} references transformer type {type_id!r} "
                "that is not available."
            )

    def _include(self, in_service: bool) -> bool:
        return in_service or self.policy.include_out_of_service

    def _coordinates(self, x: float | None, y: float | None) -> dict[str, float]:
        if not self.policy.include_coordinates or x is None or y is None:
            return {}
        return {"coordinate_x": x, "coordinate_y": y}

    def _display_name(
        self,
        name: str,
        source_id: object | None,
        *,
        source_kind: str | None = None,
    ) -> str:
        if source_kind == "network":
            return name
        # Operational codes are expected in the mapped `name` fields.
        text = name.strip() if name else ""
        if not text and source_id is not None:
            text = str(source_id).strip()
        return text[:40] if text else "unnamed"

    def _object(
        self,
        class_name: str,
        foreign_key: str,
        name: str,
        attributes: dict[str, Any] | None = None,
        references: dict[str, PowerFactoryReference] | None = None,
        *,
        parent: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> PowerFactoryObject:
        return PowerFactoryObject(
            class_name=str(class_name),
            foreign_key=foreign_key,
            name=self._display_name(name, source_id, source_kind=source_kind),
            attributes=attributes or {},
            references=references or {},
            parent=PowerFactoryReference(parent) if parent is not None else None,
            source_kind=source_kind,
            source_id=source_id,
        )


def _propagate_system_ids(network: NetworkModel) -> None:
    """Copy system_id / feeder_id from annotated buses onto connected neighbors."""

    from collections import defaultdict, deque

    from gis2dgs.domain.bus import Bus
    from gis2dgs.domain.identifiers import ElectricalSystemId, FeederId

    adjacency: dict[str, set[str]] = defaultdict(set)
    for line in network.lines.values():
        a = str(line.from_bus)
        b = str(line.to_bus)
        adjacency[a].add(b)
        adjacency[b].add(a)
    for transformer in network.transformers.values():
        a = str(transformer.hv_bus)
        b = str(transformer.lv_bus)
        adjacency[a].add(b)
        adjacency[b].add(a)

    seeds = [
        bus
        for bus in network.buses.values()
        if bus.system_id is not None or bus.feeder_id is not None
    ]
    if not seeds:
        return

    visited: set[str] = set()
    queue: deque[str] = deque()
    context: dict[str, tuple[FeederId | None, ElectricalSystemId | None]] = {}
    for bus in seeds:
        key = str(bus.id)
        context[key] = (bus.feeder_id, bus.system_id)
        queue.append(key)

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        feeder, system = context[current]
        for neighbor in adjacency.get(current, ()):
            if neighbor in visited:
                continue
            existing = context.get(neighbor)
            if existing is None:
                context[neighbor] = (feeder, system)
            else:
                n_feeder, n_system = existing
                context[neighbor] = (
                    n_feeder if n_feeder is not None else feeder,
                    n_system if n_system is not None else system,
                )
            queue.append(neighbor)

    updates: list[Bus] = []
    for bus in network.buses.values():
        key = str(bus.id)
        if key not in context:
            continue
        feeder, system = context[key]
        if feeder == bus.feeder_id and system == bus.system_id:
            continue
        updates.append(
            Bus(
                id=bus.id,
                name=bus.name,
                nominal_voltage_kv=bus.nominal_voltage_kv,
                x=bus.x,
                y=bus.y,
                feeder_id=feeder if feeder is not None else bus.feeder_id,
                system_id=system if system is not None else bus.system_id,
                substation_id=bus.substation_id,
            )
        )
    for bus in updates:
        network.buses[bus.id] = bus

