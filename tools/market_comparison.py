"""
Market Data Comparison Tool

Compares market data from different sources and provides structured comparisons.
"""

import json
from typing import Optional, List, Dict, Any
from decimal import Decimal, InvalidOperation


def _parse_decimal(value: Any) -> Optional[Decimal]:
    """Safely parse a value to Decimal."""
    try:
        if value is None or value == "":
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def compare_pools(pool_data_list: List[Dict[str, Any]]) -> str:
    """
    Compare multiple pools from GeckoTerminal data.

    Args:
        pool_data_list: List of pool data dictionaries (as returned by GeckoTerminal tools)

    Returns:
        JSON string with structured comparison including liquidity, volume, and price metrics
    """
    if not pool_data_list:
        return json.dumps({
            "error": "No pool data provided for comparison",
            "source": "MarketComparison"
        })

    comparisons = []

    for pool in pool_data_list:
        try:
            attributes = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            # Extract basic info
            network_id = attributes.get("network_id", "unknown")
            address = attributes.get("address", "unknown")

            # Extract token info
            base_token = relationships.get("base_token", {}).get("data", {})
            quote_token = relationships.get("quote_token", {}).get("data", {})
            base_symbol = base_token.get("attributes", {}).get("symbol", "unknown")
            quote_symbol = quote_token.get("attributes", {}).get("symbol", "unknown")

            # Extract metrics
            price_usd = _parse_decimal(attributes.get("base_token_price_usd"))
            liquidity_usd = _parse_decimal(attributes.get("reserve_in_usd"))
            volume_24h = _parse_decimal(attributes.get("volume_usd", {}).get("h24"))

            comparison = {
                "network": network_id,
                "address": address,
                "pair": f"{base_symbol}/{quote_symbol}",
                "price_usd": str(price_usd) if price_usd else "unavailable",
                "liquidity_usd": str(liquidity_usd) if liquidity_usd else "unavailable",
                "volume_24h_usd": str(volume_24h) if volume_24h else "unavailable",
                "transactions_24h": attributes.get("transactions", {}).get("h24", "unavailable")
            }

            comparisons.append(comparison)

        except Exception as e:
            comparisons.append({
                "error": f"Failed to parse pool data: {str(e)}",
                "raw_data": pool
            })

    # Sort by liquidity if available
    try:
        comparisons.sort(
            key=lambda x: float(x.get("liquidity_usd", 0)) if x.get("liquidity_usd") != "unavailable" else 0,
            reverse=True
        )
    except (ValueError, TypeError):
        pass

    result = {
        "source": "MarketComparison",
        "comparison_type": "pools",
        "count": len(comparisons),
        "data": comparisons,
        "note": "Prices and metrics are for comparison only; do not imply safety or profitability"
    }

    return json.dumps(result)


def compare_tokens(token_data_list: List[Dict[str, Any]]) -> str:
    """
    Compare multiple tokens across different pools/markets.

    Args:
        token_data_list: List of token data from various sources

    Returns:
        JSON string with structured token comparison
    """
    if not token_data_list:
        return json.dumps({
            "error": "No token data provided for comparison",
            "source": "MarketComparison"
        })

    comparisons = []

    for token in token_data_list:
        try:
            # Handle different data structures
            if isinstance(token, dict):
                # GeckoTerminal-style data
                if "attributes" in token:
                    attributes = token["attributes"]
                    symbol = attributes.get("symbol", "unknown")
                    price_usd = _parse_decimal(attributes.get("price_usd"))
                    market_cap = _parse_decimal(attributes.get("market_cap_usd"))
                    volume_24h = _parse_decimal(attributes.get("volume_usd", {}).get("h24"))

                    comparison = {
                        "symbol": symbol,
                        "price_usd": str(price_usd) if price_usd else "unavailable",
                        "market_cap_usd": str(market_cap) if market_cap else "unavailable",
                        "volume_24h_usd": str(volume_24h) if volume_24h else "unavailable",
                        "source": token.get("source", "unknown")
                    }
                # CoinAPI-style data
                elif "asset_id_base" in token or "rate" in token:
                    comparison = {
                        "asset_id_base": token.get("asset_id_base"),
                        "asset_id_quote": token.get("asset_id_quote"),
                        "rate": token.get("rate"),
                        "source": token.get("source", "CoinAPI")
                    }
                # Legacy format (symbol in dict)
                elif "symbol" in token:
                    comparison = {
                        "symbol": token.get("symbol"),
                        "price": token.get("price", "unavailable"),
                        "source": token.get("source", "unknown")
                    }
                else:
                    comparison = {
                        "error": "Unrecognized token data format",
                        "raw_data": token
                    }
            else:
                comparison = {
                    "error": "Token data must be a dictionary",
                    "raw_data": str(token)
                }

            comparisons.append(comparison)

        except Exception as e:
            comparisons.append({
                "error": f"Failed to parse token data: {str(e)}",
                "raw_data": token
            })

    result = {
        "source": "MarketComparison",
        "comparison_type": "tokens",
        "count": len(comparisons),
        "data": comparisons,
        "note": "Compare only tokens on the same network or exchange. Cross-chain comparisons may not be meaningful."
    }

    return json.dumps(result)
