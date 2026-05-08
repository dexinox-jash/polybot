"""
PolyBot Notification Manager

Unified notification system supporting Discord webhooks and Telegram bots.
Provides rate-limited, async notifications for trading signals, position updates,
and system alerts.

Environment Variables:
    DISCORD_WEBHOOK_URL: Discord webhook URL for notifications
    TELEGRAM_BOT_TOKEN: Telegram bot token
    TELEGRAM_CHAT_ID: Default Telegram chat ID
    NOTIFICATION_RATE_LIMIT: Max notifications per minute (default: 30)
    NOTIFICATION_COOLDOWN_SECONDS: Cooldown between same-type notifications (default: 60)
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Union
from collections import defaultdict
import aiohttp

# Configure logging
logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications for categorization and rate limiting."""
    HIGH_EV_OPPORTUNITY = "high_ev"
    TRADE_EXECUTED = "trade_executed"
    POSITION_UPDATE = "position_update"
    STOP_LOSS_HIT = "stop_loss"
    TAKE_PROFIT_HIT = "take_profit"
    ERROR = "error"
    SYSTEM_ALERT = "system_alert"
    DAILY_SUMMARY = "daily_summary"
    WHALE_ACTIVITY = "whale_activity"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""
    # Discord settings
    discord_webhook_url: Optional[str] = None
    discord_username: str = "PolyBot"
    discord_avatar_url: Optional[str] = None
    
    # Telegram settings
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_parse_mode: str = "HTML"
    
    # Rate limiting
    rate_limit_per_minute: int = 30
    cooldown_seconds: int = 60
    
    # Notification toggles
    enable_discord: bool = True
    enable_telegram: bool = True
    enable_console: bool = True
    
    # Type-specific settings
    min_ev_threshold: float = 0.05  # Minimum EV to notify (5%)
    min_whale_usd: float = 5000.0   # Minimum whale trade to notify
    
    @classmethod
    def from_env(cls) -> "NotificationConfig":
        """Create configuration from environment variables."""
        return cls(
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
            discord_username=os.getenv("DISCORD_USERNAME", "PolyBot"),
            discord_avatar_url=os.getenv("DISCORD_AVATAR_URL"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            telegram_parse_mode=os.getenv("TELEGRAM_PARSE_MODE", "HTML"),
            rate_limit_per_minute=int(os.getenv("NOTIFICATION_RATE_LIMIT", "30")),
            cooldown_seconds=int(os.getenv("NOTIFICATION_COOLDOWN_SECONDS", "60")),
            enable_discord=os.getenv("ENABLE_DISCORD", "true").lower() == "true",
            enable_telegram=os.getenv("ENABLE_TELEGRAM", "true").lower() == "true",
            enable_console=os.getenv("ENABLE_CONSOLE_NOTIFICATIONS", "true").lower() == "true",
            min_ev_threshold=float(os.getenv("MIN_EV_THRESHOLD", "0.05")),
            min_whale_usd=float(os.getenv("MIN_WHALE_USD", "5000")),
        )


class RateLimiter:
    """Rate limiter for notifications to prevent spam."""
    
    def __init__(self, max_per_minute: int = 30, cooldown_seconds: int = 60):
        self.max_per_minute = max_per_minute
        self.cooldown_seconds = cooldown_seconds
        self.notifications: List[float] = []
        self.last_notification_time: Dict[NotificationType, float] = defaultdict(float)
        self._lock = asyncio.Lock()
    
    async def can_send(self, notif_type: NotificationType) -> bool:
        """Check if a notification can be sent based on rate limits."""
        async with self._lock:
            now = time.time()
            
            # Clean up old notifications (older than 1 minute)
            cutoff = now - 60
            self.notifications = [t for t in self.notifications if t > cutoff]
            
            # Check global rate limit
            if len(self.notifications) >= self.max_per_minute:
                logger.debug(f"Global rate limit reached: {len(self.notifications)}/{self.max_per_minute}")
                return False
            
            # Check per-type cooldown
            last_time = self.last_notification_time[notif_type]
            if now - last_time < self.cooldown_seconds:
                logger.debug(f"Cooldown active for {notif_type.value}: {now - last_time:.1f}s < {self.cooldown_seconds}s")
                return False
            
            return True
    
    async def record_sent(self, notif_type: NotificationType) -> None:
        """Record that a notification was sent."""
        async with self._lock:
            now = time.time()
            self.notifications.append(now)
            self.last_notification_time[notif_type] = now


class NotificationManager:
    """
    Unified notification manager for PolyBot.
    
    Supports Discord webhooks and Telegram bot API with rate limiting,
    async operations, and formatted messages with emojis.
    
    Example:
        manager = NotificationManager()
        await manager.notify_trade_executed({
            "market": "BTC 5-Minute",
            "side": "YES",
            "size": 100,
            "entry_price": 0.52
        })
    """
    
    # Emoji mappings for different notification types
    EMOJIS = {
        NotificationType.HIGH_EV_OPPORTUNITY: "🎯",
        NotificationType.TRADE_EXECUTED: "✅",
        NotificationType.POSITION_UPDATE: "📊",
        NotificationType.STOP_LOSS_HIT: "🛑",
        NotificationType.TAKE_PROFIT_HIT: "💰",
        NotificationType.ERROR: "⚠️",
        NotificationType.SYSTEM_ALERT: "🔔",
        NotificationType.DAILY_SUMMARY: "📈",
        NotificationType.WHALE_ACTIVITY: "🐋",
        NotificationType.CIRCUIT_BREAKER: "⛔",
    }
    
    # Color codes for Discord embeds
    COLORS = {
        NotificationType.HIGH_EV_OPPORTUNITY: 0x00FF00,  # Green
        NotificationType.TRADE_EXECUTED: 0x3498db,       # Blue
        NotificationType.POSITION_UPDATE: 0x9b59b6,      # Purple
        NotificationType.STOP_LOSS_HIT: 0xe74c3c,        # Red
        NotificationType.TAKE_PROFIT_HIT: 0xf1c40f,      # Yellow
        NotificationType.ERROR: 0xe74c3c,                # Red
        NotificationType.SYSTEM_ALERT: 0x95a5a6,         # Gray
        NotificationType.DAILY_SUMMARY: 0x1abc9c,        # Teal
        NotificationType.WHALE_ACTIVITY: 0xe67e22,       # Orange
        NotificationType.CIRCUIT_BREAKER: 0x000000,      # Black
    }
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        """
        Initialize the notification manager.
        
        Args:
            config: Notification configuration. If None, loads from environment.
        """
        self.config = config or NotificationConfig.from_env()
        self.rate_limiter = RateLimiter(
            max_per_minute=self.config.rate_limit_per_minute,
            cooldown_seconds=self.config.cooldown_seconds
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            )
        return self._session
    
    async def close(self) -> None:
        """Close the notification manager and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._get_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    # ==================== Core Send Methods ====================
    
    async def send_discord(
        self,
        message: str,
        webhook_url: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
        notif_type: NotificationType = NotificationType.SYSTEM_ALERT
    ) -> bool:
        """
        Send a notification via Discord webhook.
        
        Args:
            message: Plain text message (used if no embed)
            webhook_url: Discord webhook URL (uses config if not provided)
            embed: Optional Discord embed dictionary
            notif_type: Type of notification for formatting
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.enable_discord:
            return False
        
        webhook_url = webhook_url or self.config.discord_webhook_url
        if not webhook_url:
            logger.warning("Discord webhook URL not configured")
            return False
        
        try:
            payload = {
                "username": self.config.discord_username,
                "content": message if not embed else None,
            }
            
            if self.config.discord_avatar_url:
                payload["avatar_url"] = self.config.discord_avatar_url
            
            if embed:
                payload["embeds"] = [embed]
            
            session = await self._get_session()
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 204:
                    logger.debug(f"Discord notification sent: {notif_type.value}")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"Discord webhook failed: {response.status} - {text}")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("Discord webhook timeout")
            return False
        except Exception as e:
            logger.error(f"Discord webhook error: {e}")
            return False
    
    async def send_telegram(
        self,
        message: str,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        notif_type: NotificationType = NotificationType.SYSTEM_ALERT
    ) -> bool:
        """
        Send a notification via Telegram bot.
        
        Args:
            message: Message text (supports HTML formatting)
            bot_token: Telegram bot token (uses config if not provided)
            chat_id: Telegram chat ID (uses config if not provided)
            parse_mode: Message parse mode (HTML, Markdown, etc.)
            notif_type: Type of notification for logging
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.enable_telegram:
            return False
        
        bot_token = bot_token or self.config.telegram_bot_token
        chat_id = chat_id or self.config.telegram_chat_id
        
        if not bot_token or not chat_id:
            logger.warning("Telegram bot token or chat ID not configured")
            return False
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        try:
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            
            session = await self._get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.debug(f"Telegram notification sent: {notif_type.value}")
                    return True
                else:
                    text = await response.text()
                    logger.error(f"Telegram API failed: {response.status} - {text}")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("Telegram API timeout")
            return False
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return False
    
    async def _send_all_channels(
        self,
        notif_type: NotificationType,
        discord_message: Optional[str] = None,
        discord_embed: Optional[Dict[str, Any]] = None,
        telegram_message: Optional[str] = None,
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Send notification to all configured channels.
        
        Args:
            notif_type: Type of notification
            discord_message: Plain text for Discord
            discord_embed: Rich embed for Discord
            telegram_message: HTML-formatted message for Telegram
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        results = {"discord": False, "telegram": False, "console": False}
        
        # Check rate limits
        if not bypass_rate_limit and not await self.rate_limiter.can_send(notif_type):
            logger.debug(f"Notification rate limited: {notif_type.value}")
            return results
        
        # Send to Discord
        if self.config.enable_discord and (discord_message or discord_embed):
            results["discord"] = await self.send_discord(
                message=discord_message or "",
                embed=discord_embed,
                notif_type=notif_type
            )
        
        # Send to Telegram
        if self.config.enable_telegram and telegram_message:
            results["telegram"] = await self.send_telegram(
                message=telegram_message,
                notif_type=notif_type
            )
        
        # Console output
        if self.config.enable_console:
            emoji = self.EMOJIS.get(notif_type, "📢")
            console_msg = f"{emoji} [{notif_type.value.upper()}] {discord_message or telegram_message or ''}"
            # Truncate for console
            if len(console_msg) > 200:
                console_msg = console_msg[:200] + "..."
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {console_msg}")
            results["console"] = True
        
        # Record sent notification
        if any(results.values()):
            await self.rate_limiter.record_sent(notif_type)
        
        return results
    
    # ==================== Notification Helpers ====================
    
    def _format_currency(self, value: float) -> str:
        """Format a value as currency."""
        if abs(value) >= 1000:
            return f"${value:,.2f}"
        return f"${value:.2f}"
    
    def _format_percentage(self, value: float) -> str:
        """Format a value as percentage with sign."""
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    
    def _create_discord_embed(
        self,
        notif_type: NotificationType,
        title: str,
        description: str,
        fields: List[Dict[str, Any]] = None,
        footer: Optional[str] = None,
        timestamp: bool = True
    ) -> Dict[str, Any]:
        """Create a Discord embed dictionary."""
        embed = {
            "title": f"{self.EMOJIS.get(notif_type, '📢')} {title}",
            "description": description,
            "color": self.COLORS.get(notif_type, 0x95a5a6),
        }
        
        if fields:
            embed["fields"] = [
                {
                    "name": field.get("name", ""),
                    "value": str(field.get("value", "")),
                    "inline": field.get("inline", True)
                }
                for field in fields
            ]
        
        if footer:
            embed["footer"] = {"text": footer}
        
        if timestamp:
            embed["timestamp"] = datetime.utcnow().isoformat()
        
        return embed
    
    # ==================== Specific Notification Methods ====================
    
    async def notify_trade_executed(
        self,
        position: Dict[str, Any],
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Notify when a trade is executed.
        
        Args:
            position: Dictionary with trade details:
                - market: Market name
                - side: YES/NO
                - size: Position size in USD
                - entry_price: Entry price (0-1)
                - expected_value: Optional EV
                - market_url: Optional market URL
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.TRADE_EXECUTED
        
        market = position.get("market", "Unknown")
        side = position.get("side", "UNKNOWN")
        size = position.get("size", 0)
        entry_price = position.get("entry_price", 0)
        ev = position.get("expected_value")
        market_url = position.get("market_url", "")
        
        # Side emoji
        side_emoji = "🟢" if side.upper() == "YES" else "🔴"
        
        # Discord embed
        fields = [
            {"name": "Market", "value": market, "inline": False},
            {"name": "Side", "value": f"{side_emoji} {side.upper()}", "inline": True},
            {"name": "Size", "value": self._format_currency(size), "inline": True},
            {"name": "Entry Price", "value": f"{entry_price:.1%}", "inline": True},
        ]
        
        if ev is not None:
            fields.append({"name": "Expected Value", "value": f"{ev:.2%}", "inline": True})
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="Trade Executed",
            description=f"Copy trade executed successfully{f' [{market}]({market_url})' if market_url else ''}",
            fields=fields,
            footer="PolyBot Trade Execution"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>✅ Trade Executed</b>

<b>Market:</b> {market}
<b>Side:</b> {side_emoji} {side.upper()}
<b>Size:</b> {self._format_currency(size)}
<b>Entry:</b> {entry_price:.1%}
{f'<b>EV:</b> {ev:.2%}' if ev else ''}
{f'<a href="{market_url}">View Market</a>' if market_url else ''}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_high_ev_opportunity(
        self,
        signal: Dict[str, Any],
        ev: float,
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Alert when a high EV opportunity is detected.
        
        Args:
            signal: Dictionary with signal details:
                - market: Market name
                - side: Recommended side (YES/NO)
                - confidence: Confidence score (0-1)
                - current_price: Current market price
                - target_price: Target price
                - market_url: Optional market URL
            ev: Expected value as decimal (e.g., 0.15 for 15%)
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.HIGH_EV_OPPORTUNITY
        
        # Skip if below threshold
        if ev < self.config.min_ev_threshold:
            logger.debug(f"EV {ev:.2%} below threshold {self.config.min_ev_threshold:.2%}")
            return {"discord": False, "telegram": False, "console": False}
        
        market = signal.get("market", "Unknown")
        side = signal.get("side", "UNKNOWN")
        confidence = signal.get("confidence", 0)
        current_price = signal.get("current_price", 0)
        target_price = signal.get("target_price")
        market_url = signal.get("market_url", "")
        
        # Side emoji
        side_emoji = "🟢" if side.upper() == "YES" else "🔴"
        
        # Confidence level
        conf_emoji = "🔥" if confidence > 0.8 else "⭐" if confidence > 0.6 else "📊"
        
        # Discord embed
        fields = [
            {"name": "Market", "value": market, "inline": False},
            {"name": "Side", "value": f"{side_emoji} {side.upper()}", "inline": True},
            {"name": "Expected Value", "value": f"🎯 {ev:.2%}", "inline": True},
            {"name": "Confidence", "value": f"{conf_emoji} {confidence:.1%}", "inline": True},
            {"name": "Current Price", "value": f"{current_price:.1%}", "inline": True},
        ]
        
        if target_price:
            fields.append({"name": "Target", "value": f"{target_price:.1%}", "inline": True})
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="🎯 High-EV Opportunity Detected",
            description=f"Potential +EV trade detected{f' [{market}]({market_url})' if market_url else ''}",
            fields=fields,
            footer="PolyBot Signal Generator"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>🎯 High-EV Opportunity</b>

<b>Market:</b> {market}
<b>Side:</b> {side_emoji} {side.upper()}
<b>Expected Value:</b> 🎯 {ev:.2%}
<b>Confidence:</b> {conf_emoji} {confidence:.1%}
<b>Current:</b> {current_price:.1%}
{f'<b>Target:</b> {target_price:.1%}' if target_price else ''}
{f'<a href="{market_url}">View Market</a>' if market_url else ''}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_position_update(
        self,
        position: Dict[str, Any],
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Notify about position updates (P&L changes, stops, take profits).
        
        Args:
            position: Dictionary with position details:
                - market: Market name
                - side: YES/NO
                - size: Position size
                - entry_price: Entry price
                - current_price: Current price
                - pnl: P&L in USD
                - pnl_percent: P&L percentage
                - status: open/closed/partial
                - exit_reason: Optional (stop_loss, take_profit, manual)
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        market = position.get("market", "Unknown")
        pnl = position.get("pnl", 0)
        pnl_pct = position.get("pnl_percent", 0)
        status = position.get("status", "open")
        exit_reason = position.get("exit_reason")
        
        # Determine notification type based on exit reason
        if exit_reason == "stop_loss":
            notif_type = NotificationType.STOP_LOSS_HIT
        elif exit_reason == "take_profit":
            notif_type = NotificationType.TAKE_PROFIT_HIT
        else:
            notif_type = NotificationType.POSITION_UPDATE
        
        # P&L formatting
        pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
        
        # Discord embed
        fields = [
            {"name": "Market", "value": market, "inline": False},
            {"name": "Status", "value": status.upper(), "inline": True},
            {"name": "P&L", "value": f"{pnl_emoji} {self._format_currency(pnl)}", "inline": True},
            {"name": "Return", "value": f"{self._format_percentage(pnl_pct)}", "inline": True},
        ]
        
        if exit_reason:
            fields.append({"name": "Exit Reason", "value": exit_reason.replace("_", " ").title(), "inline": True})
        
        title = "Position Update"
        if exit_reason == "stop_loss":
            title = "🛑 Stop Loss Triggered"
        elif exit_reason == "take_profit":
            title = "💰 Take Profit Hit"
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title=title,
            description=f"Position update for {market}",
            fields=fields,
            footer="PolyBot Position Manager"
        )
        
        # Telegram message
        status_line = f"<b>{'🛑 STOP LOSS' if exit_reason == 'stop_loss' else '💰 TAKE PROFIT' if exit_reason == 'take_profit' else '📊 Position Update'}</b>"
        telegram_msg = f"""
{status_line}

<b>Market:</b> {market}
<b>Status:</b> {status.upper()}
<b>P&L:</b> {pnl_emoji} {self._format_currency(pnl)} ({self._format_percentage(pnl_pct)})
{f'<b>Exit:</b> {exit_reason.replace("_", " ").title()}' if exit_reason else ''}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_daily_summary(
        self,
        stats: Dict[str, Any],
        bypass_rate_limit: bool = True
    ) -> Dict[str, bool]:
        """
        Send daily performance summary.
        
        Args:
            stats: Dictionary with daily statistics:
                - date: Date string
                - total_trades: Number of trades
                - winning_trades: Number of winners
                - losing_trades: Number of losers
                - total_pnl: Total P&L
                - win_rate: Win rate percentage
                - avg_trade: Average trade return
                - largest_win: Largest winner
                - largest_loss: Largest loser
            bypass_rate_limit: If True, skip rate limit check (default for summaries)
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.DAILY_SUMMARY
        
        date = stats.get("date", datetime.now().strftime("%Y-%m-%d"))
        total_trades = stats.get("total_trades", 0)
        total_pnl = stats.get("total_pnl", 0)
        win_rate = stats.get("win_rate", 0)
        avg_trade = stats.get("avg_trade", 0)
        
        pnl_emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
        
        # Discord embed
        fields = [
            {"name": "📅 Date", "value": date, "inline": True},
            {"name": "🔄 Total Trades", "value": str(total_trades), "inline": True},
            {"name": "💰 Total P&L", "value": f"{pnl_emoji} {self._format_currency(total_pnl)}", "inline": True},
            {"name": "📈 Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
            {"name": "📊 Avg Trade", "value": f"{avg_trade:+.2f}%", "inline": True},
        ]
        
        if "largest_win" in stats:
            fields.append({"name": "🏆 Largest Win", "value": self._format_currency(stats["largest_win"]), "inline": True})
        if "largest_loss" in stats:
            fields.append({"name": "💥 Largest Loss", "value": self._format_currency(stats["largest_loss"]), "inline": True})
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="📈 Daily Performance Summary",
            description=f"Trading performance for {date}",
            fields=fields,
            footer="PolyBot Daily Report"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>📈 Daily Summary - {date}</b>

<b>Total Trades:</b> {total_trades}
<b>Total P&L:</b> {pnl_emoji} {self._format_currency(total_pnl)}
<b>Win Rate:</b> {win_rate:.1f}%
<b>Avg Trade:</b> {avg_trade:+.2f}%
{f'<b>🏆 Largest Win:</b> {self._format_currency(stats["largest_win"])}' if 'largest_win' in stats else ''}
{f'<b>💥 Largest Loss:</b> {self._format_currency(stats["largest_loss"])}' if 'largest_loss' in stats else ''}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_error(
        self,
        error_message: str,
        error_details: Optional[str] = None,
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Send error notification.
        
        Args:
            error_message: Short error description
            error_details: Optional detailed error information
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.ERROR
        
        # Discord embed
        fields = [
            {"name": "Error", "value": error_message, "inline": False},
        ]
        
        if error_details:
            # Truncate for Discord
            truncated = error_details[:1000] + "..." if len(error_details) > 1000 else error_details
            fields.append({"name": "Details", "value": f"```{truncated}```", "inline": False})
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="⚠️ System Error",
            description="An error occurred in PolyBot",
            fields=fields,
            footer="PolyBot Error Handler"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>⚠️ System Error</b>

<b>Error:</b> {error_message}
{f'<b>Details:</b> <pre>{error_details[:500]}</pre>' if error_details else ''}

<i>Check logs for more information.</i>
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_circuit_breaker(
        self,
        reason: str,
        details: Optional[Dict[str, Any]] = None,
        bypass_rate_limit: bool = True
    ) -> Dict[str, bool]:
        """
        Notify when circuit breaker is triggered.
        
        Args:
            reason: Reason for circuit breaker (e.g., "Max drawdown exceeded")
            details: Optional dictionary with additional details
            bypass_rate_limit: If True, skip rate limit check (default for circuit breakers)
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.CIRCUIT_BREAKER
        
        details = details or {}
        
        # Discord embed
        fields = [
            {"name": "Reason", "value": reason, "inline": False},
        ]
        
        for key, value in details.items():
            fields.append({"name": key.replace("_", " ").title(), "value": str(value), "inline": True})
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="⛔ Circuit Breaker Triggered",
            description="Trading has been halted due to risk limits",
            fields=fields,
            footer="PolyBot Risk Manager"
        )
        
        # Telegram message
        details_str = "\n".join([f"<b>{k.replace('_', ' ').title()}:</b> {v}" for k, v in details.items()])
        telegram_msg = f"""
<b>⛔ CIRCUIT BREAKER TRIGGERED</b>

<b>Reason:</b> {reason}

{details_str}

<i>Trading halted. Manual intervention required.</i>
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_whale_activity(
        self,
        whale_data: Dict[str, Any],
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Notify about notable whale activity.
        
        Args:
            whale_data: Dictionary with whale trade details:
                - trader: Trader identifier/name
                - market: Market name
                - side: YES/NO
                - size: Trade size in USD
                - price: Trade price
                - timestamp: Trade time
                - wallet_url: Optional wallet explorer URL
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.WHALE_ACTIVITY
        
        trader = whale_data.get("trader", "Unknown")
        market = whale_data.get("market", "Unknown")
        side = whale_data.get("side", "UNKNOWN")
        size = whale_data.get("size", 0)
        price = whale_data.get("price", 0)
        wallet_url = whale_data.get("wallet_url", "")
        
        # Skip if below threshold
        if size < self.config.min_whale_usd:
            logger.debug(f"Whale trade ${size:,.0f} below threshold ${self.config.min_whale_usd:,.0f}")
            return {"discord": False, "telegram": False, "console": False}
        
        # Side emoji
        side_emoji = "🟢" if side.upper() == "YES" else "🔴"
        
        # Discord embed
        fields = [
            {"name": "🐋 Trader", "value": f"`{trader[:20]}...`" if len(trader) > 20 else f"`{trader}`", "inline": False},
            {"name": "Market", "value": market, "inline": True},
            {"name": "Side", "value": f"{side_emoji} {side.upper()}", "inline": True},
            {"name": "Size", "value": self._format_currency(size), "inline": True},
            {"name": "Price", "value": f"{price:.1%}", "inline": True},
        ]
        
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title="🐋 Whale Activity Detected",
            description=f"Large trade from tracked whale{f' [View Wallet]({wallet_url})' if wallet_url else ''}",
            fields=fields,
            footer="PolyBot Whale Tracker"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>🐋 Whale Activity</b>

<b>Trader:</b> <code>{trader[:30]}{'...' if len(trader) > 30 else ''}</code>
<b>Market:</b> {market}
<b>Side:</b> {side_emoji} {side.upper()}
<b>Size:</b> 🐋 {self._format_currency(size)}
<b>Price:</b> {price:.1%}
{f'<a href="{wallet_url}">View Wallet</a>' if wallet_url else ''}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )
    
    async def notify_system_alert(
        self,
        title: str,
        message: str,
        alert_type: str = "info",
        bypass_rate_limit: bool = False
    ) -> Dict[str, bool]:
        """
        Send general system alert.
        
        Args:
            title: Alert title
            message: Alert message
            alert_type: Alert type (info, warning, critical)
            bypass_rate_limit: If True, skip rate limit check
            
        Returns:
            Dictionary with success status for each channel
        """
        notif_type = NotificationType.SYSTEM_ALERT
        
        type_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert_type, "🔔")
        
        # Discord embed
        discord_embed = self._create_discord_embed(
            notif_type=notif_type,
            title=f"{type_emoji} {title}",
            description=message,
            footer="PolyBot System Alert"
        )
        
        # Telegram message
        telegram_msg = f"""
<b>{type_emoji} {title}</b>

{message}
""".strip()
        
        return await self._send_all_channels(
            notif_type=notif_type,
            discord_embed=discord_embed,
            telegram_message=telegram_msg,
            bypass_rate_limit=bypass_rate_limit
        )


# ==================== Synchronous Wrapper ====================

class SyncNotificationManager:
    """
    Synchronous wrapper for NotificationManager for use in non-async contexts.
    
    Example:
        manager = SyncNotificationManager()
        manager.notify_trade_executed(position)
    """
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self._config = config
        self._manager: Optional[NotificationManager] = None
    
    def _get_manager(self) -> NotificationManager:
        if self._manager is None:
            self._manager = NotificationManager(self._config)
        return self._manager
    
    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If in running loop, schedule and wait
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(coro)
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create new one
            return asyncio.run(coro)
    
    def send_discord(self, message: str, webhook_url: Optional[str] = None) -> bool:
        """Send Discord notification (sync)."""
        manager = self._get_manager()
        result = self._run_async(manager.send_discord(message, webhook_url))
        return result
    
    def send_telegram(self, message: str, bot_token: Optional[str] = None, chat_id: Optional[str] = None) -> bool:
        """Send Telegram notification (sync)."""
        manager = self._get_manager()
        result = self._run_async(manager.send_telegram(message, bot_token, chat_id))
        return result
    
    def notify_trade_executed(self, position: Dict[str, Any]) -> Dict[str, bool]:
        """Notify trade execution (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_trade_executed(position))
    
    def notify_high_ev_opportunity(self, signal: Dict[str, Any], ev: float) -> Dict[str, bool]:
        """Notify high EV opportunity (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_high_ev_opportunity(signal, ev))
    
    def notify_position_update(self, position: Dict[str, Any]) -> Dict[str, bool]:
        """Notify position update (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_position_update(position))
    
    def notify_daily_summary(self, stats: Dict[str, Any]) -> Dict[str, bool]:
        """Notify daily summary (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_daily_summary(stats))
    
    def notify_error(self, error_message: str, error_details: Optional[str] = None) -> Dict[str, bool]:
        """Notify error (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_error(error_message, error_details))
    
    def notify_circuit_breaker(self, reason: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """Notify circuit breaker (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_circuit_breaker(reason, details))
    
    def notify_whale_activity(self, whale_data: Dict[str, Any]) -> Dict[str, bool]:
        """Notify whale activity (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_whale_activity(whale_data))
    
    def notify_system_alert(self, title: str, message: str, alert_type: str = "info") -> Dict[str, bool]:
        """Notify system alert (sync)."""
        manager = self._get_manager()
        return self._run_async(manager.notify_system_alert(title, message, alert_type))
    
    def close(self):
        """Close the manager."""
        if self._manager:
            self._run_async(self._manager.close())


# ==================== Helper Functions ====================

def create_sample_config() -> str:
    """Create a sample environment configuration file content."""
    return """
# PolyBot Notification Configuration

# Discord Webhook
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
DISCORD_USERNAME=PolyBot
DISCORD_AVATAR_URL=

# Telegram Bot
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
TELEGRAM_PARSE_MODE=HTML

# Rate Limiting
NOTIFICATION_RATE_LIMIT=30
NOTIFICATION_COOLDOWN_SECONDS=60

# Feature Toggles
ENABLE_DISCORD=true
ENABLE_TELEGRAM=true
ENABLE_CONSOLE_NOTIFICATIONS=true

# Thresholds
MIN_EV_THRESHOLD=0.05
MIN_WHALE_USD=5000
""".strip()


# For testing
async def main():
    """Test the notification manager."""
    print("PolyBot Notification Manager Test")
    print("=" * 50)
    
    # Create config from env or use defaults for testing
    config = NotificationConfig.from_env()
    config.enable_console = True  # Always enable console for demo
    
    async with NotificationManager(config) as manager:
        # Test trade execution
        print("\n1. Testing Trade Execution Notification...")
        result = await manager.notify_trade_executed({
            "market": "BTC 5-Minute > $95k",
            "side": "YES",
            "size": 150.0,
            "entry_price": 0.52,
            "expected_value": 0.08,
            "market_url": "https://polymarket.com/market/btc-5min"
        })
        print(f"   Result: {result}")
        
        # Test high EV opportunity
        print("\n2. Testing High-EV Opportunity Notification...")
        result = await manager.notify_high_ev_opportunity({
            "market": "ETH 5-Minute > $3k",
            "side": "NO",
            "confidence": 0.72,
            "current_price": 0.65,
            "target_price": 0.55,
            "market_url": "https://polymarket.com/market/eth-5min"
        }, ev=0.12)
        print(f"   Result: {result}")
        
        # Test position update
        print("\n3. Testing Position Update Notification...")
        result = await manager.notify_position_update({
            "market": "BTC 5-Minute > $95k",
            "side": "YES",
            "size": 150.0,
            "entry_price": 0.52,
            "current_price": 0.58,
            "pnl": 9.0,
            "pnl_percent": 6.0,
            "status": "open"
        })
        print(f"   Result: {result}")
        
        # Test stop loss
        print("\n4. Testing Stop Loss Notification...")
        result = await manager.notify_position_update({
            "market": "ETH 5-Minute",
            "side": "NO",
            "size": 100.0,
            "entry_price": 0.65,
            "current_price": 0.72,
            "pnl": -7.0,
            "pnl_percent": -7.0,
            "status": "closed",
            "exit_reason": "stop_loss"
        })
        print(f"   Result: {result}")
        
        # Test daily summary
        print("\n5. Testing Daily Summary Notification...")
        result = await manager.notify_daily_summary({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_trades": 12,
            "winning_trades": 7,
            "losing_trades": 5,
            "total_pnl": 145.50,
            "win_rate": 58.3,
            "avg_trade": 1.2,
            "largest_win": 45.0,
            "largest_loss": -20.0
        })
        print(f"   Result: {result}")
        
        # Test error
        print("\n6. Testing Error Notification...")
        result = await manager.notify_error(
            error_message="API Connection Failed",
            error_details="Failed to connect to Polymarket API after 3 retries."
        )
        print(f"   Result: {result}")
        
        # Test circuit breaker
        print("\n7. Testing Circuit Breaker Notification...")
        result = await manager.notify_circuit_breaker(
            reason="Maximum daily loss exceeded",
            details={
                "daily_pnl": -500.0,
                "max_loss_limit": -400.0,
                "trades_today": 15
            }
        )
        print(f"   Result: {result}")
        
        # Test whale activity
        print("\n8. Testing Whale Activity Notification...")
        result = await manager.notify_whale_activity({
            "trader": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
            "market": "BTC 5-Minute > $95k",
            "side": "YES",
            "size": 15000.0,
            "price": 0.48,
            "wallet_url": "https://polygonscan.com/address/0x742d..."
        })
        print(f"   Result: {result}")
        
        # Test system alert
        print("\n9. Testing System Alert Notification...")
        result = await manager.notify_system_alert(
            title="Bot Started",
            message="PolyBot has successfully started and is now monitoring markets.",
            alert_type="info"
        )
        print(f"   Result: {result}")
        
        print("\n" + "=" * 50)
        print("All tests completed!")


if __name__ == "__main__":
    # Print sample config
    print("Sample .env configuration:")
    print("-" * 50)
    print(create_sample_config())
    print("-" * 50)
    print()
    
    # Run tests
    asyncio.run(main())
