"""Instagram KOL 发现流程：搜用户 → 去重 → 获取详情 → 过滤。"""

import logging
import time
from dataclasses import dataclass, field, asdict

from instagram_client import InstagramClient
from config import IG_MIN_FOLLOWERS, IG_MAX_FOLLOWERS
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
class IGKOL:
    username: str
    name: str
    biography: str = ""
    follower_count: int = 0
    following_count: int = 0
    media_count: int = 0
    profile_url: str = ""
    external_url: str = ""
    is_verified: bool = False
    category: str = ""
    content_focus: list[str] = field(default_factory=list)
    discovered_via_keywords: list[str] = field(default_factory=list)
    hk_relevance_score: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _quick_screen(name: str, bio: str) -> bool:
    """初步筛选：名字或 bio 中至少包含一个财经或港澳信号词。"""
    text = (name + " " + bio).lower()
    has_finance = any(kw in text for kw in FINANCE_SIGNALS)
    has_hk = any(kw.lower() in text for kw in HK_MACAU_SIGNALS)
    return has_finance or has_hk


def discover_ig_kols(
    client: InstagramClient,
    keywords: list[str],
    min_followers: int = IG_MIN_FOLLOWERS,
    max_followers: int = IG_MAX_FOLLOWERS,
) -> list[IGKOL]:
    """主发现流程。"""

    # ── 阶段1: 搜索候选用户 ──
    candidates: dict[str, list[str]] = {}
    phase_start = time.time()

    for keyword in keywords:
        try:
            users = client.search_users(keyword)
        except Exception as e:
            logger.warning(f"[IG] 搜索失败 ({keyword}): {e}")
            continue

        added = 0
        for u in users:
            username = u.get("username", "")
            if not username:
                continue
            if username in candidates:
                if keyword not in candidates[username]:
                    candidates[username].append(keyword)
                continue
            full_name = u.get("full_name", "")
            if _quick_screen(full_name, ""):
                candidates[username] = [keyword]
                added += 1

        logger.info(f"[IG] '{keyword}' → 新增 {added} 个候选 (累计 {len(candidates)})")

    search_elapsed = time.time() - phase_start
    logger.info(
        f"[IG] ── 搜索阶段完成 ── "
        f"{len(candidates)} 个候选, 耗时 {search_elapsed:.0f}s, "
        f"{client.stats_summary}"
    )

    if not candidates:
        logger.warning("[IG] 没有候选用户")
        return []

    # ── 阶段2: 获取详情并过滤 ──
    kols = []
    excluded = {
        "粉丝不足": 0, "粉丝过多": 0, "媒体": 0,
        "机构": 0, "非财经": 0, "非港澳": 0, "私密账号": 0, "请求失败": 0,
    }
    total = len(candidates)
    detail_start = time.time()

    for idx, (username, kw_list) in enumerate(candidates.items(), 1):
        # 每 10 个打一次进度
        if idx % 10 == 0 or idx == 1 or idx == total:
            elapsed = time.time() - detail_start
            speed = idx / elapsed if elapsed > 0 else 0
            eta = (total - idx) / speed if speed > 0 else 0
            logger.info(
                f"[IG] 详情 {idx}/{total} "
                f"({elapsed:.0f}s, ~{eta:.0f}s 剩余, "
                f"已发现 {len(kols)} KOL, {client.stats_summary})"
            )

        try:
            info = client.get_user_info(username)
        except Exception as e:
            logger.warning(f"[IG] @{username} 请求失败: {e}")
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
        if not _is_finance_relevant(name, bio):
            excluded["非财经"] += 1
            continue

        hk_score = _calc_hk_relevance(name, bio, "")
        if hk_score == 0:
            excluded["非港澳"] += 1
            continue

        bio_links = info.get("bio_links", [])
        ext_url = ""
        if isinstance(bio_links, list) and bio_links:
            ext_url = bio_links[0].get("url", "")
        elif info.get("external_url"):
            ext_url = info["external_url"]

        kol = IGKOL(
            username=username,
            name=name,
            biography=bio[:500],
            follower_count=followers,
            following_count=info.get("following_count", 0),
            media_count=info.get("media_count", 0),
            profile_url=f"https://www.instagram.com/{username}/",
            external_url=ext_url,
            is_verified=info.get("is_verified", False),
            category=info.get("category_name", info.get("category", "")),
            content_focus=_infer_content_focus(name, bio),
            discovered_via_keywords=kw_list,
            hk_relevance_score=hk_score,
        )
        kols.append(kol)
        logger.info(f"[IG] ✓ @{username} ({name}, {followers:,} 粉丝, HK={hk_score})")

    kols.sort(key=lambda k: (k.hk_relevance_score, k.follower_count), reverse=True)

    total_elapsed = time.time() - phase_start
    logger.info(f"[IG] {'='*50}")
    logger.info(
        f"[IG] 完成! {len(kols)} 个港澳财经 KOL "
        f"({min_followers:,}~{max_followers:,} 粉丝)"
    )
    logger.info(f"[IG] 排除: {', '.join(f'{k}={v}' for k, v in excluded.items() if v > 0)}")
    logger.info(f"[IG] {client.stats_summary}")
    logger.info(f"[IG] 总耗时: {total_elapsed:.0f}s")
    logger.info(f"[IG] {'='*50}")
    return kols
