# -*- coding: utf-8 -*-
"""
通用爬虫模板，支持两种模式：
  json_api  — 直接调 JSON 接口（如湖北文旅厅、中国政府网）
  html      — 解析静态 HTML（如文旅部时政要闻）

用法：python crawler.py config.json
"""
import csv
import os
import re
import json
import time
import sys
import traceback
from datetime import datetime
from urllib.parse import urljoin, quote

import requests
from lxml import html as lxml_html, etree
import html as html_lib


class Crawler:
    def __init__(self, config):
        self.cfg = config
        self.name = config.get('name', 'unnamed')
        self.source_type = config.get('source_type', 'html')
        self.delay = config.get('request_delay', 1)
        self.max_pages = config.get('max_pages', 0)
        self.output_dir = os.environ.get('OUTPUT_DIR', '.')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/149.0.0.0 Safari/537.36'
        })

    # ==================== JSON API ====================
    def run_api(self):
        api = self.cfg['api']
        url = api['url']
        method = api.get('method', 'POST').upper()
        headers = api.get('headers', {})
        body_template = api.get('body', {})
        data_path = api.get('data_path', 'data')
        pager_path = api.get('pager_path', '')
        keywords = api.get('keywords', [''])
        page_size = api.get('page_size', 10)
        field_map = api.get('field_map', {})
        code_success = api.get('code_success', None)
        code_path = api.get('code_path', '')

        all_items = []

        for kw in keywords:
            print(f'\n搜索: {kw}')
            page_no = 1

            while True:
                body = json.loads(json.dumps(body_template))  # deep copy
                body.update({api.get('keyword_field', 'searchWord'): kw})
                if api.get('page_field'):
                    body[api['page_field']] = page_no
                if api.get('page_size_field'):
                    body[api['page_size_field']] = page_size

                try:
                    if method == 'POST':
                        resp = self.session.post(url, json=body, headers=headers, timeout=20)
                    else:
                        resp = self.session.get(url, params=body, headers=headers, timeout=20)
                    data = resp.json()
                except Exception as e:
                    print(f'  请求失败: {e}')
                    break

                # 检查状态码
                if code_path:
                    parts = code_path.split('.')
                    val = data
                    for p in parts:
                        if isinstance(val, dict):
                            val = val.get(p, {})
                    if code_success is not None and val != code_success:
                        print(f'  状态异常: {val}')
                        break

                # 取数据列表
                items = data
                for key in data_path.split('.'):
                    if isinstance(items, dict):
                        items = items.get(key, [])
                    elif isinstance(items, list):
                        break
                    else:
                        items = []
                        break
                if not isinstance(items, list):
                    items = []

                # 取分页信息
                pager = data
                if pager_path:
                    for key in pager_path.split('.'):
                        if isinstance(pager, dict):
                            pager = pager.get(key, {})
                    total = pager.get('total', 0)
                    page_count = pager.get('pageCount', 0)
                    if page_no == 1:
                        print(f'  共 {total} 条, {page_count} 页')

                if not items:
                    break

                for item in items:
                    row = {}
                    for csv_col, json_key in field_map.items():
                        val = item
                        for k in json_key.split('.'):
                            if isinstance(val, dict):
                                val = val.get(k, '')
                            else:
                                val = ''
                                break
                        row[csv_col] = str(val).strip() if val else ''
                    row['keyword'] = kw
                    # 清理 HTML 标签
                    if 'title' in row:
                        row['title'] = re.sub(r'<[^>]+>', '', row['title']).strip()
                    all_items.append(row)

                print(f'  第 {page_no} 页: {len(items)} 条')

                if len(items) < page_size or (self.max_pages and page_no >= self.max_pages):
                    break
                page_no += 1
                time.sleep(self.delay)

            time.sleep(1)

        return all_items

    # ==================== HTML ====================
    def run_html(self):
        hcfg = self.cfg['html']
        entry_url = hcfg['entry_url']
        list_cfg = hcfg['list_page']
        detail_cfg = hcfg.get('detail_page', {})
        pagination = hcfg.get('pagination', {})

        all_items = []
        cur_url = entry_url
        page_num = 1

        while cur_url:
            if self.max_pages and page_num > self.max_pages:
                break
            print(f'\n第 {page_num} 页: {cur_url}')

            try:
                resp = self.session.get(cur_url, timeout=15)
                resp.encoding = self.cfg.get('encoding', 'utf-8')
                tree = lxml_html.fromstring(resp.text)
            except Exception as e:
                print(f'  请求失败: {e}')
                break

            # 提取列表项
            sel = list_cfg['item_selector']
            sel_type = list_cfg.get('selector_type', 'xpath')
            items = tree.xpath(sel) if sel_type == 'xpath' else tree.cssselect(sel)

            if not items:
                print('  无列表项')
                break

            print(f'  找到 {len(items)} 条')

            for item in items:
                title = self._extract(item, list_cfg.get('title_selector', ''), sel_type)
                link = self._extract(item, list_cfg.get('link_selector', ''), sel_type)
                if not title or not link:
                    continue
                full_url = urljoin(cur_url, link)

                row = {'title': title, 'url': full_url, 'publish_time': '', 'source': ''}

                # 抓详情页
                if detail_cfg:
                    try:
                        dresp = self.session.get(full_url, timeout=15)
                        dresp.encoding = self.cfg.get('encoding', 'utf-8')
                        dtree = lxml_html.fromstring(dresp.text)
                        ds = detail_cfg.get('selector_type', 'xpath')

                        detail_title = self._extract(dtree, detail_cfg.get('title', ''), ds)
                        time_raw = self._extract(dtree, detail_cfg.get('publish_time', ''), ds)
                        source_raw = self._extract(dtree, detail_cfg.get('source', ''), ds)

                        if time_raw and detail_cfg.get('time_regex'):
                            m = re.search(detail_cfg['time_regex'], time_raw)
                            if m:
                                row['publish_time'] = m.group(1)
                        else:
                            row['publish_time'] = time_raw

                        if source_raw and detail_cfg.get('source_regex'):
                            m = re.search(detail_cfg['source_regex'], source_raw)
                            if m:
                                row['source'] = m.group(1).strip()
                        else:
                            row['source'] = source_raw

                        content_parts = self._extract(dtree, detail_cfg.get('content', ''), ds, multi=True)
                        row['content'] = '\n'.join([self._clean_text(c) for c in content_parts])

                        if detail_title:
                            row['title'] = detail_title

                    except Exception as e:
                        print(f'    详情页失败({full_url[:40]}): {e}')

                    time.sleep(hcfg.get('detail_delay', 0.5))

                # 兜底：从 URL 提取时间
                if not row.get('publish_time'):
                    m = re.search(r'/(\d{4})(\d{2})/(\d{2})/', full_url)
                    if m:
                        row['publish_time'] = f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

                all_items.append(row)

            # 翻页
            if not pagination:
                break
            cur_url = self._next_page(tree, cur_url, page_num, pagination)
            page_num += 1
            time.sleep(self.delay)

        return all_items

    def _extract(self, element, selector, sel_type, multi=False):
        if not selector:
            return [] if multi else ''
        results = element.xpath(selector) if sel_type == 'xpath' else element.cssselect(selector)
        if multi:
            return [self._clean_text(r) for r in results]
        return self._clean_text(results[0]) if results else ''

    def _clean_text(self, text):
        if not text:
            return ''
        if isinstance(text, (etree._Element, lxml_html.HtmlElement)):
            text = text.text_content()
        text = str(text)
        text = html_lib.unescape(text)
        text = re.sub(r'[\u200B\u200C\u200D\uFEFF\u00AD]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _next_page(self, tree, cur_url, page_num, cfg):
        ptype = cfg.get('type', '')
        if ptype == 'selector':
            sel = cfg['next_selector']
            st = cfg.get('selector_type', 'xpath')
            href = self._extract(tree, sel, st)
            return urljoin(cur_url, href) if href else None
        elif ptype == 'url_pattern':
            pattern = cfg.get('pattern', '')
            if '#{page}' in pattern:
                return pattern.replace('#{page}', str(page_num + 1))
        return None

    # ==================== 统一入口 ====================
    def run(self):
        if self.source_type == 'json_api':
            items = self.run_api()
        elif self.source_type == 'html':
            items = self.run_html()
        else:
            print(f'不支持的类型: {self.source_type}')
            return

        if items:
            self._save(items)
        else:
            print('无数据')

    def _save(self, items):
        os.makedirs(self.output_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(self.output_dir, f'{self.name}_{ts}.csv')

        # 确定表头
        if items:
            fieldnames = list(items[0].keys())
        else:
            fieldnames = ['title', 'url', 'publish_time', 'source']

        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in items:
                writer.writerow({k: row.get(k, '') for k in fieldnames})
        print(f'\n保存 {len(items)} 条到 {filename}')


# ============ CLI ============
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python crawler.py <config.json>')
        print('示例: python crawler.py guojiawenlv/config.json')
        sys.exit(1)

    config_path = sys.argv[1]
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    crawler = Crawler(cfg)
    crawler.output_dir = os.path.dirname(os.path.abspath(config_path))
    crawler.run()
