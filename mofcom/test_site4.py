# -*- coding: utf-8 -*-
"""探测商务部搜索API"""
import requests
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json',
    'Referer': 'https://search.mofcom.gov.cn/',
}

# 1. 测试 getTips API
print('=== getTips ===')
for body in [
    {'keyword': '文化旅游', 'page': 1, 'pageSize': 20},
    {'searchWord': '文化旅游', 'pageNo': 1, 'pageSize': 20},
    {'q': '文化旅游', 'page': 1},
    {'word': '文化旅游'},
    '文化旅游',
]:
    try:
        r = requests.post(
            'http://search.mofcom.gov.cn/getTips',
            json=body if isinstance(body, dict) else {'keyword': body},
            headers=headers, timeout=10
        )
        print(f'  body={body} → status={r.status_code} len={len(r.text)}')
        if r.status_code == 200:
            try:
                data = r.json()
                print(f'  JSON keys: {list(data.keys())[:10]}')
                print(f'  {json.dumps(data, ensure_ascii=False)[:400]}')
            except:
                print(f'  text: {r.text[:300]}')
    except Exception as e:
        print(f'  body={body} → 失败: {e}')

# 2. 测试其他 API 路径
print('\n=== 其他API路径 ===')
base = 'http://search.mofcom.gov.cn'
for path, method in [
    ('/swb/search/search.do', 'POST'),
    ('/swb/search/search.do', 'GET'),
    ('/search', 'POST'),
    ('/search/search.jsp', 'POST'),
    ('/api/search', 'POST'),
    ('/api/search', 'GET'),
    ('/swb/search/search.jsp', 'GET'),
]:
    try:
        params = {'searchword': '文化旅游', 'page': '1'}
        if method == 'POST':
            r = requests.post(base + path, data=params, headers=headers, timeout=10)
        else:
            r = requests.get(base + path, params=params, headers=headers, timeout=10)
        ct = r.headers.get('Content-Type', '')
        print(f'  {method} {path} → {r.status_code}  {ct[:40]}  {len(r.text)}chars')
        if 'json' in ct and r.text:
            print(f'    {r.text[:300]}')
    except Exception as e:
        print(f'  {method} {path} → 失败: {e}')

# 3. 搜索结果页实际HTML分析 - 看script标签里的数据
print('\n=== 搜索页HTML中的内嵌数据 ===')
try:
    r = requests.get(
        'https://search.mofcom.gov.cn/swb/search/search.jsp?searchword=文化旅游&page=1',
        headers={'User-Agent': 'Mozilla/5.0'}, timeout=15
    )
    r.encoding = 'utf-8'
    # 找 JSON 数据块
    for m in __import__('re').finditer(r'(?:\"|")(?:data|result|list|items|records)(?:\"|")\s*:\s*\[', r.text):
        print(f'  找到数据块: ...{r.text[m.start():m.start()+300]}...')
    # 找所有 script 里的变量赋值
    jsons = __import__('re').findall(r'=\s*(\[[^\]]{20,500}\])', r.text)
    for j in jsons[:5]:
        print(f'  可能的JSON: {j[:200]}')
except Exception as e:
    print(f'  失败: {e}')
