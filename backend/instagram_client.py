"""Instagram 数据客户端 — 通过 TikHub API 获取 IG 用户数据。

TikHub 负责代理池、TLS 伪装、签名逆向等反风控工作，
我们只需携带 API Key 调用 REST 接口。

定价: 搜索 $0.002/req, 用户详情 $0.002/req
限流: 默认 10 RPS (TikHub 网关层)
"""

import logging
from typing import Optional

import requests

from config import TIKHUB_API_KEY

logger = logging.getLogger(__name__)

_TIKHUB_BASE = "https://api.tikhub.io/api/v1/instagram"
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 20
_MAX_RETRIES = 2


class InstagramClient:
    def __init__(self, api_key: str = TIKHUB_API_KEY):
        if not api_key:
            raise ValueError(
                "TIKHUB_API_KEY 未设置。请在 .env 中添加 TIKHUB_API_KEY=<你的 TikHub API Key>"
            )
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })
        self._request_count = 0
        self._failed_count = 0

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def estimated_cost(self) -> float:
        return self._request_count * 0.002

    @property
    def stats_summary(self) -> str:
        return (
            f"请求={self._request_count}, "
            f"失败={self._failed_count}, "
            f"费用=${self.estimated_cost:.3f}"
        )

    def search_users(self, keyword: str) -> list[dict]:
        """按关键词搜索 IG 用户。"""
        data = self._get(
            f"{_TIKHUB_BASE}/v2/search_users",
            params={"keyword": keyword},
            label=f"search({keyword})",
        )
        if data is None:
            return []

        items = data.get("data", {}).get("items", [])
        if not items:
            items = data.get("items", [])

        result = [
            {
                "username": u.get("username", ""),
                "full_name": u.get("full_name", ""),
                "user_id": str(u.get("pk", u.get("pk_id", ""))),
                "is_private": u.get("is_private", False),
                "is_verified": u.get("is_verified", False),
            }
            for u in items
            if u.get("username")
        ]
        logger.info(f"[TikHub-IG] search('{keyword}') → {len(result)} 个用户")
        return result

    def get_user_info(self, username: str, user_id: str = "") -> Optional[dict]:
        """获取用户详情。"""
        data = self._get(
            f"{_TIKHUB_BASE}/v2/fetch_user_info",
            params={"username": username},
            label=f"user(@{username})",
        )
        if data is None:
            return None

        info = data.get("data", data)
        if not info or not info.get("username"):
            return None

        bio_links = info.get("bio_links", [])
        if isinstance(bio_links, list):
            bio_links = [{"url": bl.get("url", "")} for bl in bio_links if bl.get("url")]

        return {
            "username": info.get("username", username),
            "full_name": info.get("full_name", ""),
            "biography": info.get("biography", ""),
            "follower_count": info.get("follower_count", 0),
            "following_count": info.get("following_count", 0),
            "media_count": info.get("media_count", 0),
            "is_private": info.get("is_private", False),
            "is_verified": info.get("is_verified", False),
            "external_url": info.get("external_url", ""),
            "bio_links": bio_links,
            "category_name": info.get("category_name", info.get("category", "")),
            "category": info.get("category", ""),
            "profile_pic_url": info.get("profile_pic_url", ""),
            "public_email": info.get("public_email", "") or "",
            "public_phone_number": info.get("public_phone_number", "") or "",
            "contact_phone_number": info.get("contact_phone_number", "") or "",
            "is_business": info.get("is_business", False),
            "business_contact_method": info.get("business_contact_method", ""),
            "is_whatsapp_linked": info.get("is_whatsapp_linked", False),
        }

    def _get(self, url: str, params: dict, label: str) -> Optional[dict]:
        """带重试的 GET 请求。"""
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = self._session.get(
                    url, params=params,
                    timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
                )
                self._request_count += 1

                if resp.status_code == 200:
                    return resp.json().get("data", resp.json())

                if resp.status_code == 429:
                    logger.warning(f"[TikHub-IG] {label} 429 限流, 重试 {attempt}/{_MAX_RETRIES}")
                    if attempt < _MAX_RETRIES:
                        import time, random
                        time.sleep(2 + random.uniform(0, 2))
                        continue
                    self._failed_count += 1
                    return None

                if resp.status_code == 402:
                    logger.error(f"[TikHub-IG] {label} 402 — 余额不足, 请充值 TikHub 账户")
                    self._failed_count += 1
                    return None

                logger.warning(f"[TikHub-IG] {label} HTTP {resp.status_code}")
                self._failed_count += 1
                if attempt < _MAX_RETRIES:
                    continue
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"[TikHub-IG] {label} 网络异常: {e}")
                self._failed_count += 1
                if attempt < _MAX_RETRIES:
                    import time
                    time.sleep(3)
                    continue
                return None

        return None
