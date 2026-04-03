import os
import sys

# Add qimah-tutor-api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_load_config():
    from app.config import load_config
    cfg = load_config(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["rag"]["initial_candidates"] == 15
    assert cfg["security"]["hmac_timestamp_window_seconds"] == 60


def test_get_config_caches():
    from app.config import get_config, load_config
    load_config(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    cfg1 = get_config()
    cfg2 = get_config()
    assert cfg1 is cfg2  # same object returned (cached)
