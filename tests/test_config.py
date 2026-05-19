"""配置加载测试"""
from __future__ import annotations

from src.core.config import (
    LLMConfig,
    RuntimeSettings,
    get_llm_config,
    get_settings,
    llm_config,
    settings,
    soul_text,
)


def test_runtime_settings_loaded():
    """runtime.yaml 能正确加载"""
    assert isinstance(settings, RuntimeSettings)
    assert settings.app.version
    assert settings.audio.sample_rate == 16000


def test_llm_config_loaded():
    """llm.yaml 能正确加载"""
    assert isinstance(llm_config, LLMConfig)
    assert "deepseek" in llm_config.providers


def test_routing_targets_resolvable():
    """每个 routing 目标都能在 providers 找到对应"""
    for task, route in llm_config.routing.items():
        provider, model = llm_config.parse_target(route.primary)
        assert provider is not None
        assert model
        if route.fallback:
            p2, m2 = llm_config.parse_target(route.fallback)
            assert p2 is not None
            assert m2


def test_parse_target_invalid():
    import pytest

    with pytest.raises(ValueError):
        llm_config.parse_target("missing_dot")
    with pytest.raises(KeyError):
        llm_config.parse_target("nonexistent.foo")
    with pytest.raises(KeyError):
        llm_config.parse_target("deepseek.nonexistent_alias")


def test_soul_text_has_content():
    soul = soul_text()
    assert "小张" in soul
    assert len(soul) > 100


def test_resolve_path():
    """相对路径解析为绝对路径"""
    p = settings.resolve_path("data/x.txt")
    assert p.is_absolute()
    assert p.parts[-1] == "x.txt"


def test_local_models_config_complete():
    """4 个本地模型配置都齐全"""
    assert "wake_word" in settings.local_models
    assert "silero_vad" in settings.local_models
    assert "sensevoice" in settings.local_models
    assert "omniparser" in settings.local_models


def test_mode_models_consistency():
    """gaming 模式只保留 wake_word"""
    assert settings.mode_models["gaming"] == ["wake_word"]
    assert "sensevoice" in settings.mode_models["standard"]


def test_high_risk_actions_defined():
    actions = settings.actions.high_risk_actions
    assert "delete_file" in actions
    assert "send_message" in actions
    assert "shutdown" in actions


def test_lru_cache_get_settings_consistent():
    """get_settings/get_llm_config 缓存一致性"""
    assert get_settings() is settings
    assert get_llm_config() is llm_config
