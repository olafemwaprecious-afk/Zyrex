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

## Deployment

This backend is designed for deployment to Railway or similar Node.js hosting platforms.

## Security

- Groq API key is stored in server-side environment variables
- Never exposed to the frontend
- CORS configured for development (configure appropriately for production)

## AI Configuration

- Model: `openai/gpt-oss-120b`
- Temperature: 0.7
- Max tokens: 2000
- Conversation history: Last 8 messages
