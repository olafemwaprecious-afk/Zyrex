import asyncio
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import websockets
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import InvalidStatus

import main


class FakeAgent:
    def __init__(self, chunks=("first ", "second")):
        self.chunks = chunks
        self.prompts = []

    async def arun(self, prompt, *, stream, stream_events):
        self.prompts.append(prompt)
        for chunk in self.chunks:
            yield SimpleNamespace(event=main.RunEvent.run_content, content=chunk)


class FailingAgent:
    async def arun(self, prompt, *, stream, stream_events):
        if False:
            yield None
        raise ProviderError("Model not found; api_key=gsk_test_secret")


class ProviderError(Exception):
    status_code = 404


class BackendIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = await serve(
            main.handle_websocket,
            "127.0.0.1",
            0,
            origins=[main.ALLOWED_ORIGIN],
            process_request=main.process_request,
            process_response=main.log_handshake_response,
            logger=main.logger,
        )
        self.port = self.server.sockets[0].getsockname()[1]
        self.http_url = f"http://127.0.0.1:{self.port}"
        self.ws_url = f"ws://127.0.0.1:{self.port}/"

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def _exchange(self, payload):
        async with connect(self.ws_url, origin=main.ALLOWED_ORIGIN) as websocket:
            await websocket.send(payload)
            frames = []
            async for frame in websocket:
                frames.append(frame)
                if frame == "[DONE]":
                    break
            return frames

    async def test_health_returns_200_and_plain_http_root_returns_426(self):
        async with httpx.AsyncClient() as client:
            health = await client.get(f"{self.http_url}/health")
            root = await client.get(f"{self.http_url}/")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.text, "ZYREX Engine Online")
        self.assertEqual(root.status_code, 426)

    async def test_malformed_upgrade_returns_400(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(
            (
                "GET / HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{self.port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Origin: {main.ALLOWED_ORIGIN}\r\n"
                "\r\n"
            ).encode()
        )
        await writer.drain()
        status_line = await reader.readline()
        writer.close()
        await writer.wait_closed()
        self.assertIn(b" 400 ", status_line)

    async def test_wrong_origin_is_rejected_during_handshake(self):
        with self.assertRaises(InvalidStatus) as caught:
            async with connect(self.ws_url, origin="https://untrusted.example"):
                pass
        self.assertEqual(caught.exception.response.status_code, 403)

    async def test_direct_payload_streams_ordered_chunks_then_done(self):
        agent = FakeAgent()
        payload = json.dumps(
            {
                "prompt": "Explain a liquidity sweep",
                "mode": "analyst",
                "history": [],
            }
        )
        with patch.object(main, "GROQ_API_KEY", "test-key"), patch.object(
            main, "create_zyrex_agent", return_value=agent
        ):
            frames = await self._exchange(payload)

        self.assertEqual(frames, ["first ", "second", "[DONE]"])
        self.assertEqual(agent.prompts, ["Explain a liquidity sweep"])

    async def test_legacy_payload_is_unwrapped(self):
        agent = FakeAgent(("legacy answer",))
        payload = json.dumps(
            {
                "type": "action",
                "action": "chat_turn",
                "params": {"prompt": "Legacy question", "history": ["ignored"]},
            }
        )
        with patch.object(main, "GROQ_API_KEY", "test-key"), patch.object(
            main, "create_zyrex_agent", return_value=agent
        ):
            frames = await self._exchange(payload)

        self.assertEqual(frames, ["legacy answer", "[DONE]"])
        self.assertEqual(agent.prompts, ["Legacy question"])

    async def test_invalid_json_and_empty_prompt_return_error_then_done(self):
        for payload, expected in (
            ("{", "Invalid JSON payload."),
            (json.dumps({"prompt": "  "}), "A non-empty prompt is required."),
        ):
            with self.subTest(payload=payload):
                frames = await self._exchange(payload)
                self.assertEqual(json.loads(frames[0]), {"error": expected})
                self.assertEqual(frames[1], "[DONE]")

    async def test_missing_key_returns_safe_error_then_done(self):
        with patch.object(main, "GROQ_API_KEY", None):
            frames = await self._exchange(json.dumps({"prompt": "Hello"}))

        self.assertEqual(
            json.loads(frames[0]), {"error": "The assistant is not configured."}
        )
        self.assertEqual(frames[1], "[DONE]")

    async def test_provider_failure_is_logged_redacted_and_returns_done(self):
        with patch.object(main, "GROQ_API_KEY", "gsk_test_secret"), patch.object(
            main, "create_zyrex_agent", return_value=FailingAgent()
        ):
            with self.assertLogs("main", level="ERROR") as captured:
                frames = await self._exchange(json.dumps({"prompt": "Hello"}))

        log_output = "\n".join(captured.output)
        self.assertIn("status=groq_model_access_error", log_output)
        self.assertIn("error_type=ProviderError", log_output)
        self.assertIn("provider_status=404", log_output)
        self.assertNotIn("gsk_test_secret", log_output)
        self.assertEqual(json.loads(frames[0])["error"], "The assistant could not complete this request. Please try again later.")
        self.assertEqual(frames[1], "[DONE]")

    def test_server_uses_asyncio_api_callback_signatures(self):
        self.assertEqual(websockets.__version__, "15.0.1")
        self.assertEqual(
            list(inspect.signature(main.process_request).parameters),
            ["connection", "request"],
        )
        self.assertEqual(
            list(inspect.signature(main.log_handshake_response).parameters),
            ["connection", "request", "response"],
        )

    def test_text_only_agent_constructor_has_no_tools(self):
        with patch.object(main, "GROQ_API_KEY", "test-key"):
            agent = main.create_zyrex_agent()
        self.assertEqual(agent.model.id, "llama-3.3-70b-versatile")
        self.assertFalse(agent.tools)


if __name__ == "__main__":
    unittest.main()
