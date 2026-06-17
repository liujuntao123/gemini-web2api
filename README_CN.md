# gemini-web2api

<p align="center">
  <img src="logo.png" width="180" alt="gemini-web2api logo">
</p>

[English](README.md)

把 Google Gemini 网页端转换成本地 OpenAI 兼容 API。支持 Chat Completions、Responses API、Gemini 原生接口、流式输出、工具调用，以及内置调用统计看板。

## 核心功能

- OpenAI 兼容接口：`/v1/chat/completions`、`/v1/models`、`/v1/responses`
- Gemini 原生接口：`/v1beta/models/*:generateContent`
- SSE 流式输出
- 可选 API Key 鉴权
- 多种 Gemini Web 模型模式
- 匿名纯文本上游请求，无需配置 Cookie
- SQLite 持久化调用日志和 `/dashboard` 数据看板

## 快速开始

```bash
pip install -r requirements.txt
python -m gemini_web2api
```

默认 Base URL：

```text
http://localhost:8081/v1
```

源码目录中的兼容入口也可用：

```bash
python gemini_web2api.py
```

## 客户端配置

Cherry Studio、ChatBox、OpenAI SDK 或其他 OpenAI 兼容客户端：

| 字段 | 值 |
| --- | --- |
| Base URL | `http://localhost:8081/v1` |
| API Key | 配置的任意 key；关闭鉴权时可随便填 |
| Model | `gemini-3.5-flash-thinking` |

示例请求：

```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"你好!"}]}'
```

## 模型

| 模型 | 说明 |
| --- | --- |
| `gemini-3.5-flash` | 快速默认模型 |
| `gemini-3.5-flash-thinking` | 更长输出，深度思考模式 |
| `gemini-3.5-flash-thinking-lite` | 较轻的思考模式 |
| `gemini-3.1-pro` | Pro 模型标签 |
| `gemini-auto` | Gemini Web 自动模式 |
| `gemini-flash-lite` | 轻量快速模式 |

可用 `@think=N` 调整思考深度：

```text
gemini-3.5-flash-thinking@think=0
gemini-3.5-flash-thinking@think=2
gemini-3.5-flash-thinking@think=4
```

## 配置

从 `config.example.json` 复制出 `config.json` 后按需修改：

```json
{
  "port": 8081,
  "host": "0.0.0.0",
  "max_request_body_bytes": 52428800,
  "max_upstream_prompt_bytes": 184320,
  "api_keys": ["sk-your-key"],
  "proxy": null,
  "log_requests": true,
  "analytics_enabled": true,
  "analytics_db_path": "data/gemini_web2api_usage.sqlite3"
}
```

说明：

- `api_keys` 设为 `[]` 时关闭鉴权。
- 配置 key 后，`/v1/*` 接口需要 `Authorization: Bearer <key>`。
- 无法访问 `gemini.google.com` 时设置 `proxy`。
- 上游请求固定为匿名纯文本请求，不支持 Cookie 模式。
- 图片和文件输入会直接返回 `400`。
- Gemini Web 表单 payload 超过 `max_upstream_prompt_bytes` 的 prompt 会直接返回 `413`。

## 调用看板

打开：

```text
http://localhost:8081/dashboard
```

看板包含调用量、成功率、响应耗时、token 估算、模型分布、接口分布和最近日志。启用 API Key 时，在看板右上角输入一个可用 key。

原始数据接口：

- `GET /v1/usage/stats?days=1`
- `GET /v1/usage/logs?limit=100&offset=0`

统计数据存储在 SQLite 中。默认不保存 prompt 和 response 正文。

## Docker

使用 GitHub Container Registry 上的预构建镜像：

```bash
cp config.example.json config.json
docker compose up -d
```

Docker 默认 Base URL：

```text
http://localhost:18081/v1
```

看板地址：

```text
http://localhost:18081/dashboard
```

`docker-compose.yml` 会把宿主机 `./data` 挂载到容器 `/app/data`，调用日志在容器重建后仍会保留。
不会挂载也不支持 Cookie 文件；Docker 与本地运行一样使用匿名纯文本上游模式。

指定镜像标签：

```bash
GEMINI_WEB2API_IMAGE=ghcr.io/liujuntao123/gemini-web2api:v1.1.0 docker compose up -d
```

本地开发构建：

```bash
docker compose -f docker-compose.local.yml up -d --build
```

GitHub Actions 会在推送默认分支和 `v1.1.0` 这类版本标签时，将 Docker 镜像发布到 `ghcr.io/liujuntao123/gemini-web2api`。

## Gemini CLI

```bash
export GEMINI_API_KEY=none
export GOOGLE_GEMINI_BASE_URL=http://localhost:8081
gemini
```

支持的原生接口：

- `GET /v1beta/models`
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`

## 已知限制

- Gemini Web 行为可能变化，导致桥接失效。
- 请求按单轮处理，多轮上下文需要放进 prompt。
- 高频调用可能触发 Google 限流。
- 不支持 OpenAI `image_url`、Responses `input_file`、Google 原生 `inlineData` 和 Google 原生 HTTP `fileData` 输入。

## License

MIT
