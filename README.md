# gemini-web2api

<p align="center">
  <img src="logo.png" width="180" alt="gemini-web2api logo">
</p>

[中文文档](README_CN.md)

Convert Google Gemini Web into an OpenAI-compatible local API. It supports Chat Completions, Responses API, Gemini native endpoints, streaming, tool calls, and a built-in usage dashboard.

## Highlights

- OpenAI-compatible `/v1/chat/completions`, `/v1/models`, and `/v1/responses`
- Gemini native `/v1beta/models/*:generateContent` support
- Streaming SSE responses
- Optional API key protection
- Multiple Gemini Web model modes
- Persistent SQLite call logs and `/dashboard` usage analytics

## Quick Start

```bash
pip install -r requirements.txt
python -m gemini_web2api
```

Default base URL:

```text
http://localhost:8081/v1
```

The legacy source-tree entry point also works:

```bash
python gemini_web2api.py
```

## Client Setup

For Cherry Studio, ChatBox, OpenAI SDK, or any OpenAI-compatible client:

| Field | Value |
| --- | --- |
| Base URL | `http://localhost:8081/v1` |
| API Key | any configured key, or any value when auth is disabled |
| Model | `gemini-3.5-flash-thinking` |

Example request:

```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-key" \
  -d '{"model":"gemini-3.5-flash","messages":[{"role":"user","content":"Hello!"}]}'
```

## Models

| Model | Notes |
| --- | --- |
| `gemini-3.5-flash` | fast default model |
| `gemini-3.5-flash-thinking` | longer output, deeper reasoning mode |
| `gemini-3.5-flash-thinking-lite` | lighter thinking mode |
| `gemini-3.1-pro` | Pro label, real routing may require cookies |
| `gemini-auto` | Gemini Web auto mode |
| `gemini-flash-lite` | lightweight fast mode |

Thinking depth can be adjusted with `@think=N`:

```text
gemini-3.5-flash-thinking@think=0
gemini-3.5-flash-thinking@think=2
gemini-3.5-flash-thinking@think=4
```

## Configuration

Create `config.json` from `config.example.json` and edit as needed:

```json
{
  "port": 8081,
  "host": "0.0.0.0",
  "max_request_body_bytes": 52428800,
  "current_input_file_enabled": true,
  "current_input_file_min_bytes": 95000,
  "current_input_file_name": "message.txt",
  "api_keys": ["sk-your-key"],
  "cookie_file": null,
  "proxy": null,
  "log_requests": true,
  "analytics_enabled": true,
  "analytics_db_path": "data/gemini_web2api_usage.sqlite3"
}
```

Notes:

- Set `api_keys` to `[]` to disable authentication.
- `/v1/*` endpoints require `Authorization: Bearer <key>` when keys are configured.
- Set `proxy` if your machine cannot access `gemini.google.com`.
- Optional cookie support can improve real Pro routing: set `cookie_file` to a cookie file path. The file may contain a raw Cookie header value, a `Cookie: ...` line, a pasted full request header block, or JSON with `cookie`/`headers`.
- Upstream cookie mode is selected per request. Small text-only prompts are sent without Cookie/Authorization headers. File/image uploads and large-context file references are sent with Cookie/Authorization headers.
- File upload, image upload, and large prompt attachment mode require `cookie_file`.
- `current_input_file_enabled` is enabled by default. When a structured chat/history request exceeds `current_input_file_min_bytes` and `cookie_file` is available, prior context is uploaded as `current_input_file_name` and bound to Gemini Web as a file reference while the latest user turn stays inline.

## Usage Dashboard

Open:

```text
http://localhost:8081/dashboard
```

The dashboard shows call volume, success rate, latency, token estimates, model distribution, endpoint distribution, and recent logs. If API keys are enabled, enter one key in the dashboard header.

Raw APIs:

- `GET /v1/usage/stats?days=1`
- `GET /v1/usage/logs?limit=100&offset=0`

The analytics database is SQLite. Prompt and response bodies are not stored.

## Docker

Use the prebuilt GitHub Container Registry image:

```bash
cp config.example.json config.json
docker compose up -d
```

Default Docker base URL:

```text
http://localhost:18081/v1
```

Dashboard:

```text
http://localhost:18081/dashboard
```

`docker-compose.yml` mounts `./data` to `/app/data`, so usage logs persist across container rebuilds.

To use a specific image tag:

```bash
GEMINI_WEB2API_IMAGE=ghcr.io/liujuntao123/gemini-web2api:v1.1.0 docker compose up -d
```

For local development builds:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

GitHub Actions publishes Docker images to `ghcr.io/liujuntao123/gemini-web2api` on pushes to the default branch and version tags such as `v1.1.0`.

## Gemini CLI

```bash
export GEMINI_API_KEY=none
export GOOGLE_GEMINI_BASE_URL=http://localhost:8081
gemini
```

Supported native endpoints:

- `GET /v1beta/models`
- `POST /v1beta/models/{model}:generateContent`
- `POST /v1beta/models/{model}:streamGenerateContent`

## Limitations

- Gemini Web behavior can change and may break this bridge.
- Requests are single-turn; multi-turn context is passed in the prompt.
- Google may rate-limit high-frequency use.
- OpenAI `image_url`, Responses `input_file`, Google native `inlineData`, and Google native HTTP `fileData` inputs are uploaded through Gemini Web when cookies are configured.
- Without suitable cookies, Pro/Ultra labels may not mean real upstream Pro/Ultra routing.

## License

MIT
