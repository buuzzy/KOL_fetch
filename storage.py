"""数据存储与月度轧差：Supabase 快照 + 本地 JSON 兜底 + diff 逻辑。"""

import json
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass

from discovery import KOL
from config import DATA_DIR

SNAPSHOT_PREFIX = "kol_snapshot_"
IG_SNAPSHOT_PREFIX = "ig_kol_snapshot_"


def save_snapshot(kols: list[KOL], tag: str = "") -> str:
    """保存 KOL 快照到 JSON 文件，返回文件路径。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"{SNAPSHOT_PREFIX}{timestamp}{suffix}.json"
    filepath = os.path.join(DATA_DIR, filename)

    data = {
        "timestamp": datetime.now().isoformat(),
        "total": len(kols),
        "kols": [k.to_dict() for k in kols],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def load_snapshot(filepath: str) -> list[KOL]:
    """从 JSON 文件加载 KOL 快照。"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    kols = []
    for item in data["kols"]:
        kols.append(KOL(**item))
    return kols


def get_latest_snapshot() -> str | None:
    """获取最新的快照文件路径。"""
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith(SNAPSHOT_PREFIX) and f.endswith(".json")
    ]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(DATA_DIR, files[0])


def list_snapshots() -> list[dict]:
    """列出所有快照文件及其元信息。"""
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith(SNAPSHOT_PREFIX) and f.endswith(".json")
    ]
    files.sort(reverse=True)

    result = []
    for f in files:
        filepath = os.path.join(DATA_DIR, f)
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result.append({
            "filename": f,
            "filepath": filepath,
            "timestamp": data.get("timestamp", ""),
            "total": data.get("total", 0),
        })
    return result


def save_ig_snapshot(kols: list, tag: str = "") -> str:
    """保存 Instagram KOL 快照到 JSON 文件。"""
    from instagram_discovery import IGKOL
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    filename = f"{IG_SNAPSHOT_PREFIX}{timestamp}{suffix}.json"
    filepath = os.path.join(DATA_DIR, filename)

    data = {
        "timestamp": datetime.now().isoformat(),
        "platform": "instagram",
        "total": len(kols),
        "kols": [k.to_dict() for k in kols],
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath


def load_ig_snapshot(filepath: str) -> list:
    """从 JSON 文件加载 IG KOL 快照。"""
    from instagram_discovery import IGKOL
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [IGKOL(**item) for item in data["kols"]]


def get_latest_ig_snapshot() -> str | None:
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith(IG_SNAPSHOT_PREFIX) and f.endswith(".json")
    ]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(DATA_DIR, files[0])


def list_ig_snapshots() -> list[dict]:
    files = [
        f for f in os.listdir(DATA_DIR)
        if f.startswith(IG_SNAPSHOT_PREFIX) and f.endswith(".json")
    ]
    files.sort(reverse=True)
    result = []
    for f in files:
        filepath = os.path.join(DATA_DIR, f)
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        result.append({
            "filename": f,
            "filepath": filepath,
            "timestamp": data.get("timestamp", ""),
            "total": data.get("total", 0),
        })
    return result


def diff_ig_snapshots(old_kols: list, new_kols: list):
    """对比两次 IG 快照。"""
    old_map = {k.username: k for k in old_kols}
    new_map = {k.username: k for k in new_kols}

    new_ids = set(new_map.keys()) - set(old_map.keys())
    lost_ids = set(old_map.keys()) - set(new_map.keys())
    common = set(old_map.keys()) & set(new_map.keys())

    grown = []
    for uid in common:
        old_f = old_map[uid].follower_count
        new_f = new_map[uid].follower_count
        if new_f > old_f:
            grown.append({
                "kol": new_map[uid],
                "old_followers": old_f,
                "growth": new_f - old_f,
            })
    grown.sort(key=lambda x: x["growth"], reverse=True)

    return DiffResult(
        new_kols=[new_map[uid] for uid in new_ids],
        lost_kols=[old_map[uid] for uid in lost_ids],
        grown_kols=grown,
        total_old=len(old_kols),
        total_new=len(new_kols),
    )


@dataclass
class DiffResult:
    new_kols: list[KOL]
    lost_kols: list[KOL]
    grown_kols: list[dict]  # {"kol": KOL, "old_subscribers": int, "growth": int}
    total_old: int
    total_new: int


def diff_snapshots(old_kols: list[KOL], new_kols: list[KOL]) -> DiffResult:
    """对比两次快照，找出新增、消失和增长的 KOL。"""
    old_map = {k.channel_id: k for k in old_kols}
    new_map = {k.channel_id: k for k in new_kols}

    new_ids = set(new_map.keys()) - set(old_map.keys())
    lost_ids = set(old_map.keys()) - set(new_map.keys())
    common_ids = set(old_map.keys()) & set(new_map.keys())

    grown = []
    for cid in common_ids:
        old_sub = old_map[cid].subscriber_count
        new_sub = new_map[cid].subscriber_count
        growth = new_sub - old_sub
        if growth > 0:
            grown.append({
                "kol": new_map[cid],
                "old_subscribers": old_sub,
                "growth": growth,
            })

    grown.sort(key=lambda x: x["growth"], reverse=True)

    return DiffResult(
        new_kols=[new_map[cid] for cid in new_ids],
        lost_kols=[old_map[cid] for cid in lost_ids],
        grown_kols=grown,
        total_old=len(old_kols),
        total_new=len(new_kols),
    )


# ══════════════════════════════════════════════════════
# Supabase 快照存储（Web 中台使用）
# ══════════════════════════════════════════════════════

def _get_db():
    from web.deps import get_admin_client
    return get_admin_client()


def save_snapshot_db(kols_data: list[dict], platform: str,
                     search_params: dict, user_id: str = None) -> str:
    """保存快照到 Supabase，返回快照 ID。"""
    snapshot_id = str(uuid.uuid4())
    _get_db().table("snapshots").insert({
        "id": snapshot_id,
        "platform": platform,
        "search_params": search_params,
        "kols_data": kols_data,
        "total_kols": len(kols_data),
        "created_by": user_id,
    }).execute()
    return snapshot_id


def load_snapshot_db(snapshot_id: str) -> dict | None:
    """从 Supabase 加载一条快照，返回完整行或 None。"""
    resp = _get_db().table("snapshots").select("*").eq("id", snapshot_id).execute()
    return resp.data[0] if resp.data else None


def list_snapshots_db(platform: str | None = None) -> list[dict]:
    """列出 Supabase 中的快照（不含 kols_data 大字段）。"""
    query = _get_db().table("snapshots").select(
        "id, platform, search_params, total_kols, created_by, created_at"
    ).order("created_at", desc=True)
    if platform:
        query = query.eq("platform", platform)
    resp = query.execute()
    return resp.data or []


def delete_snapshot_db(snapshot_id: str):
    """删除 Supabase 中的一条快照。"""
    _get_db().table("snapshots").delete().eq("id", snapshot_id).execute()
