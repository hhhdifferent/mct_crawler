# -*- coding: utf-8 -*-
"""深入探测商务部搜索结果页"""
import requests
import re
from lxml import html

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}

url = 'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword=文化旅游&page=1'
resp = requests.get(url, headers=headers, timeout=15)
resp.encoding = 'utf-8'
tree = html.fromstring(resp.text)

print(f'页面长度: {len(resp.text)} 字符')

# 1. 找分页/总数
total = re.search(r'(?:共|找到|约|about)\s*(\d[\d,]*)\s*(?:条|项|篇|结果|result)', resp.text)
if total:
    print(f'结果总数: {total.group(1)}')

# 2. 找所有链接
as_el = tree.xpath('//a')
print(f'\n=== 所有链接 ({len(as_el)}条) ===')
count = 0
for a in as_el:
    href = a.get('href', '')
    text = a.text_content().strip()[:60]
    if href and len(text) > 10:
        print(f'  [{text}] → {href[:100]}')
        count += 1
        if count >= 20:
            break

# 3. 找结果列表容器
print('\n=== 带id/class的容器 ===')
containers = tree.xpath('//*[@id or @class][.//a]')
for c in containers[:15]:
    cid = c.get('id', '') 
    ccls = c.get('class', '')
    links = c.xpath('.//a')
    texts = [l.text_content().strip()[:30] for l in links if l.text_content().strip()]
    if texts:
        print(f'  <{c.tag}> id="{cid[:30]}" class="{ccls[:50]}"> → {len(links)}个链接: {texts[:3]}')

# 4. 尝试找 JSON/API
print('\n=== 搜索 API JSON ===')
api_urls = [
    'https://search.mofcom.gov.cn/swb/search/search.jsp',
    'https://search.mofcom.gov.cn/swb/search/search.do',
]
for au in api_urls:
    try:
        # POST
        r = requests.post(au, data={'searchword': '文化旅游', 'page': '1'}, headers=headers, timeout=10)
        print(f'  POST {au} → {r.status_code}  {r.headers.get("Content-Type","")[:40]}  {len(r.text)}chars')
        if 'json' in r.headers.get('Content-Type', ''):
            print(f'    JSON: {r.text[:500]}')
    except Exception as e:
        print(f'  POST {au} → 失败: {e}')

# 5. 找分页
print('\n=== 分页元素 ===')
pagers = tree.xpath('//*[contains(@class,"page")]//a | //*[contains(@class,"pager")]//a')
for p in pagers[:10]:
    print(f'  {p.text_content().strip()} → {p.get("href","")[:80]}')

# 6. 查看页面核心HTML片段
print('\n=== 页面核心HTML (2000字符) ===')
# 只取body中间部分
body = resp.text
# 找到结果区域
idx = body.find('文化旅游')
if idx > 0:
    print(body[max(0,idx-200):idx+500])
