# -*- coding: utf-8 -*-
"""探测商务部网站"""
import requests
import re
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}

# 1. 首页
resp = requests.get('https://www.mofcom.gov.cn/', headers=headers, timeout=15)
resp.encoding = 'utf-8'
print(f'首页: 状态={resp.status_code}  长度={len(resp.text)}')

# 2. 找 JS 文件
js_files = re.findall(r'<script[^>]*src=["\']([^"\']+\.js[^"\']*)["\']', resp.text)
print(f'\n=== JS文件 ({len(js_files)}) ===')
for j in js_files[:15]:
    if 'jquery' not in j.lower() and 'bootstrap' not in j.lower():
        print(f'  {j[:100]}')

# 3. 找 API / JSON
apis = re.findall(r'(https?://[^\s\'"<>]+\.json[^\s\'"<>]*|https?://[^\s\'"<>]+/api/[^\s\'"<>]+)', resp.text)
print(f'\n=== 可能的API ===')
for a in apis[:10]:
    print(f'  {a[:120]}')

# 4. 找 search 相关
searches = re.findall(r'["\']([^"\']*(?:search|sousuo|query)[^"\']*)["\']', resp.text, re.IGNORECASE)
print(f'\n=== 搜索相关 ===')
for s in searches[:10]:
    print(f'  {s[:120]}')

# 5. 尝试搜索 API
print(f'\n=== 搜索API探测 ===')
search_urls = [
    'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword=文化旅游&page=1',
    'https://www.mofcom.gov.cn/search/search.shtml?searchword=文化旅游',
    'https://www.mofcom.gov.cn/article/',
]
for u in search_urls:
    try:
        r = requests.get(u, headers=headers, timeout=10)
        print(f'  {u[:80]} → {r.status_code}  {len(r.text)}chars  {r.headers.get("Content-Type","")[:40]}')
    except Exception as e:
        print(f'  {u[:80]} → 失败: {str(e)[:60]}')
