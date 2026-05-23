"""Token 消耗追踪器 — 实时统计 + 预警

功能：
  1. 每次 LLM 调用后记录 input/output/cache_hit tokens
  2. 按 provider 分别统计
  3. 计算实时费用（基于各 provider 定价）
  4. 超过预算阈值时发出预警
  5. 持久化到 data/token_usage.json（进程重启不丢失）

使用：
  from src.core.token_tracker import tracker
  tracker.record(provider="deepseek", model="deepseek-chat",
                 input_tokens=1200, output_tokens=300, cache_hit=800)
  print(tracker.summary())
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from src.core.logger import get_logger

log = get_logger(__name__)

# DeepSeek 定价（¥/M tokens，2026-05 价格）
# https://platform.deepseek.com/api-docs/pricing
_PRICING = {
    "deepseek": {
        "deepseek-chat": {"input": 1.0, "output": 2.0, "cache_hit": 0.1},
        "deepseek-reasoner": {"input": 4.0, "output": 16.0, "cache_hit": 0.4},
    },
    "groq": {
        # Groq 免费，但有 TPM 限制
        "*": {"input": 0.0, "output": 0.0, "cache_hit": 0.0},
    },
    "gemini": {
        # Gemini 免费额度内
        "*": {"input": 0.0, "output": 0.0, "cache_hit": 0.0},
    },
    "qwen": {
        "qwen-vl-max": {"input": 2.0, "output": 6.0, "cache_hit": 0.2},
        "qwen-vl-plus": {"input": 0.8, "output": 2.0, "cache_hit": 0.08},
        "qwen-max": {"input": 2.0, "output": 6.0, "cache_hit": 0.2},
    },
}

_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "token_usage.json"


@dataclass
class UsageRecord:
    """单次调用记录"""
    ts: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int = 0
    cost_yuan: float = 0.0


@dataclass
class ProviderStats:
    """单个 provider 的累计统计"""
    total_input: int = 0
    total_output: int = 0
    total_cache_hit: int = 0
    total_cost_yuan: float = 0.0
    call_count: int = 0
    last_call_ts: float = 0.0


@dataclass
class TokenTracker:
    """全局 token 追踪器（线程安全）"""
    stats: dict[str, ProviderStats] = field(default_factory=dict)
    session_stats: dict[str, ProviderStats] = field(default_factory=dict)  # 本次进程启动后
    budget_warn_yuan: float = 15.0  # 累计消耗超过此值时预警
    budget_limit_yuan: float = 20.0  # 硬限制（可选）
    _lock: Lock = field(default_factory=Lock)
    _dirty: bool = False

    def __post_init__(self):
        self._load()

    def record(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit_tokens: int = 0,
    ) -> UsageRecord:
        """记录一次 LLM 调用的 token 消耗"""
        cost = self._calc_cost(provider, model, input_tokens, output_tokens, cache_hit_tokens)
        rec = UsageRecord(
            ts=time.time(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cost_yuan=cost,
        )

        with self._lock:
            # 全局累计
            if provider not in self.stats:
                self.stats[provider] = ProviderStats()
            s = self.stats[provider]
            s.total_input += input_tokens
            s.total_output += output_tokens
            s.total_cache_hit += cache_hit_tokens
            s.total_cost_yuan += cost
            s.call_count += 1
            s.last_call_ts = rec.ts

            # 本次 session 累计
            if provider not in self.session_stats:
                self.session_stats[provider] = ProviderStats()
            ss = self.session_stats[provider]
            ss.total_input += input_tokens
            ss.total_output += output_tokens
            ss.total_cache_hit += cache_hit_tokens
            ss.total_cost_yuan += cost
            ss.call_count += 1
            ss.last_call_ts = rec.ts

            self._dirty = True

        # 预警检查
        total_cost = self.total_cost()
        if total_cost >= self.budget_warn_yuan:
            log.warning(
                "⚠️ Token 消耗预警",
                total_cost=f"¥{total_cost:.3f}",
                budget=f"¥{self.budget_warn_yuan}",
            )

        # 日志输出（每次调用都打印，方便实时观察）
        log.info(
            "📊 token 消耗",
            provider=provider,
            model=model,
            input=input_tokens,
            output=output_tokens,
            cache_hit=cache_hit_tokens,
            cost=f"¥{cost:.4f}",
            session_total=f"¥{self.session_cost():.4f}",
        )

        # 定期持久化（每 5 次调用写一次磁盘）
        if self._total_calls() % 5 == 0:
            self._save()

        return rec

    def total_cost(self) -> float:
        """全局累计费用"""
        with self._lock:
            return sum(s.total_cost_yuan for s in self.stats.values())

    def session_cost(self) -> float:
        """本次进程启动后的费用"""
        with self._lock:
            return sum(s.total_cost_yuan for s in self.session_stats.values())

    def summary(self) -> str:
        """人类可读的统计摘要"""
        with self._lock:
            lines = ["═══ Token 消耗统计 ═══"]
            for provider, s in sorted(self.stats.items()):
                lines.append(
                    f"  {provider}: {s.call_count} 次调用 | "
                    f"输入 {s.total_input:,} | 输出 {s.total_output:,} | "
                    f"缓存命中 {s.total_cache_hit:,} | "
                    f"费用 ¥{s.total_cost_yuan:.4f}"
                )
            lines.append(f"  ─── 总计: ¥{self.total_cost():.4f} ───")

            # 本次 session
            sc = self.session_cost()
            if sc > 0:
                session_calls = sum(s.call_count for s in self.session_stats.values())
                lines.append(f"  本次启动: {session_calls} 次 | ¥{sc:.4f}")

            return "\n".join(lines)

    def summary_oneliner(self) -> str:
        """一行摘要（适合终端/气泡显示）"""
        sc = self.session_cost()
        tc = self.total_cost()
        session_calls = sum(s.call_count for s in self.session_stats.values())
        return f"本次 {session_calls} 调用 ¥{sc:.4f} | 累计 ¥{tc:.4f}/{self.budget_warn_yuan}"

    def _total_calls(self) -> int:
        return sum(s.call_count for s in self.stats.values())

    def _calc_cost(
        self, provider: str, model: str,
        input_tokens: int, output_tokens: int, cache_hit: int,
    ) -> float:
        """计算单次调用费用（¥）"""
        pricing = _PRICING.get(provider, {})
        model_price = pricing.get(model) or pricing.get("*")
        if model_price is None:
            # 未知 provider/model，用 DeepSeek-chat 价格估算
            model_price = {"input": 1.0, "output": 2.0, "cache_hit": 0.1}

        # 缓存命中的 tokens 从 input 中扣除（只付缓存价）
        real_input = input_tokens - cache_hit
        cost = (
            real_input * model_price["input"] / 1_000_000
            + output_tokens * model_price["output"] / 1_000_000
            + cache_hit * model_price["cache_hit"] / 1_000_000
        )
        return cost

    def _load(self) -> None:
        """从磁盘加载历史统计"""
        if not _DATA_FILE.exists():
            return
        try:
            data = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
            for provider, raw in data.get("stats", {}).items():
                self.stats[provider] = ProviderStats(
                    total_input=raw.get("total_input", 0),
                    total_output=raw.get("total_output", 0),
                    total_cache_hit=raw.get("total_cache_hit", 0),
                    total_cost_yuan=raw.get("total_cost_yuan", 0.0),
                    call_count=raw.get("call_count", 0),
                    last_call_ts=raw.get("last_call_ts", 0.0),
                )
            self.budget_warn_yuan = data.get("budget_warn_yuan", 15.0)
            self.budget_limit_yuan = data.get("budget_limit_yuan", 20.0)
        except Exception as e:
            log.warning("token_usage.json 加载失败", err=str(e))

    def _save(self) -> None:
        """持久化到磁盘"""
        with self._lock:
            if not self._dirty:
                return
            data = {
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "budget_warn_yuan": self.budget_warn_yuan,
                "budget_limit_yuan": self.budget_limit_yuan,
                "stats": {},
            }
            for provider, s in self.stats.items():
                data["stats"][provider] = {
                    "total_input": s.total_input,
                    "total_output": s.total_output,
                    "total_cache_hit": s.total_cache_hit,
                    "total_cost_yuan": round(s.total_cost_yuan, 6),
                    "call_count": s.call_count,
                    "last_call_ts": s.last_call_ts,
                }
            self._dirty = False

        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def save(self) -> None:
        """外部显式保存（进程退出时调用）"""
        self._dirty = True
        self._save()


# 全局单例
tracker = TokenTracker()
