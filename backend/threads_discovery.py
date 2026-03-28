"""Threads KOL 发现流程：搜内容提取用户 → 去重 → 获取详情 → 过滤。

与 IG 不同：Threads 没有可用的 search_profiles 接口，
通过 search_top + search_recent 搜内容，从帖子中提取唯一用户作为候选。
"""

import logging
import time
from dataclasses import dataclass, field, asdict

from threads_client import ThreadsClient
from config import THREADS_MIN_FOLLOWERS, THREADS_MAX_FOLLOWERS
from discovery import (
    HK_MACAU_SIGNALS,
    FINANCE_SIGNALS,
    _is_media_outlet,
    _is_institution,
    _calc_hk_relevance,
    _is_finance_relevant,
    _infer_content_focus,
)

logger = logging.getLogger(__name__)


@dataclass
class ThreadsKOL:
    username: str
    name: str
    biography: str = ""
    follower_count: int = 0
    is_verified: bool = False
    profile_url: str = ""
    content_focus: list[str] = field(default_factory=list)
    discovered_via_keywords: list[str] = field(default_factory=list)
    hk_relevance_score: int = 0
    llm_verdict: str = ""
    llm_reason: str = ""
    recent_posts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _quick_screen(name: str, bio: str, sample_text: str = "") -> bool:
    """初步筛选：名字、bio 或示例帖子中至少包含一个财经或港澳信号词。"""
    text = (name + " " + bio + " " + sample_text).lower()
    has_finance = any(kw in text for kw in FINANCE_SIGNALS)
    has_hk = any(kw.lower() in text for kw in HK_MACAU_SIGNALS)
    return has_finance or has_hk


def discover_threads_kols(
    client: ThreadsClient,
    keywords: list[str],
    min_followers: int = THREADS_MIN_FOLLOWERS,
    max_followers: int = THREADS_MAX_FOLLOWERS,
) -> list[ThreadsKOL]:
    """主发现流程。"""

    # ── 阶段1: 搜索内容提取候选用户 ──
    candidates: dict[str, dict] = {}
    phase_start = time.time()

    for keyword in keywords:
        for mode in ("top", "recent"):
            try:
                users = client.search_content(keyword, mode=mode)
            except Exception as e:
                logger.warning(f"[Threads] 搜索失败 ({keyword}/{mode}): {e}")
                continue

            added = 0
            for u in users:
                username = u.get("username", "")
                if not username:
                    continue
                if username in candidates:
                    if keyword not in candidates[username]["keywords"]:
                        candidates[username]["keywords"].append(keyword)
                    continue
                sample = u.get("sample_text", "")
                if _quick_screen("", "", sample):
                    candidates[username] = {
                        "keywords": [keyword],
                        "pk": u.get("pk", ""),
                        "sample_text": sample,
                    }
                    added += 1

            logger.info(f"[Threads] '{keyword}/{mode}' → 新增 {added} 个候选 (累计 {len(candidates)})")

    search_elapsed = time.time() - phase_start
    logger.info(
        f"[Threads] ── 搜索阶段完成 ── "
        f"{len(candidates)} 个候选, 耗时 {search_elapsed:.0f}s, "
        f"{client.stats_summary}"
    )

    if not candidates:
        logger.warning("[Threads] 没有候选用户")
        return []

    # ── 阶段2: 获取详情并过滤 ──
    kols = []
    excluded = {
        "粉丝不足": 0, "粉丝过多": 0, "媒体": 0,
        "机构": 0, "非财经": 0, "非港澳": 0, "私密账号": 0, "请求失败": 0,
    }
    total = len(candidates)
    detail_start = time.time()

    for idx, (username, meta) in enumerate(candidates.items(), 1):
        kw_list = meta["keywords"]
        if idx % 10 == 0 or idx == 1 or idx == total:
            elapsed = time.time() - detail_start
            speed = idx / elapsed if elapsed > 0 else 0
            eta = (total - idx) / speed if speed > 0 else 0
            logger.info(
                f"[Threads] 详情 {idx}/{total} "
                f"({elapsed:.0f}s, ~{eta:.0f}s 剩余, "
                f"已发现 {len(kols)} KOL, {client.stats_summary})"
            )

        try:
            info = client.get_user_info(username)
        except Exception as e:
            logger.warning(f"[Threads] @{username} 请求失败: {e}")
            excluded["请求失败"] += 1
            continue

        if not info:
            excluded["请求失败"] += 1
            continue

        if info.get("is_private", False):
            excluded["私密账号"] += 1
            continue

        name = info.get("full_name", username)
        bio = info.get("biography", "")
        followers = info.get("follower_count", 0)

        if followers < min_followers:
            excluded["粉丝不足"] += 1
            continue
        if followers > max_followers:
            excluded["粉丝过多"] += 1
            continue
        if _is_media_outlet(name, bio):
            excluded["媒体"] += 1
            continue
        if _is_institution(name, bio):
            excluded["机构"] += 1
            continue

        combined_text = name + " " + bio + " " + meta.get("sample_text", "")
        if not _is_finance_relevant(name, combined_text):
            excluded["非财经"] += 1
            continue

        hk_score = _calc_hk_relevance(name, bio, "")
        if hk_score == 0:
            sample = meta.get("sample_text", "")
            hk_score = _calc_hk_relevance("", sample, "")

        if hk_score == 0:
            excluded["非港澳"] += 1
            continue

        kol = ThreadsKOL(
            username=username,
            name=name,
            biography=bio[:500],
            follower_count=followers,
            is_verified=info.get("is_verified", False),
            profile_url=f"https://www.threads.net/@{username}",
            content_focus=_infer_content_focus(name, bio),
            discovered_via_keywords=kw_list,
            hk_relevance_score=hk_score,
            recent_posts=[meta.get("sample_text", "")][:1] if meta.get("sample_text") else [],
        )
        kols.append(kol)
        logger.info(f"[Threads] ✓ @{username} ({name}, {followers:,} 粉丝, HK={hk_score})")

    kols.sort(key=lambda k: (k.hk_relevance_score, k.follower_count), reverse=True)

    total_elapsed = time.time() - phase_start
    logger.info(f"[Threads] {'='*50}")
    logger.info(
        f"[Threads] 完成! {len(kols)} 个港澳财经 KOL "
        f"({min_followers:,}~{max_followers:,} 粉丝)"
    )
    logger.info(f"[Threads] 排除: {', '.join(f'{k}={v}' for k, v in excluded.items() if v > 0)}")
    logger.info(f"[Threads] {client.stats_summary}")
    logger.info(f"[Threads] 总耗时: {total_elapsed:.0f}s")
    logger.info(f"[Threads] {'='*50}")
    return kols
