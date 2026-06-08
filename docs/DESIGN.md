# 设计说明

## 产品目标

把手机拍摄或相册里的视频，快速转换为即梦 / Seedance 2.0 可直接粘贴的视频提示词。

第一版优先解决三个动作：

1. 手机上选择或拍摄视频。
2. 本地服务调用 MiniMax-M3 理解视频内容。
3. 返回并复制即梦提示词。

## 核心流程

```text
手机浏览器
  -> 上传视频到本地 FastAPI
  -> 后端创建任务
  -> 后端调用 MiniMax-M3
  -> 前端轮询任务状态
  -> 展示 Seedance 2.0 提示词
```

## 输出结构

后端要求模型返回 JSON：

- `summary`：视频摘要
- `subject`：主体
- `scene`：场景
- `action`：动作
- `camera`：运镜
- `lighting`：光线
- `style`：风格
- `seedance_prompt`：即梦一键粘贴版
- `storyboard_prompt`：分镜增强版
- `negative_prompt`：负面提示词
- `english_prompt`：英文版

## 移动端界面原则

- 首屏就是上传与生成，不做落地页。
- 控件使用 Vant，保证手机浏览器体验。
- 任务采用轮询，避免移动端长请求不稳定。
- 切换或删除视频时立即停止旧任务轮询，避免旧任务结果覆盖当前界面。
- 结果按复制频率排序，最常用的即梦一键粘贴版放在最前。

## MiniMax 调用策略

第一版使用 OpenAI SDK 兼容接口：

```text
base_url = https://api.minimaxi.com/v1
model = MiniMax-M3
content type = video_url
```

小视频走 base64 data URL。大视频后续走 MiniMax Files API，并通过 `mm_file://{file_id}` 传入模型。

上传大小在后端流式写入阶段控制：未启用 Files API 时按 `MINIMAX_MAX_BASE64_MB` 拦截，启用 Files API 后按 `MAX_UPLOAD_MB` 拦截。任务结束后删除本地临时视频，任务状态只保留识别结果和必要元数据。
