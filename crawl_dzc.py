#!/usr/bin/env python3
"""爬取低智商犯罪 第24集 可用在线资源"""
import requests
import re
import json
import sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def search_goudaitv():
    """狗带TV搜索"""
    try:
        url = "https://www.goudaitv.com/search"
        r = session.get(url, params={"keyword": "低智商犯罪"}, timeout=15)
        r.encoding = "utf-8"
        # 找播放页链接
        links = re.findall(r'href="(/vodplay/\d+-\d-24\.html)"', r.text)
        if links:
            return f"https://www.goudaitv.com{links[0]}"
        # 找详情页
        detail = re.findall(r'href="(/voddetail/\d+\.html)"', r.text)
        if detail:
            return f"https://www.goudaitv.com{detail[0]}"
    except Exception as e:
        return f"[狗带TV错误] {e}"
    return "未找到"


def search_ddrk():
    """低端影视搜索"""
    try:
        url = "https://ddrk.me/search/"
        r = session.get(url, params={"q": "低智商犯罪"}, timeout=15)
        r.encoding = "utf-8"
        links = re.findall(r'href="(https?://ddrk\.me/[^"]+)"', r.text)
        for link in links:
            if "dizhishang" in link.lower() or "低智商" in link:
                # 查第24集播放页
                r2 = session.get(link, timeout=15)
                r2.encoding = "utf-8"
                ep_links = re.findall(r'href="([^"]*24[^"]*)"', r2.text)
                for el in ep_links:
                    if el.startswith("/"):
                        return f"https://ddrk.me{el}"
                    return el
                return link
    except Exception as e:
        return f"[低端影视错误] {e}"
    return "未找到"


def search_1080pzy():
    """1080P影视搜索"""
    try:
        url = "https://www.1080pzy.com/search/"
        r = session.get(url, params={"wd": "低智商犯罪"}, timeout=15)
        r.encoding = "utf-8"
        links = re.findall(r'href="(/voddetail/\d+\.html)"', r.text)
        if links:
            detail_url = f"https://www.1080pzy.com{links[0]}"
            r2 = session.get(detail_url, timeout=15)
            r2.encoding = "utf-8"
            # 找第24集
            ep24 = re.findall(r'href="(/vodplay/\d+-1-24\.html)"', r2.text)
            if ep24:
                return f"https://www.1080pzy.com{ep24[0]}"
            # 找所有播放链接
            all_ep = re.findall(r'href="(/vodplay/\d+-1-\d+\.html)"', r2.text)
            if all_ep:
                return f"https://www.1080pzy.com{all_ep[-1]}"  # 最后一集
            return detail_url
    except Exception as e:
        return f"[1080P影视错误] {e}"
    return "未找到"


def search_eagcar():
    """草民影院 - 直接试第24集"""
    try:
        # 之前找到的是 99405
        urls_to_try = [
            "https://www.eagcar.com/vodplay/99405-1-24.html",
            "https://www.eagcar.com/voddetail/99405.html",
        ]
        for url in urls_to_try:
            r = session.get(url, timeout=15, allow_redirects=True)
            r.encoding = "utf-8"
            if r.status_code == 200 and "低智商犯罪" in r.text:
                # 看看有没有播放源
                if "player" in r.text or "video" in r.text or "iframe" in r.text:
                    return url
                # 找iframe里的实际视频源
                iframes = re.findall(r'src="(https?://[^"]+)"', r.text)
                for iframe in iframes:
                    if "player" in iframe.lower() or "m3u8" in iframe or "vod" in iframe:
                        return f"{url} (iframe: {iframe})"
    except Exception as e:
        return f"[草民影院错误] {e}"
    return "未找到"


def main():
    results = {}
    
    print("=" * 60)
    print("  爬取《低智商犯罪》第24集可用资源")
    print("=" * 60)
    
    print("\n[1/4] 搜索狗带TV...")
    results["狗带TV"] = search_goudaitv()
    print(f"  -> {results['狗带TV']}")
    
    print("\n[2/4] 搜索1080P影视...")
    results["1080P影视"] = search_1080pzy()
    print(f"  -> {results['1080P影视']}")
    
    print("\n[3/4] 搜索低端影视...")
    results["低端影视"] = search_ddrk()
    print(f"  -> {results['低端影视']}")
    
    print("\n[4/4] 检查草民影院...")
    results["草民影院"] = search_eagcar()
    print(f"  -> {results['草民影院']}")
    
    print("\n" + "=" * 60)
    print("  可用资源汇总")
    print("=" * 60)
    valid = {k: v for k, v in results.items() if v and "错误" not in v and v != "未找到"}
    if valid:
        for name, url in valid.items():
            print(f"  ✅ {name}: {url}")
    else:
        print("  ❌ 以上站点都未找到，尝试其他方案...")
    
    print("\n输出JSON方便解析:")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
