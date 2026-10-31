import asyncio
import json
import logging
import os
import re
import uuid
from http import HTTPStatus
from urllib.parse import urlsplit
from agno.agent import Agent, RunEvent
from agno.models.groq import Groq
from dotenv import load_dotenv
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response
from websockets.exceptions import ConnectionClosed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

PORT = int(os.environ.get("PORT", 8080))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_ID = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
ALLOWED_ORIGIN = "https://zyrex.wasmer.app"

SYSTEM_INSTRUCTION = """You are ZYREX AI, a trading-focused assistant.
Explain trading concepts clearly without claiming access to live market data,
personal trading data, or certainty about future market moves."""

_BEARER_SECRET = re.compile(r"(?i)(bearer\s+)[^\s,;\"']+")
_API_KEY_FIELD = re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;\"']+")
_GROQ_KEY = re.compile(r"\bgsk_[A-Za-z0-9_-]+\b")


class EmptyPromptError(ValueError):
    pass


def _response(status: HTTPStatus, body: str) -> Response:
    body_bytes = body.encode("utf-8")
    headers = Headers(
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body_bytes))),
        ]
    )
    return Response(status.value, status.phrase, headers, body_bytes)


def process_request(
    connection: ServerConnection, request: Request
) -> Response | None:
    """Serve health checks and reject invalid paths or WebSocket origins."""
    path = urlsplit(request.path).path
    origin = request.headers.get("Origin", "")

    if path == "/health":
        logger.info(
            "status=http_health_response path=%s origin=%s http_status=%d",
            path,
            origin or "none",
            HTTPStatus.OK,
        )
        return _response(HTTPStatus.OK, "ZYREX Engine Online")

    if path != "/":
        logger.warning(
            "status=http_request_rejected path=%s origin=%s http_status=%d",
            path,
            origin or "none",
            HTTPStatus.NOT_FOUND,
        )
        return _response(HTTPStatus.NOT_FOUND, "Not Found")

    is_websocket_upgrade = (
        request.headers.get("Upgrade", "").lower() == "websocket"
    )
    if is_websocket_upgrade and origin != ALLOWED_ORIGIN:
        logger.warning(
            "status=websocket_rejected path=%s origin=%s reason=origin_mismatch http_status=%d",
            path,
            origin or "none",
            HTTPStatus.FORBIDDEN,
        )
        return _response(HTTPStatus.FORBIDDEN, "Origin not allowed")

    return None


def log_handshake_response(
    connection: ServerConnection, request: Request, response: Response
) -> Response:
    logger.info(
        "status=handshake_response path=%s origin=%s http_status=%d",
        urlsplit(request.path).path,
        request.headers.get("Origin", "none"),
        response.status_code,
    )
    return response


def create_zyrex_agent() -> Agent:
    """Create the text-only Agno agent for the configured Groq model."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    agent = Agent(
        model=Groq(id=MODEL_ID, api_key=GROQ_API_KEY),
        description=SYSTEM_INSTRUCTION,
        instructions=[
            "Answer the user's prompt directly.",
            "Do not claim to have current market data or use external tools.",
        ],
        markdown=True,
        telemetry=False,
    )
    logger.info("status=agent_initialized model=%s tools=0", MODEL_ID)
    return agent


def extract_prompt(message: str | bytes) -> str:
    payload = json.loads(message)
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    if payload.get("type") == "action" and payload.get("action") == "chat_turn":
        payload = payload.get("params")
        if not isinstance(payload, dict):
            raise ValueError("Legacy chat params must be an object")

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise EmptyPromptError("A non-empty prompt is required")
    return prompt.strip()


def _safe_exception_detail(error: Exception) -> str:
    detail = str(error).replace("\r", " ").replace("\n", " ").strip()
    if GROQ_API_KEY:
        detail = detail.replace(GROQ_API_KEY, "[REDACTED]")
    detail = _BEARER_SECRET.sub(r"\1[REDACTED]", detail)
    detail = _API_KEY_FIELD.sub(r"\1[REDACTED]", detail)
    detail = _GROQ_KEY.sub("[REDACTED]", detail)
    return detail[:1000] or "No provider detail supplied"


def _provider_status(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(getattr(error, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _log_inference_error(request_id: str, error: Exception) -> None:
    provider_status = _provider_status(error)
    detail = _safe_exception_detail(error)
    lowered_detail = detail.lower()
    is_model_access_error = provider_status in (400, 403, 404) or any(
        marker in lowered_detail
        for marker in ("model decommission", "model not found", "model access")
    )
    if provider_status == 401:
        status = "groq_authentication_error"
    elif is_model_access_error:
        status = "groq_model_access_error"
    else:
        status = "groq_inference_failed"
    logger.error(
        "request_id=%s status=%s model=%s error_type=%s provider_status=%s provider_error=%s",
        request_id,
        status,
        MODEL_ID,
        type(error).__name__,
        provider_status if provider_status is not None else "unknown",
        detail,
    )


async def _send_error(connection: ServerConnection, message: str) -> None:
    await connection.send(json.dumps({"error": message}))
    await connection.send("[DONE]")


async def handle_websocket(connection: ServerConnection) -> None:
    request_id = str(uuid.uuid4())[:8]
    path = urlsplit(connection.request.path).path
    origin = connection.request.headers.get("Origin", "")
    if path != "/" or origin != ALLOWED_ORIGIN:
        logger.warning(
            "request_id=%s status=websocket_rejected path=%s origin=%s reason=invalid_request",
            request_id,
            path,
            origin or "none",
        )
        await connection.close(code=1008, reason="WebSocket request not allowed")
        return

    logger.info(
        "request_id=%s status=websocket_accepted path=%s origin=%s http_status=%d",
        request_id,
        path,
        origin,
        HTTPStatus.SWITCHING_PROTOCOLS,
    )

    try:
        message = await connection.recv()
    except ConnectionClosed:
        logger.info("request_id=%s status=connection_closed_before_message", request_id)
        return

    try:
        prompt = extract_prompt(message)
    except json.JSONDecodeError:
        logger.warning("request_id=%s status=invalid_json", request_id)
        await _send_error(connection, "Invalid JSON payload.")
        return
    except EmptyPromptError:
        logger.warning("request_id=%s status=empty_prompt", request_id)
        await _send_error(connection, "A non-empty prompt is required.")
        return
    except (TypeError, ValueError, UnicodeDecodeError):
        logger.warning("request_id=%s status=invalid_request", request_id)
        await _send_error(connection, "Invalid request payload.")
        return

    logger.info(
        "request_id=%s status=request_received prompt_length=%d",
        request_id,
        len(prompt),
    )
    if not GROQ_API_KEY:
        logger.error("request_id=%s status=groq_key_missing", request_id)
        await _send_error(connection, "The assistant is not configured.")
        return

    try:
        agent = create_zyrex_agent()
    except Exception as error:
        logger.error(
            "request_id=%s status=agent_initialization_failed model=%s error_type=%s error_details=%s",
            request_id,
            MODEL_ID,
            type(error).__name__,
            _safe_exception_detail(error),
        )
        await _send_error(connection, "The assistant is temporarily unavailable.")
        return

    try:
        chunks_sent = 0
        async for event in agent.arun(
            prompt,
            stream=True,
            stream_events=False,
        ):
            if event.event == RunEvent.run_content and event.content:
                await connection.send(event.content)
                chunks_sent += 1
        await connection.send("[DONE]")
        logger.info(
            "request_id=%s status=response_completed model=%s chunks=%d",
            request_id,
            MODEL_ID,
            chunks_sent,
        )
    except Exception as error:
        _log_inference_error(request_id, error)
        await _send_error(
            connection,
            "The assistant could not complete this request. Please try again later.",
        )


async def main() -> None:
    async with serve(
        handle_websocket,
        "0.0.0.0",
        PORT,
        origins=[ALLOWED_ORIGIN],
        process_request=process_request,
        process_response=log_handshake_response,
        logger=logger,
    ):
        logger.info(
            "status=server_started host=0.0.0.0 port=%d allowed_origin=%s model=%s",
            PORT,
            ALLOWED_ORIGIN,
            MODEL_ID,
        )
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
