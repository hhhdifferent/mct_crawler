# 湖北省文化和旅游厅政策爬虫

用于爬取湖北省文化和旅游厅官方网站政策文件的爬虫工具。

## 功能特点

- 支持 XPath 和 CSS 选择器
- 配置化设计，易于扩展到其他网站
- 自动分页爬取
- 数据保存为 CSV 格式
- 支持 GitHub Actions 定时任务

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python hubeipolicy.py
```

## 配置说明

配置文件 `config.json` 包含以下字段：

- `name`: 站点名称
- `entry_url`: 入口 URL
- `encoding`: 编码格式
- `request_delay`: 请求间隔（秒）
- `detail_delay`: 详情页请求间隔（秒）
- `max_pages`: 最大爬取页数（0 表示全部）
- `list_page`: 列表页配置
- `pagination`: 分页配置
- `detail_page`: 详情页配置

## GitHub Actions

项目已配置 GitHub Actions 工作流，默认每日 0 点执行爬取任务。

手动触发时可通过 `max_pages` 参数指定爬取页数。