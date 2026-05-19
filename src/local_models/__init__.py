"""本地模型层（v2.0 新增）

通过 ResourceManager 协同：标准模式加载全部，游戏模式只保留 wake_word。
"""

from src.local_models.base import LocalModel, available_providers, has_directml

__all__ = ["LocalModel", "available_providers", "has_directml"]
