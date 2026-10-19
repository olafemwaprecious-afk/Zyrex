"""
Diagnostics Tool

Provides status information about configured market-data integrations.
Does not expose secrets, API keys, or internal configuration.
"""

import json
import httpx
from datetime import datetime


async def check_tool_status() -> str:
    """
    Check the operational status of all configured market-data integrations.

    Returns:
        JSON string with status of each integration without exposing secrets
    """
    status_checks = {
        "timestamp": datetime.now().isoformat(),
        "integrations": {}
    }

    # Check GeckoTerminal API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.geckoterminal.com/api/v2/networks",
                headers={"Accept": "application/json;version=20230203"}
            )
            if response.status_code == 200:
                status_checks["integrations"]["geckoterminal"] = {
                    "status": "operational",
                    "endpoint": "https://api.geckoterminal.com/api/v2",
                    "rate_limit": "~30 calls/minute (public API)",
                    "authentication": "not required for public endpoints"
                }
            else:
                status_checks["integrations"]["geckoterminal"] = {
                    "status": "error",
                    "http_status": response.status_code
                }
    except Exception as e:
        status_checks["integrations"]["geckoterminal"] = {
            "status": "unreachable",
            "error": str(e)
        }

    # Check Binance public API
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://data-api.binance.vision/api/v3/ping")
            if response.status_code == 200:
                status_checks["integrations"]["binance"] = {
                    "status": "operational",
                    "endpoint": "https://data-api.binance.vision",
                    "authentication": "not required for public market data endpoints"
                }
            else:
                status_checks["integrations"]["binance"] = {
                    "status": "error",
                    "http_status": response.status_code
                }
    except Exception as e:
        status_checks["integrations"]["binance"] = {
            "status": "unreachable",
            "error": str(e)
        }

    # Local tools (always operational)
    status_checks["integrations"]["risk_checker"] = {
        "status": "operational",
        "type": "local deterministic calculation"
    }

    status_checks["integrations"]["market_comparison"] = {
        "status": "operational",
        "type": "local data processing"
    }

    return json.dumps(status_checks)
