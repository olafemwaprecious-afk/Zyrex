"""
Risk Checking Engine

Deterministic trade validation and risk calculation tool.
Does not depend on external APIs or the language model for arithmetic.
"""

import json
from typing import Optional, Dict, Any
from decimal import Decimal, InvalidOperation


def _parse_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    """Safely parse a value to Decimal, returning None if invalid."""
    try:
        if value is None or value == "":
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def validate_trade_parameters(
    entry_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    position_size: Optional[float] = None,
    equity: Optional[float] = None,
    direction: Optional[str] = None
) -> str:
    """
    Validate trade parameters and check for logical consistency.

    Args:
        entry_price: Planned entry price
        stop_loss: Stop-loss price
        take_profit: Take-profit price
        position_size: Position size or quantity
        equity: Account equity (optional, for percentage-based risk)
        direction: Trade direction ('long' or 'short')

    Returns:
        JSON string with validation results and any errors found
    """
    errors = []
    warnings = []

    # Parse all values
    entry = _parse_decimal(entry_price, "entry_price")
    sl = _parse_decimal(stop_loss, "stop_loss")
    tp = _parse_decimal(take_profit, "take_profit")
    size = _parse_decimal(position_size, "position_size")
    acct_equity = _parse_decimal(equity, "equity")

    # Check for required fields
    if entry is None or entry <= 0:
        errors.append("Entry price must be a positive number")

    if sl is None or sl <= 0:
        errors.append("Stop-loss must be a positive number")

    if tp is None or tp <= 0:
        errors.append("Take-profit must be a positive number")

    # Check direction consistency
    if direction:
        direction = direction.lower()
        if direction not in ['long', 'short']:
            errors.append("Direction must be 'long' or 'short'")

        # Check price ordering based on direction
        if entry and sl and tp:
            if direction == 'long':
                if sl >= entry:
                    errors.append("For long trades, stop-loss must be below entry price")
                if tp <= entry:
                    errors.append("For long trades, take-profit must be above entry price")
            elif direction == 'short':
                if sl <= entry:
                    errors.append("For short trades, stop-loss must be above entry price")
                if tp >= entry:
                    errors.append("For short trades, take-profit must be below entry price")

    # Check position size
    if size is not None:
        if size <= 0:
            errors.append("Position size must be positive")
        elif size > 1000000:  # Reasonable upper bound
            warnings.append("Position size is unusually large")

    # Check equity
    if acct_equity is not None:
        if acct_equity <= 0:
            errors.append("Equity must be positive")

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "parameters": {
            "entry_price": str(entry) if entry else None,
            "stop_loss": str(sl) if sl else None,
            "take_profit": str(tp) if tp else None,
            "position_size": str(size) if size else None,
            "equity": str(acct_equity) if acct_equity else None,
            "direction": direction
        }
    }

    return json.dumps(result)


def evaluate_trade_risk(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    position_size: Optional[float] = None,
    equity: Optional[float] = None,
    direction: Optional[str] = None
) -> str:
    """
    Calculate risk metrics for a trade setup.

    Args:
        entry_price: Planned entry price
        stop_loss: Stop-loss price
        take_profit: Take-profit price
        position_size: Position size or quantity
        equity: Account equity (for percentage-based risk calculation)
        direction: Trade direction ('long' or 'short')

    Returns:
        JSON string with calculated risk metrics including:
        - Risk amount (price difference)
        - Risk percentage (if equity provided)
        - Reward amount (price difference)
        - Reward-to-risk ratio
    """
    # Parse values
    entry = _parse_decimal(entry_price, "entry_price")
    sl = _parse_decimal(stop_loss, "stop_loss")
    tp = _parse_decimal(take_profit, "take_profit")
    size = _parse_decimal(position_size, "position_size")
    acct_equity = _parse_decimal(equity, "equity")

    # Validate basic requirements
    if entry is None or entry <= 0:
        return json.dumps({
            "error": "Entry price must be a positive number",
            "source": "RiskChecker"
        })

    if sl is None or sl <= 0:
        return json.dumps({
            "error": "Stop-loss must be a positive number",
            "source": "RiskChecker"
        })

    if tp is None or tp <= 0:
        return json.dumps({
            "error": "Take-profit must be a positive number",
            "source": "RiskChecker"
        })

    # Calculate risk and reward amounts
    if direction and direction.lower() == 'short':
        risk_amount = sl - entry
        reward_amount = entry - tp
    else:
        # Default to long logic if direction not specified
        risk_amount = entry - sl
        reward_amount = tp - entry

    # Calculate percentage-based risk if equity provided
    risk_percentage = None
    if acct_equity and acct_equity > 0 and size:
        risk_value = risk_amount * size
        risk_percentage = (risk_value / acct_equity) * 100

    # Calculate reward-to-risk ratio
    rrr = None
    if risk_amount > 0:
        rrr = reward_amount / risk_amount

    result = {
        "source": "RiskChecker",
        "entry_price": str(entry),
        "stop_loss": str(sl),
        "take_profit": str(tp),
        "direction": direction.lower() if direction else "long (assumed)",
        "risk_amount": str(risk_amount),
        "reward_amount": str(reward_amount),
        "reward_to_risk_ratio": str(rrr) if rrr is not None else None,
        "risk_percentage": f"{risk_percentage:.2f}%" if risk_percentage is not None else None,
        "position_size": str(size) if size else None,
        "equity": str(acct_equity) if acct_equity else None,
        "note": "This is a calculation tool, not a trading recommendation"
    }

    return json.dumps(result)
