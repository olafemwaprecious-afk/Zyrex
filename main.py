import os
import asyncio
import json
import http
from websockets.server import serve
from agno.agent import Agent, RunEvent
from agno.models.groq import Groq
from agno.tools import tool
import httpx

from tools import (
    search_pools,
    get_pool_data,
    get_pool_ohlcv,
    get_trending_pools,
    get_ticker_price,
    get_24hr_ticker,
    get_klines,
    evaluate_trade_risk,
    validate_trade_parameters,
    compare_pools,
    compare_tokens,
    check_tool_status,
)

PORT = int(os.environ.get("PORT", 8080))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_ID = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
ALLOWED_ORIGIN = "https://zyrex.wasmer.app"
KEEP_AWAKE_URL = "https://zyrex-mpya.onrender.com/health"

SYSTEM_INSTRUCTION = """You are ZYREX AI, a trading-focused assistant.

Purpose:
- Explain trading concepts clearly for beginners and intermediate traders.
- Focus on market structure, liquidity, risk management, execution, psychology, and setup analysis.
- Do not claim personal trading data or fabricate account history.
- Do not guarantee profits or claim certainty about future market moves.
- Do not invent trades, PnL, analytics, or market data.
- If personal trading data is unavailable, say that the personal trading data is not currently connected.

Trading Context and Terminology:
- When explaining trading concepts, prioritize the price-action/discretionary trading meaning over market-microstructure meanings.
- For terms like "liquidity sweep", "order block", "fair value gap", "market structure", "break of structure", "change of character", "stop hunt", "imbalance", and "displacement", use the Smart Money Concepts (SMC)/ICT-style price-action interpretation when the user is discussing chart analysis.
- Use order-book or market-microstructure meanings only when the user explicitly asks about order execution, order books, bid/ask liquidity, or market microstructure.
- If a term is genuinely ambiguous, briefly mention the distinction rather than giving the wrong meaning.

Teaching Style:
- Be conversational and clean.
- Use simple explanations suitable for beginner and intermediate traders.
- When introducing a concept: define it, give a simple example, explain what the trader sees on the chart, and explain why it matters.
- Do not teach trading myths as absolute facts. Use language like "traders commonly describe this as", "may be", "is often called", rather than presenting interpretive concepts as guaranteed truths.
- For liquidity sweeps: explain that price moves beyond a significant high/low to interact with liquidity, but emphasize that a sweep does NOT guarantee a reversal.

Style:
- Use brief paragraphs and bullets when helpful.
- You may use Markdown formatting (headings, bold, lists, code blocks) for clarity—the frontend will render it properly.
- Do NOT use HTML tags like <br>, <div>, <span>, etc. Use Markdown instead: double line breaks for paragraphs, or bullet lists.
- For tables, use proper Markdown table syntax with | separators and a header separator row. Example:
  | Step | What to check |
  |------|--------------|
  | 1️⃣ Identify | Description |
  | 2️⃣ Observe | Description |
- Use emojis to make responses friendly and engaging (e.g., 💡 for tips, 📊 for data, ⚠️ for warnings, ✅ for confirmations).
- Do not force every response into a huge Markdown document.
- Do not start every response with ## or ###.
- Do not wrap the entire response in **.
- Do not return raw JSON."""


async def keep_awake():
    """Silent background task to keep the Render instance awake by pinging itself every 11 minutes."""
    while True:
        try:
            async with httpx.AsyncClient() as client:
                await client.get(KEEP_AWAKE_URL, timeout=10.0)
        except Exception:
            # Silently ignore all network errors to prevent crashing the main server
            pass
        await asyncio.sleep(660)  # 11 minutes = 660 seconds


def create_zyrex_agent():
    """Create and configure the ZYREX agent with Agno and Groq."""
    return Agent(
        model=Groq(id=MODEL_ID, api_key=GROQ_API_KEY),
        description=SYSTEM_INSTRUCTION,
        instructions=[
            "You are ZYREX AI, a trading-focused assistant.",
            "Use tools when the user asks for current market data, token prices, or trade analysis.",
            "For a current price for an asset pair such as BTC/USDT, call get_ticker_price with the base and quote asset IDs. This returns CoinAPI's aggregated rolling 24-hour VWAP, not a price from a specific exchange.",
            "For exchange-specific candles, use get_klines or get_24hr_ticker with a CoinAPI symbol ID. Do not describe a daily candle as a rolling 24-hour statistic.",
            "For general trading questions without data requests, answer directly without tools.",
            "Always explain concepts clearly for beginners and intermediate traders.",
            "Never fabricate market data, prices, or token information.",
            "If a tool fails or returns an error, explain the issue honestly to the user.",
            "Use the risk-checking tools when users ask about trade validation or risk calculations.",
            "Provide clear, concise answers with appropriate use of Markdown formatting.",
            "Use emojis to make responses friendly and engaging.",
        ],
        tools=[
            search_pools,
            get_pool_data,
            get_pool_ohlcv,
            get_trending_pools,
            get_ticker_price,
            get_24hr_ticker,
            get_klines,
            evaluate_trade_risk,
            validate_trade_parameters,
            compare_pools,
            compare_tokens,
            check_tool_status,
        ],
        markdown=True,
        show_tool_calls=False,  # Hide internal tool calls from user
        temperature=0.7,
    )


async def handle_websocket(websocket):
    """Handle incoming WebSocket connections and stream Agno agent responses."""
    try:
        # Verify origin
        origin = websocket.request_headers.get("Origin", "")
        if origin != ALLOWED_ORIGIN:
            await websocket.close(code=1008, reason="Origin not allowed")
            return

        if not GROQ_API_KEY:
            await websocket.send(json.dumps({"error": "Groq API key is missing"}))
            await websocket.send("[DONE]")
            return

        # Create agent instance
        agent = create_zyrex_agent()

        async for message in websocket:
            try:
                data = json.loads(message)
                prompt = data.get("prompt", "").strip()
                mode = data.get("mode", "analyst")
                history = data.get("history", [])

                if not prompt:
                    await websocket.send(json.dumps({"error": "A message is required"}))
                    await websocket.send("[DONE]")
                    continue

                # Build conversation context from history
                conversation_context = []
                for entry in history[-8:]:
                    if entry and isinstance(entry.get("text"), str) and entry["text"].strip():
                        role = entry.get("role", "user")
                        conversation_context.append(f"{role}: {entry['text'].strip()}")

                # Add mode and current prompt
                full_prompt = f"Mode: {mode}\n\n"
                if conversation_context:
                    full_prompt += "Previous conversation:\n" + "\n".join(conversation_context) + "\n\n"
                full_prompt += f"Current question: {prompt}"

                # Stream response from Agno agent
                try:
                    async for event in agent.arun(
                        full_prompt,
                        stream=True,
                        stream_events=False  # Only stream content, not internal events
                    ):
                        if event.event == RunEvent.run_content and event.content:
                            await websocket.send(event.content)

                    await websocket.send("[DONE]")

                except Exception as agent_error:
                    print(f"Agent request failed: {type(agent_error).__name__}")
                    await websocket.send(json.dumps({"error": "The assistant could not complete this request. Please try again later."}))
                    await websocket.send("[DONE]")

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON payload"}))
                await websocket.send("[DONE]")
            except Exception as e:
                print(f"WebSocket message failed: {type(e).__name__}")
                await websocket.send(json.dumps({"error": "The request could not be processed."}))
                await websocket.send("[DONE]")

    except Exception:
        pass
    finally:
        await websocket.close()


def process_request(path, headers):
    """Intercept HTTP health pings purely on the /health route, leaving the root path clear for WebSockets."""
    if path == "/health":
        import http
        return http.HTTPStatus.OK, [("Content-Type", "text/plain")], b"ZYREX Engine Online"
    return None


async def main():
    """Main entry point: start keep-awake task and WebSocket server."""
    # Start background keep-awake task
    asyncio.create_task(keep_awake())

    # Start WebSocket server
    async with serve(handle_websocket, "0.0.0.0", PORT, process_request=process_request):
        print(f"ZYREX WebSocket server listening on port {PORT}")
        print(f"Allowed origin: {ALLOWED_ORIGIN}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
