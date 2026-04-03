import yaml
from pathlib import Path

_config = None


def load_config(path: str = None) -> dict:
    global _config
    if _config is not None and path is None:
        return _config
    config_path = Path(path) if path else Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        _config = yaml.safe_load(f)
    return _config


def get_config() -> dict:
    if _config is None:
        return load_config()
    return _config
