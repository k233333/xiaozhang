#!/usr/bin/env python3
"""提取草民影院的真实视频源"""
import requests
import re
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}

session = requests.Session()
session.headers.update(HEADERS)

url = "https://www.eagcar.com/vodplay/99405-1-24.html"
r = session.get(url, timeout=15)
r.encoding = "utf-8"

# 提取完整的 player_aaaa 变量
# 它可能跨多行
match = re.search(r'var player_aaaa=({.*?});', r.text, re.DOTALL)
if match:
    raw = match.group(1)
    print("=== 原始 player_aaaa ===")
    print(raw[:2000])
    print()
    
    # 尝试 JSON 解析（注意里面是 JS 对象，需要处理转义）
    # 先处理单引号
    cleaned = raw.replace("'", '"')
    try:
        data = json.loads(cleaned)
        print("=== JSON 解析成功 ===")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\n视频URL: {data.get('url', 'N/A')}")
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        # 手动提取 url 字段
        url_match = re.search(r'"url":"(.*?)"', raw)
        if url_match:
            url_val = url_match.group(1).replace('\\/', '/')
            print(f"\n手动提取视频URL: {url_val}")

# 也看看其他script里的完整内容
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
for i, s in enumerate(scripts):
    if 'player_aaaa' in s:
        print(f"\n=== Script [{i}] 完整内容 ===")
        print(s[:5000])
