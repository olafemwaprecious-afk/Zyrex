# ZYREX Backend

Agentic Trading Intelligence API for ZYREX AI powered by Agno + Groq.

## Overview

This is the Python backend server for ZYREX AI. It provides:
- **Agno agent framework** for agentic tool calling and reasoning
- **Groq API integration** for fast LLM inference
- **Market data tools**: GeckoTerminal (DEX) and Binance (CEX) public APIs
- **Risk checking engine**: Deterministic trade validation and risk calculations
- **WebSocket streaming**: Real-time response streaming to the frontend
- **Keep-alive system**: Automatic self-ping for Render deployment
- **Health checks**: Endpoint for deployment monitoring

## Architecture

The backend uses an agentic architecture:

1. **User Request** → WebSocket → ZYREX Backend
2. **Agno Agent** receives the request with conversation history
3. **Tool Selection**: Agent decides when to use tools based on context
4. **Tool Execution**: Market data, risk checking, or comparison tools run
5. **Result Integration**: Tool results feed back into the agent's reasoning
6. **Response Generation**: Agent produces final answer with tool-informed insights
7. **Streaming**: Response streams incrementally through WebSocket to frontend

### Available Tools

- **GeckoTerminal Tools**: Search pools, get pool data, OHLCV charts, trending pools
- **Binance Tools**: Ticker prices, 24hr statistics, kline/candlestick data
- **Risk Checker**: Trade validation, risk amount calculation, reward-to-risk ratio
- **Market Comparison**: Compare pools and tokens across different sources
- **Diagnostics**: Check operational status of all integrations

## Environment Variables

Required environment variables (see `.env.example`):

- `GROQ_API_KEY` - Your Groq API key (required)
- `GROQ_MODEL` - Groq model ID (default: `openai/gpt-oss-120b`)
- `PORT` - Server port (default: 8080)
- `ALLOWED_ORIGIN` - Frontend origin for CORS (default: `https://zyrex.wasmer.app`)
- `KEEP_AWAKE_URL` - URL for keep-alive self-ping (default: Render deployment URL)

## Setup

### Prerequisites

- Python 3.9 or higher
- pip or uv package manager

### Installation

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your Groq API key to `.env`:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   # or with uv:
   uv pip install -r requirements.txt
   ```

4. Start the server:
   ```bash
   python main.py
   ```

The server will start on the configured port (default 8080) and listen on `0.0.0.0`.

## Running Tests

Run the test suite to verify the implementation:

```bash
pytest tests/
```

Tests cover:
- Risk checker calculations and validation
- Market comparison logic
- GeckoTerminal API integration (with mocked HTTP)
- Binance API integration (with mocked HTTP)
- Main backend configuration

## API Protocol

### WebSocket Connection

The backend uses WebSocket for real-time streaming:

**Connection URL:** `wss://zyrex-mpya.onrender.com`

**Allowed Origin:** `https://zyrex.wasmer.app`

### Message Format

**Request:**
```json
{
  "prompt": "What is the current price of BTC?",
  "mode": "analyst",
  "history": [
    { "role": "user", "text": "Previous message" },
    { "role": "assistant", "text": "Previous response" }
  ]
}
```

**Response Stream:**
- Text chunks sent incrementally
- Ends with `[DONE]` marker
- Errors sent as JSON before `[DONE]`

### Health Check

**GET /health**

Health check endpoint for Render and monitoring.

**Response:**
```
ZYREX Engine Online
```

## Render Deployment

The backend is deployed on Render at: https://zyrex-mpya.onrender.com

### Deployment Configuration

- **Start Command:** `python main.py` (defined in `Procfile`)
- **Python Version:** Latest supported by Render
- **Dependencies:** Defined in `requirements.txt`

### Environment Variables on Render

Add these in Render → Environment:

1. `GROQ_API_KEY` - Your Groq API key (required)
2. `GROQ_MODEL` - `openai/gpt-oss-120b` (optional, has default)
3. `PORT` - Render sets this automatically (optional)
4. `ALLOWED_ORIGIN` - `https://zyrex.wasmer.app` (optional, has default)
5. `KEEP_AWAKE_URL` - `https://zyrex-mpya.onrender.com/health` (optional, has default)

### Deployment Steps

1. Push code to GitHub main branch
2. Render auto-deploys from the main branch
3. Add environment variables in Render dashboard
4. Verify deployment at https://zyrex-mpya.onrender.com/health

## API Integrations

### GeckoTerminal (DEX Data)

- **Purpose:** Decentralized exchange token and pool data
- **Base URL:** `https://api.geckoterminal.com/api/v2`
- **Rate Limit:** ~30 calls/minute (public API)
- **Authentication:** Not required for public endpoints
- **Required for MVP:** Yes (free tier sufficient)
- **Environment Variable:** None required

### Binance (CEX Data)

- **Purpose:** Centralized exchange market data
- **Base URL:** `https://data-api.binance.vision` (public data only)
- **Rate Limit:** Public market data endpoints
- **Authentication:** Not required for public endpoints
- **Required for MVP:** Yes (public endpoints sufficient)
- **Environment Variable:** None required

### Groq (LLM)

- **Purpose:** Fast language model inference
- **Base URL:** Groq API (handled by SDK)
- **Authentication:** Required via API key
- **Required for MVP:** Yes
- **Environment Variable:** `GROQ_API_KEY` (required)
- **Get Key:** https://console.groq.com/keys

## Security

- Groq API key is stored as a server-side environment variable
- Never exposed to the frontend, logs, or error responses
- WebSocket origin restricted to `https://zyrex.wasmer.app`
- No live trade execution or private API access
- Tools use public read-only endpoints only
- Risk calculations are deterministic and local

## Current Implementation

### What's Implemented Now

- ✅ Agno + Groq agent integration
- ✅ GeckoTerminal market data tools
- ✅ Binance market data tools
- ✅ Deterministic risk checking engine
- ✅ Market comparison tools
- ✅ WebSocket streaming protocol
- ✅ Keep-alive for Render
- ✅ Health check endpoint
- ✅ Comprehensive test suite
- ✅ Tool status diagnostics

### Deferred to Later Phases

- ❌ Supabase/persistent database (not required for MVP)
- ❌ Private exchange API keys (public endpoints sufficient)
- ❌ Live order execution (analysis and simulation only)
- ❌ MT5 integration (not required for MVP)
- ❌ Wallet signing or private key handling
- ❌ Real-money trading capabilities

## Troubleshooting

### Common Issues

**Import errors:**
```bash
pip install -r requirements.txt
```

**Groq API key errors:**
- Verify `GROQ_API_KEY` is set in environment
- Check key is valid at https://console.groq.com/

**WebSocket connection failures:**
- Verify frontend origin matches `ALLOWED_ORIGIN`
- Check Render deployment status
- Review Render logs for errors

**Rate limit errors:**
- GeckoTerminal: ~30 calls/minute (free tier)
- Implement caching to reduce requests
- Consider paid plan for higher limits

## Development

### Project Structure

```
ZYREX BACKEND/
├── main.py                 # Main WebSocket server and agent setup
├── requirements.txt        # Python dependencies
├── Procfile               # Render deployment config
├── .env.example          # Environment variable template
├── tools/                # Tool implementations
│   ├── __init__.py
│   ├── geckoterminal.py  # DEX market data
│   ├── binance.py        # CEX market data
│   ├── risk_checker.py   # Trade validation
│   ├── market_comparison.py
│   └── diagnostics.py
└── tests/                # Test suite
    ├── test_main.py
    ├── test_risk_checker.py
    ├── test_market_comparison.py
    ├── test_geckoterminal.py
    └── test_binance.py
```

### Adding New Tools

1. Create tool function in `tools/` directory
2. Add docstring with parameters and return format
3. Import in `tools/__init__.py`
4. Add to agent tools list in `main.py`
5. Write tests in `tests/`

## License

This is the backend for ZYREX AI. See the main project repository for license information.
