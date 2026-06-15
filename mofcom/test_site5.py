# -*- coding: utf-8 -*-
"""探测商务部 POST /search 返回的 HTML"""
import requests
from lxml import html

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://search.mofcom.gov.cn/',
    'Content-Type': 'application/x-www-form-urlencoded',
}

# POST /search 获取搜索结果
data = {'searchword': '文化旅游', 'page': '1'}
r = requests.post('http://search.mofcom.gov.cn/search', data=data, headers=headers, timeout=15)
r.encoding = 'utf-8'
print(f'状态: {r.status_code}  长度: {len(r.text)}')

tree = html.fromstring(r.text)

# 找所有链接
links = tree.xpath('//a')
print(f'\n=== 链接总数: {len(links)} ===')
for a in links:
    text = a.text_content().strip()[:50]
    href = a.get('href', '')[:100]
    if text and len(text) > 5:
        print(f'  [{text}] → {href}')

# 找所有带 class/id 的容器元素
print('\n=== 容器元素 ===')
for tag in ['div', 'ul', 'section', 'article']:
    items = tree.xpath(f'//{tag}[@class or @id]')
    if items:
        print(f'  {tag}: {len(items)} 个')

# 找分页
print('\n=== 分页 ===')
pagers = tree.xpath('//*[contains(@class,"page")]//a/@href | //*[contains(text(),"下一页")]/@href | //*[contains(text(),"下页")]/@href')
for p in pagers[:10]:
    print(f'  {p[:100]}')

# 找 script 中的数据
import re
scripts = tree.xpath('//script/text()')
for s in scripts[:10]:
    if len(s) > 50:
        # 找可能的数据
        json_patterns = re.findall(r'(?:var|let|const)\s+\w+\s*=\s*(\[.*?\]);', s)
        for jp in json_patterns:
            if len(jp) > 20:
                print(f'\n  script内数据: {jp[:300]}')

# 试不同的 POST 参数
print('\n\n=== 测试不同参数 ===')
for params in [
    {'searchword': '文化旅游'},
    {'searchword': '文化旅游', 'page': '1'},
    {'searchword': '文旅', 'page': '1'},
    {'keyword': '文化旅游', 'page': '1'},
]:
    r2 = requests.post('http://search.mofcom.gov.cn/search', data=params, headers=headers, timeout=10)
    r2.encoding = 'utf-8'
    # 判断是否有搜索结果（排除纯导航链接）
    cnt = len(html.fromstring(r2.text).xpath('//a'))
    print(f'  {params} → {cnt} 个链接')
