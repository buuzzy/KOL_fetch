"""TikHub Instagram API 客户端封装。"""

import logging
import time

import requests

from config import TIKHUB_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tikhub.io/api/v1/instagram/v2"
REQUEST_TIMEOUT = (5, 15)  # (connect_timeout, read_timeout)
MAX_RETRIES = 2
COST_PER_REQUEST = 0.002


class InstagramClient:
    def __init__(self, api_key: str = TIKHUB_API_KEY):
        if not api_key:
            raise ValueError("TIKHUB_API_KEY 未设置。请在 .env 文件中配置")
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}"})
        self._request_count = 0
        self._cache_hits = 0
        self._failed_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def estimated_cost(self) -> float:
        return self._request_count * COST_PER_REQUEST

    @property
    def stats_summary(self) -> str:
        return (
            f"请求={self._request_count}, 缓存命中={self._cache_hits}, "
            f"失败={self._failed_count}, 费用=${self.estimated_cost:.3f}"
        )

    def _get(self, endpoint: str, params: dict, label: str = "") -> dict:
        url = f"{BASE_URL}/{endpoint}"
        tag = label or endpoint

        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.time()
            try:
                resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                elapsed = time.time() - t0
            except requests.exceptions.Timeout:
                elapsed = time.time() - t0
                logger.warning(f"[IG-API] {tag} 超时 ({elapsed:.1f}s), 重试 {attempt}/{MAX_RETRIES}")
                if attempt == MAX_RETRIES:
                    self._failed_count += 1
                    raise
                continue
            except requests.exceptions.ConnectionError as e:
                elapsed = time.time() - t0
                logger.warning(f"[IG-API] {tag} 连接失败 ({elapsed:.1f}s): {e}")
                if attempt == MAX_RETRIES:
                    self._failed_count += 1
                    raise
                time.sleep(2)
                continue
            break

        self._request_count += 1

        if resp.status_code == 402:
            raise RuntimeError("TikHub 余额不足，请充值")
        if resp.status_code == 403:
            raise PermissionError("TikHub API Token 缺少 Instagram 权限")
        if resp.status_code != 200:
            self._failed_count += 1
            logger.warning(f"[IG-API] {tag} HTTP {resp.status_code} ({elapsed:.1f}s)")
            resp.raise_for_status()

        body = resp.json()
        is_cached = "cache_url" in body and body.get("cache_url")
        if is_cached:
            self._cache_hits += 1

        logger.debug(
            f"[IG-API] {tag} OK ({elapsed:.1f}s)"
            f"{' [cached]' if is_cached else ''}"
        )
        return body

    def search_users(self, keyword: str) -> list[dict]:
        """搜索用户。$0.002/次。"""
        data = self._get("search_users", {"keyword": keyword}, label=f"search({keyword})")
        items = data.get("data", {}).get("data", {}).get("items", [])
        logger.info(f"[IG-API] search_users('{keyword}') → {len(items)} 个用户")
        return items

    def get_user_info(self, username: str) -> dict | None:
        """获取用户详情。$0.002/次。"""
        data = self._get("fetch_user_info", {"username": username}, label=f"user(@{username})")
        return data.get("data", {}).get("data", {})
