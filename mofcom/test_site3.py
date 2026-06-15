# -*- coding: utf-8 -*-
"""分析商务部 search.js / index.js"""
import requests
import re

headers = {'User-Agent': 'Mozilla/5.0'}

# 抓 search.js
try:
    resp = requests.get(
        'https://www.mofcom.gov.cn/cms_files/webshangwubu/tplobject/defaultSet/'
        '229896a16318433a8f9940c8ec5d46c8/images/search.js',
        headers=headers, timeout=15
    )
    resp.encoding = 'utf-8'
    js = resp.text
    print(f'search.js: {len(js)} 字符\n')

    # 找所有完整 URL
    urls = re.findall(r'https?://[^\s\'">,\\]+', js)
    print('=== 所有URL ===')
    for u in sorted(set(urls)):
        print(f'  {u[:150]}')

    # 找搜索相关 API
    print('\n=== 搜索/数据 API ===')
    for m in re.finditer(r'(?:url|src|href|action)\s*[=:]\s*[\'"]([^\'"]*(?:search|irs|query|json|api|data|fetch|getList|.do|.jsp)[^\'"]*)[\'"]', js, re.I):
        print(f'  {m.group(1)[:150]}')

    # 找 ajax/fetch
    print('\n=== AJAX/Fetch 调用 ===')
    for m in re.finditer(r'(?:ajax|get|post|fetch)\s*\([^)]{20,300}\)', js, re.I):
        print(f'  {m.group()[:200]}')

except Exception as e:
    print(f'search.js 失败: {e}')

# index.js
try:
    resp2 = requests.get(
        'https://www.mofcom.gov.cn/cms_files/webshangwubu/tplobject/defaultSet/'
        '229896a16318433a8f9940c8ec5d46c8/images/index.js',
        headers=headers, timeout=15
    )
    resp2.encoding = 'utf-8'
    print(f'\n\nindex.js: {len(resp2.text)} 字符')
    urls2 = re.findall(r'https?://[^\s\'">,\\]+', resp2.text)
    for u in sorted(set(urls2)):
        print(f'  {u[:150]}')
    api2 = re.findall(r'[\'"](/[^\'"]*(?:search|irs|query|json|api|data)[^\'"]*)[\'"]', resp2.text, re.I)
    if api2:
        print('\n=== API ===')
        for a in api2:
            print(f'  {a[:150]}')
except:
    pass

# 试一下搜索结果页的 iframe
print('\n\n=== 搜索结果页 iframe 探测 ===')
try:
    r = requests.get(
        'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword=文化旅游&page=1',
        headers=headers, timeout=15
    )
    r.encoding = 'utf-8'
    # 找 iframe
    for m in re.finditer(r'<iframe[^>]*src=["\']([^"\']+)["\']', r.text):
        print(f'  iframe: {m.group(1)[:150]}')
    # 找 data-url 之类
    for m in re.finditer(r'data-[a-z]*(?:url|src|api)\s*=\s*["\']([^"\']+)["\']', r.text, re.I):
        print(f'  data-url: {m.group(1)[:150]}')
except:
    pass
