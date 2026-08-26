from collections.abc import Callable
from collections import Counter
import logging
from typing import Any

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point

from gis2dgs.config.models import LayerMapping, MappingConfig
from gis2dgs.domain.bus import Bus
from gis2dgs.domain.generator import Generator
from gis2dgs.domain.identifiers import (
    BusId,
    ElectricalSystemId,
    FeederId,
    GeneratorId,
    LineId,
    LoadId,
    SourceId,
    SubstationId,
    SwitchId,
    TransformerId,
)
from gis2dgs.domain.line import Line
from gis2dgs.domain.load import Load
from gis2dgs.domain.network import NetworkModel
from gis2dgs.domain.source import Source
from gis2dgs.domain.substation import Substation
from gis2dgs.domain.switch import Switch
from gis2dgs.domain.transformer import Transformer
from gis2dgs.gis.dataset import GisDataset
from gis2dgs.gis.exceptions import GisMappingError
from gis2dgs.gis.geodataframe_utils import safe_frame_crs
from gis2dgs.gis.normalizer import (
    convert_active_power_to_mw,
    convert_apparent_power_to_mva,
    convert_length_to_km,
    convert_reactive_power_to_mvar,
    convert_voltage_to_kv,
    is_missing,
    normalize_identifier,
    normalize_name,
    normalize_number,
    normalize_optional_identifier,
    normalize_service_state,
    parse_xy_from_geometry_text,
    normalize_switch_state,
)
from gis2dgs.gis.voltage_lookup import VoltageLookup

from .accessor import RowAccessor

logger = logging.getLogger(__name__)


class GisToDomainMapper:
    """Convert extracted GIS layers to the canonical electrical domain model.

    This is the Phase 3 boundary. Readers remain responsible only for extraction;
    this mapper owns field mapping, unit normalization and domain construction.
    """

    def __init__(
        self,
        config: MappingConfig,
        *,
        voltage_lookup: VoltageLookup | None = None,
    ) -> None:
        self.config = config
        self.voltage_lookup = voltage_lookup
        self._defaulted_load_powers: Counter[str] = Counter()
        self._skipped_loads: Counter[str] = Counter()

    def _voltage_codes(self) -> dict[str, float] | None:
        if self.voltage_lookup is None:
            return None
        return self.voltage_lookup.by_code

    def map(self, dataset: GisDataset) -> NetworkModel:
        prepared = dataset.reprojected(self.config.target_crs)
        network = NetworkModel()

        self._map_layer(prepared, self.config.buses, self._build_bus, network.add_bus)
        self._map_layer(
            prepared,
            self.config.substations,
            self._build_substation,
            network.add_substation,
        )
        self._map_layer(prepared, self.config.lines, self._build_line, network.add_line)
        self._map_layer(
            prepared,
            self.config.transformers,
            self._build_transformer,
            network.add_transformer,
        )
        self._map_layer(
            prepared,
            self.config.switches,
            self._build_switch,
            network.add_switch,
        )
        self._map_layer(prepared, self.config.loads, self._build_load, network.add_load)
        self._map_layer(
            prepared,
            self.config.generators,
            self._build_generator,
            network.add_generator,
        )
        self._map_layer(
            prepared,
            self.config.sources,
            self._build_source,
            network.add_source,
        )
        self._ensure_referenced_buses(network)
        self._emit_defaulted_power_warnings()
        return network

    def _ensure_referenced_buses(self, network: NetworkModel) -> None:
        """Create placeholder buses for endpoints referenced by equipment."""

        default_voltage = 1.0
        if self.config.buses is not None:
            raw = self.config.buses.defaults.get("nominal_voltage_kv", 1.0)
            try:
                default_voltage = float(raw)
            except (TypeError, ValueError):
                default_voltage = 1.0

        voltages: dict[BusId, float] = {}
        feeders: dict[BusId, FeederId | None] = {}
        systems: dict[BusId, ElectricalSystemId | None] = {}

        def _need(bus_id: BusId, voltage: float) -> None:
            if bus_id in network.buses:
                return
            previous = voltages.get(bus_id)
            if previous is None or voltage > previous:
                voltages[bus_id] = voltage

        for line in network.lines.values():
            _need(line.from_bus, line.nominal_voltage_kv or default_voltage)
            _need(line.to_bus, line.nominal_voltage_kv or default_voltage)
        for transformer in network.transformers.values():
            _need(transformer.hv_bus, transformer.hv_voltage_kv)
            _need(transformer.lv_bus, transformer.lv_voltage_kv)
            hv = network.buses.get(transformer.hv_bus)
            if hv is not None:
                feeders[transformer.lv_bus] = hv.feeder_id
                systems[transformer.lv_bus] = hv.system_id
                if transformer.hv_bus not in network.buses:
                    feeders[transformer.hv_bus] = hv.feeder_id
                    systems[transformer.hv_bus] = hv.system_id
        for switch in network.switches.values():
            _need(switch.from_bus, default_voltage)
            _need(switch.to_bus, default_voltage)
        for load in network.loads.values():
            _need(load.bus_id, default_voltage)
        for generator in network.generators.values():
            _need(generator.bus_id, default_voltage)
        for source in network.sources.values():
            _need(source.bus_id, source.nominal_voltage_kv)

        for bus_id, voltage in voltages.items():
            if bus_id in network.buses:
                continue
            code = str(bus_id)
            network.add_bus(
                Bus(
                    id=bus_id,
                    name=code,
                    nominal_voltage_kv=voltage if voltage > 0 else default_voltage,
                    feeder_id=feeders.get(bus_id),
                    system_id=systems.get(bus_id),
                )
            )

    def _map_layer(
        self,
        dataset: GisDataset,
        mapping: LayerMapping | None,
        builder: Callable[[RowAccessor], Any],
        add: Callable[[Any], None],
    ) -> None:
        if mapping is None:
            return

        frame = dataset.layer(mapping.source)
        id_column = mapping.fields.get("id")
        if id_column and id_column in frame.columns:
            frame = frame.drop_duplicates(subset=[id_column], keep="first")
        frame_crs = safe_frame_crs(frame)
        for row_index, row in frame.iterrows():
            accessor = RowAccessor(
                mapping.source,
                row_index,
                row,
                mapping,
                crs=frame_crs,
            )
            try:
                built = builder(accessor)
                if built is None:
                    continue
                add(built)
            except GisMappingError:
                raise
            except (TypeError, ValueError) as exc:
                raise GisMappingError(
                    f"Layer {mapping.source!r}, row {row_index!r}: {exc}"
                ) from exc

    def _build_bus(self, row: RowAccessor) -> Bus:
        object_id = normalize_identifier(row.require("id"))
        x, y = self._coordinates(row)
        feeder = normalize_optional_identifier(row.get("feeder_id"))
        system = normalize_optional_identifier(row.get("system_id"))
        substation = normalize_optional_identifier(row.get("substation_id"))
        return Bus(
            id=BusId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            nominal_voltage_kv=self._convert_voltage(
                row.require("nominal_voltage_kv"),
                row.unit("nominal_voltage_kv", "kV"),
            ),
            x=x,
            y=y,
            feeder_id=FeederId(feeder) if feeder is not None else None,
            system_id=(
                ElectricalSystemId(system) if system is not None else None
            ),
            substation_id=(
                SubstationId(substation) if substation is not None else None
            ),
        )

    def _build_substation(self, row: RowAccessor) -> Substation:
        object_id = normalize_identifier(row.require("id"))
        x, y = self._coordinates(row)
        return Substation(
            id=SubstationId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            x=x,
            y=y,
        )

    def _build_line(self, row: RowAccessor) -> Line:
        object_id = normalize_identifier(row.require("id"))
        return Line(
            id=LineId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            from_bus=BusId(normalize_identifier(row.require("from_bus"))),
            to_bus=BusId(normalize_identifier(row.require("to_bus"))),
            length_km=self._line_length_km(row),
            nominal_voltage_kv=self._convert_voltage(
                row.require("nominal_voltage_kv"),
                row.unit("nominal_voltage_kv", "kV"),
            ),
            type_id=normalize_optional_identifier(row.get("type_id")),
            in_service=self._service_state(row),
        )

    def _build_transformer(self, row: RowAccessor) -> Transformer:
        object_id = normalize_identifier(row.require("id"))
        return Transformer(
            id=TransformerId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            hv_bus=BusId(normalize_identifier(row.require("hv_bus"))),
            lv_bus=BusId(normalize_identifier(row.require("lv_bus"))),
            hv_voltage_kv=self._convert_voltage(
                row.require("hv_voltage_kv"),
                row.unit("hv_voltage_kv", "kV"),
            ),
            lv_voltage_kv=self._convert_voltage(
                row.require("lv_voltage_kv"),
                row.unit("lv_voltage_kv", "kV"),
            ),
            rated_power_mva=convert_apparent_power_to_mva(
                row.require("rated_power_mva"),
                row.unit("rated_power_mva", "MVA"),
            ),
            type_id=normalize_optional_identifier(row.get("type_id")),
            in_service=self._service_state(row),
        )

    def _build_switch(self, row: RowAccessor) -> Switch:
        object_id = normalize_identifier(row.require("id"))
        return Switch(
            id=SwitchId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            from_bus=BusId(normalize_identifier(row.require("from_bus"))),
            to_bus=BusId(normalize_identifier(row.require("to_bus"))),
            closed=normalize_switch_state(row.get("closed", default=True)),
            in_service=self._service_state(row),
        )

    def _build_load(self, row: RowAccessor) -> Load | None:
        object_id = normalize_identifier(row.require("id"))
        bus_raw = row.get("bus_id")
        if is_missing(bus_raw):
            self._skipped_loads["missing_bus_id"] += 1
            return None
        try:
            bus_id = BusId(normalize_identifier(bus_raw))
        except (TypeError, ValueError):
            self._skipped_loads["invalid_bus_id"] += 1
            return None
        return Load(
            id=LoadId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            bus_id=bus_id,
            active_power_mw=self._load_active_power_mw(row),
            reactive_power_mvar=self._load_reactive_power_mvar(row),
            in_service=self._service_state(row),
        )

    def _load_active_power_mw(self, row: RowAccessor) -> float:
        """Resolve load P; blank cells default to 0.0 MW with a layered warning.

        Distribution inventories often leave contracted/active power empty on
        service connections. DigSILENT accepts zero-MW loads; crashing the whole
        conversion is worse than a documented placeholder.
        """

        source = row.mapping.fields.get("active_power_mw")
        if source is not None and source in row.row.index:
            column_value = row.row[source]
            if not is_missing(column_value):
                try:
                    return convert_active_power_to_mw(
                        column_value,
                        row.unit("active_power_mw", "MW"),
                    )
                except (TypeError, ValueError) as exc:
                    self._defaulted_load_powers["active_power_mw_invalid"] += 1
                    logger.debug(
                        "Layer %r, row %r: invalid active_power_mw (%s); "
                        "defaulting to 0.0 MW",
                        row.layer_name,
                        row.row_index,
                        exc,
                    )
                    return 0.0
            self._defaulted_load_powers["active_power_mw"] += 1
            fallback = row.mapping.defaults.get("active_power_mw", 0.0)
            try:
                return convert_active_power_to_mw(
                    fallback,
                    row.unit("active_power_mw", "MW"),
                )
            except (TypeError, ValueError):
                return 0.0

        raw = row.get("active_power_mw")
        if is_missing(raw):
            self._defaulted_load_powers["active_power_mw"] += 1
            return 0.0
        try:
            return convert_active_power_to_mw(
                raw,
                row.unit("active_power_mw", "MW"),
            )
        except (TypeError, ValueError) as exc:
            self._defaulted_load_powers["active_power_mw_invalid"] += 1
            logger.debug(
                "Layer %r, row %r: invalid active_power_mw (%s); defaulting to 0.0 MW",
                row.layer_name,
                row.row_index,
                exc,
            )
            return 0.0

    def _load_reactive_power_mvar(self, row: RowAccessor) -> float:
        raw = row.get("reactive_power_mvar", default=0.0)
        if is_missing(raw):
            return 0.0
        try:
            return convert_reactive_power_to_mvar(
                raw,
                row.unit("reactive_power_mvar", "Mvar"),
            )
        except (TypeError, ValueError) as exc:
            self._defaulted_load_powers["reactive_power_mvar_invalid"] += 1
            logger.debug(
                "Layer %r, row %r: invalid reactive_power_mvar (%s); defaulting to 0.0 Mvar",
                row.layer_name,
                row.row_index,
                exc,
            )
            return 0.0

    def _emit_defaulted_power_warnings(self) -> None:
        missing = self._defaulted_load_powers.get("active_power_mw", 0)
        if missing:
            logger.warning(
                "Defaulted missing load active_power_mw to 0.0 MW on %d row(s); "
                "review source PAC/P columns or mapping units before DigSILENT studies.",
                missing,
            )
        invalid_p = self._defaulted_load_powers.get("active_power_mw_invalid", 0)
        if invalid_p:
            logger.warning(
                "Defaulted invalid load active_power_mw to 0.0 MW on %d row(s).",
                invalid_p,
            )
        invalid_q = self._defaulted_load_powers.get("reactive_power_mvar_invalid", 0)
        if invalid_q:
            logger.warning(
                "Defaulted invalid load reactive_power_mvar to 0.0 Mvar on %d row(s).",
                invalid_q,
            )
        skipped_bus = self._skipped_loads.get("missing_bus_id", 0)
        if skipped_bus:
            logger.warning(
                "Skipped %d load row(s) with missing bus_id (no DigSILENT connection).",
                skipped_bus,
            )
        skipped_invalid_bus = self._skipped_loads.get("invalid_bus_id", 0)
        if skipped_invalid_bus:
            logger.warning(
                "Skipped %d load row(s) with invalid bus_id.",
                skipped_invalid_bus,
            )

    def _build_generator(self, row: RowAccessor) -> Generator:
        object_id = normalize_identifier(row.require("id"))
        technology = normalize_optional_identifier(row.get("technology"))
        return Generator(
            id=GeneratorId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            bus_id=BusId(normalize_identifier(row.require("bus_id"))),
            active_power_mw=convert_active_power_to_mw(
                row.require("active_power_mw"),
                row.unit("active_power_mw", "MW"),
            ),
            reactive_power_mvar=convert_reactive_power_to_mvar(
                row.get("reactive_power_mvar", default=0.0),
                row.unit("reactive_power_mvar", "Mvar"),
            ),
            technology=technology,
            in_service=self._service_state(row),
        )

    def _build_source(self, row: RowAccessor) -> Source | None:
        # When buses and sources share a layer, hierarchical synthesis appends
        # placeholder bus rows without operational source attributes — skip them.
        if "name" in row.mapping.fields and is_missing(row.get("name")):
            return None
        object_id = normalize_identifier(row.require("id"))
        return Source(
            id=SourceId(object_id),
            name=normalize_name(row.get("name"), fallback=object_id),
            bus_id=BusId(normalize_identifier(row.require("bus_id"))),
            nominal_voltage_kv=self._convert_voltage(
                row.require("nominal_voltage_kv"),
                row.unit("nominal_voltage_kv", "kV"),
            ),
            in_service=self._service_state(row),
        )

    @staticmethod
    def _service_state(row: RowAccessor) -> bool:
        return normalize_service_state(row.get("in_service", default=True))

    def _convert_voltage(self, value: object, unit: str) -> float:
        return convert_voltage_to_kv(
            value,
            unit,
            code_lookup=self._voltage_codes(),
        )

    @staticmethod
    def _line_length_km(row: RowAccessor) -> float:
        length_value = row.get("length_km")
        if not is_missing(length_value):
            return convert_length_to_km(length_value, row.unit("length_km", "km"))
        length_km = _length_km_from_geometry(row)
        if length_km is None or length_km <= 0:
            raise ValueError(
                "length_km is missing and geometry does not provide a usable length."
            )
        return length_km

    @staticmethod
    def _coordinates(row: RowAccessor) -> tuple[float | None, float | None]:
        x_value = row.get("x")
        y_value = row.get("y")

        if not is_missing(x_value) or not is_missing(y_value):
            if is_missing(x_value) or is_missing(y_value):
                # Same GEOMETRÍA text mapped (or only one side filled): try parse.
                for candidate in (x_value, y_value):
                    parsed = parse_xy_from_geometry_text(candidate)
                    if parsed is not None:
                        return parsed
                raise ValueError("Both x and y coordinates must be provided together.")
            parsed_pair = parse_xy_from_geometry_text(x_value)
            if parsed_pair is not None and (
                is_missing(y_value)
                or parse_xy_from_geometry_text(y_value) is not None
                or str(x_value).strip() == str(y_value).strip()
            ):
                return parsed_pair
            try:
                return normalize_number(x_value), normalize_number(y_value)
            except ValueError:
                parsed = parse_xy_from_geometry_text(x_value) or parse_xy_from_geometry_text(
                    y_value
                )
                if parsed is not None:
                    return parsed
                raise

        geometry = row.row.get("geometry")
        if isinstance(geometry, Point) and not geometry.is_empty:
            return float(geometry.x), float(geometry.y)

        # Inventory text columns (e.g. GEOMETRÍA) when x/y were not mapped.
        for key, value in row.row.items():
            token = str(key).casefold()
            if "geometr" in token or token in {"coord", "coordenada", "coordenadas"}:
                parsed = parse_xy_from_geometry_text(value)
                if parsed is not None:
                    return parsed
        return None, None


def _length_km_from_geometry(row: RowAccessor) -> float | None:
    geometry = row.row.get("geometry")
    if not isinstance(geometry, (LineString, MultiLineString)) or geometry.is_empty:
        return None
    if geometry.length <= 0:
        return None
    if row.crs is None:
        return None
    from pyproj import CRS, Geod

    crs = CRS.from_user_input(row.crs)
    if crs.is_geographic:
        metres = abs(Geod(ellps="WGS84").geometry_length(geometry))
        return metres / 1000.0
    units = {
        axis.unit_name.lower()
        for axis in crs.axis_info
        if axis.unit_name
    }
    if any("metre" in unit or "meter" in unit for unit in units):
        return float(geometry.length) / 1000.0
    if any(unit in {"kilometre", "kilometer", "km"} for unit in units):
        return float(geometry.length)
    return None
