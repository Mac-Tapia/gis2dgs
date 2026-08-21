from pathlib import Path

from gis2dgs.validation.policy import ValidationPolicy

from .loader import load_yaml


def load_validation_policy(path: Path) -> ValidationPolicy:
    data = load_yaml(path)
    return ValidationPolicy.from_mapping(data)
