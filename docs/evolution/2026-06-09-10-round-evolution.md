# 2026-06-09 十轮 Autoresearch 进化报告

目标：提升 MiniMaxVidPromat 的稳定性、提示词质量、手机端体验和自动化可维护性。

适应度函数沿用 `docs/AUTORESEARCH.md`：

| 指标 | 权重 |
| --- | ---: |
| 构建与编译 | 30 |
| 核心流程稳定性 | 25 |
| 手机端可用性 | 20 |
| 提示词质量 | 15 |
| 文档与配置 | 10 |

## Round 1：Eval 失败捕获

候选：

- A. 只保留原有 `eval.ps1`。
- B. 对 npm/python 原生命令显式检查 `$LASTEXITCODE`。
- C. 迁移到 Python 统一执行器。

胜出：B。

原因：Windows PowerShell 对原生命令失败不会自动中断，B 的收益最高且改动最小。

评分：90/100。自动化验证：通过。

## Round 2：后端 API Smoke

候选：

- A. 引入 pytest。
- B. 使用 FastAPI TestClient 写无额外依赖 smoke 脚本。
- C. 只依赖编译检查。

胜出：B。

原因：能覆盖 health、非法格式、空文件、超限上传、任务公开数据和解析兜底，不增加新测试依赖。

评分：88/100。自动化验证：通过。

## Round 3：公开数据边界

候选：

- A. 前端继续接收完整 `meta`。
- B. 后端返回任务时过滤 `meta.path`。
- C. 删除公开响应中的 `meta` 字段。

胜出：B。

原因：避免泄露本地文件路径，同时保持前端类型兼容。

评分：87/100。自动化验证：通过。

## Round 4：模型 JSON 解析兜底

候选：

- A. 保持严格 `json.loads`。
- B. 支持 Markdown fenced JSON、正文包裹 JSON、`result` 嵌套对象和列表/对象字段字符串化。
- C. 模型失败后再次请求修复 JSON。

胜出：B。

原因：提高输出容错，不增加额外 API 调用成本。

评分：86/100。自动化验证：通过。

## Round 5：API 错误展示

候选：

- A. 原样展示 Axios 错误。
- B. 前端格式化 FastAPI `detail` 字符串和校验数组。
- C. 后端统一包装所有错误响应。

胜出：B。

原因：改动小，能直接改善手机端错误可读性。

评分：84/100。自动化验证：通过。

## Round 6：轮询调度

候选：

- A. 保持 `setInterval`。
- B. 使用递归 `setTimeout`，请求完成后再安排下一轮。
- C. 改成 SSE。

胜出：B。

原因：消除慢网络下的重叠请求，又不引入连接保活复杂度。

评分：86/100。自动化验证：通过。

## Round 7：复制体验

候选：

- A. 只使用 `navigator.clipboard`。
- B. 增加 `document.execCommand('copy')` fallback。
- C. 失败时只提示用户手动长按复制。

胜出：B。

原因：局域网 HTTP 或部分手机浏览器可能禁用 Clipboard API，fallback 能提升成功率。

评分：82/100。自动化验证：前端构建通过；真实手机复制仍需人工验证。

## Round 8：开发启动形态

候选：

- A. 只保留 README 手动启动。
- B. 新增 `scripts/dev.ps1` 同时启动前后端。
- C. 直接引入 Docker Compose。

胜出：B。

原因：本项目优先本地 Windows 使用，PowerShell 一键启动成本低于 Docker。

评分：80/100。自动化验证：脚本语法随仓库提交；未在本轮长时间驻留运行。

## Round 9：使用文档

候选：

- A. 不更新文档。
- B. 在 README 增加 dev/eval/evolve 使用路径。
- C. 另建完整运维手册。

胜出：B。

原因：用户最常用路径应直接放在 README，避免简单项目文档过重。

评分：85/100。自动化验证：文档纳入版本库。

## Round 10：进化收敛

候选：

- A. 继续引入运行时功能。
- B. 生成本报告，执行最终 eval，提交并推送。
- C. 重构项目结构。

胜出：B。

原因：十轮已覆盖主要稳定性和自动化缺口，最后一轮应收敛证据而不是扩大风险。

评分：90/100。自动化验证：最终 `scripts/eval.ps1` 通过。

## 最终验证

自动化通过：

```text
.\scripts\eval.ps1
frontend build passed
backend compile passed
backend import passed
backend smoke passed
powershell syntax passed
```

仍需人工或真实环境验证：

- 配置真实 `MINIMAX_API_KEY` 后的小视频识别链路。
- 手机局域网访问、上传和复制按钮在目标浏览器上的表现。
- MiniMax Files API 的 `purpose` 是否仍为当前配置值。
