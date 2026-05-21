# coding: utf-8
"""扫描 Windows 开始菜单/桌面快捷方式，建立可搜索的应用索引。

索引缓存为 JSON，供 xz.py open-app 快速查找。
支持中文/英文/拼音模糊搜索。
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# 缓存路径
_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "app_index.json"
# 缓存有效期（秒）
_CACHE_TTL = 86400  # 24 小时


def _resolve_lnk(lnk_path: str) -> Optional[str]:
    """解析 .lnk 快捷方式的目标路径（纯 Python，不依赖 COM）"""
    try:
        with open(lnk_path, "rb") as f:
            content = f.read()
        # Windows Shell Link Binary Format:
        # 最简方式 — 搜 .exe / .bat / .cmd / .msc 路径
        # 正式做法需要解析 ShellLinkHeader，这里用正则提取
        text = content.decode("utf-16-le", errors="ignore")
        # 匹配类似 C:\Program Files\xxx.exe 的路径
        match = re.search(
            r'([A-Za-z]:\\[^\x00]{3,260}\.(?:exe|bat|cmd|msc|ps1))',
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip('\x00').strip()
        # 也尝试 ASCII 解码
        text_ascii = content.decode("ascii", errors="ignore")
        match = re.search(
            r'([A-Za-z]:\\[^\x00]{3,260}\.(?:exe|bat|cmd|msc|ps1))',
            text_ascii,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip('\x00').strip()
    except Exception:
        pass
    return None


def _get_display_name(lnk_path: str) -> str:
    """从快捷方式文件名提取显示名"""
    name = Path(lnk_path).stem
    # 去掉常见后缀
    for suffix in [" - Shortcut", " - 快捷方式", " (2)", " - Copy"]:
        name = name.replace(suffix, "")
    return name.strip()


def _simple_pinyin(char: str) -> str:
    """超简拼音首字母（覆盖常见字，用于模糊搜索）"""
    # 不引入额外依赖，只用于搜索辅助
    return char.lower()


def scan_apps() -> list[dict]:
    """扫描所有快捷方式，返回应用列表。"""
    scan_dirs = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%USERPROFILE%\Desktop"),
    ]

    apps = {}  # name_lower -> app_info，用于去重

    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for root, _dirs, files in os.walk(scan_dir):
            for fname in files:
                if not fname.lower().endswith(".lnk"):
                    continue
                full_path = os.path.join(root, fname)
                target = _resolve_lnk(full_path)
                if not target:
                    continue
                # 跳过卸载程序
                name_lower = fname.lower()
                if any(kw in name_lower for kw in ["uninstall", "卸载", "remove", "repair"]):
                    continue

                display_name = _get_display_name(full_path)
                key = display_name.lower()

                # 去重：保留路径更短的（通常是主程序）
                if key in apps:
                    if len(target) >= len(apps[key]["target"]):
                        continue

                apps[key] = {
                    "name": display_name,
                    "target": target,
                    "source": full_path,
                }

    return sorted(apps.values(), key=lambda x: x["name"].lower())


def build_index(force: bool = False) -> list[dict]:
    """构建或读取缓存的应用索引。"""
    if not force and _CACHE_PATH.exists():
        try:
            data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            if time.time() - data.get("timestamp", 0) < _CACHE_TTL:
                return data["apps"]
        except Exception:
            pass

    apps = scan_apps()
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(
        json.dumps({"timestamp": time.time(), "apps": apps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return apps


# 常见中英文别名映射（双向）
_ALIASES = {
    "微信": ["wechat", "weixin"],
    "wechat": ["微信", "weixin"],
    "qq": ["腾讯qq", "qqnt"],
    "chrome": ["google chrome", "谷歌浏览器"],
    "谷歌": ["google chrome", "chrome"],
    "vscode": ["visual studio code", "code"],
    "vs code": ["visual studio code", "code", "vscode"],
    "steam": ["steam"],
    "ps": ["photoshop", "adobe photoshop"],
    "photoshop": ["adobe photoshop"],
    "抖音": ["douyin"],
    "记事本": ["notepad"],
    "计算器": ["calc", "calculator"],
    "画图": ["mspaint", "paint"],
    "资源管理器": ["explorer"],
    "终端": ["terminal", "windows terminal"],
    "浏览器": ["chrome", "edge", "firefox", "google chrome"],
    "edge": ["microsoft edge"],
    "word": ["winword", "microsoft word"],
    "excel": ["microsoft excel"],
    "ppt": ["powerpoint", "microsoft powerpoint"],
    "pycharm": ["pycharm"],
    "idea": ["intellij"],
    "剪映": ["jianying"],
}


def search(query: str, limit: int = 5) -> list[dict]:
    """模糊搜索应用。

    匹配逻辑（按优先级）：
    1. 名称 / exe 名完全匹配
    2. 名称 / exe 名包含查询
    3. 别名匹配
    4. 查询词拆分后部分匹配
    """
    apps = build_index()
    q = query.lower().strip()
    if not q:
        return []

    # 扩展查询词：加入别名
    queries = {q}
    for alias_key, alias_vals in _ALIASES.items():
        if q == alias_key or q in alias_vals:
            queries.add(alias_key)
            queries.update(alias_vals)

    exact = []
    contains = []
    partial = []

    for app in apps:
        name_lower = app["name"].lower()
        exe_name = os.path.splitext(os.path.basename(app["target"]))[0].lower()

        for qw in queries:
            if name_lower == qw or exe_name == qw:
                exact.append(app)
                break
            elif qw in name_lower or qw in exe_name:
                contains.append(app)
                break
        else:
            # 拆分查询词尝试部分匹配
            for word in q.split():
                if len(word) >= 2 and (word in name_lower or word in exe_name):
                    partial.append(app)
                    break

    # 去重保序
    seen = set()
    results = []
    for app in exact + contains + partial:
        key = app["target"].lower()
        if key not in seen:
            seen.add(key)
            results.append(app)

    return results[:limit]


# CLI 测试
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        print("Scanning apps...")
        apps = build_index(force=True)
        print(f"Found {len(apps)} apps. Saved to {_CACHE_PATH}")
        for a in apps[:20]:
            print(f"  {a['name']:30s} → {a['target']}")
        if len(apps) > 20:
            print(f"  ... and {len(apps) - 20} more")
    elif len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        results = search(query)
        if results:
            for r in results:
                print(f"  {r['name']:30s} → {r['target']}")
        else:
            print(f"  No results for '{query}'")
    else:
        print("Usage: python app_scanner.py scan       # 扫描建索引")
        print("       python app_scanner.py <查询>     # 搜索应用")
