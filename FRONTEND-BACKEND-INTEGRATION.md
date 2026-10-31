# ZYREX Frontend–Backend Integration

## Endpoints

- WebSocket chat: `wss://zyrex-mpya.onrender.com/`
- Health check: `GET https://zyrex-mpya.onrender.com/health`
- Allowed browser Origin: `https://zyrex.wasmer.app`

The WebSocket handshake checks the exact frontend Origin. Do not use a wildcard or omit the Origin header.

## Chat request

Open one WebSocket connection for a prompt and send one JSON message:

```json
{
  "prompt": "What is a liquidity sweep?",
  "mode": "analyst",
  "history": []
}
```

`prompt` must be a non-empty string. `mode` and `history` are accepted for client compatibility but are not used by this minimal baseline. Each connection handles one prompt and one response.

The backend temporarily accepts the previous action envelope:

```json
{
  "type": "action",
  "action": "chat_turn",
  "params": {
    "prompt": "What is a liquidity sweep?"
  }
}
```

New client code must use the direct request shape.

## Chat response

Text chunks are sent as WebSocket text frames in generation order. The stream ends with `[DONE]`. On a request or provider error, the backend sends a JSON error frame followed by `[DONE]`, for example:

```json
{"error":"The assistant could not complete this request. Please try again later."}
```

The Groq API key remains server-side and is never sent to the frontend.

## HTTP and handshake diagnostics

- `GET /health` returns HTTP `200` and `ZYREX Engine Online`.
- A plain HTTP `GET /` is not a health check and returns HTTP `426 Upgrade Required`; use a WebSocket client there.
- Invalid WebSocket handshakes can return HTTP `400`.
- A WebSocket upgrade with an Origin other than `https://zyrex.wasmer.app` is rejected with HTTP `403`.
- Message parsing and Groq errors occur only after a successful WebSocket handshake and are reported as WebSocket error frames.

## Render environment

Set `GROQ_API_KEY` as a secret in the Render service environment and set `GROQ_MODEL` to exactly `llama-3.3-70b-versatile`. Render supplies `PORT`; the Procfile starts the backend with `python main.py`.

The exact model must be tested with the deployed key before treating generation as verified. Groq's deprecation notice says `llama-3.3-70b-versatile` was decommissioned for free and developer-tier accounts on August 16, 2026; access depends on the configured account tier.

## Incremental restoration

Restore and test one capability at a time, in this order:

1. Conversation history.
2. One market-data tool.
3. Additional trading tools and diagnostics.
4. Dynamic tool selection.
5. Remaining integrations.
