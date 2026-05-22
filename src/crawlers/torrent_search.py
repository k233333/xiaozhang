# coding: utf-8
"""磁力资源搜索 — 从多个公开站点搜索美剧/电影资源

支持站点：
- 1337x.to（综合，英文资源多）
- TorrentGalaxy（综合，有中文字幕标记）
- BTDIG（DHT 搜索引擎，覆盖广）

返回结构化结果（标题/大小/做种数/磁力链），不返回 HTML 垃圾。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx

from src.core.logger import get_logger

log = get_logger(__name__)

# 代理配置（走系统代理）
_PROXY = "http://127.0.0.1:7897"
_TIMEOUT = 15
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
}


@dataclass
class TorrentResult:
    """一条搜索结果"""
    title: str
    size: str
    seeders: int
    magnet: str
    source: str  # 来源站点

    def summary(self) -> str:
        """人类可读的一行摘要"""
        return f"[{self.seeders}种] {self.title} ({self.size}) — {self.source}"


async def search_1337x(query: str, limit: int = 5) -> list[TorrentResult]:
    """从 1337x 搜索资源"""
    results = []
    url = f"https://1337x.to/search/{quote_plus(query)}/1/"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers=_HEADERS, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("1337x 请求失败", status=resp.status_code)
                return []

            html = resp.text
            # 提取搜索结果页的链接
            links = re.findall(r'<a href="(/torrent/\d+/[^"]+)"', html)
            if not links:
                return []

            for link in links[:limit]:
                detail_url = f"https://1337x.to{link}"
                try:
                    detail_resp = await client.get(detail_url)
                    detail_html = detail_resp.text

                    # 提取标题
                    title_match = re.search(r'<title>(.+?)(?:\s*\||\s*-\s*1337x)', detail_html)
                    title = title_match.group(1).strip() if title_match else link.split("/")[-1]

                    # 提取磁力链
                    magnet_match = re.search(r'(magnet:\?xt=urn:btih:[^"&]+)', detail_html)
                    if not magnet_match:
                        continue
                    magnet = magnet_match.group(1)

                    # 提取大小
                    size_match = re.search(r'Total size.*?<span>([^<]+)</span>', detail_html, re.DOTALL)
                    size = size_match.group(1).strip() if size_match else "未知"

                    # 提取做种数
                    seed_match = re.search(r'Seeders.*?<span>(\d+)</span>', detail_html, re.DOTALL)
                    seeders = int(seed_match.group(1)) if seed_match else 0

                    results.append(TorrentResult(
                        title=title,
                        size=size,
                        seeders=seeders,
                        magnet=magnet,
                        source="1337x",
                    ))
                except Exception as e:
                    log.debug("1337x 详情页解析失败", err=str(e))
                    continue

    except Exception as e:
        log.warning("1337x 搜索异常", err=str(e))

    return results


async def search_btdig(query: str, limit: int = 5) -> list[TorrentResult]:
    """从 BTDIG（DHT 搜索引擎）搜索"""
    results = []
    url = f"https://btdig.com/search?q={quote_plus(query)}&order=0"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers=_HEADERS, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("btdig 请求失败", status=resp.status_code)
                return []

            html = resp.text
            # BTDIG 结果格式：每个结果在 <div class="one_result">
            blocks = re.findall(
                r'<div class="one_result">(.*?)</div>\s*</div>',
                html, re.DOTALL
            )

            for block in blocks[:limit]:
                # 标题
                title_match = re.search(r'<div class="torrent_name"[^>]*>.*?<a[^>]*>(.+?)</a>', block, re.DOTALL)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                if not title:
                    continue

                # 磁力链
                magnet_match = re.search(r'(magnet:\?xt=urn:btih:[a-fA-F0-9]+)', block)
                if not magnet_match:
                    continue
                magnet = magnet_match.group(1)

                # 大小
                size_match = re.search(r'<span class="torrent_size"[^>]*>([^<]+)</span>', block)
                size = size_match.group(1).strip() if size_match else "未知"

                results.append(TorrentResult(
                    title=title,
                    size=size,
                    seeders=0,  # BTDIG 不显示做种数
                    magnet=magnet,
                    source="btdig",
                ))

    except Exception as e:
        log.warning("btdig 搜索异常", err=str(e))

    return results


async def search_all(query: str, limit: int = 5, min_resolution: int = 1080) -> list[TorrentResult]:
    """从所有源搜索，合并去重，过滤低分辨率，按做种数排序。

    Args:
        query: 搜索关键词
        limit: 最大返回数
        min_resolution: 最低分辨率（默认 1080，低于此的过滤掉）
    """
    import asyncio

    tasks = [
        search_apibay(query, limit=limit * 2),  # 多取一些，过滤后可能不够
        search_1337x(query, limit=limit * 2),
    ]
    all_results = []
    for coro in asyncio.as_completed(tasks):
        try:
            results = await coro
            all_results.extend(results)
        except Exception:
            continue

    # 过滤低分辨率
    if min_resolution > 0:
        filtered = []
        for r in all_results:
            res = _extract_resolution(r.title)
            if res >= min_resolution:
                filtered.append(r)
            else:
                log.debug("过滤低分辨率", title=r.title[:50], resolution=res)
        all_results = filtered

    # 过滤死种（0 seeders）
    all_results = [r for r in all_results if r.seeders > 0]

    # 按做种数降序
    all_results.sort(key=lambda r: r.seeders, reverse=True)

    # 去重（按磁力链的 btih hash）
    seen_hashes = set()
    unique = []
    for r in all_results:
        hash_match = re.search(r'btih:([a-fA-F0-9]+)', r.magnet)
        if hash_match:
            h = hash_match.group(1).lower()
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
        unique.append(r)

    return unique[:limit]


def _extract_resolution(title: str) -> int:
    """从标题提取分辨率数值。

    匹配：2160p/4K, 1080p, 720p, 480p 等
    没有标注的默认返回 0（不过滤）。
    """
    title_lower = title.lower()

    if "2160p" in title_lower or "4k" in title_lower or "uhd" in title_lower:
        return 2160
    if "1080p" in title_lower or "1080i" in title_lower:
        return 1080
    if "720p" in title_lower:
        return 720
    if "480p" in title_lower or "sd" in title_lower:
        return 480

    # 没标注分辨率的，看文件大小推断（大于 2GB 的大概率是高清）
    return 0  # 未知，不过滤


async def check_torrent_health(magnet: str) -> dict:
    """检查种子健康度（是否有活跃的 seeders/peers）。

    通过 tracker 查询获取实时 seeders/leechers 数据。
    """
    import struct
    import socket
    import random

    info_hash_match = re.search(r'btih:([a-fA-F0-9]{40})', magnet, re.IGNORECASE)
    if not info_hash_match:
        return {"alive": False, "error": "无法提取 info_hash"}

    info_hash = bytes.fromhex(info_hash_match.group(1))

    # 公共 UDP tracker 列表
    trackers = [
        ("tracker.opentrackr.org", 1337),
        ("open.stealth.si", 80),
        ("tracker.torrent.eu.org", 451),
        ("exodus.desync.com", 6969),
    ]

    best_seeders = 0
    best_leechers = 0
    responded = False

    for host, port in trackers:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _udp_scrape, host, port, info_hash
            )
            if result:
                responded = True
                if result["seeders"] > best_seeders:
                    best_seeders = result["seeders"]
                    best_leechers = result["leechers"]
        except Exception:
            continue

    if not responded:
        return {"alive": None, "seeders": 0, "leechers": 0, "note": "tracker 无响应（可能网络问题）"}

    return {
        "alive": best_seeders > 0,
        "seeders": best_seeders,
        "leechers": best_leechers,
        "note": f"{'活跃' if best_seeders > 0 else '死种'} — {best_seeders} 做种 / {best_leechers} 下载中",
    }


def _udp_scrape(host: str, port: int, info_hash: bytes, timeout: float = 3.0) -> dict | None:
    """UDP tracker scrape 协议 — 获取种子的 seeders/leechers"""
    import struct
    import socket
    import random

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    try:
        # 解析 hostname
        addr = (socket.gethostbyname(host), port)

        # Step 1: Connect
        transaction_id = random.randint(0, 0xFFFFFFFF)
        connect_req = struct.pack(">QII", 0x41727101980, 0, transaction_id)
        sock.sendto(connect_req, addr)

        resp = sock.recv(16)
        action, resp_tid, connection_id = struct.unpack(">IIQ", resp)
        if action != 0 or resp_tid != transaction_id:
            return None

        # Step 2: Scrape
        transaction_id = random.randint(0, 0xFFFFFFFF)
        scrape_req = struct.pack(">QII", connection_id, 2, transaction_id) + info_hash
        sock.sendto(scrape_req, addr)

        resp = sock.recv(20)
        action, resp_tid = struct.unpack(">II", resp[:8])
        if action != 2 or resp_tid != transaction_id:
            return None

        seeders, completed, leechers = struct.unpack(">III", resp[8:20])
        return {"seeders": seeders, "leechers": leechers, "completed": completed}

    except (socket.timeout, OSError):
        return None
    finally:
        sock.close()


async def search_apibay(query: str, limit: int = 5) -> list[TorrentResult]:
    """从 apibay.org（PirateBay API 镜像）搜索 — 最稳定，JSON API"""
    results = []
    url = f"https://apibay.org/q.php?q={quote_plus(query)}&cat=0"

    try:
        async with httpx.AsyncClient(proxy=_PROXY, timeout=_TIMEOUT, headers=_HEADERS, verify=False) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("apibay 请求失败", status=resp.status_code)
                return []

            data = resp.json()
            if not data or (len(data) == 1 and data[0].get("name") == "No results returned"):
                return []

            for item in data[:limit]:
                name = item.get("name", "")
                info_hash = item.get("info_hash", "")
                size_bytes = int(item.get("size", 0))
                seeders = int(item.get("seeders", 0))

                if not name or not info_hash:
                    continue

                # 格式化大小
                if size_bytes > 1024 * 1024 * 1024:
                    size = f"{size_bytes / (1024**3):.1f} GB"
                elif size_bytes > 1024 * 1024:
                    size = f"{size_bytes / (1024**2):.0f} MB"
                else:
                    size = f"{size_bytes / 1024:.0f} KB"

                magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote_plus(name)}"

                results.append(TorrentResult(
                    title=name,
                    size=size,
                    seeders=seeders,
                    magnet=magnet,
                    source="PirateBay",
                ))

    except Exception as e:
        log.warning("apibay 搜索异常", err=str(e))

    return results
