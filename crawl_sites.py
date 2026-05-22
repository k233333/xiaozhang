#!/usr/bin/env python3
"""多站点爬取低智商犯罪第24集实际视频源"""
import requests
import re
import json

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
})


def extract_player_config(html):
    """从页面提取播放器配置中的视频URL"""
    results = []
    # 各种常见播放器变量名
    json_matches = re.findall(r'player_(\w+)\s*=\s*({.*?});', html, re.DOTALL)
    for name, raw in json_matches:
        try:
            cleaned = raw.replace("'", '"')
            data = json.loads(cleaned)
            if 'url' in data:
                u = data['url'].replace('\\/', '/')
                results.append(u)
        except:
            pass
    
    # 直接找m3u8链接
    direct = re.findall(r'https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*', html)
    results.extend(direct)
    
    return list(set(results))


def try_site(name, search_url, detail_pattern, play_pattern):
    result = {"name": name, "status": "未找到", "video_urls": [], "play_url": ""}
    
    try:
        r = session.get(search_url, timeout=15)
        r.encoding = "utf-8"
        
        details = re.findall(detail_pattern, r.text)
        if not details:
            result["status"] = "未匹配到详情页"
            return result
        
        d = details[0]
        detail_url = d if d.startswith("http") else f"https://{name}{d}"
        
        r2 = session.get(detail_url, timeout=15)
        r2.encoding = "utf-8"
        
        plays = re.findall(play_pattern, r2.text)
        if not plays:
            result["status"] = f"详情页无第24集: {detail_url}"
            result["play_url"] = detail_url
            return result
        
        p = plays[0]
        play_url = p if p.startswith("http") else f"https://{name}{p}"
        
        r3 = session.get(play_url, timeout=15)
        r3.encoding = "utf-8"
        
        video_urls = extract_player_config(r3.text)
        if video_urls:
            result["status"] = "成功"
            result["video_urls"] = video_urls
            result["play_url"] = play_url
        else:
            result["status"] = f"播放页无视频源"
            result["play_url"] = play_url
    
    except Exception as e:
        result["status"] = f"错误: {str(e)[:100]}"
    
    return result


def main():
    site_list = [
        {
            "name": "www.goudaitv.com",
            "search_url": "https://www.goudaitv.com/search?keyword=低智商犯罪",
            "detail_pattern": r'href="(/voddetail/\d+\.html)"',
            "play_pattern": r'href="(/vodplay/\d+-1-24\.html)"',
        },
        {
            "name": "www.cicilady.org",
            "search_url": "https://www.cicilady.org/search/低智商犯罪.html",
            "detail_pattern": r'href="(/voddetail/\d+\.html)"',
            "play_pattern": r'href="(/vodplay/\d+-1-24\.html)"',
        },
        {
            "name": "www.kankanwu.com",
            "search_url": "https://www.kankanwu.com/search/低智商犯罪.html",
            "detail_pattern": r'href="(/voddetail/\d+\.html)"',
            "play_pattern": r'href="(/vodplay/\d+-1-24\.html)"',
        },
        {
            "name": "www.tiankong.tv",
            "search_url": "https://www.tiankong.tv/search/低智商犯罪.html",
            "detail_pattern": r'href="(/voddetail/\d+\.html)"',
            "play_pattern": r'href="(/vodplay/\d+-1-24\.html)"',
        },
    ]
    
    all_results = []
    for site in site_list:
        print(f"\n[爬取] {site['name']}...", end=" ", flush=True)
        result = try_site(**site)
        all_results.append(result)
        print(f"{result['status']}")
        if result.get("video_urls"):
            for v in result["video_urls"]:
                print(f"  🎬 {v}")
        if result.get("play_url"):
            print(f"  📄 {result['play_url']}")

    print("\n" + "=" * 60)
    print("结果汇总")
    print("=" * 60)
    
    found = [r for r in all_results if r["video_urls"]]
    if found:
        for r in found:
            print(f"\n✅ {r['name']}:")
            for v in r["video_urls"]:
                print(f"   {v}")
            print(f"   播放页: {r.get('play_url', 'N/A')}")
        best = found[0]
        print(f"\n\n最佳视频源: {best['video_urls'][0]}")
    else:
        print("所有站点均未提取到视频源")
        for r in all_results:
            print(f"  {r['name']}: {r['status']}")


if __name__ == "__main__":
    main()
