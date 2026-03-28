"""Threads 数据客户端 — 通过 TikHub API 获取 Threads 用户数据。

Threads 搜索策略：
- search_profiles 在测试中返回空（Threads 平台限制），不使用
- 通过 search_top + search_recent 搜内容 → 提取发帖用户作为候选
- fetch_user_info 获取用户详情

定价: $0.002/req (所有端点统一)
限流: 默认 10 RPS (TikHub 网关层)
"""

import logging
from typing import Optional

import requests

from config import TIKHUB_API_KEY

logger = logging.getLogger(__name__)

_TIKHUB_BASE = "https://api.tikhub.io/api/v1/threads/web"
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 20
_MAX_RETRIES = 2


class ThreadsClient:
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

    def search_content(self, query: str, mode: str = "recent") -> list[dict]:
        """搜索 Threads 内容并提取发帖用户。

        mode: "recent" | "top"
        返回去重后的用户列表 [{username, pk, ...}]
        """
        endpoint = "search_recent" if mode == "recent" else "search_top"
        data = self._get(
            f"{_TIKHUB_BASE}/{endpoint}",
            params={"query": query},
            label=f"{endpoint}({query})",
        )
        if data is None:
            return []

        edges = data.get("searchResults", {}).get("edges", [])
        users_seen: dict[str, dict] = {}

        for edge in edges:
            thread = edge.get("node", {}).get("thread", {})
            for ti in thread.get("thread_items", []):
                post = ti.get("post", {})
                user = post.get("user", {})
                username = user.get("username", "")
                if username and username not in users_seen:
                    caption = post.get("caption", {})
                    text = ""
                    if isinstance(caption, dict):
                        text = caption.get("text", "")
                    users_seen[username] = {
                        "username": username,
                        "pk": str(user.get("pk", "")),
                        "is_verified": user.get("is_verified", False),
                        "sample_text": text[:200],
                    }

        result = list(users_seen.values())
        logger.info(f"[TikHub-Threads] {endpoint}('{query}') → {len(edges)} 帖子, {len(result)} 个用户")
        return result

    def get_user_info(self, username: str) -> Optional[dict]:
        """获取 Threads 用户详情。"""
        data = self._get(
            f"{_TIKHUB_BASE}/fetch_user_info",
            params={"username": username},
            label=f"user(@{username})",
        )
        if data is None:
            return None

        user = data.get("user", data)
        if not user or not user.get("username"):
            return None

        return {
            "username": user.get("username", username),
            "full_name": user.get("full_name", ""),
            "biography": user.get("biography", ""),
            "follower_count": user.get("follower_count", 0),
            "is_verified": user.get("is_verified", False),
            "is_private": user.get("text_post_app_is_private", False),
            "pk": str(user.get("pk", "")),
            "profile_pic_url": user.get("profile_pic_url", ""),
        }

    def get_user_posts(self, user_id: str, max_posts: int = 10) -> list[dict]:
        """获取用户近期帖子（用于内容判断）。"""
        data = self._get(
            f"{_TIKHUB_BASE}/fetch_user_posts",
            params={"user_id": user_id},
            label=f"posts(uid={user_id})",
        )
        if data is None:
            return []

        edges = data.get("mediaData", {}).get("edges", [])
        posts = []
        for edge in edges[:max_posts]:
            node = edge.get("node", {})
            for ti in node.get("thread_items", []):
                post = ti.get("post", {})
                caption = post.get("caption", {})
                text = caption.get("text", "") if isinstance(caption, dict) else ""
                posts.append({
                    "text": text[:300],
                    "like_count": post.get("like_count", 0),
                    "taken_at": post.get("taken_at", 0),
                })
        return posts

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
                    logger.warning(f"[TikHub-Threads] {label} 429 限流, 重试 {attempt}/{_MAX_RETRIES}")
                    if attempt < _MAX_RETRIES:
                        import time, random
                        time.sleep(2 + random.uniform(0, 2))
                        continue
                    self._failed_count += 1
                    return None

                if resp.status_code == 402:
                    logger.error(f"[TikHub-Threads] {label} 402 — 余额不足, 请充值 TikHub 账户")
                    self._failed_count += 1
                    return None

                logger.warning(f"[TikHub-Threads] {label} HTTP {resp.status_code}")
                self._failed_count += 1
                if attempt < _MAX_RETRIES:
                    continue
                return None

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.warning(f"[TikHub-Threads] {label} 网络异常: {e}")
                self._failed_count += 1
                if attempt < _MAX_RETRIES:
                    import time
                    time.sleep(3)
                    continue
                return None

        return None
