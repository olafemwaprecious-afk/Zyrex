"""
Binance API Integration Tool

Provides access to public market data from Binance's spot trading API.
Uses public endpoints that do not require authentication.

Base URL: https://data-api.binance.vision (public market data only)
"""

import asyncio
import httpx
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

# Base URL for Binance public market data API
BASE_URL = "https://data-api.binance.vision"


async def get_ticker_price(
    symbol: Optional[str] = None,
    symbols: Optional[List[str]] = None
) -> str:
    """
    Get current price for one or more trading pairs.

    Args:
        symbol: Single trading pair symbol (e.g., 'BTCUSDT')
        symbols: List of trading pair symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
                 Cannot be used with 'symbol' parameter

    Returns:
        JSON string with current price data
    """
    try:
        if symbol and symbols:
            return json.dumps({
                "error": "Cannot use both 'symbol' and 'symbols' parameters",
                "source": "Binance"
            })

        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        elif symbols:
            params["symbols"] = json.dumps([s.upper() for s in symbols])

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/api/v3/ticker/price",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "Binance",
                "timestamp": datetime.now().isoformat(),
                "data": data
            }

            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return json.dumps({
                "error": "Invalid symbol or request parameters",
                "source": "Binance"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "Binance"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "Binance"
        })


async def get_24hr_ticker(
    symbol: Optional[str] = None,
    symbols: Optional[List[str]] = None
) -> str:
    """
    Get 24-hour ticker price change statistics for one or more trading pairs.

    Args:
        symbol: Single trading pair symbol (e.g., 'BTCUSDT')
        symbols: List of trading pair symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
                 Cannot be used with 'symbol' parameter

    Returns:
        JSON string with 24-hour price change, volume, and other statistics
    """
    try:
        if symbol and symbols:
            return json.dumps({
                "error": "Cannot use both 'symbol' and 'symbols' parameters",
                "source": "Binance"
            })

        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        elif symbols:
            params["symbols"] = json.dumps([s.upper() for s in symbols])

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/api/v3/ticker/24hr",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "Binance",
                "timestamp": datetime.now().isoformat(),
                "data": data
            }

            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return json.dumps({
                "error": "Invalid symbol or request parameters",
                "source": "Binance"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "Binance"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "Binance"
        })


async def get_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 100
) -> str:
    """
    Get K-line/candlestick data for a trading pair.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        interval: K-line interval (e.g., '1m', '5m', '15m', '1h', '4h', '1d')
        limit: Number of candles to return (default: 100, max: 1000)

    Returns:
        JSON string with OHLCV candlestick data
    """
    try:
        valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        if interval not in valid_intervals:
            return json.dumps({
                "error": f"Invalid interval. Valid intervals: {', '.join(valid_intervals)}",
                "source": "Binance"
            })

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": min(limit, 1000)
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/api/v3/klines",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            # Format klines data
            formatted_klines = []
            for kline in data:
                formatted_klines.append({
                    "open_time": kline[0],
                    "open": kline[1],
                    "high": kline[2],
                    "low": kline[3],
                    "close": kline[4],
                    "volume": kline[5],
                    "close_time": kline[6],
                    "quote_volume": kline[7],
                    "trades": kline[8]
                })

            result = {
                "source": "Binance",
                "symbol": symbol.upper(),
                "interval": interval,
                "timestamp": datetime.now().isoformat(),
                "count": len(formatted_klines),
                "klines": formatted_klines
            }

            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            return json.dumps({
                "error": "Invalid symbol or request parameters",
                "source": "Binance"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "Binance"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "Binance"
        })
