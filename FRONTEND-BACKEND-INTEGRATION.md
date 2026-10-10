# ZYREX Frontend–Backend Integration

This document contains the backend details a frontend developer or coding agent needs to connect the ZYREX frontend to this API.

## Backend base URL

Configure the frontend with the **deployed backend's origin** (scheme and hostname, without an API path), then append the endpoint paths below.

```text
VITE_API_BASE_URL=https://zyrex-backend-obafemip715.wasmer.app
```

The deployed Wasmer backend origin is:

```text
https://zyrex-backend-obafemip715.wasmer.app
```

Use this backend origin, not a frontend URL, as `VITE_API_BASE_URL`.

For local Node.js development, the server defaults to:

```text
http://localhost:3001
```

The AI endpoint is:

```text
POST {BACKEND_BASE_URL}/api/zyrex-ai
```

The health endpoint is:

```text
GET {BACKEND_BASE_URL}/api/health
```

For example, if the deployed backend origin is `https://example-backend.wasmer.app`, the AI endpoint is `https://example-backend.wasmer.app/api/zyrex-ai`.

## CORS: allowed frontend origins

The Wasmer configuration in `app.yaml` currently sets `CORS_ORIGINS` to:

- `https://zyrex.vercel.app`
- `https://zyrex.wasmer.app`

These are **frontend origins allowed to make browser requests**. They are not backend URLs or API endpoints. The browser's `Origin` must match one of these values exactly (scheme and hostname; no path or trailing slash) for the Wasmer worker to return `Access-Control-Allow-Origin`.

If the frontend is hosted at a different origin, add that exact origin to the backend deployment's `CORS_ORIGINS` environment variable and redeploy/restart the backend. The variable is a comma-separated list, for example:

```text
CORS_ORIGINS=https://zyrex.vercel.app,https://zyrex.wasmer.app,http://localhost:5173
```

The Node server allows `http://localhost:5173` by default when `CORS_ORIGINS` is not set. If it is set, it uses the configured list instead. The Wasmer configuration shown above does not include localhost.

The backend permits `GET`, `POST`, and `OPTIONS`, and allows the `Content-Type` request header. The frontend should send JSON and does not need to send cookies or credentials.

The Wasmer worker responds to preflight `OPTIONS` requests with HTTP `200`. The Node server responds with HTTP `204`. Both responses must include `Access-Control-Allow-Origin` matching the requesting frontend origin, along with the allowed methods and headers. The backend only sends `Access-Control-Allow-Origin` for an exact allowlist match; it does not grant access to unknown origins.

### Current deployment status

The CORS fix is committed and pushed in commit `ea50629` (`Fix CORS and configure Wasmer deployment`). As of 2026-10-10, the live Wasmer app still responds to `OPTIONS /api/zyrex-ai` with HTTP `500` and no CORS headers. The code change is not active in that deployment yet. Redeploy the Wasmer app from the repository:

```bash
wasmer deploy --owner obafemip715 --publish-package
```

After deployment, verify the preflight response from each production frontend origin. For example, in PowerShell use `curl.exe`:

```powershell
curl.exe -i -X OPTIONS "https://zyrex-backend-obafemip715.wasmer.app/api/zyrex-ai" `
  -H "Origin: https://zyrex.wasmer.app" `
  -H "Access-Control-Request-Method: POST" `
  -H "Access-Control-Request-Headers: content-type"
```

Expect a successful status and `Access-Control-Allow-Origin: https://zyrex.wasmer.app`. Repeat with `https://zyrex.vercel.app` as the origin. A successful `GET /api/health` alone does not verify CORS; the preflight must succeed before the browser sends the AI `POST`.

## AI answer request

Send a JSON `POST` to `/api/zyrex-ai` with this shape:

```json
{
  "prompt": "What is a liquidity sweep?",
  "mode": "analyst",
  "history": [
    { "role": "user", "text": "What is market structure?" },
    { "role": "assistant", "text": "Market structure describes..." }
  ]
}
```

Fields:

| Field | Required | Details |
|---|---|---|
| `prompt` | Yes | The current user message. Must be a non-empty string after trimming. |
| `mode` | No | String passed to the AI as conversation context. Defaults to `"analyst"`. |
| `history` | No | Array of `{ "role": "user" \| "assistant", "text": string }` entries. The backend uses at most the last 8 entries. |

Send only conversation messages needed for context. The AI backend does not load frontend user/account/trading data and will not have access to it unless the frontend explicitly includes relevant context in the prompt/history.

## Successful AI answer response

On success, the backend returns HTTP `200` with:

```json
{
  "status": "ready",
  "title": "ZYREX AI",
  "blocks": [
    {
      "type": "summary",
      "text": "A liquidity sweep is ... "
    }
  ]
}
```

Render the answer from `blocks` (typically the `text` of the `summary` block). The text may contain Markdown. The endpoint is not streaming: wait for the complete JSON response. Do not expect a top-level `answer` property.

## Errors and status codes

Error responses are JSON. For AI endpoint errors, the common shape is:

```json
{
  "status": "offline",
  "reason": "A human-readable explanation."
}
```

| HTTP status | Meaning |
|---|---|
| `400` | Invalid JSON request body or missing/blank `prompt`. |
| `404` | Method/path does not match a defined endpoint. |
| `500` | Backend is missing its `GROQ_API_KEY` configuration. |
| `502` | AI provider/network failure, unavailable model, rate limit/quota issue, or empty provider response. |

The frontend should check `response.ok` before treating the response as a successful answer, and show the returned `reason` when available. A browser CORS rejection or network outage may prevent JavaScript from reading any JSON response; handle that as a connection error.

## Frontend example

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function askZyrex({ prompt, mode = "analyst", history = [] }) {
  if (!API_BASE_URL) {
    throw new Error("VITE_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${API_BASE_URL}/api/zyrex-ai`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt, mode, history }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.reason || data.error || `Request failed (${response.status}).`);
  }

  if (data.status !== "ready" || !Array.isArray(data.blocks)) {
    throw new Error("The backend returned an unexpected response.");
  }

  return data.blocks;
}
```

Example rendering:

```js
const blocks = await askZyrex({ prompt: "What is a liquidity sweep?" });
const answer = blocks
  .filter((block) => block.type === "summary")
  .map((block) => block.text)
  .join("\n\n");
```

If Markdown is rendered as HTML, use a Markdown renderer with appropriate HTML sanitization rather than injecting untrusted HTML directly.

## Health check

Use `GET /api/health` to verify that the backend is reachable:

```json
{
  "status": "ok",
  "service": "ZYREX Backend",
  "version": "1.0.0"
}
```

This checks backend availability; it does not guarantee that the AI provider credentials or quota are working.

## Backend configuration boundary

- The frontend must never contain or send the `GROQ_API_KEY`.
- The backend uses `GROQ_API_KEY` server-side to call Groq.
- The configured model defaults to `openai/gpt-oss-120b`; the backend can override it using `GROQ_MODEL`.
- The frontend calls only the ZYREX backend endpoints above, not the Groq API directly.
