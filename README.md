本项目仅用于学习交流
# 通用定时爬虫模板

支持 `json_api`（调 JSON 接口）和 `html`（解析 HTML 页面）两种模式，可在 GitHub Actions 上定时运行。

## 快速上手：添加一个新站点

只需 **3 步**：

### 1. 创建站点目录和配置文件

```
mkdir 你的站点名
```

在目录里创建 `config.json`（或放在项目根目录，如 `mct_config.json`）：

#### 模式一：json_api（调 JSON 接口）

```json
{
  "name": "站点名称",
  "source_type": "json_api",
  "request_delay": 0.5,
  "api": {
    "url": "https://xxx.com/api/search",
    "method": "POST",
    "headers": {},
    "body": {},
    "keyword_field": "searchWord",
    "page_field": "pageNo",
    "page_size_field": "pageSize",
    "page_size": 10,
    "data_path": "data.list",
    "pager_path": "data.pager",
    "keywords": ["关键词1", "关键词2"],
    "field_map": {
      "title": "title",
      "url": "url",
      "publish_time": "publishTime"
    }
  },
  "detail_page": {
    "selector_type": "xpath",
    "content": "//div[@class='content']//p//text()"
  }
}
```

#### 模式二：html（解析 HTML 页面）

```json
{
  "name": "站点名称",
  "source_type": "html",
  "request_delay": 1.5,
  "encoding": "utf-8",
  "html": {
    "entry_url": "https://xxx.com/news/list.html",
    "list_page": {
      "selector_type": "xpath",
      "item_selector": "//ul[@class='news-list']/li",
      "title_selector": ".//a/text()",
      "link_selector": ".//a/@href"
    },
    "detail_page": {
      "selector_type": "xpath",
      "title": "//h1/text()",
      "publish_time": "//span[@class='time']/text()",
      "source": "//span[@class='source']/text()",
      "content": "//div[@class='content']//p//text()",
      "time_regex": "(\\d{4}-\\d{2}-\\d{2})"
    },
    "pagination": {
      "type": "url_pattern",
      "pattern": "https://xxx.com/news/list_#{page}.html"
    }
  }
}
```

### 2. 测试

```bash
pip install requests lxml
python crawler.py 你的站点名/config.json
```

### 3. 提交到 GitHub

```bash
git add 你的站点名/
git commit -m "添加新站点"
git push
```

之后就**自动生效**了——workflow 会自动扫描所有 `config.json` 并定时运行，无需修改任何 workflow 文件。

## 配置字段说明

### json_api 模式

| 字段 | 说明 |
|------|------|
| `api.url` | 接口地址 |
| `api.method` | `GET` 或 `POST`（默认 POST） |
| `api.headers` | 请求头（如 auth token） |
| `api.body` | POST 请求体模板 |
| `api.keyword_field` | 搜索关键词字段名 |
| `api.page_field` | 翻页字段名 |
| `api.page_size_field` | 每页条数字段名 |
| `api.data_path` | 数据列表在响应中的 JSON 路径，如 `data.list` |
| `api.pager_path` | 分页信息在响应中的 JSON 路径 |
| `api.keywords` | 搜索关键词数组 |
| `api.field_map` | 字段映射：CSV 列名 → JSON 键路径 |
| `detail_page.content` | XPath 选择器，提取正文内容 |

### html 模式

| 字段 | 说明 |
|------|------|
| `html.entry_url` | 列表页起始 URL |
| `html.list_page.item_selector` | 列表项的 XPath/CSS 选择器 |
| `html.list_page.title_selector` | 标题选择器（相对路径） |
| `html.list_page.link_selector` | 链接选择器（相对路径） |
| `html.detail_page.*` | 详情页各字段选择器 |
| `html.pagination` | 翻页配置：`url_pattern` 或 `selector` |

## 定时运行

- 默认每天北京时间 10:00 自动运行（UTC 2:00）
- 也可在 GitHub 仓库的 **Actions** 页面手动触发
- 运行结果可在 Actions 的 **Artifacts** 下载（保留 90 天）

## 项目结构

```
.
├── crawler.py              # 通用爬虫引擎
├── README.md               # 本说明
├── requirements.txt        # Python 依赖
├── .github/workflows/      # GitHub Actions 定时任务
│   └── crawl_all.yml       # 统一 workflow（自动发现所有站点）
├── guojiawenlv/            # 站点示例：中国政府网
│   └── config.json
├── hubeipolicy/            # 站点示例：湖北文旅厅
│   └── config.json
└── mct_config.json         # 站点示例：文旅部时政要闻
```
