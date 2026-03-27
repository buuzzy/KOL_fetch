"""KOL 搜索中台 Web 服务入口。"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    is_prod = os.getenv("ENV") == "production"
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=not is_prod)
