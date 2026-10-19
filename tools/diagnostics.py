"""
Diagnostics Tool

Provides status information about configured market-data integrations.
Does not expose secrets, API keys, or internal configuration.
"""

import os
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
    except httpx.TimeoutException:
        status_checks["integrations"]["geckoterminal"] = {
            "status": "unreachable",
            "error": "Request timed out"
        }
    except httpx.RequestError:
        status_checks["integrations"]["geckoterminal"] = {
            "status": "unreachable",
            "error": "Provider could not be reached"
        }

    # Check CoinAPI
    coinapi_key = os.environ.get("COINAPI_KEY")
    if coinapi_key:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://rest.coinapi.io/v1/exchanges",
                    headers={"X-CoinAPI-Key": coinapi_key}
                )
                if response.status_code == 200:
                    status_checks["integrations"]["coinapi"] = {
                        "status": "operational",
                        "endpoint": "https://rest.coinapi.io/v1",
                        "authentication": "configured via COINAPI_KEY"
                    }
                elif response.status_code == 401:
                    status_checks["integrations"]["coinapi"] = {
                        "status": "authentication_error",
                        "error": "Credentials rejected"
                    }
                elif response.status_code == 403:
                    status_checks["integrations"]["coinapi"] = {
                        "status": "access_error",
                        "error": "Endpoint access is unavailable for this subscription"
                    }
                elif response.status_code == 429:
                    status_checks["integrations"]["coinapi"] = {
                        "status": "rate_limited",
                        "error": "Subscription rate limit reached"
                    }
                else:
                    status_checks["integrations"]["coinapi"] = {
                        "status": "error",
                        "http_status": response.status_code
                    }
        except httpx.TimeoutException:
            status_checks["integrations"]["coinapi"] = {
                "status": "unreachable",
                "error": "Request timed out"
            }
        except httpx.RequestError:
            status_checks["integrations"]["coinapi"] = {
                "status": "unreachable",
                "error": "Provider could not be reached"
            }
    else:
        status_checks["integrations"]["coinapi"] = {
            "status": "not_configured",
            "error": "COINAPI_KEY environment variable not set"
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
