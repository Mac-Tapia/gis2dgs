"""Compatibility module retained for v0.8.0 imports.

The canonical API is now :mod:`gis2dgs.dgs.schema` and uses ``DgsSchema``.
No DIgSILENT/PowerFactory version discriminator is part of the DGS model.
"""

from .schema import (
    DgsClassMapping,
    DgsFormat,
    DgsIdentityMapping,
    DgsMappingProfile,
    DgsReferenceMapping,
    DgsSchema,
    DgsValueMapping,
    UnmappedPolicy,
)

__all__ = [
    "DgsClassMapping",
    "DgsFormat",
    "DgsIdentityMapping",
    "DgsMappingProfile",
    "DgsReferenceMapping",
    "DgsSchema",
    "DgsValueMapping",
    "UnmappedPolicy",
]
