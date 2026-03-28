"""KOL 发现流程：关键词搜索 → 频道去重 → 信息补全 → 港澳相关性过滤 → 活跃度筛选。"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

from youtube_client import YouTubeClient, QuotaExhaustedError
from config import (
    MIN_SUBSCRIBER_COUNT,
    MAX_SUBSCRIBER_COUNT,
    REGION_CODE,
    RELEVANCE_LANGUAGE,
    MAX_RESULTS_PER_SEARCH,
    MAX_PAGES_PER_KEYWORD,
)

logger = logging.getLogger(__name__)

# ── 媒体黑名单：这些是新闻媒体/电视台，不是 KOL ──
MEDIA_BLACKLIST = [
    "bloomberg", "reuters", "cnbc", "bbc", "cnn",
    "彭博", "信報", "經濟日報", "明報", "星島",
    "南華早報", "香港電台", "有線新聞", "now新聞", "now tv",
    "新華社", "央視", "cctv", "人民日報", "環球時報",
    "中天電視", "風傳媒", "東森", "三立", "tvbs",
    "寰宇新聞", "非凡電視", "ustv", "民視", "壹電視",
    "etnet", "經濟一週", "on.cc東網", "東網",
    "tv9", "ndtv", "zee business", "moneycontrol",
    "yahoo finance", "yahoo財經",
    "鳳凰衛視", "大公報", "文匯報",
    "rthk", "商業電台", "香港01",
]

# ── 机构黑名单：券商、银行、基金公司、政府机构 — 这些不是个人 KOL ──
INSTITUTION_BLACKLIST = [
    "恒生銀行", "hang seng bank", "中銀香港", "匯豐", "hsbc",
    "富途", "futu", "老虎證券", "tiger brokers", "tiger trade",
    "華盛証券", "vbrokers", "輝立証券", "phillip securities",
    "耀才證券", "bsgroup", "富昌金融", "fulbright",
    "國泰君安", "中信証券", "海通國際", "交銀國際",
    "aastocks", "經濟通", "etnet",
    "global x etfs", "富達國際", "fidelity", "blackrock", "貝萊德",
    "ifast", "奕豐",
    "香港金融管理局", "hkma", "投委會", "ifec",
    "香港年金", "hkmc annuity", "強積金", "積金局",
    "moneysmart", "comparehero",
    "策略王電視", "stv.hk",
    "jet media",
]

# ── 港澳受众信号词：频道名称/描述中出现这些词，说明内容面向港澳群体 ──
HK_MACAU_SIGNALS = [
    "港股", "恒指", "恒生", "hsi", "hang seng",
    "香港", "hong kong", "hk",
    "澳門", "macau", "macao",
    "港人", "港仔", "港女", "港幣", "港元",
    "港交所", "hkex",
    "聯繫匯率", "強積金", "mpf",
    "窩輪", "牛熊證",
    "紅籌", "國企股", "h股",
    "南下資金", "港股通",
    "屯門", "沙田", "旺角", "銅鑼灣", "中環",
    "紅磡", "尖沙咀", "觀塘", "荃灣",
    "粵語", "廣東話", "cantonese",
]

# ── 财经相关性信号词 ──
FINANCE_SIGNALS = [
    "港股", "美股", "恒指", "恒生", "a股",
    "投資", "投资", "理財", "理财",
    "etf", "基金", "fund",
    "股票", "stock", "trading", "交易",
    "期權", "option", "窩輪", "牛熊",
    "加密", "crypto", "bitcoin", "比特幣",
    "技術分析", "technical analysis",
    "價值投資", "value invest",
    "財務自由", "被動收入", "財自",
    "finance", "financial", "invest",
    "dividend", "收息",
    "分析師", "analyst",
    "月供股票", "退休理財",
]


@dataclass
class KOL:
    channel_id: str
    name: str
    description: str = ""
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    profile_url: str = ""
    thumbnail_url: str = ""
    country: str = ""
    custom_url: str = ""
    content_focus: list[str] = field(default_factory=list)
    discovered_via_keywords: list[str] = field(default_factory=list)
    hk_relevance_score: int = 0
    recent_titles: list[str] = field(default_factory=list)
    llm_verdict: str = ""
    llm_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _is_media_outlet(name: str, description: str) -> bool:
    text = (name + " " + description).lower()
    return any(kw in text for kw in MEDIA_BLACKLIST)


def _is_institution(name: str, description: str) -> bool:
    text = (name + " " + description).lower()
    return any(kw.lower() in text for kw in INSTITUTION_BLACKLIST)


def _calc_hk_relevance(name: str, description: str, country: str) -> int:
    """计算港澳相关性得分。0 = 不相关，分数越高越相关。"""
    text = (name + " " + description).lower()
    score = 0

    for signal in HK_MACAU_SIGNALS:
        if signal.lower() in text:
            score += 1

    if country.upper() in ("HK", "MO"):
        score += 3

    name_lower = name.lower()
    for signal in HK_MACAU_SIGNALS:
        if signal.lower() in name_lower:
            score += 2
            break

    return score


def _is_finance_relevant(name: str, description: str) -> bool:
    text = (name + " " + description).lower()
    return any(kw in text for kw in FINANCE_SIGNALS)


def _infer_content_focus(name: str, description: str) -> list[str]:
    text = (name + " " + description).lower()
    focus_map = {
        "港股": ["港股"],
        "美股": ["美股"],
        "恒指": ["恒指", "恒生"],
        "A股": ["a股", "a 股"],
        "ETF": ["etf"],
        "加密貨幣": ["加密", "crypto", "bitcoin", "比特幣", "虛擬貨幣"],
        "技術分析": ["技術分析", "technical analysis", "圖表"],
        "價值投資": ["價值投資", "value invest"],
        "期權": ["期權", "option"],
        "窩輪牛熊": ["窩輪", "牛熊"],
        "理財": ["理財", "財務自由", "被動收入", "退休"],
        "基金": ["基金", "fund"],
        "交易": ["交易", "trading", "操盤"],
        "收息股": ["收息", "dividend"],
        "強積金": ["強積金", "mpf"],
    }
    result = []
    for label, keywords in focus_map.items():
        if any(kw in text for kw in keywords):
            result.append(label)
    return result


def discover_kols(
    client: YouTubeClient,
    keywords: list[str],
    min_subscribers: int = MIN_SUBSCRIBER_COUNT,
    max_subscribers: int = MAX_SUBSCRIBER_COUNT,
    max_pages: int = MAX_PAGES_PER_KEYWORD,
    strategy: str = "video",
    max_inactive_days: int = 90,
) -> list[KOL]:
    """
    主发现流程。

    strategy:
        "channel" — 直接搜频道
        "video"   — 搜视频再提取频道（推荐：相关性更高）
        "both"    — 两者都跑
    """
    channel_ids: dict[str, list[str]] = {}

    for keyword in keywords:
        logger.info(f"搜索关键词: {keyword} (策略: {strategy})")

        try:
            if strategy in ("channel", "both"):
                _search_by_channel(client, keyword, channel_ids, max_pages)

            if strategy in ("video", "both"):
                _search_by_video(client, keyword, channel_ids, max_pages)

        except QuotaExhaustedError as e:
            logger.warning(f"Quota 耗尽，停止搜索: {e}")
            break

    if not channel_ids:
        logger.warning("未搜索到任何频道")
        return []

    all_ids = list(channel_ids.keys())
    logger.info(f"去重后共 {len(all_ids)} 个频道，开始获取详情...")

    try:
        details = client.get_channel_details(all_ids)
    except QuotaExhaustedError as e:
        logger.warning(f"获取频道详情时 quota 耗尽: {e}")
        return []

    kols = []
    uploads_map: dict[str, str] = {}  # channel_id → uploads playlist ID
    excluded = {"粉丝不足": 0, "粉丝过多": 0, "媒体": 0, "机构": 0, "非财经": 0, "非港澳": 0, "不活跃": 0}

    for item in details:
        cid = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        branding = item.get("brandingSettings", {}).get("channel", {})
        content_details = item.get("contentDetails", {})

        name = snippet.get("title", "")
        description = snippet.get("description", "")
        country = snippet.get("country", branding.get("country", ""))
        sub_count = int(stats.get("subscriberCount", 0))

        if sub_count < min_subscribers:
            excluded["粉丝不足"] += 1
            continue

        if sub_count > max_subscribers:
            excluded["粉丝过多"] += 1
            logger.debug(f"排除大V: {name} ({sub_count:,})")
            continue

        if _is_media_outlet(name, description):
            excluded["媒体"] += 1
            continue

        if _is_institution(name, description):
            excluded["机构"] += 1
            logger.debug(f"排除机构: {name}")
            continue

        if not _is_finance_relevant(name, description):
            excluded["非财经"] += 1
            continue

        hk_score = _calc_hk_relevance(name, description, country)
        if hk_score == 0:
            excluded["非港澳"] += 1
            continue

        custom_url = snippet.get("customUrl", "")
        profile_url = (
            f"https://www.youtube.com/{custom_url}" if custom_url
            else f"https://www.youtube.com/channel/{cid}"
        )

        kol = KOL(
            channel_id=cid,
            name=name,
            description=description,
            subscriber_count=sub_count,
            video_count=int(stats.get("videoCount", 0)),
            view_count=int(stats.get("viewCount", 0)),
            profile_url=profile_url,
            thumbnail_url=snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            country=country,
            custom_url=custom_url,
            content_focus=_infer_content_focus(name, description),
            discovered_via_keywords=channel_ids.get(cid, []),
            hk_relevance_score=hk_score,
        )
        kols.append(kol)

        uploads_id = content_details.get("relatedPlaylists", {}).get("uploads", "")
        if uploads_id:
            uploads_map[cid] = uploads_id

    # ── 活跃度筛选 + 收集近期视频标题 ──
    if max_inactive_days > 0 and kols:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_inactive_days)
        logger.info(
            f"活跃度检查: {len(kols)} 个频道, "
            f"要求 {cutoff.strftime('%Y-%m-%d')} 之后有发布 (~{len(kols)} quota)"
        )
        active_kols = []
        for kol in kols:
            playlist_id = uploads_map.get(kol.channel_id)
            if not playlist_id:
                active_kols.append(kol)
                continue
            try:
                recent = client.get_recent_uploads(playlist_id, max_results=3)
            except QuotaExhaustedError:
                logger.warning("活跃度检查时 quota 耗尽，跳过剩余检查")
                active_kols.append(kol)
                active_kols.extend(
                    k for k in kols
                    if k.channel_id != kol.channel_id and k not in active_kols
                )
                break
            except Exception as e:
                logger.debug(f"活跃度检查失败 ({kol.name}): {e}")
                active_kols.append(kol)
                continue

            if not recent:
                excluded["不活跃"] += 1
                logger.debug(f"排除不活跃(无视频): {kol.name}")
                continue

            kol.recent_titles = [v["title"] for v in recent if v.get("title")]

            last_date_str = recent[0].get("published_at", "")
            if not last_date_str:
                active_kols.append(kol)
                continue

            try:
                last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                if last_date < cutoff:
                    excluded["不活跃"] += 1
                    days_ago = (datetime.now(timezone.utc) - last_date).days
                    logger.debug(f"排除不活跃: {kol.name} (最后发布 {days_ago} 天前)")
                    continue
            except (ValueError, TypeError):
                pass

            active_kols.append(kol)

        kols = active_kols

    kols.sort(key=lambda k: (k.hk_relevance_score, k.subscriber_count), reverse=True)

    logger.info(
        f"筛选完成: {len(kols)} 个港澳财经 KOL "
        f"({min_subscribers:,} ~ {max_subscribers:,} 订阅)"
    )
    excluded_parts = ", ".join(f"{k}={v}" for k, v in excluded.items() if v > 0)
    logger.info(f"排除统计: {excluded_parts}")
    logger.info(f"Quota 已用: {client.quota_used}")
    return kols


def _search_by_channel(
    client: YouTubeClient,
    keyword: str,
    channel_ids: dict[str, list[str]],
    max_pages: int,
):
    page_token = None
    for page in range(max_pages):
        response = client.search_channels(
            keyword=keyword,
            region_code=REGION_CODE,
            relevance_language=RELEVANCE_LANGUAGE,
            max_results=MAX_RESULTS_PER_SEARCH,
            page_token=page_token,
        )
        for item in response.get("items", []):
            cid = item["snippet"]["channelId"]
            if cid not in channel_ids:
                channel_ids[cid] = []
            if keyword not in channel_ids[cid]:
                channel_ids[cid].append(keyword)

        page_token = response.get("nextPageToken")
        if not page_token:
            break


def _search_by_video(
    client: YouTubeClient,
    keyword: str,
    channel_ids: dict[str, list[str]],
    max_pages: int,
):
    page_token = None
    for page in range(max_pages):
        response = client.search_videos(
            keyword=keyword,
            region_code=REGION_CODE,
            relevance_language=RELEVANCE_LANGUAGE,
            max_results=MAX_RESULTS_PER_SEARCH,
            page_token=page_token,
        )
        for item in response.get("items", []):
            cid = item["snippet"]["channelId"]
            if cid not in channel_ids:
                channel_ids[cid] = []
            if keyword not in channel_ids[cid]:
                channel_ids[cid].append(keyword)

        page_token = response.get("nextPageToken")
        if not page_token:
            break
