# ZYREX Backend

Text-chat backend for ZYREX AI powered by Agno + Groq.

## Overview

This is the Python backend server for ZYREX AI. Its active baseline provides:
- **Agno + Groq** for text-only model inference
- **Groq API integration** for fast LLM inference
- **Retained trading modules**: GeckoTerminal, CoinAPI, risk checking, and comparison code (not registered in the active agent)
- **WebSocket streaming**: Real-time response streaming to the frontend
- **Health checks**: Endpoint for deployment monitoring

## Current request path

One text prompt is sent over a WebSocket connection, passed to an Agno/Groq agent with no registered tools, and streamed back as text frames followed by `[DONE]`. Conversation history, market-data tools, dynamic tool selection, and the background self-ping are disabled in this baseline; their source modules are retained.

## Environment Variables

Required environment variables (see `.env.example`):

- `GROQ_API_KEY` - Your Groq API key (required)
- `GROQ_MODEL` - Groq model ID (default: `llama-3.3-70b-versatile`)
- `PORT` - Server port (default: 8080)
- `COINAPI_KEY` - Retained for later market-data restoration; unused by the baseline

## Setup

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Installation

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Set `GROQ_API_KEY` in `.env`. `COINAPI_KEY` is optional and unused by the current baseline:
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
  "prompt": "What is a liquidity sweep?",
  "mode": "analyst",
  "history": []
}
```

`mode` and `history` are accepted but ignored by the minimal baseline. Each WebSocket connection handles one prompt. Text chunks arrive in order, followed by `[DONE]`; an error is sent as a JSON frame followed by `[DONE]`.

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
2. `GROQ_MODEL` - `llama-3.3-70b-versatile` (set this exact value)
3. `PORT` - Render sets this automatically

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
- **Active in the text-only baseline:** No; retained for later restoration
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
- **Required model ID:** `llama-3.3-70b-versatile`
- **Render environment:** Set `GROQ_MODEL` to that exact value and verify account access before claiming generation works
- **Get Key:** https://console.groq.com/keys

## Security

- Groq and CoinAPI keys are stored as server-side environment variables
- CoinAPI key is sent only in the `X-CoinAPI-Key` request header; it is not included in tool results, logs, or error responses
- WebSocket origin restricted to `https://zyrex.wasmer.app`
- No live trade execution or private API access
- Tools use public read-only endpoints only
- Risk calculations are deterministic and local

## Current Implementation

### Active baseline

- ✅ Agno + Groq agent integration
- ✅ Text-only single-prompt request path
- ✅ WebSocket streaming protocol
- ✅ Health check endpoint

Trading tool implementations remain in `tools/` but are disconnected from the active agent.

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

### Testing

Run `python -m unittest discover -s tests -v` for the WebSocket and request-contract tests. A real model-access check is separate and requires a valid server-side `GROQ_API_KEY`.

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
    └── test_main.py
```

### Adding New Tools

1. Create tool function in `tools/` directory
2. Add docstring with parameters and return format
3. Import in `tools/__init__.py`
4. Restore/register one tool only as a separate incremental change
5. Write tests in `tests/` and verify before restoring the next feature

## License

This is the backend for ZYREX AI. See the main project repository for license information.
