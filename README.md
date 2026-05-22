# 小红书/抖音反馈监控 MVP

这是第一版可运行工具，先完成数据管线：

- 按关键词导入主帖和评论
- SQLite 本地去重存储
- 基础情感分类和问题归因
- 导出 Excel：主帖明细、评论明细、每日统计、归因分析
- 可选页面截图
- 打印小红书/抖音关键词搜索入口，方便人工或半自动采集

## 安装

```bash
cd ~/project/social_feedback_monitor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

如果暂时不需要截图，可以先不执行 `python -m playwright install chromium`。

## 快速试跑

```bash
cd ~/project/social_feedback_monitor
source .venv/bin/activate
python main.py import-csv --input sample_import.csv
python main.py export
```

默认输出：

```text
outputs/feedback_YYYYMMDD.xlsx
data/feedback.sqlite3
```

## 手动添加一条

```bash
python main.py add \
  --item-type post \
  --platform xiaohongshu \
  --keyword 面对面红包 \
  --text "微信面对面红包入口在哪里，找了半天没找到" \
  --url "https://example.com/xhs/1" \
  --published-at "2026-05-20"
```

## 批量导入 CSV

CSV 字段：

```text
item_type,platform,keyword,text,url,published_at,author,likes_count,comments_count,parent_url
```

说明：

- `item_type`: `post` 或 `comment`
- `platform`: `xiaohongshu` 或 `douyin`
- `parent_url`: 评论所属主帖链接，主帖可留空

## 获取搜索入口

```bash
python main.py search-urls
```

工具会按 `config/keywords.yaml` 打印小红书和抖音搜索页入口。

## 小红书浏览器采集

第一版小红书采集使用浏览器自动化。你先手动登录一次，程序保存登录态；后续再自动打开搜索页、滚动、读取当前搜索结果页里可见的笔记卡片，并写入本地库。

首次登录：

```bash
python main.py login --platform xiaohongshu
```

浏览器打开后，在小红书页面里完成登录。登录完成后回到终端按 Enter，登录态会保存到：

```text
auth/xiaohongshu.json
```

采集搜索结果：

```bash
python main.py collect --platform xiaohongshu --keyword 面对面红包 --max-items 30 --scrolls 6 --export
```

参数说明：

- `--max-items`: 本次最多入库多少条搜索结果。
- `--scrolls`: 自动滚动加载次数。
- `--export`: 采集后立即导出 Excel。
- `--headless`: 无头模式。平台风控较严时不建议开启。
- `--min-delay-ms` / `--max-delay-ms`: 每次滚动或页面动作后的随机等待时间。
- `--diagnostics-dir`: 失败或空结果时保存页面 HTML 和截图。
- `--log-dir`: 采集日志目录。

如果页面要求重新登录或出现验证，程序会暂停，你在浏览器里处理完以后回到终端按 Enter 继续。

当前版本先采集搜索结果页可见内容，包括标题/摘要、链接、作者和点赞数等能直接读到的字段。详情页完整正文和评论区会在下一版接入。

没有账号时，可以先用本地 HTML 样例验证解析器：

```bash
python main.py diagnose-xhs-parser --html samples/xhs_search_sample.html
```

采集时如果页面结构变化、登录失效、结果为空或发生异常，程序会自动把现场保存到：

```text
diagnostics/
logs/
```

这些文件可以用来判断是登录/验证问题，还是页面结构解析规则需要更新。

## 稳定性采集模式

日常运行建议使用批量采集命令。它会按关键词分批采集，不一次性抓太多；每个关键词之间随机休息；单个关键词失败时保存现场、写日志，并继续下一个关键词。

使用配置文件里的全部关键词：

```bash
python main.py collect-batch \
  --platform xiaohongshu \
  --max-items-per-keyword 30 \
  --scrolls 6 \
  --min-delay-ms 2500 \
  --max-delay-ms 6500 \
  --rest-min-seconds 30 \
  --rest-max-seconds 90 \
  --export
```

只采指定关键词：

```bash
python main.py collect-batch \
  --platform xiaohongshu \
  --keywords 面对面红包 扫码红包 \
  --max-items-per-keyword 20 \
  --export
```

这个模式包含：

- 随机等待和随机滚动
- 每个关键词之间休息几十秒
- 采集失败自动截图并保存 HTML
- 检测登录失效、验证码、安全验证、访问频繁后暂停
- 按关键词分批采集
- DOM 解析失败或结果为空时导出页面 HTML
- 采集日志记录每次成功/失败原因

输出位置：

```text
logs/collector_YYYYMMDD.log
diagnostics/*.html
diagnostics/*.png
```

## 截图

导入真实链接后，可以尝试：

```bash
python main.py screenshot --limit 10
```

如果页面需要登录，第一版建议先人工打开链接截图，或后续用 Playwright 登录态文件接入。
由于小红书和抖音页面权限与反自动化策略会变化，截图失败不会影响数据入库和 Excel 导出。

## 下一版建议

- 加入浏览器辅助采集：登录后打开搜索页，自动读取当前页公开可见内容。
- 对小红书/抖音分别维护解析器。
- 接入大模型，对负面评论做更细的归因和建议动作。
