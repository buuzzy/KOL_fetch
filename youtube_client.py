"""YouTube Data API v3 客户端封装，支持多 Key 自动轮转。"""

import logging
import socket

import requests
import urllib3.util.connection

from config import YOUTUBE_API_KEY, YOUTUBE_API_KEYS

logger = logging.getLogger(__name__)

DAILY_QUOTA_LIMIT = 10_000
BASE_URL = "https://www.googleapis.com/youtube/v3"
REQUEST_TIMEOUT = 20

QUOTA_COSTS = {
    "search.list": 100,
    "channels.list": 1,
    "videos.list": 1,
}

_original_allowed_gai_family = urllib3.util.connection.allowed_gai_family


def _force_ipv4():
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET


def _restore_gai():
    urllib3.util.connection.allowed_gai_family = _original_allowed_gai_family


class QuotaExhaustedError(Exception):
    pass


class YouTubeClient:
    def __init__(self, api_keys: list[str] | None = None):
        keys = api_keys or YOUTUBE_API_KEYS
        if not keys:
            raise ValueError(
                "YOUTUBE_API_KEY 未设置。请在 .env 文件中配置，"
                "参考 .env.example"
            )
        self._api_keys = keys
        self._key_index = 0
        self._session = requests.Session()
        self._quota_used: dict[int, int] = {i: 0 for i in range(len(keys))}
        self._exhausted_keys: set[int] = set()
        logger.info("YouTube API 已加载 %d 个 Key", len(keys))
        _force_ipv4()

    @property
    def _api_key(self) -> str:
        return self._api_keys[self._key_index]

    @property
    def quota_used(self) -> int:
        return sum(self._quota_used.values())

    @property
    def quota_remaining(self) -> int:
        return DAILY_QUOTA_LIMIT * len(self._api_keys) - self.quota_used

    def _rotate_key(self) -> bool:
        """切换到下一个可用 Key，返回是否成功。"""
        self._exhausted_keys.add(self._key_index)
        for i in range(len(self._api_keys)):
            if i not in self._exhausted_keys:
                old_idx = self._key_index
                self._key_index = i
                logger.info(
                    "Key #%d 额度耗尽，切换到 Key #%d（共 %d 个）",
                    old_idx + 1, i + 1, len(self._api_keys),
                )
                return True
        return False

    def _consume_quota(self, operation: str, count: int = 1):
        cost = QUOTA_COSTS.get(operation, 1) * count
        if self._quota_used[self._key_index] + cost > DAILY_QUOTA_LIMIT:
            if not self._rotate_key():
                raise QuotaExhaustedError(
                    f"所有 {len(self._api_keys)} 个 Key 额度均已耗尽"
                )
        self._quota_used[self._key_index] += cost

    def _get(self, endpoint: str, params: dict) -> dict:
        params["key"] = self._api_key
        url = f"{BASE_URL}/{endpoint}"
        resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()

        if resp.status_code == 403:
            error_reason = (
                data.get("error", {}).get("errors", [{}])[0].get("reason", "")
            )
            if error_reason in ("quotaExceeded", "dailyLimitExceeded"):
                if self._rotate_key():
                    params["key"] = self._api_key
                    resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                    data = resp.json()
                    if resp.status_code != 403:
                        resp.raise_for_status()
                        return data
                raise QuotaExhaustedError(
                    f"所有 {len(self._api_keys)} 个 Key 额度均已耗尽"
                )
            raise QuotaExhaustedError(f"API 返回 403: {data}")

        resp.raise_for_status()
        return data

    def search_channels(
        self,
        keyword: str,
        region_code: str = "HK",
        relevance_language: str = "zh-Hant",
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict:
        """搜索频道。每次调用消耗 100 quota units。"""
        self._consume_quota("search.list")
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "channel",
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "maxResults": min(max_results, 50),
        }
        if page_token:
            params["pageToken"] = page_token
        return self._get("search", params)

    def search_videos(
        self,
        keyword: str,
        region_code: str = "HK",
        relevance_language: str = "zh-Hant",
        max_results: int = 50,
        page_token: str | None = None,
        order: str = "relevance",
    ) -> dict:
        """搜索视频，用于发现发布相关内容的频道。每次调用消耗 100 quota units。"""
        self._consume_quota("search.list")
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
            "maxResults": min(max_results, 50),
            "order": order,
        }
        if page_token:
            params["pageToken"] = page_token
        return self._get("search", params)

    def get_channel_details(self, channel_ids: list[str]) -> list[dict]:
        """批量获取频道详情（含 contentDetails）。每次调用消耗 1 quota unit，最多 50 个频道/次。"""
        results = []
        for i in range(0, len(channel_ids), 50):
            batch = channel_ids[i : i + 50]
            self._consume_quota("channels.list")
            data = self._get("channels", {
                "part": "snippet,statistics,brandingSettings,contentDetails",
                "id": ",".join(batch),
            })
            results.extend(data.get("items", []))
        return results

    def get_latest_upload_date(self, uploads_playlist_id: str) -> str | None:
        """取频道最新一条视频的发布时间。消耗 1 quota unit。返回 ISO 日期字符串或 None。"""
        self._consume_quota("channels.list")
        data = self._get("playlistItems", {
            "part": "snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": 1,
        })
        items = data.get("items", [])
        if not items:
            return None
        return items[0].get("snippet", {}).get("publishedAt")

    def get_video_details(self, video_ids: list[str]) -> list[dict]:
        """批量获取视频详情。每次调用消耗 1 quota unit，最多 50 个视频/次。"""
        results = []
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            self._consume_quota("videos.list")
            data = self._get("videos", {
                "part": "snippet,statistics",
                "id": ",".join(batch),
            })
            results.extend(data.get("items", []))
        return results
