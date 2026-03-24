"""
港澳财经 KOL 发现工具 (YouTube + Instagram)

用法:
    python main.py discover              # YouTube: 用核心关键词搜索 KOL
    python main.py discover --tier all   # YouTube: 跑全部关键词
    python main.py ig-discover           # Instagram: 搜索港澳财经 KOL
    python main.py diff                  # 与上一次快照做轧差
    python main.py snapshots             # 查看所有快照
    python main.py quota                 # 预估 quota 消耗
"""

import argparse
import logging
import sys

from config import (
    SEARCH_KEYWORDS,
    SEARCH_KEYWORDS_EXTENDED,
    SEARCH_KEYWORDS_LONG_TAIL,
    MAX_PAGES_PER_KEYWORD,
    IG_SEARCH_KEYWORDS,
)
from youtube_client import YouTubeClient, QuotaExhaustedError
from discovery import discover_kols
from storage import (
    save_snapshot, load_snapshot, get_latest_snapshot, list_snapshots, diff_snapshots,
    save_ig_snapshot, list_ig_snapshots,
)
from report import export_csv, export_excel, export_diff_report, export_ig_csv, export_ig_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_discover(args):
    keyword_tiers = {
        "core": SEARCH_KEYWORDS,
        "extended": SEARCH_KEYWORDS + SEARCH_KEYWORDS_EXTENDED,
        "all": SEARCH_KEYWORDS + SEARCH_KEYWORDS_EXTENDED + SEARCH_KEYWORDS_LONG_TAIL,
    }
    keywords = keyword_tiers.get(args.tier, SEARCH_KEYWORDS)
    strategy = args.strategy
    max_pages = args.pages

    estimated = _estimate_quota(len(keywords), max_pages, strategy)
    logger.info(f"关键词: {len(keywords)} 个, 策略: {strategy}, 预估 quota: ~{estimated}")

    client = YouTubeClient()

    try:
        kols = discover_kols(
            client=client,
            keywords=keywords,
            max_pages=max_pages,
            strategy=strategy,
        )
    except QuotaExhaustedError as e:
        logger.error(f"Quota 耗尽: {e}")
        logger.info("已搜索到的结果仍会保存")
        kols = []

    if not kols:
        logger.warning("未找到符合条件的 KOL")
        logger.info(f"Quota 已用: {client.quota_used}")
        return

    snapshot_path = save_snapshot(kols, tag=args.tier)
    logger.info(f"快照已保存: {snapshot_path}")

    csv_path = export_csv(kols)
    xlsx_path = export_excel(kols)
    logger.info(f"CSV 报告: {csv_path}")
    logger.info(f"Excel 报告: {xlsx_path}")

    logger.info(f"\n{'='*60}")
    logger.info(f"发现 {len(kols)} 个 KOL (>= 1000 订阅)")
    logger.info(f"Quota 已用: {client.quota_used} / 10,000")
    logger.info(f"{'='*60}")

    _print_top_kols(kols)


def cmd_ig_discover(args):
    from instagram_client import InstagramClient
    from instagram_discovery import discover_ig_kols

    keywords = IG_SEARCH_KEYWORDS
    logger.info(f"[IG] 关键词: {len(keywords)} 个")
    logger.info(f"[IG] 预估费用: ~${len(keywords) * 0.002:.3f} (搜索) + 详情费用取决于候选数")

    client = InstagramClient()

    try:
        kols = discover_ig_kols(client=client, keywords=keywords)
    except Exception as e:
        logger.error(f"[IG] 发现过程出错: {e}")
        kols = []

    if not kols:
        logger.warning("[IG] 未找到符合条件的 KOL")
        logger.info(f"[IG] API 调用: {client.request_count} 次, 费用: ${client.estimated_cost:.3f}")
        return

    snapshot_path = save_ig_snapshot(kols)
    logger.info(f"[IG] 快照已保存: {snapshot_path}")

    csv_path = export_ig_csv(kols)
    xlsx_path = export_ig_excel(kols)
    logger.info(f"[IG] CSV 报告: {csv_path}")
    logger.info(f"[IG] Excel 报告: {xlsx_path}")

    logger.info(f"\n{'='*60}")
    logger.info(f"[IG] 发现 {len(kols)} 个港澳财经 KOL")
    logger.info(f"[IG] API 调用: {client.request_count} 次, 费用: ${client.estimated_cost:.3f}")
    logger.info(f"{'='*60}")

    _print_ig_top_kols(kols)


def _print_ig_top_kols(kols: list, top_n: int = 30):
    logger.info(f"\nTOP {min(top_n, len(kols))} IG 港澳财经 KOL:")
    logger.info(f"{'名称':<25} {'@用户名':<20} {'粉丝数':>10} {'HK分':>5} {'内容方向':<20}")
    logger.info("-" * 100)
    for kol in kols[:top_n]:
        focus = ", ".join(kol.content_focus[:3]) if kol.content_focus else "待分析"
        logger.info(
            f"{kol.name:<25} @{kol.username:<19} {kol.follower_count:>10,} "
            f"{kol.hk_relevance_score:>5} {focus:<20}"
        )


def cmd_diff(args):
    latest = get_latest_snapshot()
    if not latest:
        logger.error("没有历史快照，请先运行 discover 命令")
        return

    if args.old:
        old_path = args.old
    else:
        snapshots = list_snapshots()
        if len(snapshots) < 2:
            logger.error("至少需要 2 个快照才能做轧差。请再运行一次 discover。")
            return
        old_path = snapshots[1]["filepath"]
        latest = snapshots[0]["filepath"]

    logger.info(f"旧快照: {old_path}")
    logger.info(f"新快照: {latest}")

    old_kols = load_snapshot(old_path)
    new_kols = load_snapshot(latest)

    result = diff_snapshots(old_kols, new_kols)

    report_path = export_diff_report(result)
    logger.info(f"轧差报告: {report_path}")

    logger.info(f"\n{'='*60}")
    logger.info(f"上期: {result.total_old} 个 KOL → 本期: {result.total_new} 个")
    logger.info(f"新增: {len(result.new_kols)} 个")
    logger.info(f"不再出现: {len(result.lost_kols)} 个")
    logger.info(f"有粉丝增长: {len(result.grown_kols)} 个")
    logger.info(f"{'='*60}")

    if result.new_kols:
        logger.info("\n新增 KOL:")
        for kol in result.new_kols[:10]:
            logger.info(f"  {kol.name} ({kol.subscriber_count:,} 订阅) - {kol.profile_url}")

    if result.grown_kols:
        logger.info("\n粉丝增长 TOP 10:")
        for item in result.grown_kols[:10]:
            kol = item["kol"]
            logger.info(
                f"  {kol.name}: {item['old_subscribers']:,} -> "
                f"{kol.subscriber_count:,} (+{item['growth']:,})"
            )


def cmd_snapshots(_args):
    snapshots = list_snapshots()
    if not snapshots:
        logger.info("暂无快照")
        return

    logger.info(f"共 {len(snapshots)} 个快照:\n")
    for s in snapshots:
        logger.info(f"  {s['filename']}  |  {s['total']} 个 KOL  |  {s['timestamp']}")


def cmd_quota(args):
    keyword_tiers = {
        "core": SEARCH_KEYWORDS,
        "extended": SEARCH_KEYWORDS + SEARCH_KEYWORDS_EXTENDED,
        "all": SEARCH_KEYWORDS + SEARCH_KEYWORDS_EXTENDED + SEARCH_KEYWORDS_LONG_TAIL,
    }
    keywords = keyword_tiers.get(args.tier, SEARCH_KEYWORDS)
    strategy = args.strategy
    max_pages = args.pages

    search_cost = _estimate_quota(len(keywords), max_pages, strategy)

    logger.info(f"关键词数: {len(keywords)}")
    logger.info(f"每关键词最大页数: {max_pages}")
    logger.info(f"搜索策略: {strategy}")
    logger.info(f"预估搜索消耗: ~{search_cost} units")
    logger.info(f"频道详情补全: ~10-20 units (取决于去重后频道数)")
    logger.info(f"总预估: ~{search_cost + 20} units")
    logger.info(f"每日额度: 10,000 units")
    logger.info(f"剩余可用: ~{10000 - search_cost - 20} units")


def _estimate_quota(num_keywords: int, max_pages: int, strategy: str) -> int:
    multiplier = 2 if strategy == "both" else 1
    return num_keywords * max_pages * 100 * multiplier


def _print_top_kols(kols: list, top_n: int = 30):
    logger.info(f"\nTOP {min(top_n, len(kols))} 港澳财经 KOL:")
    logger.info(f"{'名称':<25} {'订阅数':>10} {'HK分':>5} {'内容方向':<20} 链接")
    logger.info("-" * 110)
    for kol in kols[:top_n]:
        focus = ", ".join(kol.content_focus[:3]) if kol.content_focus else "待分析"
        hk_score = getattr(kol, "hk_relevance_score", 0)
        logger.info(
            f"{kol.name:<25} {kol.subscriber_count:>10,} {hk_score:>5} "
            f"{focus:<20} {kol.profile_url}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="YouTube 港澳财经 KOL 发现工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    p_discover = subparsers.add_parser("discover", help="搜索发现 KOL")
    p_discover.add_argument(
        "--tier", choices=["core", "extended", "all"], default="core",
        help="关键词层级: core(8个) / extended(16个) / all(24个)",
    )
    p_discover.add_argument(
        "--strategy", choices=["video", "channel", "both"], default="video",
        help="搜索策略: video(搜视频提取频道) / channel(直接搜频道) / both(两者)",
    )
    p_discover.add_argument(
        "--pages", type=int, default=MAX_PAGES_PER_KEYWORD,
        help=f"每个关键词最大翻页数 (默认 {MAX_PAGES_PER_KEYWORD})",
    )
    p_discover.set_defaults(func=cmd_discover)

    p_ig = subparsers.add_parser("ig-discover", help="Instagram: 搜索港澳财经 KOL")
    p_ig.set_defaults(func=cmd_ig_discover)

    p_diff = subparsers.add_parser("diff", help="与历史快照做月度轧差")
    p_diff.add_argument("--old", help="旧快照文件路径 (默认用倒数第二个)")
    p_diff.set_defaults(func=cmd_diff)

    p_snap = subparsers.add_parser("snapshots", help="查看所有快照")
    p_snap.set_defaults(func=cmd_snapshots)

    p_quota = subparsers.add_parser("quota", help="预估 quota 消耗")
    p_quota.add_argument("--tier", choices=["core", "extended", "all"], default="core")
    p_quota.add_argument("--strategy", choices=["video", "channel", "both"], default="video")
    p_quota.add_argument("--pages", type=int, default=MAX_PAGES_PER_KEYWORD)
    p_quota.set_defaults(func=cmd_quota)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
