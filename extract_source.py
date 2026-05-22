#!/usr/bin/env python3
"""从草民影院页面提取实际视频源链接"""
import requests
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.eagcar.com/",
}

session = requests.Session()
session.headers.update(HEADERS)

# 爬取第24集页面
urls = [
    "https://www.eagcar.com/vodplay/99405-1-24.html",
    "https://www.eagcar.com/voddetail/99405.html",
]

for url in urls:
    print(f"\n=== 爬取: {url} ===")
    try:
        r = session.get(url, timeout=15, allow_redirects=True)
        r.encoding = "utf-8"
        print(f"状态码: {r.status_code}, 长度: {len(r.text)}")

        # 提取所有 script 内容
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
        for i, s in enumerate(scripts):
            if len(s) > 20:
                # 找视频相关变量
                if any(k in s for k in ['player', 'video', 'm3u8', 'mp4', 'url', 'src', 'source']):
                    print(f"\n  Script [{i}] (含视频相关):")
                    # 截取相关部分
                    for line in s.split('\n'):
                        if any(k in line.lower() for k in ['m3u8', '.mp4', 'player', 'url:', '"url"', "'url'", 'video', 'source']):
                            print(f"    {line.strip()[:200]}")

        # 提取所有 iframe
        iframes = re.findall(r'<iframe[^>]*src="([^"]+)"[^>]*>', r.text)
        print(f"\n  iframe数量: {len(iframes)}")
        for ifr in iframes:
            print(f"    {ifr}")

        # 提取所有 video/audio 源
        sources = re.findall(r'<source[^>]*src="([^"]+)"', r.text)
        print(f"\n  source数量: {len(sources)}")
        for src in sources:
            print(f"    {src}")

        # 提取 m3u8/mp4/flv 链接
        m3u8s = re.findall(r'https?://[^"\'<>]+\.m3u8[^"\'<>]*', r.text)
        mp4s = re.findall(r'https?://[^"\'<>]+\.mp4[^"\'<>]*', r.text)
        print(f"\n  m3u8链接: {len(m3u8s)}")
        for m in m3u8s:
            print(f"    {m}")
        print(f"  mp4链接: {len(mp4s)}")
        for m in mp4s:
            print(f"    {m}")

        # 打印页面中可能包含视频URL的文本片段
        url_patterns = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', r.text)
        print(f"\n  引号内视频链接: {url_patterns}")

        # 找常见的播放器变量
        for pattern in ['var.*?player', 'var.*?video', 'var.*?url', 'player_data', 'video_url']:
            matches = re.findall(r'[^;]*' + pattern + r'[^;]*;', r.text, re.IGNORECASE)
            for m in matches[:5]:
                clean = m.strip()[:300]
                print(f"\n  {pattern}: {clean}")

        # 查找隐藏的配置json
        configs = re.findall(r'player_?config[^=]*=[\s]*({[^;]+})', r.text, re.DOTALL)
        for i, c in enumerate(configs):
            print(f"\n  player_config [{i}]: {c[:500]}")

    except Exception as e:
        print(f"  错误: {e}")
