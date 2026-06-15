# -*- coding: utf-8 -*-
"""彻底挖掘商务部搜索数据源"""
import requests
import re
import json
from urllib.parse import quote

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://search.mofcom.gov.cn/',
}

keyword = quote('文化旅游')

# 1. 看 search.jsp 返回的全部 HTML（跳过 header/footer）
print('=== 搜索页 script 标签中的数据 ===')
r = requests.get(
    f'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword={keyword}&page=1',
    headers=headers, timeout=15
)
r.encoding = 'utf-8'

# 找所有 script 中赋值的数据
scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
for i, s in enumerate(scripts):
    if len(s) > 100 and ('search' in s.lower() or 'data' in s.lower() or 'result' in s.lower() or 'var ' in s.lower()):
        print(f'\n--- script #{i} ({len(s)}字符) ---')
        # 提取 var = 赋值的行
        vars = re.findall(r'var\s+(\w+)\s*=\s*(.{5,200})?;', s)
        for v in vars[:10]:
            print(f'  var {v[0]} = {v[1][:120]}')
        # 提取 URL
        urls = re.findall(r'https?://[^\s\'">,\\]+', s)
        for u in urls[:5]:
            print(f'  URL: {u[:150]}')
        # 打印前500字符
        if not vars and not urls:
            print(f'  {s.strip()[:300]}')

# 2. 尝试更广泛的 API
print('\n\n=== 尝试各种 API 路径 ===')
base = 'http://search.mofcom.gov.cn'
for path, method in [
    ('/swb/search/search', 'POST'),
    ('/swb/search/list', 'GET'),
    ('/swb/search/list.jsp', 'GET'),
    ('/swb/search/data.jsp', 'GET'),
    ('/irs-net/data/1.html', 'GET'),
    ('/irs-net/data/search', 'GET'),
    ('/api/search/list', 'GET'),
    ('/front/search', 'POST'),
]:
    try:
        params = {'searchword': keyword, 'page': '1', 'pageSize': '20'}
        if method == 'POST':
            r = requests.post(base + path, data=params, headers=headers, timeout=10)
        else:
            r = requests.get(base + path, params=params, headers=headers, timeout=10)
        ct = r.headers.get('Content-Type', '')[:50]
        if r.status_code == 200 and ('json' in ct or (len(r.text) < 5000 and len(r.text) > 10)):
            print(f'  {method} {path} → {r.status_code} {ct} {len(r.text)}chars')
            try:
                print(f'    {r.json()}')
            except:
                print(f'    {r.text[:200]}')
    except:
        pass

# 3. 看 webglobal.js
print('\n\n=== webglobal.js ===')
try:
    r = requests.get('https://www.mofcom.gov.cn/script/webglobal.js', headers=headers, timeout=10)
    r.encoding = 'utf-8'
    urls = re.findall(r'https?://[^\s\'">,\\]+', r.text)
    for u in sorted(set(urls)):
        if 'search' in u or 'data' in u or 'api' in u:
            print(f'  {u[:150]}')
except Exception as e:
    print(f'  失败: {e}')

# 4. 尝试 POST search.jsp 返回的内容中是否嵌入了搜索结果
print('\n\n=== search.jsp 返回 HTML - body 中间部分 ===')
r = requests.get(
    f'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword={keyword}&page=1',
    headers=headers, timeout=15
)
r.encoding = 'utf-8'
html = r.text
# 从中间5000字符开始找
mid = len(html) // 2
print(html[mid:mid+2000])
