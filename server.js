import http from "node:http";

const PORT = Number(process.env.PORT || 3001);
const API_KEY = process.env.GROQ_API_KEY;
const MODEL_ID = process.env.GROQ_MODEL || "openai/gpt-oss-120b";
const GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions";

// Parse CORS origins from environment variable
const CORS_ORIGINS = process.env.CORS_ORIGINS
  ? process.env.CORS_ORIGINS.split(",").map((origin) => origin.trim())
  : ["http://localhost:5173"];

const SYSTEM_INSTRUCTION = `You are ZYREX AI, a trading-focused assistant.

Purpose:
|- Explain trading concepts clearly for beginners and intermediate traders.
|- Focus on market structure, liquidity, risk management, execution, psychology, and setup analysis.
|- Do not claim personal trading data or fabricate account history.
|- Do not guarantee profits or claim certainty about future market moves.
|- Do not invent trades, PnL, analytics, or market data.
|- If personal trading data is unavailable, say that the personal trading data is not currently connected.

Trading Context and Terminology:
|- When explaining trading concepts, prioritize the price-action/discretionary trading meaning over market-microstructure meanings.
|- For terms like "liquidity sweep", "order block", "fair value gap", "market structure", "break of structure", "change of character", "stop hunt", "imbalance", and "displacement", use the Smart Money Concepts (SMC)/ICT-style price-action interpretation when the user is discussing chart analysis.
|- Use order-book or market-microstructure meanings only when the user explicitly asks about order execution, order books, bid/ask liquidity, or market microstructure.
|- If a term is genuinely ambiguous, briefly mention the distinction rather than giving the wrong meaning.

Teaching Style:
|- Be conversational and clean.
|- Use simple explanations suitable for beginner and intermediate traders.
|- When introducing a concept: define it, give a simple example, explain what the trader sees on the chart, and explain why it matters.
|- Do not teach trading myths as absolute facts. Use language like "traders commonly describe this as", "may be", "is often called", rather than presenting interpretive concepts as guaranteed truths.
|- For liquidity sweeps: explain that price moves beyond a significant high/low to interact with liquidity, but emphasize that a sweep does NOT guarantee a reversal.

Style:
|- Use brief paragraphs and bullets when helpful.
|- You may use Markdown formatting (headings, bold, lists, code blocks) for clarity—the frontend will render it properly.
|- Do NOT use HTML tags like <br>, <div>, <span>, etc. Use Markdown instead: double line breaks for paragraphs, or bullet lists.
|- For tables, use proper Markdown table syntax with | separators and a header separator row. Example:
  | Step | What to check |
  |------|--------------|
  | 1️⃣ Identify | Description |
  | 2️⃣ Observe | Description |
|- Use emojis to make responses friendly and engaging (e.g., 💡 for tips, 📊 for data, ⚠️ for warnings, ✅ for confirmations).
|- Do not force every response into a huge Markdown document.
|- Do not start every response with ## or ###.
|- Do not wrap the entire response in **.
|- Do not return raw JSON.`;

function sendJson(res, statusCode, payload, origin = null) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };

  if (origin && CORS_ORIGINS.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }

  res.writeHead(statusCode, headers);
  res.end(JSON.stringify(payload));
}

function toErrorReason(message) {
  const lower = String(message || "").toLowerCase();

  if (lower.includes("api key") || lower.includes("unauthorized") || lower.includes("forbidden")) {
    return "The Groq API key is invalid or unauthorized. Please check the server configuration.";
  }

  if (lower.includes("quota") || lower.includes("rate limit") || lower.includes("429")) {
    return "Groq rate limits or quota are currently exhausted. Please try again later.";
  }

  if (lower.includes("model") || lower.includes("not found")) {
    return "The requested Groq model is unavailable right now.";
  }

  if (lower.includes("timeout") || lower.includes("network")) {
    return "The Groq request timed out or the network connection failed.";
  }

  return "I couldn't connect to ZYREX right now. Please try again.";
}

function extractTextFromGroq(result) {
  const content = result?.choices?.[0]?.message?.content;
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    return content
      .map((part) => (typeof part === "string" ? part : part?.text ?? ""))
      .join(" ")
      .trim();
  }
  return "";
}

function buildBlocks(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) {
    return [{ type: "note", tone: "warn", text: "ZYREX could not generate a response." }];
  }

  return [{ type: "summary", text: trimmed }];
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin || null;

  // Health check endpoint
  if (req.method === "GET" && req.url === "/api/health") {
    sendJson(res, 200, {
      status: "ok",
      service: "ZYREX Backend",
      version: "1.0.0"
    }, origin);
    return;
  }

  // CORS preflight
  if (req.method === "OPTIONS") {
    sendJson(res, 204, {}, origin);
    return;
  }

  // Main AI endpoint
  if (req.method !== "POST" || req.url !== "/api/zyrex-ai") {
    sendJson(res, 404, { error: "Not found" }, origin);
    return;
  }

  if (!API_KEY) {
    sendJson(res, 500, {
      status: "offline",
      reason: "The Groq API key is missing from the server environment. Please configure GROQ_API_KEY.",
    }, origin);
    return;
  }

  let rawBody = "";
  req.on("data", (chunk) => {
    rawBody += chunk.toString();
  });

  req.on("end", async () => {
    try {
      let payload = {};
      try {
        payload = rawBody ? JSON.parse(rawBody) : {};
      } catch {
        sendJson(res, 400, {
          status: "offline",
          reason: "The request payload was invalid.",
        }, origin);
        return;
      }

      const prompt = String(payload.prompt ?? "").trim();
      const mode = String(payload.mode ?? "analyst");
      const history = Array.isArray(payload.history) ? payload.history.slice(-8) : [];

      if (!prompt) {
        sendJson(res, 400, {
          status: "offline",
          reason: "A message is required before ZYREX can answer.",
        }, origin);
        return;
      }

      const messages = [
        { role: "system", content: SYSTEM_INSTRUCTION },
        ...history
          .filter((entry) => entry && typeof entry.text === "string" && entry.text.trim())
          .map((entry) => ({
            role: entry.role === "user" ? "user" : "assistant",
            content: String(entry.text).trim(),
          })),
        {
          role: "user",
          content: `Mode: ${mode}\n\nUser question: ${prompt}`,
        },
      ];

      const groqResponse = await fetch(GROQ_ENDPOINT, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: MODEL_ID,
          messages,
          temperature: 0.7,
          max_tokens: 2000,
        }),
      });

      if (!groqResponse.ok) {
        const errorBody = await groqResponse.json().catch(() => ({}));
        const reason = toErrorReason(errorBody?.error?.message || `Groq HTTP ${groqResponse.status}`);
        sendJson(res, 502, { status: "offline", reason }, origin);
        return;
      }

      const data = await groqResponse.json();
      const answer = extractTextFromGroq(data);

      if (!answer) {
        sendJson(res, 502, {
          status: "offline",
          reason: "Groq returned an empty response.",
        }, origin);
        return;
      }

      sendJson(res, 200, {
        status: "ready",
        title: "ZYREX AI",
        blocks: buildBlocks(answer),
      }, origin);
    } catch (error) {
      const reason = toErrorReason(error instanceof Error ? error.message : "Groq failed to respond.");
      sendJson(res, 502, {
        status: "offline",
        reason,
      }, origin);
    }
  });
});

server.listen(PORT, () => {
  console.log(`ZYREX Backend listening on http://localhost:${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/api/health`);
});
