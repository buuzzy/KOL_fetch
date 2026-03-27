# KOL 搜索中台

港澳财经博主发现平台 — 前后端分离架构

## 架构

```
KOL_fetch/
  backend/          FastAPI API 服务 (Cloud Run)
  frontend/         React SPA (Cloudflare Pages)
```

- **前端**: React + TypeScript + TailwindCSS + Vite
- **后端**: FastAPI (Python 3.12) — 纯 JSON API
- **数据层**: Supabase (Postgres + Auth)
- **认证**: Bearer Token (Supabase JWT)

## 本地开发

### 环境变量

复制 `.env.example` 为 `.env`，填入所有密钥。

### 后端

```bash
cd backend
pip install -r requirements.txt
python run_web.py
# API 运行在 http://localhost:8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 前端运行在 http://localhost:5173，API 请求自动代理到 :8000
```

### Docker

```bash
docker compose up --build
# API 运行在 http://localhost:8000
# 前端需单独 npm run dev 或部署到 Cloudflare Pages
```

## CLI 工具

```bash
cd backend
python main.py discover              # YouTube: 搜索 KOL
python main.py ig-discover           # Instagram: 搜索 KOL
python main.py diff                  # 月度轧差
python main.py snapshots             # 查看快照
python main.py quota                 # 预估 quota 消耗
```

## 部署

- **后端**: Cloud Build → Cloud Run (`cloudbuild.yaml`)
- **前端**: Cloudflare Pages (连接仓库，Build: `cd frontend && npm run build`，Output: `frontend/dist`)
- 环境变量 `VITE_API_BASE_URL` 设为 Cloud Run 服务 URL
- 环境变量 `CORS_ORIGINS` 设为 Cloudflare Pages 域名
