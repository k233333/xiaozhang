# coding: utf-8
"""Playwright / CDP 接管 Chrome — 用 CSS 选择器找元素并点击。0 token。"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.logger import get_logger

log = get_logger(__name__)


CDP_PORT = 9222


def _is_cdp_alive(port: int = CDP_PORT, timeout: float = 0.5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


def find_chrome_executable() -> str | None:
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def launch_chrome_with_cdp(*, url: str | None = None, user_data_dir: str | None = None, port: int = CDP_PORT) -> bool:
    if _is_cdp_alive(port):
        log.info("CDP 已经活着，复用", port=port)
        # 如果传了 url，在当前 tab 导航过去
        if url:
            try:
                from playwright.sync_api import sync_playwright  # noqa: PLC0415
                with sync_playwright() as p:
                    _b, _c, page = _attach_and_get_page(p, port=port)
                    if page:
                        page.goto(url, wait_until="domcontentloaded", timeout=10000)
            except Exception as e:
                log.debug("导航失败（不影响）", err=str(e))
        return True
    # CDP 没活着 — 启动 Chrome（用用户日常 profile，共享 cookie/登录状态）
    chrome = find_chrome_executable()
    if chrome is None:
        log.warning("找不到 chrome.exe")
        return False
    args = [chrome, f"--remote-debugging-port={port}",
            "--no-first-run", "--no-default-browser-check"]
    if url:
        args.append(url)
    log.info("启动 CDP Chrome（日常 profile）", chrome=chrome, port=port, url=url)
    subprocess.Popen(args, close_fds=True)
    for _ in range(40):
        if _is_cdp_alive(port):
            return True
        time.sleep(0.2)
    log.warning("CDP 等待超时", port=port)
    return False


@dataclass
class ChromeClickResult:
    success: bool
    message: str = ""
    selector_used: str = ""
    matched_text: str = ""
    page_url: str = ""


def _attach_and_get_page(playwright, port: int = CDP_PORT):
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    if not browser.contexts:
        return browser, None, None
    ctx = browser.contexts[0]
    if not ctx.pages:
        page = ctx.new_page()
    else:
        pages = [p for p in ctx.pages if p.url and p.url != "about:blank"]
        page = pages[-1] if pages else ctx.pages[-1]
    return browser, ctx, page


def playwright_click(selector: str, *, timeout_ms: int = 5000, text_match: str | None = None,
                     port: int = CDP_PORT) -> ChromeClickResult:
    if not _is_cdp_alive(port):
        return ChromeClickResult(False, f"CDP {port} 没起来，先 launch-chrome")
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception as e:
        return ChromeClickResult(False, f"playwright 未装: {e}")

    with sync_playwright() as p:
        try:
            _b, _c, page = _attach_and_get_page(p, port=port)
        except Exception as e:
            return ChromeClickResult(False, f"attach CDP 失败: {e}")
        if page is None:
            return ChromeClickResult(False, "Chrome 没有可用 tab")
        page_url = page.url
        try:
            loc = page.locator(selector)
            if text_match:
                loc = loc.filter(has_text=text_match)
            count = loc.count()
            if count == 0:
                return ChromeClickResult(False, f"selector 未匹配: {selector}",
                                         selector_used=selector, page_url=page_url)
            target = loc.first
            target.wait_for(state="visible", timeout=timeout_ms)
            matched_text = ""
            try:
                matched_text = (target.inner_text(timeout=500) or "").strip()[:80]
            except Exception:
                pass
            target.click(timeout=timeout_ms)
            return ChromeClickResult(True, f"已点击 {selector} (匹配 {count} 个)",
                                     selector_used=selector, matched_text=matched_text,
                                     page_url=page_url)
        except Exception as e:
            return ChromeClickResult(False, f"点击失败: {e}", selector_used=selector,
                                     page_url=page_url)


def find_element_by_description(description: str, *, port: int = CDP_PORT) -> dict | None:
    if not _is_cdp_alive(port):
        return None
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception:
        return None
    desc = description.strip()
    if not desc:
        return None
    candidates = [
        f'role=button[name="{desc}"]',
        f'role=link[name="{desc}"]',
        f'button:has-text("{desc}")',
        f'a:has-text("{desc}")',
        f'[aria-label="{desc}"]',
        f'[title="{desc}"]',
        f'text="{desc}"',
        f'text={desc}',
    ]
    with sync_playwright() as p:
        try:
            _b, _c, page = _attach_and_get_page(p, port=port)
        except Exception as e:
            log.warning("CDP attach 失败", err=str(e))
            return None
        if page is None:
            return None
        page_url = page.url
        for sel in candidates:
            try:
                loc = page.locator(sel)
                count = loc.count()
                if count == 0:
                    continue
                first = loc.first
                if not first.is_visible(timeout=200):
                    continue
                bbox = None
                try:
                    bb = first.bounding_box(timeout=200)
                    if bb:
                        bbox = [int(bb["x"]), int(bb["y"]),
                                int(bb["width"]), int(bb["height"])]
                except Exception:
                    pass
                txt = ""
                try:
                    txt = (first.inner_text(timeout=200) or "").strip()[:80]
                except Exception:
                    pass
                log.info("元素命中", description=desc, selector=sel, text=txt, count=count)
                return {"method": "playwright", "selector": sel, "matched_text": txt,
                        "match_count": count, "page_url": page_url, "bbox": bbox}
            except Exception as e:
                log.debug("候选 selector 失败", sel=sel, err=str(e))
                continue
        log.info("没有候选 selector 命中", description=desc, page_url=page_url)
        return None
