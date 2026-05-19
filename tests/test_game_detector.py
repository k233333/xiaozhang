"""game_detector 测试（不依赖具体进程，只测决策逻辑）"""
from __future__ import annotations

from unittest.mock import patch

from src.core.config import settings
from src.core.game_detector import GameDetector


def test_force_user_gaming():
    settings.resource_manager.force_mode = "gaming"
    try:
        d = GameDetector()
        s = d.check_once()
        assert s.is_game is True
        assert s.matched_method == "force_user"
    finally:
        settings.resource_manager.force_mode = None


def test_force_user_standard():
    settings.resource_manager.force_mode = "standard"
    try:
        d = GameDetector()
        s = d.check_once()
        assert s.is_game is False
        assert s.matched_method == "force_user"
    finally:
        settings.resource_manager.force_mode = None


def test_blacklist_blocks_detection():
    """前台是 obs64.exe → 即使全屏/吃 GPU 也不算游戏"""
    d = GameDetector()
    with patch("src.core.game_detector._get_foreground_window_info", return_value=("obs64.exe", "OBS")):
        s = d.check_once()
        assert s.is_game is False
        assert s.matched_method == "blacklist"


def test_whitelist_match():
    """前台进程在白名单 → 直接判游戏"""
    d = GameDetector()
    with patch(
        "src.core.game_detector._get_foreground_window_info",
        return_value=("LeagueofLegends.exe", "League"),
    ):
        s = d.check_once()
        assert s.is_game is True
        assert s.matched_method == "whitelist"


def test_no_match_default_not_game():
    """非白名单非黑名单 + 没全屏 + 无高负载 → 默认非游戏"""
    d = GameDetector()
    with (
        patch(
            "src.core.game_detector._get_foreground_window_info",
            return_value=("notepad.exe", "Untitled"),
        ),
        patch("src.core.game_detector._is_fullscreen_exclusive", return_value=False),
        patch("src.core.game_detector._gpu_load_pct", return_value=10.0),
        patch("psutil.cpu_percent", return_value=5.0),
    ):
        s = d.check_once()
        assert s.is_game is False
        assert s.matched_method == ""


def test_fullscreen_triggers_and_auto_learns(tmp_path, monkeypatch):
    """全屏检测命中 → 自动加入白名单"""
    # 把 knowledge-runtime 指到 tmp（conftest 已做但这里再保险）
    monkeypatch.setattr(
        settings.paths, "knowledge_runtime", str(tmp_path / "knowledge-runtime.json")
    )
    import json

    (tmp_path / "knowledge-runtime.json").write_text(
        json.dumps({"auto_learned_games": []}), encoding="utf-8"
    )

    d = GameDetector()
    with (
        patch(
            "src.core.game_detector._get_foreground_window_info",
            return_value=("MysteryGame.exe", "X"),
        ),
        patch("src.core.game_detector._is_fullscreen_exclusive", return_value=True),
    ):
        s = d.check_once()
        assert s.is_game is True
        assert s.matched_method == "fullscreen"

    # 验证已写进 knowledge-runtime.json
    data = json.loads((tmp_path / "knowledge-runtime.json").read_text(encoding="utf-8"))
    assert "MysteryGame.exe" in data["auto_learned_games"]
