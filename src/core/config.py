"""配置加载器（v2.0）



读取 config/runtime.yaml + config/llm.yaml + .env，提供两个全局对象：

  - settings：运行时配置

  - llm_config：LLM 路由配置



所有模块都通过 `from src.core.config import settings, llm_config` 获取。

"""

from __future__ import annotations



import os

from functools import lru_cache

from pathlib import Path

from typing import Any



import yaml

from dotenv import load_dotenv

from pydantic import BaseModel, Field



PROJECT_ROOT = Path(__file__).resolve().parents[2]



_env_path = PROJECT_ROOT / ".env"

if _env_path.exists():

    load_dotenv(_env_path, override=False)





# ---------------- runtime.yaml schema ----------------



class AppCfg(BaseModel):

    name: str = "XiaoZhang"

    version: str = "0.2.0"

    log_level: str = "INFO"





class PathsCfg(BaseModel):

    data_dir: str = "./data"

    logs_dir: str = "./logs"

    skills_dir: str = "./skills"

    models_dir: str = "./models"

    memory_db: str = "./data/memory.db"

    user_profile: str = "./data/USER.md"

    long_memory: str = "./data/MEMORY.md"

    knowledge_runtime: str = "./knowledge-runtime.json"





class AudioCfg(BaseModel):

    sample_rate: int = 16000

    channels: int = 1

    device: str | None = None

    block_size: int = 480





class WakeWordCfg(BaseModel):

    enabled: bool = False

    primary: str = "小张"

    secondary: list[str] = Field(default_factory=lambda: ["你好", "小张"])

    cancel_word: str = "取消"

    armed_window_seconds: int = 4

    primary_threshold: float = 0.6

    feedback_sound: bool = True

    model_dir: str = "./models/wake_word"





class VadCfg(BaseModel):

    enabled: bool = True

    silence_threshold_seconds: float = 1.5

    aggressiveness: int = 2

    silero_threshold: float = 0.5





class StateMachineCfg(BaseModel):

    enable_voiceprint_check: bool = False





class ResourceManagerThresholds(BaseModel):

    gpu_busy_percent: int = 50

    gpu_busy_duration_seconds: int = 10

    cpu_busy_percent: int = 70

    cpu_busy_duration_seconds: int = 30





class ResourceManagerDetection(BaseModel):

    by_process_name: bool = True

    by_gpu_load: bool = True

    by_fullscreen: bool = True

    by_cpu_load: bool = True





class ResourceManagerCfg(BaseModel):

    watchdog_interval: int = 5

    switch_delay: int = 3

    notify_on_mode_change: bool = True

    detection: ResourceManagerDetection = Field(default_factory=ResourceManagerDetection)

    thresholds: ResourceManagerThresholds = Field(default_factory=ResourceManagerThresholds)

    force_mode: str | None = None  # standard | gaming | None





class LocalModelCfg(BaseModel):

    backend: str = "cpu"          # cpu | directml

    fallback: str | None = None

    model_path: str





class SkillsCfg(BaseModel):

    match_threshold: float = 0.85

    builtin_dir: str = "./skills/_builtin"

    generated_dir: str = "./skills/_generated"





class MemoryCfg(BaseModel):

    enable_vector: bool = False

    recent_session_lookback: int = 10





class ActionsCfg(BaseModel):

    automation_timeout_seconds: int = 10

    screenshot_before_each_step: bool = True

    high_risk_require_confirmation: bool = True

    confirmation_mode: str = "keyboard"

    high_risk_actions: list[str] = Field(default_factory=list)





class RuntimeSettings(BaseModel):

    app: AppCfg

    paths: PathsCfg

    audio: AudioCfg

    wake_word: WakeWordCfg

    vad: VadCfg

    state_machine: StateMachineCfg = Field(default_factory=StateMachineCfg)

    resource_manager: ResourceManagerCfg

    game_processes: list[str] = Field(default_factory=list)

    non_game_processes: list[str] = Field(default_factory=list)

    auto_learned_games: list[str] = Field(default_factory=list)

    mode_models: dict[str, list[str]] = Field(default_factory=dict)

    local_models: dict[str, LocalModelCfg] = Field(default_factory=dict)

    skills: SkillsCfg

    memory: MemoryCfg

    actions: ActionsCfg



    project_root: Path = Field(default=PROJECT_ROOT)



    def resolve_path(self, p: str | Path) -> Path:

        path = Path(p)

        if path.is_absolute():

            return path

        return (self.project_root / path).resolve()





# ---------------- llm.yaml schema ----------------



class ProviderCfg(BaseModel):

    api_key_env: str

    base_url: str | None = None

    sdk: str = "openai"

    supports_vision: bool = False

    models: dict[str, str] = Field(default_factory=dict)



    @property

    def api_key(self) -> str | None:

        return os.getenv(self.api_key_env)





class RouteCfg(BaseModel):

    primary: str

    fallback: str | None = None

    timeout: int = 30





class PolicyCfg(BaseModel):

    retry_max: int = 2

    retry_delay: float = 1.0

    on_all_fail_message: str = "模型暂时不可用，请稍后再试"

    cache_recent_planning: bool = True

    cache_size: int = 20





class LLMConfig(BaseModel):

    providers: dict[str, ProviderCfg]

    routing: dict[str, RouteCfg]

    policy: PolicyCfg



    def parse_target(self, target: str) -> tuple[ProviderCfg, str]:

        """'deepseek.v4-pro' -> (provider, 'deepseek-reasoner')"""

        if "." not in target:

            raise ValueError(f"路由目标格式应为 'provider.model_alias'，得到 {target}")

        provider_name, alias = target.split(".", 1)

        provider = self.providers.get(provider_name)

        if provider is None:

            raise KeyError(f"未配置 provider: {provider_name}")

        if alias not in provider.models:

            raise KeyError(f"provider {provider_name} 没有模型别名 {alias}")

        return provider, provider.models[alias]





# ---------------- loader ----------------



def _load_yaml(path: Path) -> dict[str, Any]:

    if not path.exists():

        raise FileNotFoundError(f"配置文件不存在: {path}")

    with path.open("r", encoding="utf-8") as f:

        return yaml.safe_load(f) or {}





@lru_cache(maxsize=1)

def get_settings() -> RuntimeSettings:

    raw = _load_yaml(PROJECT_ROOT / "config" / "runtime.yaml")

    return RuntimeSettings(**raw)





@lru_cache(maxsize=1)

def get_llm_config() -> LLMConfig:

    raw = _load_yaml(PROJECT_ROOT / "config" / "llm.yaml")

    return LLMConfig(**raw)





def soul_text() -> str:

    """读取 SOUL.md 内容（人设）"""

    p = PROJECT_ROOT / "config" / "soul.md"

    if not p.exists():

        return ""

    return p.read_text(encoding="utf-8")





# 模块级单例

settings: RuntimeSettings = get_settings()

llm_config: LLMConfig = get_llm_config()

