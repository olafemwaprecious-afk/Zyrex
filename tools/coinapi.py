"""Read-only CoinAPI market-data tools for ZYREX."""

import json
import logging
import math
import os
import re
from typing import Any

import httpx

BASE_URL = "https://rest.coinapi.io/v1"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
VALID_PERIODS = {
    "1SEC", "2SEC", "5SEC", "10SEC", "30SEC", "1MIN", "2MIN", "3MIN",
    "5MIN", "10MIN", "15MIN", "30MIN", "1HRS", "2HRS", "3HRS",
    "4HRS", "6HRS", "8HRS", "12HRS", "1DAY", "2DAY", "3DAY", "5DAY",
    "1WEEK", "2WEEK", "1MTH", "2MTH", "3MTH", "6MTH", "1YEAR",
}
_ASSET_ID = re.compile(r"^[A-Z0-9]{1,32}$")
_SYMBOL_ID = re.compile(r"^[A-Z0-9]+_[A-Z0-9]+_[A-Z0-9]+_[A-Z0-9]+$")
_logger = logging.getLogger(__name__)


def _json_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _valid_asset_id(value: str) -> bool:
    return isinstance(value, str) and bool(_ASSET_ID.fullmatch(value.strip().upper()))


def _valid_symbol_id(value: str) -> bool:
    return isinstance(value, str) and bool(_SYMBOL_ID.fullmatch(value.strip().upper()))


def _valid_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _error(message: str) -> str:
    return _json_result({"source": "CoinAPI", "error": message})


async def _request_json(tool_name: str, path: str, params: dict[str, Any] | None = None) -> Any:
    api_key = os.getenv("COINAPI_KEY")
    if not api_key:
        _logger.warning("CoinAPI tool=%s status=not_configured", tool_name)
        return {"error": "CoinAPI is not configured. Set the COINAPI_KEY environment variable on the backend."}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"{BASE_URL}{path}",
                headers={"X-CoinAPI-Key": api_key},
                params=params,
            )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, (dict, list)):
            _logger.warning("CoinAPI tool=%s status=invalid_response", tool_name)
            return {"error": "CoinAPI returned an invalid response."}
        _logger.info("CoinAPI tool=%s status=success", tool_name)
        return data
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        _logger.warning("CoinAPI tool=%s status=http_%s", tool_name, status)
        if status in (401, 403):
            message = "CoinAPI rejected the credentials or this endpoint is not enabled for the subscription."
        elif status == 404:
            message = "CoinAPI has no data for that asset or market symbol."
        elif status == 429:
            message = "CoinAPI rate limit reached. Wait before retrying and check the subscription limits."
        else:
            message = f"CoinAPI returned HTTP {status}."
        return {"error": message}
    except httpx.TimeoutException:
        _logger.warning("CoinAPI tool=%s status=timeout", tool_name)
        return {"error": "CoinAPI request timed out. Please try again later."}
    except httpx.RequestError:
        _logger.warning("CoinAPI tool=%s status=connection_error", tool_name)
        return {"error": "CoinAPI could not be reached. Please try again later."}
    except (ValueError, json.JSONDecodeError):
        _logger.warning("CoinAPI tool=%s status=invalid_json", tool_name)
        return {"error": "CoinAPI returned malformed JSON."}


def _failure(data: Any) -> str | None:
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        return data["error"]
    return None


async def get_ticker_price(asset_id_base: str, asset_id_quote: str = "USD") -> str:
    """Get CoinAPI's aggregated exchange rate for two asset IDs (not a venue quote)."""
    if not _valid_asset_id(asset_id_base) or not _valid_asset_id(asset_id_quote):
        return _error("Invalid asset ID. Use letters and digits only, for example BTC and USDT.")

    base = asset_id_base.strip().upper()
    quote = asset_id_quote.strip().upper()
    data = await _request_json("get_ticker_price", f"/exchangerate/{base}/{quote}")
    failure = _failure(data)
    if failure:
        return _error(failure)
    rate = data.get("rate") if isinstance(data, dict) else None
    timestamp = data.get("time") if isinstance(data, dict) else None
    if (
        not isinstance(data, dict)
        or data.get("asset_id_base") != base
        or data.get("asset_id_quote") != quote
        or not _valid_number(rate)
        or rate <= 0
        or not isinstance(timestamp, str)
        or not timestamp
    ):
        return _error("CoinAPI returned incomplete or invalid exchange-rate data; no price is available.")

    return _json_result({
        "source": "CoinAPI",
        "market_type": "aggregated exchange rate",
        "data_type": "rolling_24h_vwap",
        "asset_id_base": base,
        "asset_id_quote": quote,
        "price": rate,
        "quote_currency": quote,
        "timestamp": timestamp,
    })


async def get_24hr_ticker(symbol_id: str) -> str:
    """Get the latest 1-day OHLCV candle; this is not a rolling 24-hour ticker."""
    if not _valid_symbol_id(symbol_id):
        return _error("Invalid CoinAPI symbol ID. Use the EXCHANGE_SPOT_BASE_QUOTE format, for example BITSTAMP_SPOT_BTC_USD.")

    normalized = symbol_id.strip().upper()
    data = await _request_json(
        "get_24hr_ticker",
        f"/ohlcv/{normalized}/latest",
        {"period_id": "1DAY", "limit": 1},
    )
    failure = _failure(data)
    if failure:
        return _error(failure)
    candle = data[0] if isinstance(data, list) and data else None
    required = ("time_period_start", "time_period_end", "price_open", "price_high", "price_low", "price_close")
    if not isinstance(candle, dict) or any(not candle.get(key) for key in required):
        return _error("CoinAPI returned no complete daily candle for that symbol.")
    if any(not _valid_number(candle.get(key)) for key in ("price_open", "price_high", "price_low", "price_close")):
        return _error("CoinAPI returned invalid daily candle prices.")

    result = {key: candle[key] for key in required}
    result.update({key: candle[key] for key in ("volume_traded", "trades_count") if key in candle})
    return _json_result({
        "source": "CoinAPI",
        "market_type": "specific exchange spot pair",
        "data_type": "latest_1DAY_ohlcv_candle",
        "symbol_id": normalized,
        "period_id": "1DAY",
        "ohlcv": result,
        "unavailable": ["rolling 24-hour percentage change"],
        "note": "This is the latest daily candle, not a rolling 24-hour ticker.",
    })


async def get_klines(symbol_id: str, period_id: str = "1HRS", limit: int = 100) -> str:
    """Get historical OHLCV candles from CoinAPI for a specific exchange symbol."""
    if not _valid_symbol_id(symbol_id):
        return _error("Invalid CoinAPI symbol ID. Use the EXCHANGE_SPOT_BASE_QUOTE format, for example BITSTAMP_SPOT_BTC_USD.")
    if not isinstance(period_id, str) or period_id.strip().upper() not in VALID_PERIODS:
        return _error(f"Unsupported period_id. Supported values include: {', '.join(sorted(VALID_PERIODS))}.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        return _error("limit must be an integer from 1 to 1000.")

    normalized = symbol_id.strip().upper()
    period = period_id.strip().upper()
    data = await _request_json(
        "get_klines",
        f"/ohlcv/{normalized}/history",
        {"period_id": period, "limit": limit},
    )
    failure = _failure(data)
    if failure:
        return _error(failure)
    if not isinstance(data, list) or not data:
        return _error("CoinAPI returned no candles for that symbol and period.")

    candles = []
    fields = ("time_period_start", "time_period_end", "price_open", "price_high", "price_low", "price_close", "volume_traded", "trades_count")
    for candle in data:
        if not isinstance(candle, dict) or any(not candle.get(key) for key in fields[:2]):
            return _error("CoinAPI returned an incomplete candle; no candles are reported.")
        if any(not _valid_number(candle.get(key)) for key in fields[2:6]):
            return _error("CoinAPI returned an invalid OHLC candle; no candles are reported.")
        candles.append({key: candle[key] for key in fields if key in candle})

    return _json_result({
        "source": "CoinAPI",
        "market_type": "specific exchange spot pair",
        "data_type": "ohlcv",
        "symbol_id": normalized,
        "period_id": period,
        "count": len(candles),
        "candles": candles,
    })
