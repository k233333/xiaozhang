# coding: utf-8
"""网盘资源搜索 — 聚合多个夸克网盘搜索源

搜索源：
- quarksoo.cc（夸克网盘专用）
- miaosou.fun（秒搜，聚合多网盘）
- haisou.cc（海搜，支持过滤）

只返回夸克网盘链接（用户要求）。
返回结构化结果（标题+链接+时间），不返回 HTML。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx

from src.core.logger import get_logger

log = get_logger(__name__)

_PROXY = "http://127.0.0.1:7897"
_TIMEOUT = 12
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass
class PanResult:
    """一条网盘搜索结果"""
    title: str
    url: str          # 夸克网盘分享链接
    password: str     # 提取码（如果有）
    source: str       # 来源
    time: str = ""    # 分享时间

    def summary(self) -> str:
        pwd = f" 提取码:{self.password}" if self.password else ""
        t = f" ({self.time})" if self.time else ""
        return f"{self.title}{t}{pwd} — {self.source}"


async def search_quarksoo(query: str, limit: int = 5) -> list[PanResult]:
    """从 quarksoo.cc 搜索夸克网盘资源"""
    results = []
    url = f"https://quarksoo.cc/search.php?q={quote_plus(query)}"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers={
            **_HEADERS, "Referer": "https://quarksoo.cc/"
        }, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("quarksoo 请求失败", status=resp.status_code)
                return []

            html = resp.text
            # 提取搜索结果：标题 + 夸克链接
            # quarksoo 的结果通常是 <a href="https://pan.quark.cn/s/xxx">标题</a>
            blocks = re.findall(
                r'<a[^>]*href="(https://pan\.quark\.cn/s/[^"]+)"[^>]*>([^<]+)</a>',
                html
            )
            for link, title in blocks[:limit]:
                title = title.strip()
                if not title or len(title) < 2:
                    continue
                results.append(PanResult(
                    title=title,
                    url=link,
                    password="",
                    source="quarksoo",
                ))

    except Exception as e:
        log.warning("quarksoo 搜索异常", err=str(e))

    return results


async def search_miaosou(query: str, limit: int = 5) -> list[PanResult]:
    """从 miaosou.fun 搜索（API 接口）"""
    results = []
    url = f"https://miaosou.fun/api/secendsearch?name={quote_plus(query)}&pageNo=1"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers={
            **_HEADERS,
            "Referer": f"https://miaosou.fun/info?searchKey={quote_plus(query)}",
        }, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("miaosou 请求失败", status=resp.status_code)
                return []

            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", data.get("list", []))

            for item in (items or [])[:limit * 2]:
                if isinstance(item, dict):
                    title = item.get("title", item.get("name", ""))
                    link = item.get("url", item.get("link", ""))
                    pwd = item.get("password", item.get("pwd", ""))
                    time_str = item.get("time", item.get("date", ""))
                else:
                    continue

                # 只要夸克链接
                if "quark.cn" not in link:
                    continue

                if title:
                    results.append(PanResult(
                        title=title.strip(),
                        url=link,
                        password=pwd,
                        source="miaosou",
                        time=time_str,
                    ))

    except Exception as e:
        log.warning("miaosou 搜索异常", err=str(e))

    return results[:limit]


async def search_haisou(query: str, limit: int = 5) -> list[PanResult]:
    """从 haisou.cc 搜索（支持按网盘类型过滤）"""
    results = []
    # pan=quark 只搜夸克网盘
    url = f"https://haisou.cc/api/pan/share/search?query={quote_plus(query)}&scope=title&pan=quark&page=1&filter_valid=true"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers=_HEADERS, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("haisou 请求失败", status=resp.status_code)
                return []

            data = resp.json()
            items = data.get("data", data.get("list", data.get("results", [])))

            for item in (items or [])[:limit]:
                if isinstance(item, dict):
                    title = item.get("title", item.get("name", ""))
                    link = item.get("url", item.get("link", item.get("share_url", "")))
                    pwd = item.get("password", item.get("pwd", item.get("code", "")))
                    time_str = item.get("time", item.get("created_at", item.get("date", "")))
                else:
                    continue

                if title and link:
                    results.append(PanResult(
                        title=title.strip(),
                        url=link,
                        password=pwd or "",
                        source="haisou",
                        time=time_str,
                    ))

    except Exception as e:
        log.warning("haisou 搜索异常", err=str(e))

    return results


async def search_quark_all(query: str, limit: int = 8) -> list[PanResult]:
    """聚合所有源搜索夸克网盘资源，去重"""
    import asyncio

    tasks = [
        search_via_bing(query, limit=limit),
        search_quarksoo(query, limit=limit),
        search_miaosou(query, limit=limit),
        search_haisou(query, limit=limit),
    ]

    all_results = []
    for coro in asyncio.as_completed(tasks):
        try:
            results = await coro
            all_results.extend(results)
        except Exception:
            continue

    # 去重（按 URL）
    seen_urls = set()
    unique = []
    for r in all_results:
        url_key = r.url.rstrip("/").lower()
        if url_key in seen_urls:
            continue
        seen_urls.add(url_key)
        unique.append(r)

    return unique[:limit]


async def search_via_bing(query: str, limit: int = 5) -> list[PanResult]:
    """通过 Bing 搜索 site:pan.quark.cn 的分享链接（最稳定的兜底方案）"""
    results = []
    search_query = f'site:pan.quark.cn {query}'
    url = f"https://www.bing.com/search?q={quote_plus(search_query)}&count={limit}"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers={
            **_HEADERS,
            "Accept": "text/html,application/xhtml+xml",
        }, verify=False, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("bing 搜索失败", status=resp.status_code)
                return []

            html = resp.text
            # Bing 搜索结果中提取 pan.quark.cn 链接和标题
            # 格式：<a href="https://pan.quark.cn/s/xxx" ...><strong>标题</strong></a>
            # 或者在 <cite> 标签里
            blocks = re.findall(
                r'<li class="b_algo">(.*?)</li>',
                html, re.DOTALL
            )

            for block in blocks[:limit]:
                # 提取链接
                link_match = re.search(r'href="(https://pan\.quark\.cn/s/[^"]+)"', block)
                if not link_match:
                    # 有时 Bing 会重定向，链接在 cite 里
                    link_match = re.search(r'(https://pan\.quark\.cn/s/\w+)', block)
                if not link_match:
                    continue

                link = link_match.group(1)

                # 提取标题（去 HTML 标签）
                title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                if not title:
                    title = f"夸克网盘资源: {query}"

                results.append(PanResult(
                    title=title,
                    url=link,
                    password="",
                    source="bing",
                ))

    except Exception as e:
        log.warning("bing 搜索异常", err=str(e))

    return results
