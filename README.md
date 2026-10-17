# ZYREX Backend

Trading Intelligence API for ZYREX AI.

## Overview

This is the standalone backend server for ZYREX AI. It handles:
- Groq API integration
- ZYREX AI system instructions
- Request/response processing
- CORS handling
- Health checks

## Environment Variables

Required environment variables (see `.env.example`):

- `GROQ_API_KEY` - Your Groq API key
- `PORT` - Server port (default: 3001)

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your Groq API key to `.env`

3. Install dependencies (none currently required - uses Node.js built-in modules)

4. Start the server:
   ```bash
   npm run dev
   ```

## Railway Deployment

1. Push this repository to GitHub
2. Create a new project on Railway
3. Connect your GitHub repository
4. Add these environment variables in Railway:
   - `PORT` (Railway sets this automatically, but you can override)
   - `GROQ_API_KEY` (your Groq API key)
   - `CORS_ORIGINS` (comma-separated list: `http://localhost:5173,https://zyrex.vercel.app,https://zyrex.wasmer.app`)
5. Deploy
6. Railway will automatically detect it's a Node.js project and run `npm start`

## API Endpoints

### POST /api/zyrex-ai

Main AI endpoint for ZYREX analysis.

**Request Body:**
```json
{
  "prompt": "What is a liquidity sweep?",
  "mode": "analyst",
  "history": [
    { "role": "user", "text": "Previous message" },
    { "role": "assistant", "text": "Previous response" }
  ]
}
```

**Response:**
```json
{
  "status": "ready",
  "title": "ZYREX AI",
  "blocks": [
    {
      "type": "summary",
      "text": "AI response in Markdown format"
    }
  ]
}
```

### GET /api/health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "ZYREX Backend",
  "version": "1.0.0"
}
```

## Wasmer Edge Deployment

The repository includes a Wasmer Edge JavaScript worker deployment alongside
the Node.js server. Wasmer uses `src/index.js` and the `wasmer.toml` manifest;
it does not run `server.js` or load `.env` automatically.

1. Install the Wasmer CLI, sign in with `wasmer login`, then confirm the
   account with `wasmer whoami`.
2. From this project folder, deploy with:
   ```bash
   wasmer deploy --owner obafemip715 --publish-package
   ```
3. After the app exists, import the variables from your local `.env` as
   Wasmer secrets:
   ```bash
   wasmer app secret import --from-file .env --update-existing --redeploy --app obafemip715/zyrex-backend-obafemip715
   ```
   Alternatively, add `GROQ_API_KEY` in the Wasmer dashboard and redeploy.
   Do not put the key in `app.yaml` or commit `.env`; `.env` is git-ignored.
4. The Wasmer worker sends the fixed `Access-Control-Allow-Origin: https://zyrex.wasmer.app` header. Wasmer Edge strips the request `Origin` header before the worker receives it, so the worker cannot reflect or validate it. The API does not use cookies or credentialed browser requests. For Node.js deployments, the exact-origin allowlist works when `CORS_ORIGINS` is set.
5. Point the frontend API base URL to the deployed Wasmer app URL. Check
   `https://<your-app>.wasmer.app/api/health`; it should return
   `{"status":"ok",...}`.

The AI endpoint remains `POST /api/zyrex-ai`; its request and response format
is documented below. The Node.js `npm start` deployment path remains available
for Railway and other Node.js hosts.

## Security

- Groq API key is stored as a server-side environment variable/Wasmer secret
- Never exposed to the frontend
- CORS configured for development (configure appropriately for production)

## AI Configuration

- Model: `openai/gpt-oss-120b`
- Temperature: 0.7
- Max tokens: 2000
- Conversation history: Last 8 messages
