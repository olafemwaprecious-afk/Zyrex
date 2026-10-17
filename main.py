import os
import asyncio
import json
from websockets.server import serve
from groq import AsyncGroq
import httpx

PORT = int(os.environ.get("PORT", 8080))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_ID = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
ALLOWED_ORIGIN = "https://zyrex.wasmer.app/"
KEEP_AWAKE_URL = "https://zyrex.onrender.com"

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


async def handle_websocket(websocket):
    """Handle incoming WebSocket connections and stream Groq responses."""
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

        client = AsyncGroq(api_key=GROQ_API_KEY)

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

                messages = [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                ]

                # Add history (last 8 messages)
                for entry in history[-8:]:
                    if entry and isinstance(entry.get("text"), str) and entry["text"].strip():
                        role = "user" if entry.get("role") == "user" else "assistant"
                        messages.append({"role": role, "content": entry["text"].strip()})

                # Add current prompt
                messages.append({
                    "role": "user",
                    "content": f"Mode: {mode}\n\nUser question: {prompt}"
                })

                # Stream response from Groq
                stream = await client.chat.completions.create(
                    model=MODEL_ID,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                    stream=True
                )

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        await websocket.send(chunk.choices[0].delta.content)

                await websocket.send("[DONE]")

            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON payload"}))
                await websocket.send("[DONE]")
            except Exception as e:
                await websocket.send(json.dumps({"error": str(e)}))
                await websocket.send("[DONE]")

    except Exception:
        pass
    finally:
        await websocket.close()


async def main():
    """Main entry point: start keep-awake task and WebSocket server."""
    # Start background keep-awake task
    asyncio.create_task(keep_awake())

    # Start WebSocket server
    async with serve(handle_websocket, "0.0.0.0", PORT):
        print(f"ZYREX WebSocket server listening on port {PORT}")
        print(f"Allowed origin: {ALLOWED_ORIGIN}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
