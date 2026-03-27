import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TIKHUB_API_KEY = os.getenv("TIKHUB_API_KEY", "")

def _collect_youtube_keys() -> list[str]:
    """收集所有可用的 YouTube API Key（主 key + fallback keys）。"""
    keys: list[str] = []
    if YOUTUBE_API_KEY:
        keys.append(YOUTUBE_API_KEY)
    for i in range(1, 10):
        k = os.getenv(f"YOUTUBE_API_KEY_fallback{i}", "")
        if k:
            keys.append(k)
    return keys

YOUTUBE_API_KEYS: list[str] = _collect_youtube_keys()

# ── 关键词设计原则 ──
# 所有关键词必须锚定"港澳受众"，不使用通用词（"投資"、"ETF"会引入台湾/印度/美国博主）
# 策略：地域词 + 财经词 组合，确保搜出来的内容天然面向港澳群体

SEARCH_KEYWORDS = [
    "港股分析",
    "港股投資",
    "恒指部署",
    "恒生指數分析",
    "港股ETF",
    "香港理財",
    "香港投資",
    "港股美股",
]

SEARCH_KEYWORDS_EXTENDED = [
    "港股技術分析",
    "港股窩輪",
    "港股牛熊證",
    "香港財務自由",
    "港人投資",
    "港股期權",
    "香港加密貨幣",
    "港股直播",
]

SEARCH_KEYWORDS_LONG_TAIL = [
    "港股新手",
    "香港月供股票",
    "香港被動收入",
    "港股收息股",
    "恒指期貨",
    "港股開戶",
    "香港退休理財",
    "澳門投資理財",
]

MIN_SUBSCRIBER_COUNT = 1000
MAX_SUBSCRIBER_COUNT = 200_000

REGION_CODE = "HK"
RELEVANCE_LANGUAGE = "zh-Hant"

MAX_RESULTS_PER_SEARCH = 50
MAX_PAGES_PER_KEYWORD = 3

# ── Instagram (TikHub) 配置 ──
IG_SEARCH_KEYWORDS = [
    "港股",
    "香港投資",
    "香港理財",
    "港股美股",
    "hong kong finance",
    "hong kong investment",
    "hk stocks",
    "香港財經",
]

IG_MIN_FOLLOWERS = 1_000
IG_MAX_FOLLOWERS = 200_000

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
