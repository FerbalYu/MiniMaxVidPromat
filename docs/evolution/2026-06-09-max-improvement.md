# 2026-06-09 最大化改进报告

目标：把项目从可运行 MVP 推进到更接近可长期使用的本地工具，覆盖真实成功率、任务可靠性、提示词质量、手机体验、部署和验证。

## 已实现

### 后端可靠性

- 任务从内存表升级为 SQLite 持久化，服务重启后可读取历史任务。
- 引入受控 `ThreadPoolExecutor`，通过 `MAX_CONCURRENT_JOBS` 限制 MiniMax 并发。
- 增加任务取消、重试入口和过期任务清理。
- 任务公开响应过滤本地文件路径，内部仍可用 `meta.path` 处理文件。
- `health` 暴露模型、上传上限、并发和任务保留时长，便于前端预检。

### MiniMax 质量链路

- 视频分析改为两阶段：先提取视频事实 JSON，再生成即梦/Seedance 提示词。
- OpenAI 兼容客户端增加统一超时配置。
- JSON 解析支持 Markdown fenced JSON、正文包裹 JSON、`result` 嵌套、列表/对象字段字符串化。
- 可选 JSON 修复兜底由 `MINIMAX_REPAIR_JSON` 控制。
- 增加真实 API 手动验收脚本：`scripts/real-e2e.ps1`。

### 前端手机体验

- 启动时读取后端 health，展示模型、上传上限和并发。
- 上传前按后端配置做文件大小预检。
- 上传时显示上传进度。
- 最近任务列表可查看历史任务。
- 支持取消任务、重新生成、结果编辑、下载 TXT。
- 轮询仍保持递归 `setTimeout`，避免请求重叠。

### 自动化验证

- 后端 smoke 覆盖：
  - health
  - 非法格式
  - 空视频
  - 超限上传
  - 公开响应不暴露本地路径
  - MiniMax 成功/失败 mock
  - 处理后文件清理
  - JSON 解析兜底
- 前端 Playwright 手机端 smoke 覆盖：
  - health 展示
  - 选择视频
  - 提交任务
  - mock 完成轮询
  - 结果渲染
  - 编辑器和历史任务
- `eval.ps1` 统一运行前端构建、前端 E2E、后端编译、后端 smoke 和 PowerShell 脚本语法检查。

### 部署和启动

- `scripts/setup.ps1`：安装后端、前端和 Playwright 依赖。
- `scripts/dev.ps1`：开发模式同时启动前后端。
- `scripts/start.ps1`：构建前端后由 FastAPI 同源托管。
- FastAPI 自动挂载 `frontend/dist`。
- 新增 Dockerfile 和 docker-compose.yml。

## 自动验证结果

已通过：

```text
.\scripts\eval.ps1
frontend build passed
frontend e2e passed
backend compile passed
backend import passed
backend smoke passed
powershell syntax passed
```

## 未在本机验证

- Docker：本机没有 `docker` 命令，Dockerfile 和 Compose 未实际 build。
- 真实 MiniMax API：未提供真实 `MINIMAX_API_KEY` 和样例视频，本轮未调用真实 API。
- 真实手机局域网：Playwright 已覆盖移动视口，但未用实体手机验证上传和复制。

## 下一步建议

1. 配置真实 `MINIMAX_API_KEY` 后运行 `scripts/real-e2e.ps1`。
2. 在安装 Docker 的机器上执行 `docker compose up --build`。
3. 用实体手机访问 `scripts/start.ps1` 或 `scripts/dev.ps1` 启动后的局域网地址，验证真实上传与复制。

