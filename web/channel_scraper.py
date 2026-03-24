"""YouTube 频道页面爬取：从频道 About 页面的 HTML 提取外部链接（社媒、联系方式）。"""

import json
import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

_YT_INITIAL_DATA_RE = re.compile(
    r"var ytInitialData\s*=\s*({.*?});</script>", re.DOTALL,
)
_LINK_RE = re.compile(
    r'"channelExternalLinkViewModel":\s*\{'
    r'"title":\s*\{"content":\s*"([^"]+)"\}.*?'
    r'"link":\s*\{"content":\s*"([^"]+)"',
)

_CHANNEL_CLASSIFIERS: list[tuple[str, re.Pattern]] = [
    ("telegram", re.compile(r"t\.me/", re.I)),
    ("whatsapp", re.compile(r"wa\.me/|whatsapp", re.I)),
    ("wechat", re.compile(r"wechat|weixin|微信", re.I)),
    ("instagram", re.compile(r"instagram\.com/", re.I)),
    ("facebook", re.compile(r"facebook\.com/", re.I)),
    ("threads", re.compile(r"threads\.(?:com|net)/", re.I)),
    ("x", re.compile(r"(?:x\.com|twitter\.com)/", re.I)),
]


def _classify_link(title: str, url: str) -> tuple[str, str]:
    """根据标题和 URL 判断渠道类型，返回 (channel_type, normalized_url)。"""
    combined = f"{title} {url}"
    for channel_type, pattern in _CHANNEL_CLASSIFIERS:
        if pattern.search(combined):
            if not url.startswith("http"):
                url = f"https://{url}"
            return channel_type, url
    if not url.startswith("http"):
        url = f"https://{url}"
    return "other", url


def _normalize_channel_url(profile_url: str) -> str | None:
    """从 KOL profile_url 构造频道 about 页面 URL。"""
    if not profile_url:
        return None
    url = profile_url.rstrip("/")
    if "/about" not in url:
        url += "/about"
    return url


def scrape_channel_links(channel_url: str, timeout: int = 15) -> dict[str, list[str]]:
    """爬取单个 YouTube 频道的 About 页面，提取外部链接。

    返回格式与 extract_contacts() 一致：{channel_type: [url, ...]}
    失败时返回空字典。
    """
    try:
        resp = requests.get(channel_url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("爬取失败 %s: %s", channel_url, e)
        return {}

    html = resp.text
    match = _YT_INITIAL_DATA_RE.search(html)
    if not match:
        logger.debug("未找到 ytInitialData: %s", channel_url)
        return {}

    raw_json = match.group(1)
    link_pairs = _LINK_RE.findall(raw_json)
    if not link_pairs:
        return {}

    channels: dict[str, list[str]] = {}
    for title, link_text in link_pairs:
        ch_type, url = _classify_link(title, link_text)
        if ch_type == "other":
            continue
        channels.setdefault(ch_type, [])
        if url not in channels[ch_type]:
            channels[ch_type].append(url)

    return channels


def scrape_channels_batch(
    profile_urls: list[str],
    delay: float = 2.0,
    max_retries: int = 1,
) -> dict[str, dict[str, list[str]]]:
    """批量爬取频道链接，串行执行，带延迟控制。

    Args:
        profile_urls: KOL profile_url 列表
        delay: 每次请求间隔（秒）
        max_retries: 失败重试次数

    Returns:
        {profile_url: {channel_type: [url, ...]}, ...}
    """
    results: dict[str, dict[str, list[str]]] = {}

    for i, profile_url in enumerate(profile_urls):
        about_url = _normalize_channel_url(profile_url)
        if not about_url:
            continue

        links = scrape_channel_links(about_url)

        if not links and max_retries > 0:
            time.sleep(delay)
            links = scrape_channel_links(about_url)

        results[profile_url] = links

        if i < len(profile_urls) - 1:
            time.sleep(delay)

    return results
