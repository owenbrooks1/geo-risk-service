"""Load and validate config files. A bad config stops the run (AC-11)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from geo_risk_service.models import Policy, Settings


class ConfigError(Exception):
    """Config is missing or invalid. The message names the file and the problem."""


def _load(path: Path, model: type[BaseModel]) -> BaseModel:
    """Read a YAML file and validate it against a model, or raise ConfigError."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a mapping of settings")
    try:
        return model.model_validate(data)
    except ValidationError as error:
        # List every problem at once, so one fix-and-rerun is enough.
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()
        )
        raise ConfigError(f"{path}: {problems}") from None


def load_policy(path: Path) -> Policy:
    """Load the versioned decision rules (config/policy.yaml)."""
    return _load(path, Policy)


def load_settings(path: Path) -> Settings:
    """Load the run settings (config/settings.yaml)."""
    return _load(path, Settings)
