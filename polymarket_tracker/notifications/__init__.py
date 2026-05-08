"""
PolyBot Notification System

Provides unified Discord and Telegram notification support for:
- High-EV opportunities
- Trade executions
- Position updates (P&L, stops, take profits)
- System alerts (errors, circuit breakers, daily summaries)
- Whale activity alerts

Usage:
    from polymarket_tracker.notifications import NotificationManager
    
    manager = NotificationManager()
    await manager.notify_trade_executed(position)
"""

from .notification_manager import (
    NotificationManager,
    NotificationConfig,
    NotificationType,
    RateLimiter,
)

__all__ = [
    "NotificationManager",
    "NotificationConfig", 
    "NotificationType",
    "RateLimiter",
]

__version__ = "1.0.0"
