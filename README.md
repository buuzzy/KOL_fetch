# YouTube 港澳财经 KOL 发现工具

通过 YouTube Data API v3 发现港澳群体受众的财经类个人 KOL（1K~20万订阅），支持月度轧差追踪新冒起的 KOL。

## 日常使用

```bash
# 每月跑一次，生成 KOL 名单
python main.py discover

# 跑更多关键词（覆盖面更广，消耗更多 quota）
python main.py discover --tier extended
python main.py discover --tier all

# 月度轧差（需要至少 2 个快照）
python main.py diff

# 查看历史快照
python main.py snapshots

# 预估 quota 消耗（不调 API）
python main.py quota
```

产出文件在 `output/` 目录，Excel 可直接发给 BD。

## 想调整条件？改 config.py

```
config.py 里可以改的东西：
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `SEARCH_KEYWORDS` | 核心搜索关键词 | 8 个港澳财经词 |
| `SEARCH_KEYWORDS_EXTENDED` | 扩展关键词 | 8 个细分词 |
| `SEARCH_KEYWORDS_LONG_TAIL` | 长尾关键词 | 8 个长尾词 |
| `MIN_SUBSCRIBER_COUNT` | 最低订阅数 | 1,000 |
| `MAX_SUBSCRIBER_COUNT` | 最高订阅数 | 200,000 |
| `MAX_PAGES_PER_KEYWORD` | 每关键词翻页数 | 3 |

## 想调整过滤规则？改 discovery.py

| 规则 | 位置 | 说明 |
|------|------|------|
| `MEDIA_BLACKLIST` | discovery.py 顶部 | 排除的媒体名单（彭博/东网等） |
| `INSTITUTION_BLACKLIST` | discovery.py 顶部 | 排除的机构名单（券商/银行等） |
| `HK_MACAU_SIGNALS` | discovery.py 顶部 | 判断港澳相关性的信号词 |
| `FINANCE_SIGNALS` | discovery.py 顶部 | 判断财经相关性的信号词 |

## 首次配置

### 1. 申请 API Key（免费）

1. [Google Cloud Console](https://console.cloud.google.com/) 创建项目
2. 启用 [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com)
3. 创建凭据 → API Key

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

## Quota 管理

每日免费额度 10,000 units。搜索消耗 100 units/次，频道信息只需 1 unit/次。

| 配置 | 预估消耗 |
|------|---------|
| `--tier core --pages 2` | ~1,600 |
| `--tier extended --pages 2` | ~3,200 |
| `--tier all --pages 2` | ~4,800 |

## 文件结构

```
├── main.py            # CLI 入口
├── youtube_client.py   # YouTube API 封装（强制 IPv4 + quota 跟踪）
├── discovery.py        # KOL 发现（搜索/去重/港澳过滤/机构排除）
├── storage.py          # 数据快照 + 月度轧差
├── report.py           # Excel/CSV 报告
├── config.py           # 关键词 + 筛选条件配置
├── data/               # 快照数据（gitignore）
└── output/             # 输出报告（gitignore）
```
