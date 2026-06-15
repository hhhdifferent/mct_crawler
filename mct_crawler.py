# -*- coding: utf-8 -*-
import requests
from lxml import html
import time
import csv
import re
import os
import sys
from datetime import datetime
from urllib.parse import urljoin
import html as html_parser

# 配置
BASE_URL = "https://www.mct.gov.cn"
START_URL = "https://www.mct.gov.cn/whzx/szyw/index.htm"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.mct.gov.cn/',
    'Accept-Language': 'zh-CN,zh;q=0.9'
}
REQUEST_DELAY = 1
DETAIL_DELAY = 0.5

# GitHub Actions 环境变量控制
MAX_PAGES = int(os.environ.get('MAX_PAGES', '0'))  # 0=全部页面
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', '.')  # 输出目录


def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        resp.raise_for_status()
        return html.fromstring(resp.text)
    except Exception as e:
        print(f"  请求失败 {url}: {e}")
        return None


def parse_news_list(tree, page_url):
    news_items = []
    links = tree.xpath('//td[1]/a')
    if not links:
        links = tree.xpath('//a[contains(@href, "szyw") or contains(@href, "/2026-")]')
    for link in links:
        title = link.text.strip() if link.text else ''
        href = link.get('href')
        if title and href:
            full_url = urljoin(page_url, href)
            if not any(item['url'] == full_url for item in news_items):
                news_items.append({'title': title, 'url': full_url})
    return news_items


def get_next_page_url(tree, current_url):
    """
    获取下一页URL。
    mct.gov.cn 的分页链接由 JS 动态生成，静态 HTML 中不存在。
    因此按 URL 规律直接构造：index.htm → index_1.htm → index_2.htm → ...
    """
    import re
    # 匹配 /whzx/szyw/index.htm 或 /whzx/szyw/index_N.htm
    match = re.match(r'(.*/whzx/szyw/index)(_(\d+))?\.htm', current_url)
    if match:
        base = match.group(1)  # e.g. ".../index"
        suffix = match.group(3)  # e.g. None (page 1) or "1" (page 2), "2" (page 3)
        if suffix is None:
            # 第1页 index.htm → 第2页 index_1.htm
            next_url = f'{base}_1.htm'
        else:
            page_n = int(suffix) + 1
            next_url = f'{base}_{page_n}.htm'
        print(f"    → 下一页: {next_url}")
        return next_url

    # 兜底：尝试 XPath 找下一页链接（其他网站可能有用）
    next_link = tree.xpath('/html/body/div[6]/div[2]/div[2]/div/span[4]/a')
    if next_link and next_link[0].get('href'):
        href = next_link[0].get('href')
        if href and 'javascript' not in href and 'void' not in href:
            return urljoin(current_url, href)

    print(f"    ✗ 无法构造下一页URL")
    return None


def clean_text_ex(text):
    """增强清理：去除零宽空格、不可见控制字符、HTML实体残留"""
    if not text:
        return ''
    # 替换已知乱码
    text = text.replace('ENSP', ' ').replace('&ensp;', ' ').replace('&emsp;', '  ')
    # 移除零宽空格 \u200B, \u200C, \u200D, \uFEFF 等
    text = re.sub(r'[\u200B\u200C\u200D\uFEFF]', '', text)
    # 移除软连字符 \u00AD 等
    text = re.sub(r'[\u00AD]', '', text)
    # 移除所有不可见控制字符（保留换行、回车、制表符，但后续会替换为空格）
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    # HTML实体反转义
    text = html_parser.unescape(text)
    # 合并多余空白字符（包括换行、制表）为单个空格
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_article_detail(url):
    tree = fetch_page(url)
    if tree is None:
        return {'title': '', 'publish_time': '', 'source': '', 'content': ''}

    # 标题
    title = ''
    ti = tree.xpath('//*[@id="ti"]')
    if ti:
        title = ti[0].text_content().strip()
    if not title:
        h1 = tree.xpath('//h1')
        if h1:
            title = h1[0].text_content().strip()

    # 时间和来源
    publish_time = ''
    source = ''

    # ------ 时间提取：gov.cn / mct.gov.cn 兼容 ------
    # 优先顺序：meta标签 > 特定class/id > 特征文本

    # 1) meta 标签（最可靠）
    time_candidates = tree.xpath('//meta[@property="article:published_time"]/@content')
    if not time_candidates:
        time_candidates = tree.xpath('//meta[@name="publishdate"]/@content')

    # 2) gov.cn：class="pages-date" 或 id="PubTime"
    if not time_candidates:
        time_candidates = tree.xpath('//span[contains(@class, "pages-date")]/text()')
    if not time_candidates:
        time_candidates = tree.xpath('//span[@id="PubTime"]/text()')

    # 3) mct.gov.cn 新版：包含日期特征的文本（优先匹配与URL一致的日期）
    if not time_candidates:
        # 从URL提取年月用于校验
        url_match = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
        if url_match:
            url_year, url_month, url_day = url_match.groups()
            # 找与URL年月日完全匹配的日期文本
            time_candidates = tree.xpath(
                f"//text()[contains(., '{url_year}-{url_month}-{url_day}')]"
            )
        if not time_candidates:
            # 找包含年份且格式像日期的文本（限制长度避免匹配到正文）
            time_candidates = tree.xpath(
                "//text()[contains(., '202') and string-length(normalize-space(.)) <= 30]"
            )

    # 从URL提取年月日用于校验
    url_ymd = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
    url_year = url_ymd.group(1) if url_ymd else None
    url_month = url_ymd.group(2) if url_ymd else None
    url_day = url_ymd.group(3) if url_ymd else None

    for raw_time in (tc.strip() for tc in time_candidates if tc and tc.strip()):
        # 精确匹配 "YYYY-MM-DD HH:MM" 格式
        match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', raw_time)
        if not match:
            match = re.search(r'(\d{4}-\d{2}-\d{2})', raw_time)
        if match:
            candidate_date = match.group(1)
            # 如果URL有完整年月日，校验日期是否一致
            if url_year and url_month and url_day:
                # 候选日期是否与URL的月日一致
                if candidate_date[:10] == f'{url_year}-{url_month}-{url_day}':
                    publish_time = candidate_date
                    break
                # 如果候选日期月份不对，跳过（可能是正文中的历史日期）
                elif candidate_date[5:7] != url_month:
                    continue  # 月份不匹配，跳过这条候选
                else:
                    publish_time = candidate_date
                    break
            else:
                publish_time = candidate_date
                break

    # ------ 来源提取：gov.cn / mct.gov.cn 兼容 ------
    # 1) gov.cn：class="pages-source" 或 class="ly"
    source_elem = tree.xpath('//span[contains(@class, "pages-source")]/text()')
    if not source_elem:
        source_elem = tree.xpath('//span[contains(@class, "ly")]/text()')
    # 2) 包含"来源"文字的 span/div
    if not source_elem:
        source_elem = tree.xpath('//span[contains(text(), "来源")]/text() | //div[contains(text(), "来源")]/text()')
    # 3) mct.gov.cn 原始 XPath
    if not source_elem:
        source_elem = tree.xpath('/html/body/div[3]/div[1]/div/div[1]/span')

    if source_elem:
        raw_source = source_elem[0].strip() if isinstance(source_elem[0], str) else source_elem[
            0].text_content().strip()
        source = clean_text_ex(raw_source)  # 关键清理步骤
        # 提取"来源：xxx"中的名称
        sm = re.search(r'来源[：:]\s*(.*)', source)
        if sm:
            source = clean_text_ex(sm.group(1).strip())

    # 备选逻辑（如果精确XPath失效）
    if not publish_time or not source:
        meta_candidates = tree.xpath(
            '//div[contains(text(), "来源") or contains(text(), "时间")] | //span[contains(text(), "来源") or contains(text(), "时间")]')
        meta_text = ''
        for elem in meta_candidates:
            txt = elem.text_content().strip()
            if txt and ('来源' in txt or '时间' in txt or re.search(r'\d{4}-\d{2}-\d{2}', txt)):
                meta_text = txt
                break
        if meta_text:
            if not publish_time:
                tm = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', meta_text)
                if not tm:
                    tm = re.search(r'(\d{4}-\d{2}-\d{2})', meta_text)
                if not tm:
                    # 中文日期格式：如 "6月9日"
                    tm = re.search(r'(\d{1,2})月(\d{1,2})日', meta_text)
                    if tm:
                        month = tm.group(1).zfill(2)
                        day = tm.group(2).zfill(2)
                        yr = re.search(r'/(\d{4})\d{2}/', url)
                        publish_time = f'{yr.group(1)}-{month}-{day}' if yr else f'2026-{month}-{day}'
                if tm and not publish_time:
                    publish_time = tm.group(1)
            if not source:
                sm = re.search(r'来源[：:]\s*(.*?)(?:\s|$)', meta_text)
                if sm:
                    source = clean_text_ex(sm.group(1).strip())  # 清洗
                elif '新华社' in meta_text:
                    source = '新华社'
        # meta标签回退
        if not publish_time:
            meta_time = tree.xpath('//meta[@property="article:published_time"]/@content')
            if meta_time:
                publish_time = meta_time[0][:19]
        if not source:
            meta_source = tree.xpath('//meta[@name="source"]/@content')
            if meta_source:
                source = clean_text_ex(meta_source[0].strip())

    # 正文
    content = ''
    content_elem = tree.xpath('//*[@id="UCAP-CONTENT"]')
    if not content_elem:
        content_elem = tree.xpath(
            '//div[@class="TRS_Editor"] | //div[@class="article-content"] | //div[@class="content"]')
    if content_elem:
        paragraphs = content_elem[0].xpath('.//p//text() | .//div//text()')
        raw_content = '\n'.join([p.strip() for p in paragraphs if p.strip()])
        content = clean_text_ex(raw_content)  # 也使用增强清洗
    if not content and content_elem:
        raw_content = content_elem[0].text_content().strip()
        content = clean_text_ex(raw_content)

    # ===== 最终兜底：从正文提取日期（仅作最后手段）=====
    if not publish_time and content:
        # 从 URL 提取完整年月日用于校验
        url_ym = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
        if not url_ym:
            url_ym = re.search(r'/(\d{4})(\d{2})/', url)
        fallback_year = url_ym.group(1) if url_ym else '2026'
        fallback_month = url_ym.group(2) if url_ym else '06'
        fallback_day = url_ym.group(3) if url_ym and len(url_ym.groups()) >= 3 else None

        # 先在正文前2000字符中找 ISO 日期格式
        iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', content[:2000])
        if iso_match:
            iso_month = iso_match.group(2)
            # 只有月份与URL一致才采用
            if iso_month == fallback_month:
                publish_time = iso_match.group(1)
            # 否则继续找
        if not publish_time:
            # 在正文前2000字符中，优先匹配与URL月日一致的月日
            all_md = list(re.finditer(r'(\d{1,2})月(\d{1,2})日', content[:2000]))
            best_match = None
            if fallback_day:
                # URL有具体日期时，精确匹配月日
                for m in all_md:
                    if m.group(1).zfill(2) == fallback_month and m.group(2).zfill(2) == fallback_day:
                        best_match = m
                        break
            if not best_match:
                for m in all_md:
                    if m.group(1).zfill(2) == fallback_month:
                        best_match = m
                        break
            if not best_match and all_md:
                best_match = None  # 不随意取正文中月份不对的日期

            if best_match:
                month = best_match.group(1).zfill(2)
                day = best_match.group(2).zfill(2)
                publish_time = f'{fallback_year}-{month}-{day}'

    # 仍然失败：搜索整个页面文本（含导航、面包屑等可能藏日期的地方）
    if not publish_time:
        # 从 URL 提取年月用于校验
        url_ym2 = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
        if not url_ym2:
            url_ym2 = re.search(r'/(\d{4})(\d{2})/', url)
        url_year2 = url_ym2.group(1) if url_ym2 else '2026'
        url_month2 = url_ym2.group(2) if url_ym2 else '06'
        url_day2 = url_ym2.group(3) if url_ym2 and len(url_ym2.groups()) >= 3 else None

        page_text = tree.xpath('//body//text()')
        page_text = ' '.join(t.strip() for t in page_text if t.strip())
        # 先找 ISO 日期，月份必须与URL一致
        iso_page_matches = list(re.finditer(r'(\d{4})-(\d{2})-(\d{2})', page_text[:3000]))
        for m in iso_page_matches:
            if m.group(2) == url_month2:
                publish_time = m.group(1)
                break
        if not publish_time:
            # 优先找与URL月日一致的 月日
            all_page_md = list(re.finditer(r'(\d{1,2})月(\d{1,2})日', page_text[:3000]))
            if url_day2:
                for m in all_page_md:
                    if m.group(1).zfill(2) == url_month2 and m.group(2).zfill(2) == url_day2:
                        publish_time = f'{url_year2}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'
                        break
            if not publish_time:
                for m in all_page_md:
                    if m.group(1).zfill(2) == url_month2:
                        publish_time = f'{url_year2}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'
                        break

    # 仍然失败：搜索页面中所有元素的文本（不限body）
    if not publish_time:
        url_ym3 = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
        if not url_ym3:
            url_ym3 = re.search(r'/(\d{4})(\d{2})/', url)
        url_year3 = url_ym3.group(1) if url_ym3 else '2026'
        url_month3 = url_ym3.group(2) if url_ym3 else '06'
        url_day3 = url_ym3.group(3) if url_ym3 and len(url_ym3.groups()) >= 3 else None

        all_text = ' '.join(t.strip() for t in tree.xpath('//*//text()') if t.strip())
        # 先找 ISO 日期，月份必须与URL一致
        iso_all_matches = list(re.finditer(r'(\d{4})-(\d{2})-(\d{2})', all_text[:5000]))
        for m in iso_all_matches:
            if m.group(2) == url_month3:
                publish_time = m.group(1)
                break
        # 再找中文日期：优先匹配与URL月日一致的
        if not publish_time:
            all_md = list(re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日', all_text[:5000]))
            if url_day3:
                for m in all_md:
                    if m.group(2).zfill(2) == url_month3 and m.group(3).zfill(2) == url_day3:
                        publish_time = f'{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}'
                        break
            if not publish_time:
                for m in all_md:
                    if m.group(2).zfill(2) == url_month3:
                        publish_time = f'{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}'
                        break
        # 再找 6月4日 格式：优先与URL月日一致
        if not publish_time:
            all_md2 = list(re.finditer(r'(\d{1,2})月(\d{1,2})日', all_text[:5000]))
            if url_day3:
                for m in all_md2:
                    if m.group(1).zfill(2) == url_month3 and m.group(2).zfill(2) == url_day3:
                        publish_time = f'{url_year3}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'
                        break
            if not publish_time:
                for m in all_md2:
                    if m.group(1).zfill(2) == url_month3:
                        publish_time = f'{url_year3}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'
                        break

    # 仍然失败：仅用URL中的日期兜底
    if not publish_time:
        ym = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
        if not ym:
            ym = re.search(r'/(\d{4})(\d{2})/', url)
        if ym:
            if len(ym.groups()) >= 3:
                publish_time = f'{ym.group(1)}-{ym.group(2)}-{ym.group(3)}'
            else:
                publish_time = f'{ym.group(1)}-{ym.group(2)}'

    # 如果source也缺失，尝试从内容开头提取
    if not source and content:
        src_match = re.search(r'^(新华社|人民日报|央视新闻|光明日报|经济日报)', content[:100])
        if src_match:
            source = src_match.group(1)

    return {
        'title': title,
        'publish_time': publish_time,
        'source': source,
        'content': content
    }


def crawl_all_news(start_url):
    all_news = []
    current_url = start_url
    page_num = 1

    while current_url:
        if MAX_PAGES > 0 and page_num > MAX_PAGES:
            print(f"已达到最大页数限制 {MAX_PAGES}，停止爬取")
            break
        print(f"正在处理第 {page_num} 页: {current_url}")
        tree = fetch_page(current_url)
        if tree is None:
            break

        page_news = parse_news_list(tree, current_url)
        if not page_news:
            print(f"  警告：第 {page_num} 页未解析到新闻，尝试获取下一页...")
            current_url = get_next_page_url(tree, current_url)
            page_num += 1
            continue

        print(f"  第 {page_num} 页共 {len(page_news)} 条新闻，开始获取详情...")
        for idx, news in enumerate(page_news, 1):
            print(f"    正在获取 [{idx}/{len(page_news)}]: {news['title'][:30]}...")
            detail = parse_article_detail(news['url'])
            news.update(detail)
            time.sleep(DETAIL_DELAY)

        all_news.extend(page_news)
        print(f"  第 {page_num} 页完成，累计 {len(all_news)} 条新闻\n")

        current_url = get_next_page_url(tree, current_url)
        page_num += 1
        time.sleep(REQUEST_DELAY)

    return all_news


def save_to_csv(news_list, output_dir=None):
    if not news_list:
        print("没有数据可保存。")
        return
    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(output_dir, f'mct_news_{timestamp}.csv')
    fieldnames = ['title', 'publish_time', 'source', 'url', 'content']
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for news in news_list:
            row = {k: news.get(k, '') for k in fieldnames}
            writer.writerow(row)
    print(f"成功保存 {len(news_list)} 条新闻到 {filename}")


def main():
    print("=" * 60)
    # 修复语法错误：使用转义双引号
    print("文化和旅游部\"时政要闻\"爬虫")
    print(f"最大页数: {'全部' if MAX_PAGES == 0 else MAX_PAGES}  |  输出目录: {OUTPUT_DIR}")
    print("=" * 60)
    news_data = crawl_all_news(START_URL)
    if news_data:
        save_to_csv(news_data, OUTPUT_DIR)
        print("\n示例数据（第一条）：")
        sample = news_data[0]
        print(f"标题：{sample.get('title')}")
        print(f"时间：{sample.get('publish_time')}")
        print(f"来源：{sample.get('source')}")
        print(f"链接：{sample.get('url')}")
        content_preview = sample.get('content', '')[:200]
        print(f"正文预览：{content_preview}...")
    else:
        print("未获取到任何数据，请检查网络或网站结构是否已变化。")


if __name__ == "__main__":
    main()