# 视频转即梦提示词

本项目是一个本地运行的手机优先工具：手机浏览器上传视频，本地 Python 服务调用 MiniMax-M3，把视频内容转换成适合即梦 / Seedance 2.0 使用的视频提示词。

## 技术栈

- 前端：Vue 3 + Vite + TypeScript + Vant
- 后端：Python + FastAPI
- LLM：MiniMax-M3，OpenAI SDK 兼容接口
- 视频输入：小视频 base64 直传，大视频预留 MiniMax Files API

## 目录结构

```text
frontend/   手机端网页
backend/    FastAPI 本地服务
docs/       设计与提示词说明
```

## 本地启动

后端：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env，填入 MINIMAX_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

也可以在项目根目录一键启动前后端开发服务：

```powershell
.\scripts\dev.ps1
```

首次拉取项目可先执行：

```powershell
.\scripts\setup.ps1
```

如果希望由后端同源托管前端构建产物：

```powershell
.\scripts\start.ps1
```

手机访问：

```text
http://电脑局域网IP:5173
```

默认开发模式下，前端通过 Vite proxy 把 `/api` 转发到 `127.0.0.1:8000`。如果使用 `npm run preview`、静态部署 `frontend/dist`，或希望手机直接访问后端地址，请在 `frontend/.env.local` 配置：

```env
VITE_API_BASE_URL=http://电脑局域网IP:8000
```

直连后端时，`backend/.env` 的 `ALLOWED_ORIGINS` 也需要包含前端访问地址，例如：

```env
ALLOWED_ORIGINS=http://电脑局域网IP:5173
```

## MiniMax 配置

`backend/.env` 里至少需要：

```env
MINIMAX_API_KEY=你的MiniMax API Key
```

默认使用：

```env
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M3
```

当前默认小视频 base64 直传，阈值为 `45MB`，是为了避开 MiniMax URL/base64 视频 `50MB` 和请求体 `64MB` 限制。

当 `MINIMAX_ENABLE_FILES_API=false` 时，后端会按 `MINIMAX_MAX_BASE64_MB` 在上传阶段直接拦截超限视频；当启用 Files API 时，上传上限由 `MAX_UPLOAD_MB` 控制，默认 `500MB`。

任务处理完成或失败后，后端会删除本地临时视频文件，避免长期运行时堆积用户素材。

大视频 Files API 路径已预留：

```env
MINIMAX_ENABLE_FILES_API=true
MINIMAX_FILE_PURPOSE=vision
```

MiniMax 的 Files API 在视频场景下的 `purpose` 如有变化，只需要改 `MINIMAX_FILE_PURPOSE`。

## 自动化验证与进化

本项目提供统一验证脚本：

```powershell
.\scripts\eval.ps1
```

它会执行前端构建、后端编译、后端导入和 API smoke 测试。

创建一次 autoresearch 进化运行：

```powershell
.\scripts\evolve.ps1 -Rounds 10 -Goal "提升稳定性、提示词质量和手机端体验"
```

具体适应度函数和候选报告格式见 `docs/AUTORESEARCH.md`。

真实 MiniMax API 手动验收：

```powershell
.\scripts\real-e2e.ps1 -VideoPath C:\path\to\sample.mp4
```

该命令会读取 `backend/.env`，需要先配置 `MINIMAX_API_KEY`。

## Docker 运行

准备好 `backend/.env` 后，可使用：

```powershell
docker compose up --build
```

访问：

```text
http://127.0.0.1:8000
```
