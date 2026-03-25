"""发现搜索路由：提交 YouTube / Instagram 任务 + 任务进度页 + SSE 流 + Dashboard。"""

import time
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse, StreamingResponse

from web.deps import templates, get_current_user, require_auth
from web.task_manager import task_manager
from storage import list_snapshots_db

router = APIRouter()


@router.get("/dashboard")
async def dashboard_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    yt_snapshots = list_snapshots_db("youtube")
    ig_snapshots = list_snapshots_db("instagram")
    all_tasks = task_manager.list_tasks()
    running = sum(1 for t in all_tasks if t.status == "running")
    completed_today = sum(
        1 for t in all_tasks
        if t.status == "completed" and (time.time() - t.created_at) < 86400
    )

    task_display = []
    for t in all_tasks[:20]:
        t_dict = t.__dict__.copy()
        elapsed = time.time() - t.created_at
        if elapsed < 60:
            t_dict["created_at_display"] = "刚刚"
        elif elapsed < 3600:
            t_dict["created_at_display"] = f"{int(elapsed // 60)} 分钟前"
        else:
            t_dict["created_at_display"] = f"{int(elapsed // 3600)} 小时前"
        task_display.append(t_dict)

    return templates.TemplateResponse(request, "dashboard.html", context={
        "active_page": "dashboard",
        "user_email": user.email,
        "yt_snapshot_count": len(yt_snapshots),
        "ig_snapshot_count": len(ig_snapshots),
        "running_tasks": running,
        "completed_today": completed_today,
        "tasks": task_display,
    })


@router.get("/discover")
async def discover_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    from config import (
        SEARCH_KEYWORDS, SEARCH_KEYWORDS_EXTENDED, SEARCH_KEYWORDS_LONG_TAIL,
        IG_SEARCH_KEYWORDS,
    )

    platform = request.query_params.get("platform", "youtube")
    return templates.TemplateResponse(request, "discover.html", context={
        "active_page": "discover",
        "user_email": user.email,
        "platform": platform,
        "yt_core_keywords": SEARCH_KEYWORDS,
        "yt_extended_keywords": SEARCH_KEYWORDS_EXTENDED,
        "yt_longtail_keywords": SEARCH_KEYWORDS_LONG_TAIL,
        "ig_keywords": IG_SEARCH_KEYWORDS,
    })


DEPTH_PRESETS = {
    "fast":     {"strategy": "video",  "pages": 2},
    "standard": {"strategy": "video",  "pages": 3},
    "deep":     {"strategy": "both",   "pages": 3},
}


@router.post("/api/discover/youtube")
async def submit_youtube(
    request: Request,
    user=Depends(require_auth),
    selected_keywords: str = Form(""),
    custom_keywords: str = Form(""),
    min_subscribers: int = Form(1000),
    max_subscribers: int = Form(200000),
    depth: str = Form("standard"),
    max_inactive_days: int = Form(90),
):
    preset = DEPTH_PRESETS.get(depth, DEPTH_PRESETS["standard"])
    params = {
        "selected_keywords": selected_keywords,
        "custom_keywords": custom_keywords,
        "min_subscribers": min_subscribers,
        "max_subscribers": max_subscribers,
        "strategy": preset["strategy"],
        "pages": preset["pages"],
        "depth": depth,
        "max_inactive_days": max_inactive_days,
    }
    task_id = task_manager.submit_youtube(params, user.id)
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.post("/api/discover/instagram")
async def submit_instagram(
    request: Request,
    user=Depends(require_auth),
    selected_keywords: str = Form(""),
    custom_keywords: str = Form(""),
    min_followers: int = Form(1000),
    max_followers: int = Form(200000),
):
    params = {
        "selected_keywords": selected_keywords,
        "custom_keywords": custom_keywords,
        "min_followers": min_followers,
        "max_followers": max_followers,
    }
    task_id = task_manager.submit_instagram(params, user.id)
    return RedirectResponse(f"/tasks/{task_id}", status_code=302)


@router.get("/tasks/{task_id}")
async def task_progress_page(request: Request, task_id: str):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    state = task_manager.get_state(task_id)
    if not state:
        return templates.TemplateResponse(request, "task_progress.html", context={
            "active_page": "discover",
            "user_email": user.email,
            "task_id": task_id,
            "task": None,
        })

    return templates.TemplateResponse(request, "task_progress.html", context={
        "active_page": "discover",
        "user_email": user.email,
        "task_id": task_id,
        "task": state,
    })


@router.get("/api/tasks/{task_id}/stream")
async def task_stream(task_id: str, user=Depends(require_auth)):
    return StreamingResponse(
        task_manager.stream_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
