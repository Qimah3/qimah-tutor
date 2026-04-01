import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_get_router_openai():
    from app.services.llm_router import get_router
    router = get_router({"provider": "openai", "model": "gpt-4o-mini"})
    assert router.__class__.__name__ == "OpenAIRouter"


def test_get_router_claude():
    from app.services.llm_router import get_router
    router = get_router({"provider": "claude", "model": "claude-haiku-4-5-20251001"})
    assert router.__class__.__name__ == "ClaudeRouter"


def test_get_router_unknown_raises():
    from app.services.llm_router import get_router
    with pytest.raises(ValueError, match="unsupported"):
        get_router({"provider": "gemini"})


def test_router_stores_config():
    from app.services.llm_router import get_router
    cfg = {"provider": "openai", "model": "gpt-4o-mini", "temperature": 0.5, "max_tokens": 2000, "timeout": 30}
    router = get_router(cfg)
    assert router.model == "gpt-4o-mini"
    assert router.temperature == 0.5
    assert router.max_tokens == 2000
    assert router.timeout == 30


def test_router_default_config_values():
    """Router should have sensible defaults when config keys are missing."""
    from app.services.llm_router import get_router
    router = get_router({"provider": "openai", "model": "gpt-4o-mini"})
    assert router.temperature is not None
    assert router.max_tokens is not None
    assert router.timeout is not None
