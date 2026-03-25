"""认证路由：登录 / 登出 / 当前用户。"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse

from web.deps import templates, get_admin_client, get_current_user

router = APIRouter()


@router.get("/login")
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "login.html", context={"error": None})


@router.post("/api/auth/login")
async def api_login(request: Request, email: str = Form(...), password: str = Form(...)):
    try:
        client = get_admin_client()
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        token = resp.session.access_token
        response = RedirectResponse("/dashboard", status_code=302)
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 7,  # 7 天
        )
        return response
    except Exception as e:
        error_msg = "邮箱或密码错误"
        if "Invalid login" in str(e) or "invalid" in str(e).lower():
            error_msg = "邮箱或密码错误"
        elif "Email not confirmed" in str(e):
            error_msg = "邮箱未验证，请检查邮箱"
        return templates.TemplateResponse(
            request, "login.html",
            context={"error": error_msg},
            status_code=401,
        )


@router.get("/api/auth/logout")
async def api_logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/api/auth/me")
async def api_me(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse({"error": "未登录"}, status_code=401)
    return {"id": user.id, "email": user.email}
