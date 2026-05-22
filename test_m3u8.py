#!/usr/bin/env python3
"""测试 m3u8，带完整请求头"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.eagcar.com/",
    "Origin": "https://www.eagcar.com",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

url = "https://v11.ppqrrs.com/wjv11/202605/13/VVZDa26PgN92/video/index.m3u8"
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"状态码: {r.status_code}")
if r.status_code == 200:
    print(f"内容:\n{r.text[:500]}")
else:
    print(f"失败: {r.text[:300]}")
    # 可能 Referer 不对，试试不同 referer
    for ref in ["https://www.eagcar.com/vodplay/99405-1-24.html", "https://v11.ppqrrs.com/"]:
        HEADERS["Referer"] = ref
        r2 = requests.get(url, headers=HEADERS, timeout=15)
        print(f"Referer={ref} -> 状态码: {r2.status_code}")
