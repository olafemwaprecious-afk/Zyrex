"""
GeckoTerminal API Integration Tool

Provides access to decentralized exchange (DEX) token and pool data
from GeckoTerminal's public API.

Rate limit: ~30 calls/minute for public API (free tier)
Base URL: https://api.geckoterminal.com/api/v2
"""

import asyncio
import httpx
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

# Base URL for GeckoTerminal API
BASE_URL = "https://api.geckoterminal.com/api/v2"

# Simple in-memory cache with 60-second TTL
_cache: Dict[str, tuple[Any, float]] = {}
CACHE_TTL = 60.0  # seconds


def _get_from_cache(key: str) -> Optional[Any]:
    """Retrieve value from cache if not expired."""
    if key in _cache:
        value, timestamp = _cache[key]
        if datetime.now().timestamp() - timestamp < CACHE_TTL:
            return value
        del _cache[key]
    return None


def _set_cache(key: str, value: Any) -> None:
    """Store value in cache with current timestamp."""
    _cache[key] = (value, datetime.now().timestamp())


async def search_pools(
    query: str,
    network: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for pools on DEXs by token name, symbol, or address.

    Args:
        query: Search term (token name, symbol, or contract address)
        network: Optional network ID to filter (e.g., 'eth', 'bsc', 'sol')
        limit: Maximum number of results to return (default: 10, max: 50)

    Returns:
        JSON string with search results including pool addresses, tokens, and basic data
    """
    try:
        params = {
            "query": query,
            "limit": min(limit, 50),
        }
        if network:
            params["network"] = network

        cache_key = f"search_pools:{query}:{network}:{limit}"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/networks/pools/search",
                params=params,
                headers={"Accept": "application/json;version=20230203"}
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "GeckoTerminal",
                "query": query,
                "network": network,
                "timestamp": datetime.now().isoformat(),
                "count": len(data.get("data", [])),
                "pools": data.get("data", [])
            }

            _set_cache(cache_key, result)
            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return json.dumps({
                "error": "Rate limit exceeded. Please wait before making more requests.",
                "source": "GeckoTerminal",
                "retry_after": "60 seconds"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "GeckoTerminal"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "GeckoTerminal"
        })


async def get_pool_data(
    network: str,
    pool_address: str
) -> str:
    """
    Get detailed information about a specific pool.

    Args:
        network: Network ID (e.g., 'eth', 'bsc', 'sol', 'polygon')
        pool_address: Pool contract address

    Returns:
        JSON string with pool details including price, liquidity, volume, and token info
    """
    try:
        cache_key = f"pool_data:{network}:{pool_address}"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/networks/{network}/pools/{pool_address}",
                headers={"Accept": "application/json;version=20230203"}
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "GeckoTerminal",
                "network": network,
                "pool_address": pool_address,
                "timestamp": datetime.now().isoformat(),
                "data": data.get("data", {})
            }

            _set_cache(cache_key, result)
            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return json.dumps({
                "error": "Pool not found. Verify network and pool address.",
                "source": "GeckoTerminal",
                "network": network,
                "pool_address": pool_address
            })
        if e.response.status_code == 429:
            return json.dumps({
                "error": "Rate limit exceeded. Please wait before making more requests.",
                "source": "GeckoTerminal"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "GeckoTerminal"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "GeckoTerminal"
        })


async def get_pool_ohlcv(
    network: str,
    pool_address: str,
    timeframe: str = "hour",
    aggregate: int = 1,
    limit: int = 100
) -> str:
    """
    Get OHLCV (Open, High, Low, Close, Volume) candlestick data for a pool.

    Args:
        network: Network ID (e.g., 'eth', 'bsc', 'sol')
        pool_address: Pool contract address
        timeframe: Time interval (e.g., 'minute', 'hour', 'day', 'week')
        aggregate: Number of intervals to aggregate (default: 1)
        limit: Number of candles to return (default: 100, max: 1000)

    Returns:
        JSON string with OHLCV data for price analysis
    """
    try:
        params = {
            "timeframe": timeframe,
            "aggregate": aggregate,
            "limit": min(limit, 1000)
        }

        cache_key = f"pool_ohlcv:{network}:{pool_address}:{timeframe}:{aggregate}:{limit}"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}",
                params=params,
                headers={"Accept": "application/json;version=20230203"}
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "GeckoTerminal",
                "network": network,
                "pool_address": pool_address,
                "timeframe": timeframe,
                "aggregate": aggregate,
                "timestamp": datetime.now().isoformat(),
                "count": len(data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])),
                "ohlcv": data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
            }

            _set_cache(cache_key, result)
            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return json.dumps({
                "error": "Pool or OHLCV data not found.",
                "source": "GeckoTerminal"
            })
        if e.response.status_code == 429:
            return json.dumps({
                "error": "Rate limit exceeded. Please wait before making more requests.",
                "source": "GeckoTerminal"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "GeckoTerminal"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "GeckoTerminal"
        })


async def get_trending_pools(
    network: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Get trending pools on DEXs.

    Args:
        network: Optional network ID to filter (e.g., 'eth', 'bsc', 'sol')
        limit: Maximum number of results to return (default: 20, max: 50)

    Returns:
        JSON string with trending pools and their basic metrics
    """
    try:
        cache_key = f"trending_pools:{network}:{limit}"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

        params = {"limit": min(limit, 50)}
        if network:
            params["network"] = network

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{BASE_URL}/networks/trending_pools",
                params=params,
                headers={"Accept": "application/json;version=20230203"}
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "source": "GeckoTerminal",
                "network": network,
                "timestamp": datetime.now().isoformat(),
                "count": len(data.get("data", [])),
                "pools": data.get("data", [])
            }

            _set_cache(cache_key, result)
            return str(result)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return json.dumps({
                "error": "Rate limit exceeded. Please wait before making more requests.",
                "source": "GeckoTerminal"
            })
        return json.dumps({
            "error": f"HTTP error {e.response.status_code}",
            "source": "GeckoTerminal"
        })
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": "GeckoTerminal"
        })
