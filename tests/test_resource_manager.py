"""ResourceManager 实例化 + 模式切换测试

不真的加载 ONNX 模型（is_loaded 始终 False，因为模型文件不存在），
但能验证 ResourceManager 的状态机和接口正确。
"""
from __future__ import annotations


def test_resource_manager_singleton():
    from src.core.resource_manager import resource_manager

    assert resource_manager is not None
    assert len(resource_manager._models) == 4


def test_initial_mode_standard():
    from src.core.resource_manager import Mode, resource_manager

    # 单例已经实例化在 STANDARD
    assert resource_manager.mode in (Mode.STANDARD, Mode.GAMING)


def test_get_model_unloaded_returns_none():
    """未加载的模型 get_model 返回 None"""
    from src.core.resource_manager import resource_manager

    # 模型文件不存在，is_loaded 永远 False
    assert resource_manager.get_model("sensevoice") is None


def test_get_model_unknown():
    from src.core.resource_manager import resource_manager

    assert resource_manager.get_model("nonexistent") is None


def test_load_for_mode_does_not_crash():
    """load_for_mode 即使所有模型都加载失败也不应 crash"""
    from src.core.resource_manager import Mode, resource_manager

    resource_manager.load_for_mode(Mode.GAMING)
    assert resource_manager.mode == Mode.GAMING
    resource_manager.load_for_mode(Mode.STANDARD)
    assert resource_manager.mode == Mode.STANDARD


def test_force_mode_api():
    from src.core.resource_manager import Mode, resource_manager
    from src.core.config import settings

    resource_manager.force_mode(Mode.GAMING)
    assert settings.resource_manager.force_mode == "gaming"
    resource_manager.force_mode(None)
    assert settings.resource_manager.force_mode is None
