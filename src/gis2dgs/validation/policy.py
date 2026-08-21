from dataclasses import dataclass, fields, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """Configuration for network, topology and electrical-library validation."""

    name: str = "standard"
    voltage_tolerance_kv: float = 1e-6
    transformer_power_relative_tolerance: float = 1e-6
    require_in_service_source: bool = False
    require_line_type: bool = False
    require_transformer_type: bool = False
    require_electrical_library: bool = False
    require_zero_sequence_data: bool = False
    require_geographic_coordinates: bool = False
    require_all_buses_energized: bool = False
    require_radial_network: bool = False
    forbid_feeder_overlaps: bool = False
    report_open_switch_boundaries: bool = True

    def __post_init__(self) -> None:
        if self.voltage_tolerance_kv <= 0:
            raise ValueError("voltage_tolerance_kv must be greater than zero.")
        if self.transformer_power_relative_tolerance <= 0:
            raise ValueError(
                "transformer_power_relative_tolerance must be greater than zero."
            )
        if not self.name.strip():
            raise ValueError("Validation policy name cannot be empty.")

    @classmethod
    def standard(cls) -> "ValidationPolicy":
        return cls(name="standard")

    @classmethod
    def power_flow(cls) -> "ValidationPolicy":
        return cls(
            name="power_flow",
            require_in_service_source=True,
            require_line_type=True,
            require_transformer_type=True,
            require_electrical_library=True,
            require_all_buses_energized=True,
        )

    @classmethod
    def short_circuit(cls) -> "ValidationPolicy":
        return cls(
            name="short_circuit",
            require_in_service_source=True,
            require_line_type=True,
            require_transformer_type=True,
            require_electrical_library=True,
            require_zero_sequence_data=True,
            require_all_buses_energized=True,
        )

    @classmethod
    def geographic(cls) -> "ValidationPolicy":
        return cls(
            name="geographic",
            require_geographic_coordinates=True,
        )

    @classmethod
    def radial_distribution(cls) -> "ValidationPolicy":
        return cls(
            name="radial_distribution",
            require_in_service_source=True,
            require_all_buses_energized=True,
            require_radial_network=True,
            forbid_feeder_overlaps=True,
        )

    @classmethod
    def import_profile(cls) -> "ValidationPolicy":
        """First-pass structural validation for newly discovered GIS sources.

        Keeps topology/reference checks enabled through the standard rule set, but
        does not require sources, library types, or full energization until the
        project YAML and electrical library are curated.
        """

        return cls(name="import")

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ValidationPolicy":
        """Create a policy from YAML-like configuration with strict key checking."""
        raw = dict(data)
        profile = str(raw.pop("profile", raw.pop("name", "standard"))).strip()

        factories = {
            "standard": cls.standard,
            "import": cls.import_profile,
            "power_flow": cls.power_flow,
            "short_circuit": cls.short_circuit,
            "geographic": cls.geographic,
            "radial_distribution": cls.radial_distribution,
        }
        try:
            base = factories[profile]()
        except KeyError as exc:
            allowed = ", ".join(sorted(factories))
            raise ValueError(
                f"Unknown validation profile {profile!r}. Allowed profiles: {allowed}."
            ) from exc

        allowed_fields = {item.name for item in fields(cls)} - {"name"}
        unknown = sorted(set(raw) - allowed_fields)
        if unknown:
            raise ValueError("Unknown validation setting(s): " + ", ".join(unknown))

        return replace(base, **raw)
