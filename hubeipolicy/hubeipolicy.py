# -*- coding: utf-8 -*-
import requests
from lxml import html, etree
import time
import csv
import re
import os
import json
from datetime import datetime
from urllib.parse import urljoin
import html as html_parser


class UniversalCrawler:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.encoding = self.config.get('encoding', 'utf-8')
        self.delay = self.config.get('request_delay', 1)
        self.detail_delay = self.config.get('detail_delay', 0.5)
        self.max_pages = self.config.get('max_pages', 0)
        self.source_type = self.config.get('source_type', 'html')

    # ==================== JSON API 模式 ====================
    def crawl_json_api(self):
        """从 JSON API 获取数据，可选访问详情页获取正文"""
        api_url = self.config['entry_url']
        print(f"→ 请求 API: {api_url}")
        resp = requests.get(api_url, headers=self.headers, timeout=15)
        resp.encoding = self.encoding
        data = resp.json()

        # 按 data_path 取数据列表
        data_path = self.config.get('data_path', 'data')
        items = data
        for key in data_path.split('.'):
            if isinstance(items, dict):
                items = items.get(key, [])
            else:
                break

        if not isinstance(items, list):
            print(f"错误: data_path '{data_path}' 未找到列表数据")
            return []

        print(f"API 返回 {len(items)} 条记录")

        field_map = self.config.get('item_fields', {})
        all_news = []

        for idx, item in enumerate(items, 1):
            # 从 JSON 字段映射
            news = {
                'title': str(item.get(field_map.get('title', 'title'), '')),
                'url': str(item.get(field_map.get('url', 'url'), '')),
                'publish_time': str(item.get(field_map.get('publish_time', 'publish_time'), '')),
                'source': str(item.get(field_map.get('source', 'source'), '')),
                'content': ''
            }

            # 访问详情页获取正文
            detail_url = str(item.get(field_map.get('url', 'url'), ''))
            if detail_url and self.config.get('detail_page'):
                print(f"  [{idx}/{len(items)}] {news['title'][:40]}...")
                detail = self.parse_detail_page(detail_url)
                news['content'] = detail.get('content', '')
                # 如果 JSON 没有时间/来源，用详情页的
                if not news['publish_time'] and detail.get('publish_time'):
                    news['publish_time'] = detail['publish_time']
                if not news['source'] and detail.get('source'):
                    news['source'] = detail['source']
                time.sleep(self.detail_delay)
            else:
                # 不抓正文，只取 JSON 里的元数据
                print(f"  [{idx}/{len(items)}] {news['title'][:40]}...")

            # 清理时间格式
            news['publish_time'] = news['publish_time'][:10] if news['publish_time'] else ''

            all_news.append(news)

        return all_news

    # ==================== HTML 模式（原有逻辑） ====================
    def fetch(self, url):
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.encoding = self.encoding
            resp.raise_for_status()
            return html.fromstring(resp.text)
        except Exception as e:
            print(f"请求失败 {url}: {e}")
            return None

    def extract_by_selector(self, element, selector, selector_type, is_multi=False):
        if not selector:
            return [] if is_multi else ''
        if selector_type == 'xpath':
            results = element.xpath(selector)
        else:
            results = element.cssselect(selector)
        if is_multi:
            return [self.clean_text(r) for r in results]
        return self.clean_text(results[0]) if results else ''

    def clean_text(self, text):
        if not text:
            return ''
        if isinstance(text, (etree._Element, html.HtmlElement)):
            text = text.text_content()
        text = str(text)
        text = re.sub(r'[\u200B\u200C\u200D\uFEFF\u00AD]', '', text)
        text = html_parser.unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def parse_list_page(self, tree, page_url):
        cfg = self.config['list_page']
        sel_type = cfg['selector_type']
        items = tree.xpath(cfg['item_selector']) if sel_type == 'xpath' else tree.cssselect(cfg['item_selector'])

        href_filter = cfg.get('href_filter')
        news_list = []
        for item in items:
            title = self.extract_by_selector(item, cfg.get('title_selector'), sel_type)
            if not title:
                continue
            link = self.extract_by_selector(item, cfg.get('link_selector'), sel_type)
            if link:
                full_url = urljoin(page_url, link)
                if cfg.get('link_prefix'):
                    full_url = urljoin(cfg['link_prefix'], link)
                if href_filter and not re.search(href_filter, full_url):
                    continue
                news_list.append({'title': title, 'url': full_url})
        return news_list

    def get_next_page_url(self, tree, current_url):
        pg_cfg = self.config.get('pagination')
        if not pg_cfg:
            return None
        if pg_cfg['type'] == 'next_selector':
            sel = pg_cfg['next_selector']
            sel_type = pg_cfg.get('selector_type', 'xpath')
            next_url = self.extract_by_selector(tree, sel, sel_type)
            if next_url:
                return urljoin(current_url, next_url)
        return None

    def parse_detail_page(self, url):
        tree = self.fetch(url)
        if tree is None:
            return {'title': '', 'publish_time': '', 'source': '', 'content': ''}

        cfg = self.config['detail_page']
        sel_type = cfg['selector_type']

        title = self.extract_by_selector(tree, cfg.get('title'), sel_type)
        time_raw = self.extract_by_selector(tree, cfg.get('publish_time'), sel_type)
        publish_time = ''
        if time_raw and cfg.get('time_regex'):
            match = re.search(cfg['time_regex'], time_raw)
            if match:
                publish_time = match.group(1)
        else:
            publish_time = time_raw

        source_raw = self.extract_by_selector(tree, cfg.get('source'), sel_type)
        source = ''
        if source_raw and cfg.get('source_regex'):
            match = re.search(cfg['source_regex'], source_raw)
            if match:
                source = match.group(1).strip()
        else:
            source = source_raw

        content_raw = self.extract_by_selector(tree, cfg.get('content'), sel_type, is_multi=True)
        content = '\n'.join(content_raw)

        if not publish_time:
            url_date = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
            if url_date:
                publish_time = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"

        return {'title': title, 'publish_time': publish_time, 'source': source, 'content': content}

    def crawl_html(self):
        all_news = []
        current_url = self.config['entry_url']
        page_num = 1

        while current_url:
            if self.max_pages > 0 and page_num > self.max_pages:
                break
            print(f"处理第 {page_num} 页: {current_url}")
            tree = self.fetch(current_url)
            if tree is None:
                break

            page_news = self.parse_list_page(tree, current_url)
            if not page_news:
                print("未解析到新闻列表，停止。")
                break

            print(f"本页 {len(page_news)} 条新闻，开始获取详情...")
            for idx, news in enumerate(page_news, 1):
                print(f"  [{idx}/{len(page_news)}] {news['title'][:40]}...")
                detail = self.parse_detail_page(news['url'])
                news.update(detail)
                time.sleep(self.detail_delay)

            all_news.extend(page_news)

            pg_cfg = self.config.get('pagination')
            if pg_cfg:
                if pg_cfg['type'] == 'next_selector':
                    current_url = self.get_next_page_url(tree, current_url)
                elif pg_cfg['type'] == 'url_pattern':
                    pattern = pg_cfg['url_pattern']
                    base_match = re.match(r'(.*?)(?:/index)?(?:\.htm|\.html)?$', current_url)
                    if not base_match:
                        break
                    base = base_match.group(1)
                    if page_num == 1 and pg_cfg.get('first_page_no_suffix', False):
                        next_url = f"{base}/index_1.htm"
                    else:
                        next_page_num = page_num + 1
                        next_url = pattern.replace('#{page}', str(next_page_num))
                    current_url = next_url
                else:
                    current_url = None
            else:
                current_url = None

            page_num += 1
            time.sleep(self.delay)

        return all_news

    # ==================== 统一入口 ====================
    def crawl(self):
        if self.source_type == 'json_api':
            return self.crawl_json_api()
        else:
            return self.crawl_html()

    def save_csv(self, news_list, output_dir='.'):
        if not news_list:
            print("无数据。")
            return
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(output_dir, f'{self.config["name"]}_{timestamp}.csv')
        fieldnames = ['title', 'publish_time', 'source', 'url', 'content']
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for news in news_list:
                row = {k: news.get(k, '') for k in fieldnames}
                writer.writerow(row)
        print(f"保存 {len(news_list)} 条到 {filename}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.json')
    output_dir = os.environ.get('OUTPUT_DIR', script_dir)

    crawler = UniversalCrawler(config_path)
    data = crawler.crawl()
    if data:
        crawler.save_csv(data, output_dir)
        print("示例:", data[0]['title'][:50], data[0]['publish_time'])
    else:
        print("无数据。")


if __name__ == '__main__':
    main()
