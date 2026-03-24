"""快照路由：列表、详情、轧差对比（Supabase 数据源）。"""

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse

from web.deps import templates, get_current_user, require_auth
from storage import (
    list_snapshots_db, load_snapshot_db, delete_snapshot_db,
    diff_snapshots, diff_ig_snapshots,
)
from discovery import KOL
from report import export_diff_report

router = APIRouter()


def _build_display_params(search_params: dict, platform: str) -> dict:
    """将原始搜索参数转换为中文可读的展示格式。"""
    depth_label = {"fast": "快速扫描", "standard": "标准搜索", "deep": "深度搜索"}

    if platform == "youtube":
        inactive_days = int(search_params.get("max_inactive_days", 90))
        inactive_str = f"最近 {inactive_days} 天内有发布" if inactive_days > 0 else "不限"
        display = {
            "平台": "YouTube",
            "搜索深度": depth_label.get(search_params.get("depth", ""), "标准搜索"),
            "订阅范围": (
                f"{int(search_params.get('min_subscribers', 1000)):,} ~ "
                f"{int(search_params.get('max_subscribers', 200000)):,}"
            ),
            "活跃度": inactive_str,
        }
    else:
        display = {
            "平台": "Instagram",
            "粉丝范围": (
                f"{int(search_params.get('min_followers', 1000)):,} ~ "
                f"{int(search_params.get('max_followers', 200000)):,}"
            ),
        }

    selected = search_params.get("selected_keywords", "")
    keywords = [k.strip() for k in selected.strip().splitlines() if k.strip()]
    custom = search_params.get("custom_keywords", "")
    if custom.strip():
        keywords += [k.strip() for k in custom.strip().splitlines() if k.strip()]
    if keywords:
        display["关键词"] = keywords

    return display


def _snapshot_label(snap: dict) -> str:
    """为快照生成简短标签供 UI 展示。"""
    ts = (snap.get("created_at") or "")[:16].replace("T", " ")
    return f"{snap['platform'].upper()} · {snap.get('total_kols', 0)} KOL · {ts}"


@router.get("/snapshots")
async def snapshots_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    all_snapshots = list_snapshots_db()
    for s in all_snapshots:
        s["label"] = _snapshot_label(s)
        params = s.get("search_params") or {}
        kws = []
        selected = params.get("selected_keywords", "")
        if selected:
            kws += [k.strip() for k in selected.strip().splitlines() if k.strip()]
        custom = params.get("custom_keywords", "")
        if custom and custom.strip():
            kws += [k.strip() for k in custom.strip().splitlines() if k.strip()]
        s["keywords_summary"] = kws[:6]
        s["keywords_total"] = len(kws)

    return templates.TemplateResponse("snapshots.html", {
        "request": request,
        "active_page": "snapshots",
        "user_email": user.email,
        "snapshots": all_snapshots,
    })


@router.get("/snapshots/{snapshot_id}")
async def snapshot_detail_page(request: Request, snapshot_id: str):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    snap = load_snapshot_db(snapshot_id)
    if not snap:
        return templates.TemplateResponse("snapshot_detail.html", {
            "request": request,
            "active_page": "snapshots",
            "user_email": user.email,
            "snapshot_id": snapshot_id,
            "kols": [],
            "platform": "unknown",
            "error": "快照不存在",
        })

    platform = snap["platform"]
    kols_data = snap.get("kols_data") or []

    search_params = snap.get("search_params") or {}
    display_params = _build_display_params(search_params, platform)

    return templates.TemplateResponse("snapshot_detail.html", {
        "request": request,
        "active_page": "snapshots",
        "user_email": user.email,
        "snapshot_id": snapshot_id,
        "kols": kols_data,
        "platform": platform,
        "total": len(kols_data),
        "meta": {"search_params": display_params},
        "error": None,
    })


@router.delete("/api/snapshots/{snapshot_id}")
async def delete_snapshot(snapshot_id: str, user=Depends(require_auth)):
    delete_snapshot_db(snapshot_id)
    return JSONResponse({"success": True})


@router.get("/diff")
async def diff_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    yt_list = list_snapshots_db("youtube")
    ig_list = list_snapshots_db("instagram")

    for s in yt_list + ig_list:
        s["label"] = _snapshot_label(s)

    return templates.TemplateResponse("diff.html", {
        "request": request,
        "active_page": "diff",
        "user_email": user.email,
        "yt_snapshots": yt_list,
        "ig_snapshots": ig_list,
        "result": None,
    })


@router.post("/api/snapshots/diff")
async def do_diff(
    request: Request,
    user=Depends(require_auth),
    platform: str = Form(...),
    old_id: str = Form(...),
    new_id: str = Form(...),
):
    old_snap = load_snapshot_db(old_id)
    new_snap = load_snapshot_db(new_id)

    if not old_snap or not new_snap:
        yt_list = list_snapshots_db("youtube")
        ig_list = list_snapshots_db("instagram")
        for s in yt_list + ig_list:
            s["label"] = _snapshot_label(s)
        return templates.TemplateResponse("diff.html", {
            "request": request,
            "active_page": "diff",
            "user_email": user.email,
            "yt_snapshots": yt_list,
            "ig_snapshots": ig_list,
            "result": None,
            "error": "快照不存在",
        })

    old_data = old_snap.get("kols_data") or []
    new_data = new_snap.get("kols_data") or []

    if platform == "instagram":
        from instagram_discovery import IGKOL
        old_kols = [IGKOL(**d) for d in old_data]
        new_kols = [IGKOL(**d) for d in new_data]
        diff_result = diff_ig_snapshots(old_kols, new_kols)
    else:
        old_kols = [KOL(**d) for d in old_data]
        new_kols = [KOL(**d) for d in new_data]
        diff_result = diff_snapshots(old_kols, new_kols)

    report_path = ""
    if platform == "youtube":
        try:
            report_path = export_diff_report(diff_result)
        except Exception:
            pass

    new_kol_list = [k.to_dict() if hasattr(k, 'to_dict') else k.__dict__ for k in diff_result.new_kols]
    lost_kol_list = [k.to_dict() if hasattr(k, 'to_dict') else k.__dict__ for k in diff_result.lost_kols]

    grown_list = []
    for item in diff_result.grown_kols[:20]:
        kol = item["kol"]
        d = kol.to_dict() if hasattr(kol, 'to_dict') else kol.__dict__
        grown_list.append({
            "kol": d,
            "old_count": item.get("old_subscribers", item.get("old_followers", 0)),
            "growth": item["growth"],
        })

    yt_list = list_snapshots_db("youtube")
    ig_list = list_snapshots_db("instagram")
    for s in yt_list + ig_list:
        s["label"] = _snapshot_label(s)

    return templates.TemplateResponse("diff.html", {
        "request": request,
        "active_page": "diff",
        "user_email": user.email,
        "yt_snapshots": yt_list,
        "ig_snapshots": ig_list,
        "result": {
            "platform": platform,
            "total_old": diff_result.total_old,
            "total_new": diff_result.total_new,
            "new_kols": new_kol_list,
            "lost_kols": lost_kol_list,
            "grown_kols": grown_list,
            "report_path": report_path,
        },
        "error": None,
    })
