# ZYREX Backend

Agentic Trading Intelligence API for ZYREX AI powered by Agno + Groq.

## Overview

This is the Python backend server for ZYREX AI. It provides:
- **Agno agent framework** for agentic tool calling and reasoning
- **Groq API integration** for fast LLM inference
- **Market data tools**: GeckoTerminal (DEX) and CoinAPI (CEX) APIs
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
- **CoinAPI Tools**: Exchange rates, ticker data, OHLCV candlestick data
- **Risk Checker**: Trade validation, risk amount calculation, reward-to-risk ratio
- **Market Comparison**: Compare pools and tokens across different sources
- **Diagnostics**: Check operational status of all integrations

## Environment Variables

Required environment variables (see `.env.example`):

- `GROQ_API_KEY` - Your Groq API key (required)
- `COINAPI_KEY` - Your CoinAPI key (required for CEX market data)
- `GROQ_MODEL` - Groq model ID (default: `openai/gpt-oss-120b`)
- `PORT` - Server port (default: 8080)
- `ALLOWED_ORIGIN` - Frontend origin for CORS (default: `https://zyrex.wasmer.app`)
- `KEEP_AWAKE_URL` - URL for keep-alive self-ping (default: Render deployment URL)

## Setup

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Installation

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add your API keys to `.env`:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   COINAPI_KEY=your_coinapi_key_here
   ```

   **Obtain CoinAPI Key:**
   - Create an account at https://www.coinapi.io/ and create a key in the CoinAPI dashboard.
   - Put the key only in the backend `.env` as `COINAPI_KEY`; do not commit it or put it in frontend code.

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
2. `COINAPI_KEY` - Your CoinAPI key (required for CoinAPI market data)
3. `GROQ_MODEL` - `openai/gpt-oss-120b` (optional, has default)
4. `PORT` - Render sets this automatically (optional)
5. `ALLOWED_ORIGIN` - `https://zyrex.wasmer.app` (optional, has default)
6. `KEEP_AWAKE_URL` - `https://zyrex-mpya.onrender.com/health` (optional, has default)

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

### CoinAPI (Aggregated Rates and CEX OHLCV)

- **Authentication:** `X-CoinAPI-Key` HTTP header, read only by the backend from `COINAPI_KEY`.
- **Aggregated asset-pair rate:** `GET https://rest.coinapi.io/v1/exchangerate/{asset_id_base}/{asset_id_quote}`. CoinAPI describes this as an aggregated rolling 24-hour VWAP, not a price from a specific exchange.
- **Latest daily candle:** `GET https://rest.coinapi.io/v1/ohlcv/{symbol_id}/latest?period_id=1DAY&limit=1`.
- **Historical candles:** `GET https://rest.coinapi.io/v1/ohlcv/{symbol_id}/history?period_id={period_id}&limit={limit}`.
- OHLCV uses venue-specific symbol IDs such as `BITSTAMP_SPOT_BTC_USD`; it is a specific exchange market, unlike the aggregated exchange-rate endpoint.
- CoinAPI documents OHLCV REST data as potentially delayed by a few seconds. Exchange-rate responses include the provider timestamp, which the tool returns without substituting backend time.
- Endpoint access, supported assets/symbols, history, and request quotas depend on the subscription. Public docs list Startup limits of 10 requests/second and 1,000 requests/day; confirm both the limits and endpoint entitlement for the key in the CoinAPI dashboard. This backend does not make a request just to infer an account's plan.
- **Environment Variable:** `COINAPI_KEY` (backend only)
- **Official docs:** [REST API](https://www.coinapi.io/products/market-data-api/docs/rest-api), [Exchange Rates](https://www.coinapi.io/products/market-data-api/docs/rest-api/exchange-rates/Get%20specific%20rate), [OHLCV](https://www.coinapi.io/products/market-data-api/docs/rest-api/ohlcv/overview).

### Groq (LLM)

- **Purpose:** Fast language model inference
- **Base URL:** Groq API (handled by SDK)
- **Authentication:** Required via API key
- **Required for MVP:** Yes
- **Environment Variable:** `GROQ_API_KEY` (required)
- **Get Key:** https://console.groq.com/keys

## Security

- Groq and CoinAPI keys are stored as server-side environment variables
- CoinAPI key is sent only in the `X-CoinAPI-Key` request header; it is not included in tool results, logs, or error responses
- WebSocket origin restricted to `https://zyrex.wasmer.app`
- No live trade execution or private API access
- Tools use public read-only endpoints only
- Risk calculations are deterministic and local

## Current Implementation

### What's Implemented Now

- ✅ Agno + Groq agent integration
- ✅ GeckoTerminal market data tools
- ✅ CoinAPI aggregated exchange rates and venue-specific OHLCV tools
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
- CoinAPI: wait before retrying and verify the request quota and endpoint entitlement in the CoinAPI dashboard

**CoinAPI errors:**
- Missing key: set `COINAPI_KEY` in the backend environment and restart or redeploy the service.
- HTTP 401: verify the key in the CoinAPI dashboard and update the backend environment value.
- HTTP 403: the endpoint or requested data may not be included in the subscription.
- HTTP 429: the subscription request quota has been reached; wait before retrying and check current plan limits.
- Timeouts or provider outages: retry later; errors do not include request headers or credential values.

### Testing CoinAPI

Run `python -m pytest -q`. CoinAPI tests use mocked HTTP responses and do not consume API quota. For a live smoke test, ask ZYREX: "What is the current BTC/USDT price?" The agent should call the aggregated exchange-rate tool and identify the source and provider timestamp; it must explain an access or provider error instead of inventing a price.

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
│   ├── coinapi.py        # Aggregated rates and CEX OHLCV market data
│   ├── risk_checker.py   # Trade validation
│   ├── market_comparison.py
│   └── diagnostics.py
└── tests/                # Test suite
    ├── test_main.py
    ├── test_risk_checker.py
    ├── test_market_comparison.py
    ├── test_geckoterminal.py
   └── test_coinapi.py
```

### Adding New Tools

1. Create tool function in `tools/` directory
2. Add docstring with parameters and return format
3. Import in `tools/__init__.py`
4. Add to agent tools list in `main.py`
5. Write tests in `tests/`

## License

This is the backend for ZYREX AI. See the main project repository for license information.
