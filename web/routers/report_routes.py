"""报表下载路由：提供 Excel / CSV 文件下载。"""

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse

from web.deps import require_auth
from config import OUTPUT_DIR

router = APIRouter()

MIME_MAP = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv; charset=utf-8",
    ".xls": "application/vnd.ms-excel",
}


@router.get("/api/reports/download/{filename}")
async def download_report(filename: str, _user=Depends(require_auth)):
    filepath = os.path.join(OUTPUT_DIR, filename)

    if not os.path.isfile(filepath):
        return JSONResponse({"error": "文件不存在"}, status_code=404)

    _, ext = os.path.splitext(filename)
    media_type = MIME_MAP.get(ext.lower(), "application/octet-stream")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type=media_type,
    )
