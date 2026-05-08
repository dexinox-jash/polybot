"""
Polymarket Exchange Module for Live Trading.

This module provides authenticated access to Polymarket's CTF (Conditional Tokens Framework)
trading API, enabling:

- Account management (balance, positions, orders)
- Order placement and cancellation
- Market data retrieval
- Position tracking

Example:
    >>> from polymarket_tracker.exchange import PolymarketClient
    >>> client = PolymarketClient(api_key="key", api_secret="secret")
    >>> balance = client.get_balance()
    >>> print(f"Available: ${balance.usdc_available:.2f}")
"""

from .polymarket_client import (
    PolymarketClient,
    Order,
    Position,
    Balance,
    OrderSide,
    OrderStatus,
    PolymarketAPIError,
    PolymarketAuthError,
    PolymarketRateLimitError,
    PolymarketValidationError,
    create_client_from_env,
    POLYMARKET_API_BASE,
    POLYMARKET_CTF_BASE,
)

__all__ = [
    "PolymarketClient",
    "Order",
    "Position", 
    "Balance",
    "OrderSide",
    "OrderStatus",
    "PolymarketAPIError",
    "PolymarketAuthError",
    "PolymarketRateLimitError",
    "PolymarketValidationError",
    "create_client_from_env",
    "POLYMARKET_API_BASE",
    "POLYMARKET_CTF_BASE",
]
