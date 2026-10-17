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

## CORS behavior

The Wasmer worker always sends the fixed `Access-Control-Allow-Origin: https://zyrex.wasmer.app` header. Wasmer Edge strips `Origin` and `Referer` before forwarding requests to the worker, so the worker cannot reflect or validate request origins. It never returns `*`, and requests from other browser origins do not match the fixed allowed origin. The API does not use browser cookies or credentialed requests.

The Node server uses the exact-origin `CORS_ORIGINS` allowlist. Both deployments allow `GET`, `POST`, and `OPTIONS`, plus the `Content-Type` and `Authorization` request headers observed in the frontend preflight. The backend does not use `Authorization` to call Groq; the Groq key stays server-side. The Wasmer worker responds to preflight with HTTP `200` and an empty body; the Node server responds with HTTP `204`.

### Wasmer deploy and verify

From this project folder, `wasmer.toml` packages `src/index.js` as the worker. `GET /` returns the health response for Wasmer's deployment check; this is an API, not an SPA, so no `index.html` fallback is needed.

Deploy the folder:

```bash
wasmer deploy --owner obafemip715 --publish-package
```

Test a preflight with:

```powershell
curl.exe -i -X OPTIONS "https://zyrex-backend-obafemip715.wasmer.app/api/zyrex-ai" `
  -H "Origin: https://zyrex.wasmer.app" `
  -H "Access-Control-Request-Method: POST" `
  -H "Access-Control-Request-Headers: content-type,authorization"
```

Expect HTTP `200`, `Access-Control-Allow-Origin: https://zyrex.wasmer.app`, `Access-Control-Allow-Methods` including `POST`, and `Access-Control-Allow-Headers` including `Content-Type` (and `Authorization` if requested). A successful status or matching origin alone does not verify browser CORS: the preflight must allow the requested method and headers. If those headers are missing, redeploy the worker and check whether Wasmer Edge or another gateway is intercepting or overriding `OPTIONS` responses. A successful `GET /` or `/api/health` confirms routing; the preflight verifies browser CORS.

### Latest deployment verification (2026-10-11)

The Wasmer deployment completed successfully, and `GET /api/health` returned HTTP `200`. However, the live `OPTIONS /api/zyrex-ai` preflight also returned HTTP `200` but included only `Access-Control-Allow-Origin`; it omitted both `Access-Control-Allow-Methods` and `Access-Control-Allow-Headers`. The CORS issue therefore remains unresolved in production. The worker code sets these headers, so investigate whether Wasmer Edge or another gateway is intercepting or stripping them, and repeat the preflight check after resolving it.

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
