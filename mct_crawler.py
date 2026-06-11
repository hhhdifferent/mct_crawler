# -*- coding: utf-8 -*-
import requests
from lxml import html
import time
import csv
import re
import os
from datetime import datetime
from urllib.parse import urljoin
import html as html_parser
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, List, Dict, Any

# ==================== 配置 ====================
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
MAX_PAGES = int(os.environ.get('MAX_PAGES', '0'))       # 0=全部页面
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', '.')           # 输出目录

# 日志配置
LOG_DIR = os.path.join(OUTPUT_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, f'crawl_{datetime.now().strftime("%Y%m%d")}.log')
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2  # 重试延迟（秒）

# ==================== 日志设置 ====================
def setup_logging():
    """配置日志系统，同时输出到控制台和文件，并启用文件轮转"""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        LOG_FILE, 
        maxBytes=LOG_MAX_SIZE, 
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# ==================== 工具函数 ====================
def clean_text_ex(text: Optional[str]) -> str:
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

def validate_news_data(news: Dict[str, Any]) -> bool:
    """验证新闻数据是否基本完整，记录缺失情况"""
    is_valid = True
    if not news.get('title'):
        logger.warning(f"新闻数据缺失标题: {news.get('url')}")
        is_valid = False
    if not news.get('publish_time'):
        logger.warning(f"新闻数据缺失发布时间: {news.get('url')}")
        is_valid = False
    if not news.get('content'):
        logger.warning(f"新闻数据缺失正文内容: {news.get('url')}")
        is_valid = False
    return is_valid

# ==================== 请求与重试 ====================
def fetch_page_with_retry(url: str, retries: int = MAX_RETRIES) -> Optional[html.HtmlElement]:
    """带重试机制的页面请求函数，返回解析后的 HTML 树"""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.encoding = 'utf-8'
            resp.raise_for_status()
            tree = html.fromstring(resp.text)
            logger.debug(f"请求成功: {url}")
            return tree
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败 (尝试 {attempt}/{retries}): {url} - {str(e)}")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)  # 递增延迟
            else:
                logger.error(f"请求最终失败: {url} - {str(e)}")
                return None
        except Exception as e:
            logger.error(f"解析 HTML 失败 (尝试 {attempt}/{retries}): {url} - {str(e)}")
            if attempt < retries:
                time.sleep(RETRY_DELAY * attempt)
            else:
                logger.error(f"解析 HTML 最终失败: {url} - {str(e)}")
                return None

# ==================== 列表页解析 ====================
def parse_news_list(tree: html.HtmlElement, page_url: str) -> List[Dict[str, str]]:
    """解析新闻列表页，提取新闻标题和链接"""
    news_items = []
    links = tree.xpath('//td[1]/a')
    if not links:
        links = tree.xpath('//a[contains(@href, "szyw") or contains(@href, "/2026-")]')
    
    for link in links:
        try:
            title = link.text.strip() if link.text else ''
            href = link.get('href')
            if title and href:
                full_url = urljoin(page_url, href)
                # 避免重复
                if not any(item['url'] == full_url for item in news_items):
                    news_items.append({'title': title, 'url': full_url})
        except Exception as e:
            logger.error(f"解析列表链接失败: {str(e)}", exc_info=True)
            continue
    
    logger.info(f"列表页解析到 {len(news_items)} 条新闻链接")
    return news_items

# ==================== 下一页处理 ====================
def get_next_page_url(tree: html.HtmlElement, current_url: str) -> Optional[str]:
    """
    获取下一页URL。
    mct.gov.cn 的分页链接由 JS 动态生成，静态 HTML 中不存在。
    因此按 URL 规律直接构造：index.htm → index_1.htm → index_2.htm → ...
    """
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
        logger.info(f"构造下一页 URL: {next_url}")
        return next_url

    # 兜底：尝试 XPath 找下一页链接（其他网站可能有用）
    try:
        next_link = tree.xpath('/html/body/div[6]/div[2]/div[2]/div/span[4]/a')
        if next_link and next_link[0].get('href'):
            href = next_link[0].get('href')
            if href and 'javascript' not in href and 'void' not in href:
                next_url = urljoin(current_url, href)
                logger.info(f"通过 XPath 获取下一页 URL: {next_url}")
                return next_url
    except Exception as e:
        logger.error(f"通过 XPath 获取下一页链接失败: {str(e)}", exc_info=True)

    logger.warning(f"无法构造下一页 URL: {current_url}")
    return None

# ==================== 详情页解析 ====================
def parse_article_detail(url: str) -> Dict[str, str]:
    """解析文章详情页，提取标题、时间、来源、正文"""
    tree = fetch_page_with_retry(url)
    if tree is None:
        logger.error(f"无法获取详情页: {url}")
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
    
    if not title:
        logger.warning(f"详情页未找到标题: {url}")

    # 时间和来源
    publish_time = ''
    source = ''

    # ------ 时间提取：gov.cn / mct.gov.cn 兼容 ------
    time_candidates = []
    try:
        time_candidates = tree.xpath('//meta[@property="article:published_time"]/@content')
        if not time_candidates:
            time_candidates = tree.xpath('//meta[@name="publishdate"]/@content')
        if not time_candidates:
            time_candidates = tree.xpath('//span[contains(@class, "pages-date")]/text()')
        if not time_candidates:
            time_candidates = tree.xpath('//span[@id="PubTime"]/text()')
        if not time_candidates:
            url_match = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
            if url_match:
                url_year, url_month, url_day = url_match.groups()
                time_candidates = tree.xpath(
                    f"//text()[contains(., '{url_year}-{url_month}-{url_day}')]"
                )
        if not time_candidates:
            time_candidates = tree.xpath(
                "//text()[contains(., '202') and string-length(normalize-space(.)) <= 30]"
            )
    except Exception as e:
        logger.error(f"提取时间候选失败: {url} - {str(e)}", exc_info=True)

    url_ymd = re.search(r'/(\d{4})(\d{2})/(\d{2})/', url)
    url_year = url_ymd.group(1) if url_ymd else None
    url_month = url_ymd.group(2) if url_ymd else None
    url_day = url_ymd.group(3) if url_ymd else None

    for raw_time in (tc.strip() for tc in time_candidates if tc and tc.strip()):
        try:
            match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', raw_time)
            if not match:
                match = re.search(r'(\d{4}-\d{2}-\d{2})', raw_time)
            if match:
                candidate_date = match.group(1)
                if url_year and url_month and url_day:
                    if candidate_date[:10] == f'{url_year}-{url_month}-{url_day}':
                        publish_time = candidate_date
                        break
                    elif candidate_date[5:7] != url_month:
                        continue
                    else:
                        publish_time = candidate_date
                       
