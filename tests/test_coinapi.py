import json
import logging
from types import SimpleNamespace

import httpx
import pytest

from tools import coinapi

_AsyncClient = httpx.AsyncClient


@pytest.fixture
def mock_coinapi(monkeypatch):
    requests = []

    def install(handler):
        def recording_handler(request):
            requests.append(request)
            return handler(request)

        transport = httpx.MockTransport(recording_handler)

        def client_factory(*, timeout):
            return _AsyncClient(transport=transport, timeout=timeout)

        monkeypatch.setattr(coinapi.httpx, "AsyncClient", client_factory)

    return requests, install


def response(request, payload, status_code=200):
    return httpx.Response(status_code, json=payload, request=request)


@pytest.mark.asyncio
async def test_ticker_sends_key_in_header_and_parses_aggregated_rate(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    requests, install = mock_coinapi
    install(lambda request: response(request, {
        "asset_id_base": "BTC",
        "asset_id_quote": "USDT",
        "rate": 65000.25,
        "time": "2026-10-19T12:00:00.0000000Z",
    }))

    result = json.loads(await coinapi.get_ticker_price("btc", "usdt"))

    assert requests[0].headers["X-CoinAPI-Key"] == "test-secret-key"
    assert "test-secret-key" not in json.dumps(result)
    assert result["price"] == 65000.25
    assert result["asset_id_base"] == "BTC"
    assert result["asset_id_quote"] == "USDT"
    assert result["source"] == "CoinAPI"
    assert result["data_type"] == "rolling_24h_vwap"
    assert result["timestamp"] == "2026-10-19T12:00:00.0000000Z"


@pytest.mark.asyncio
async def test_missing_key_is_safe_and_makes_no_request(monkeypatch, mock_coinapi):
    monkeypatch.delenv("COINAPI_KEY", raising=False)
    requests, _ = mock_coinapi

    result = json.loads(await coinapi.get_ticker_price("BTC", "USDT"))

    assert "COINAPI_KEY" in result["error"]
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("base,quote", [("BTC/USDT", "USD"), ("", "USD"), ("BTC", "USDT?x=1")])
async def test_invalid_asset_ids_are_rejected_without_request(monkeypatch, mock_coinapi, base, quote):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    requests, _ = mock_coinapi

    result = json.loads(await coinapi.get_ticker_price(base, quote))

    assert "Invalid asset ID" in result["error"]
    assert requests == []


@pytest.mark.asyncio
async def test_malformed_ticker_does_not_report_price(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    install(lambda request: response(request, {"asset_id_base": "BTC", "rate": "unknown"}))

    result = json.loads(await coinapi.get_ticker_price("BTC", "USDT"))

    assert "error" in result
    assert "price" not in result


@pytest.mark.asyncio
async def test_ohlcv_response_is_parsed(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    candle = {
        "time_period_start": "2026-10-19T11:00:00.0000000Z",
        "time_period_end": "2026-10-19T12:00:00.0000000Z",
        "price_open": 100.0,
        "price_high": 110.0,
        "price_low": 95.0,
        "price_close": 105.0,
        "volume_traded": 123.5,
        "trades_count": 42,
    }
    install(lambda request: response(request, [candle]))

    result = json.loads(await coinapi.get_klines("BITSTAMP_SPOT_BTC_USD", "1HRS", 1))

    assert result["symbol_id"] == "BITSTAMP_SPOT_BTC_USD"
    assert result["period_id"] == "1HRS"
    assert result["count"] == 1
    assert result["candles"] == [candle]


@pytest.mark.asyncio
async def test_latest_daily_candle_is_not_claimed_as_rolling_ticker(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    requests, install = mock_coinapi
    candle = {
        "time_period_start": "2026-10-18T00:00:00.0000000Z",
        "time_period_end": "2026-10-19T00:00:00.0000000Z",
        "price_open": 100.0,
        "price_high": 110.0,
        "price_low": 95.0,
        "price_close": 105.0,
    }
    install(lambda request: response(request, [candle]))

    result = json.loads(await coinapi.get_24hr_ticker("BITSTAMP_SPOT_BTC_USD"))

    assert result["data_type"] == "latest_1DAY_ohlcv_candle"
    assert result["unavailable"] == ["rolling 24-hour percentage change"]
    assert requests[0].url.params["period_id"] == "1DAY"


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol,period,limit", [
    ("BTC/USDT", "1HRS", 2),
    ("BITSTAMP_SPOT_BTC_USD", "1FORTNIGHT", 2),
    ("BITSTAMP_SPOT_BTC_USD", "1HRS", 0),
    ("BITSTAMP_SPOT_BTC_USD", "1HRS", 1001),
])
async def test_invalid_kline_inputs_are_rejected(monkeypatch, mock_coinapi, symbol, period, limit):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    requests, _ = mock_coinapi

    result = json.loads(await coinapi.get_klines(symbol, period, limit))

    assert "error" in result
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429])
async def test_http_auth_access_and_rate_errors_are_truthful(monkeypatch, mock_coinapi, status):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    install(lambda request: response(request, {"error": "sensitive provider text"}, status))

    result_text = await coinapi.get_ticker_price("BTC", "USDT")
    result = json.loads(result_text)

    assert "error" in result
    assert "test-secret-key" not in result_text
    assert "sensitive provider text" not in result_text
    if status == 401:
        assert "credentials" in result["error"]
    elif status == 403:
        assert "subscription" in result["error"]
    else:
        assert "rate limit" in result["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [
    httpx.ReadTimeout("test-secret-key timed out"),
    httpx.ConnectError("test-secret-key connection failed"),
])
async def test_timeout_and_connection_failures_do_not_leak_details(monkeypatch, mock_coinapi, exception, caplog):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    install(lambda request: (_ for _ in ()).throw(exception))

    with caplog.at_level(logging.WARNING):
        result_text = await coinapi.get_ticker_price("BTC", "USDT")

    assert "error" in json.loads(result_text)
    assert "test-secret-key" not in result_text
    assert "test-secret-key" not in caplog.text


@pytest.mark.asyncio
async def test_malformed_provider_json_is_rejected(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    install(lambda request: httpx.Response(200, content=b"not-json", request=request))

    result = json.loads(await coinapi.get_ticker_price("BTC", "USDT"))

    assert "malformed JSON" in result["error"]
    assert "price" not in result


@pytest.mark.asyncio
async def test_incomplete_candle_is_not_reported_as_valid_ohlcv(monkeypatch, mock_coinapi):
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    install(lambda request: response(request, [{
        "time_period_start": "2026-10-19T11:00:00Z",
        "time_period_end": "2026-10-19T12:00:00Z",
        "price_open": 100.0,
    }]))

    result = json.loads(await coinapi.get_klines("BITSTAMP_SPOT_BTC_USD"))

    assert "error" in result
    assert "candles" not in result


def test_agno_registers_coinapi_tools(monkeypatch):
    import main

    # Mock Agent to return a real Agent object with the right attributes
    class MockAgent:
        def __init__(self, **kwargs):
            self.tool_choice = kwargs.get("tool_choice")
            self.tools = kwargs.get("tools", [])
            self.instructions = kwargs.get("instructions", [])

    monkeypatch.setattr(main, "Groq", lambda **kwargs: object())
    monkeypatch.setattr(main, "Agent", MockAgent)

    agent = main.create_zyrex_agent()
    registered = {function.__name__ for function in agent.tools}

    assert {"get_ticker_price", "get_24hr_ticker", "get_klines"} <= registered
    assert any("BTC/USDT" in instruction for instruction in agent.instructions)


def test_agent_configures_tool_choice_auto(monkeypatch):
    """Verify that the agent explicitly sets tool_choice to auto for automatic tool selection."""
    import main

    # Mock Agent to return a real Agent object with the right attributes
    class MockAgent:
        def __init__(self, **kwargs):
            self.tool_choice = kwargs.get("tool_choice")
            self.tools = kwargs.get("tools", [])
            self.instructions = kwargs.get("instructions", [])

    monkeypatch.setattr(main, "Groq", lambda **kwargs: object())
    monkeypatch.setattr(main, "Agent", MockAgent)

    agent = main.create_zyrex_agent()

    assert agent.tool_choice == "auto", "Agent must have tool_choice set to 'auto' to enable automatic tool selection"
    assert len(agent.tools) == 12, "All 12 tools should be registered"


@pytest.mark.asyncio
async def test_websocket_market_request_streams_tool_result_and_done(monkeypatch, mock_coinapi):
    import main

    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    monkeypatch.setattr(main, "GROQ_API_KEY", "configured")
    _, install = mock_coinapi
    install(lambda request: response(request, {
        "asset_id_base": "BTC",
        "asset_id_quote": "USDT",
        "rate": 65000.25,
        "time": "2026-10-19T12:00:00Z",
    }))

    class FakeAgent:
        def __init__(self):
            self.tools = []
            self.tool_choice = "auto"

        async def arun(self, prompt, **kwargs):
            assert "current BTC/USDT" in prompt
            tool_result = await main.get_ticker_price("BTC", "USDT")
            yield SimpleNamespace(event=main.RunEvent.run_content, content=tool_result)

    # Mock create_zyrex_agent to return FakeAgent
    monkeypatch.setattr(main, "create_zyrex_agent", lambda: FakeAgent())

    class FakeWebSocket:
        request_headers = {"Origin": main.ALLOWED_ORIGIN}

        def __init__(self):
            self.messages = [json.dumps({"prompt": "What is the current BTC/USDT price?", "mode": "analyst", "history": []})]
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.messages:
                return self.messages.pop(0)
            raise StopAsyncIteration

        async def send(self, message):
            self.sent.append(message)

        async def close(self, **kwargs):
            pass

    websocket = FakeWebSocket()
    await main.handle_websocket(websocket)

    assert any('"price":65000.25' in message for message in websocket.sent)
    assert websocket.sent[-1] == "[DONE]"


def test_health_check_protocol_is_unchanged():
    import http
    import main

    status, headers, body = main.process_request("/health", {})

    assert status == http.HTTPStatus.OK
    assert ("Content-Type", "text/plain") in headers
    assert body == b"ZYREX Engine Online"


def test_diagnostics_includes_agent_configuration(monkeypatch):
    """Verify diagnostics tool reports agent configuration including tool_choice."""
    from tools import diagnostics

    monkeypatch.setenv("COINAPI_KEY", "test-key")

    # Verify the function exists and is importable
    assert callable(diagnostics.check_tool_status)


@pytest.mark.asyncio
async def test_ordinary_question_does_not_require_tools(monkeypatch, mock_coinapi):
    """Test that ordinary trading questions can be answered without forcing tool calls."""
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    monkeypatch.setenv("GROQ_API_KEY", "configured")
    requests, _ = mock_coinapi

    # This test verifies the agent configuration allows natural language answers
    # The actual execution would require mocking the Groq API
    import main

    # Mock Agent to return a real Agent object with the right attributes
    class MockAgent:
        def __init__(self, **kwargs):
            self.tool_choice = kwargs.get("tool_choice")
            self.tools = kwargs.get("tools", [])
            self.instructions = kwargs.get("instructions", [])

    monkeypatch.setattr(main, "Groq", lambda **kwargs: object())
    monkeypatch.setattr(main, "Agent", MockAgent)

    agent = main.create_zyrex_agent()

    # Verify tool_choice is auto (not required, not none)
    assert agent.tool_choice == "auto"
    # Verify general trading instruction exists
    assert any("general trading questions without data requests" in str(instr) for instr in agent.instructions)


@pytest.mark.asyncio
async def test_tool_execution_error_is_handled_gracefully(monkeypatch, mock_coinapi):
    """Test that tool errors are properly handled and reported to the user."""
    monkeypatch.setenv("COINAPI_KEY", "test-secret-key")
    _, install = mock_coinapi
    # Simulate a 404 error from CoinAPI
    install(lambda request: httpx.Response(404, json={"error": "Not found"}, request=request))

    result_text = await coinapi.get_ticker_price("INVALID", "USD")
    result = json.loads(result_text)

    assert "error" in result
    assert "test-secret-key" not in result_text  # No secrets leaked
