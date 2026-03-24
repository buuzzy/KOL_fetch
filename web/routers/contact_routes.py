"""联系博主路由：联系人管理、快照导入、模板 CRUD、邮件发送。"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse

logger = logging.getLogger(__name__)

from web.deps import templates, get_current_user, require_auth, get_admin_client
from web.email_sender import extract_contacts, merge_contacts, send_bulk
from web.channel_scraper import scrape_channels_batch
from storage import list_snapshots_db, load_snapshot_db

router = APIRouter()


# ── 联系人列表页 ──

@router.get("/contacts")
async def contacts_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    client = get_admin_client()
    resp = client.table("kol_contacts").select("*").order("created_at", desc=True).execute()
    contacts = resp.data or []

    for c in contacts:
        try:
            notes = json.loads(c.get("notes") or "{}")
            c["hk_relevance_score"] = notes.get("hk_score", 0)
        except (json.JSONDecodeError, TypeError):
            c["hk_relevance_score"] = 0

        channels = c.get("contact_channels") or {}
        if isinstance(channels, str):
            try:
                channels = json.loads(channels)
            except (json.JSONDecodeError, TypeError):
                channels = {}
        c["_channels"] = channels
        c["_has_contact"] = bool(channels) or bool(c.get("email"))

    all_snapshots = list_snapshots_db()
    with_email = sum(1 for c in contacts if c.get("email"))
    with_contact = sum(1 for c in contacts if c.get("_has_contact"))

    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "active_page": "contacts",
        "user_email": user.email,
        "contacts": contacts,
        "snapshots": all_snapshots,
        "total": len(contacts),
        "with_email": with_email,
        "with_contact": with_contact,
    })


# ── 快照导入 ──

def _enrich_contacts_background(contact_records: list[dict]):
    """后台任务：爬取 YouTube 频道页面，补充外部链接到 contact_channels。"""
    profile_urls = [r["profile_url"] for r in contact_records if r.get("profile_url")]
    if not profile_urls:
        return

    logger.info("[Enrich] 开始爬取 %d 个 YouTube 频道外部链接...", len(profile_urls))
    scraped = scrape_channels_batch(profile_urls, delay=2.0)

    client = get_admin_client()
    enriched = 0
    for record in contact_records:
        url = record.get("profile_url", "")
        page_links = scraped.get(url)
        if not page_links:
            continue

        existing_channels = record.get("contact_channels") or {}
        merged = merge_contacts(existing_channels, page_links)
        if merged == existing_channels:
            continue

        email = merged.get("email", [""])[0] if merged.get("email") else record.get("email", "")
        update: dict = {"contact_channels": merged}
        if email and not record.get("email"):
            update["email"] = email
            update["email_source"] = "scraped"

        try:
            client.table("kol_contacts").update(update).eq("id", record["id"]).execute()
            enriched += 1
        except Exception as e:
            logger.warning("[Enrich] 更新失败 %s: %s", record.get("name"), e)

    logger.info("[Enrich] 完成，%d/%d 个联系人已补充外部链接", enriched, len(contact_records))


@router.post("/api/contacts/import")
async def import_from_snapshot(
    request: Request,
    background_tasks: BackgroundTasks,
    user=Depends(require_auth),
    snapshot_id: str = Form(...),
):
    snap = load_snapshot_db(snapshot_id)
    if not snap:
        return JSONResponse({"error": "快照不存在"}, status_code=404)

    platform = snap["platform"]
    kols_data = snap.get("kols_data") or []

    client = get_admin_client()

    existing_resp = client.table("kol_contacts").select("platform_id").execute()
    existing_ids = {r["platform_id"] for r in (existing_resp.data or [])}

    imported = 0
    skipped = 0
    new_records: list[dict] = []

    for d in kols_data:
        if platform == "youtube":
            platform_id = d.get("channel_id", "")
            name = d.get("name", "")
            follower_count = d.get("subscriber_count", 0)
            profile_url = d.get("profile_url", "")
            contact_text = d.get("description", "")
            hk_score = d.get("hk_relevance_score", 0)
        else:
            platform_id = d.get("username", "")
            name = d.get("name", "")
            follower_count = d.get("follower_count", 0)
            profile_url = d.get("profile_url", "")
            contact_text = (d.get("biography", "") or "") + " " + (d.get("external_url", "") or "")
            hk_score = d.get("hk_relevance_score", 0)

        if not platform_id or platform_id in existing_ids:
            skipped += 1
            continue

        channels = extract_contacts(contact_text)
        email = channels.get("email", [""])[0] if channels.get("email") else ""

        content_focus_str = ", ".join(d.get("content_focus", []) or [])

        record = {
            "id": str(uuid.uuid4()),
            "platform": platform,
            "platform_id": platform_id,
            "name": name,
            "email": email,
            "email_source": "auto" if email else "",
            "follower_count": follower_count,
            "profile_url": profile_url,
            "content_focus": content_focus_str,
            "contact_channels": channels,
            "notes": json.dumps({"hk_score": hk_score, "snapshot_id": snapshot_id}, ensure_ascii=False),
        }
        client.table("kol_contacts").insert(record).execute()
        existing_ids.add(platform_id)
        new_records.append(record)
        imported += 1

    if platform == "youtube" and new_records:
        background_tasks.add_task(_enrich_contacts_background, new_records)

    return JSONResponse({
        "imported": imported,
        "skipped": skipped,
        "total": imported + skipped,
        "enriching": platform == "youtube" and len(new_records) > 0,
    })


# ── 更新邮箱 ──

@router.put("/api/contacts/{contact_id}/email")
async def update_email(
    contact_id: str,
    request: Request,
    user=Depends(require_auth),
):
    body = await request.json()
    email = body.get("email", "").strip()

    client = get_admin_client()
    client.table("kol_contacts").update({
        "email": email,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()

    return JSONResponse({"success": True})


# ── 删除联系人 ──

@router.delete("/api/contacts/{contact_id}")
async def delete_contact(contact_id: str, user=Depends(require_auth)):
    client = get_admin_client()
    client.table("kol_contacts").delete().eq("id", contact_id).execute()
    return JSONResponse({"success": True})


VALID_CONTACT_STATUSES = {"pending", "contacted", "replied", "cooperating"}

@router.patch("/api/contacts/{contact_id}/status")
async def update_contact_status(contact_id: str, request: Request, user=Depends(require_auth)):
    body = await request.json()
    status = body.get("status", "")
    if status not in VALID_CONTACT_STATUSES:
        return JSONResponse({"error": f"无效状态: {status}"}, status_code=400)
    client = get_admin_client()
    client.table("kol_contacts").update({
        "contact_status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()
    return JSONResponse({"success": True})


@router.post("/api/contacts/batch-delete")
async def batch_delete_contacts(request: Request, user=Depends(require_auth)):
    body = await request.json()
    ids = body.get("ids", [])
    if not ids:
        return JSONResponse({"error": "未选择联系人"}, status_code=400)

    client = get_admin_client()
    client.table("kol_contacts").delete().in_("id", ids).execute()
    return JSONResponse({"success": True, "deleted": len(ids)})


# ── 模板管理页 ──

@router.get("/contacts/templates")
async def templates_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    client = get_admin_client()
    resp = client.table("email_templates").select("*").order("created_at", desc=True).execute()

    return templates.TemplateResponse("email_templates.html", {
        "request": request,
        "active_page": "contacts",
        "user_email": user.email,
        "email_templates": resp.data or [],
    })


# ── 模板 CRUD ──

@router.post("/api/contacts/templates")
async def create_template(
    request: Request,
    user=Depends(require_auth),
    name: str = Form(...),
    subject: str = Form(...),
    body_html: str = Form(...),
):
    client = get_admin_client()
    client.table("email_templates").insert({
        "id": str(uuid.uuid4()),
        "name": name,
        "subject": subject,
        "body": body_html,
        "created_by": user.id,
    }).execute()
    return RedirectResponse("/contacts/templates", status_code=302)


@router.put("/api/contacts/templates/{template_id}")
async def update_template(
    template_id: str,
    request: Request,
    user=Depends(require_auth),
):
    body = await request.json()
    update = {}
    if "name" in body:
        update["name"] = body["name"]
    if "subject" in body:
        update["subject"] = body["subject"]
    if "body_html" in body:
        update["body"] = body["body_html"]
    if not update:
        return JSONResponse({"error": "无更新内容"}, status_code=400)

    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    client = get_admin_client()
    client.table("email_templates").update(update).eq("id", template_id).execute()
    return JSONResponse({"success": True})


@router.delete("/api/contacts/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(require_auth)):
    client = get_admin_client()
    client.table("email_templates").delete().eq("id", template_id).execute()
    return JSONResponse({"success": True})


# ── 撰写邮件页 ──

@router.get("/contacts/compose")
async def compose_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    client = get_admin_client()
    tpl_resp = client.table("email_templates").select("*").order("created_at", desc=True).execute()
    contacts_resp = (
        client.table("kol_contacts")
        .select("*")
        .neq("email", "")
        .order("name")
        .execute()
    )

    preselected = request.query_params.get("ids", "")

    return templates.TemplateResponse("email_compose.html", {
        "request": request,
        "active_page": "contacts",
        "user_email": user.email,
        "email_templates": tpl_resp.data or [],
        "contacts": contacts_resp.data or [],
        "preselected_ids": preselected,
    })


# ── 批量发送邮件 ──

@router.post("/api/contacts/send")
async def send_emails(request: Request, user=Depends(require_auth)):
    body = await request.json()
    template_id = body.get("template_id", "")
    contact_ids = body.get("contact_ids", [])
    from_name = body.get("from_name", "")

    if not template_id or not contact_ids:
        return JSONResponse({"error": "请选择模板和收件人"}, status_code=400)

    client = get_admin_client()

    tpl_resp = client.table("email_templates").select("*").eq("id", template_id).execute()
    if not tpl_resp.data:
        return JSONResponse({"error": "模板不存在"}, status_code=404)
    tpl = tpl_resp.data[0]

    contacts_resp = (
        client.table("kol_contacts")
        .select("*")
        .in_("id", contact_ids)
        .execute()
    )
    contacts = contacts_resp.data or []

    recipients = [{"email": c["email"], "name": c["name"]} for c in contacts if c.get("email")]
    if not recipients:
        return JSONResponse({"error": "所选联系人均无邮箱"}, status_code=400)

    results = send_bulk(
        recipients=recipients,
        subject=tpl["subject"],
        body_html=tpl["body"],
        from_name=from_name,
    )

    now = datetime.now(timezone.utc).isoformat()
    for r in results:
        contact_match = next((c for c in contacts if c["email"] == r["email"]), None)
        client.table("email_logs").insert({
            "id": str(uuid.uuid4()),
            "kol_contact_id": contact_match["id"] if contact_match else None,
            "template_id": template_id,
            "recipient_email": r["email"],
            "subject": tpl["subject"].replace("{{name}}", r.get("name", "")),
            "status": "sent" if r["success"] else "failed",
            "error_message": r.get("error", ""),
            "sent_at": now,
            "created_by": user.id,
        }).execute()

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    return JSONResponse({
        "success_count": success_count,
        "fail_count": fail_count,
        "total": len(results),
        "details": results,
    })
