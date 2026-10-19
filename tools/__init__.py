"""
ZYREX AI Tools Module

This module contains all tools available to the Agno agent for market data,
risk checking, and diagnostics.
"""

from .geckoterminal import (
    search_pools,
    get_pool_data,
    get_pool_ohlcv,
    get_trending_pools,
)
from .binance import (
    get_ticker_price,
    get_24hr_ticker,
    get_klines,
)
from .risk_checker import (
    evaluate_trade_risk,
    validate_trade_parameters,
)
from .market_comparison import (
    compare_pools,
    compare_tokens,
)
from .diagnostics import (
    check_tool_status,
)

__all__ = [
    "search_pools",
    "get_pool_data",
    "get_pool_ohlcv",
    "get_trending_pools",
    "get_ticker_price",
    "get_24hr_ticker",
    "get_klines",
    "evaluate_trade_risk",
    "validate_trade_parameters",
    "compare_pools",
    "compare_tokens",
    "check_tool_status",
]
