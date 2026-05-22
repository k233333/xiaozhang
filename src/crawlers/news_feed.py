# coding: utf-8
"""资讯抓取 — 金融科技新闻摘要

来源：
- 36kr（中文科技）
- Hacker News（英文科技，取 top stories）
- 财联社/华尔街见闻（金融快讯）

返回结构化摘要（标题+来源+链接），不返回 HTML。
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.core.logger import get_logger

log = get_logger(__name__)

_PROXY = "http://127.0.0.1:7897"
_TIMEOUT = 10
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    summary: str = ""

    def one_line(self) -> str:
        return f"[{self.source}] {self.title}"


async def fetch_hackernews(limit: int = 10) -> list[NewsItem]:
    """Hacker News top stories（有 JSON API，最稳定）"""
    results = []
    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, verify=False) as client:
            resp = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
            ids = resp.json()[:limit]

            for story_id in ids:
                item_resp = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
                item = item_resp.json()
                if item and item.get("title"):
                    results.append(NewsItem(
                        title=item["title"],
                        url=item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        source="HackerNews",
                    ))
    except Exception as e:
        log.warning("HackerNews 抓取失败", err=str(e))

    return results


async def fetch_36kr(limit: int = 10) -> list[NewsItem]:
    """36kr 热门文章（通过 API）"""
    results = []
    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers=_HEADERS, verify=False) as client:
            resp = await client.get(
                "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot",
                params={"partner_id": "wap", "param_type": "1"},
            )
            data = resp.json()
            items = data.get("data", {}).get("hotRankList", [])

            for item in items[:limit]:
                title = item.get("templateMaterial", {}).get("widgetTitle", "")
                item_id = item.get("itemId", "")
                if title:
                    results.append(NewsItem(
                        title=title,
                        url=f"https://36kr.com/p/{item_id}" if item_id else "",
                        source="36kr",
                    ))
    except Exception as e:
        log.warning("36kr 抓取失败", err=str(e))

    return results


async def fetch_all_news(limit: int = 10) -> list[NewsItem]:
    """抓取所有源的资讯"""
    import asyncio

    hn_task = fetch_hackernews(limit=limit)
    kr_task = fetch_36kr(limit=limit)

    results = []
    for coro in asyncio.as_completed([hn_task, kr_task]):
        try:
            items = await coro
            results.extend(items)
        except Exception:
            continue

    return results[:limit * 2]
