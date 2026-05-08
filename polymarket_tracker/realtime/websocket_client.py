"""
High-Performance WebSocket Client for Polymarket CLOB (Central Limit Orderbook)

Provides TRUE real-time market data with millisecond latency.
Optimized for low-latency trading applications.

Reference: https://docs.polymarket.com/#websocket-api
"""

import asyncio
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from enum import Enum
from collections import defaultdict
import heapq

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from ..utils.logger import setup_logging

logger = setup_logging()


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PriceLevel:
    """Represents a price level in the orderbook."""
    price: float
    size: float
    orders: int = 0
    
    def __post_init__(self):
        self.price = float(self.price)
        self.size = float(self.size)
    
    def __hash__(self):
        return hash(self.price)
    
    def __eq__(self, other):
        if isinstance(other, PriceLevel):
            return self.price == other.price
        return self.price == other
    
    def __lt__(self, other):
        if isinstance(other, PriceLevel):
            return self.price < other.price
        return self.price < other
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'price': self.price,
            'size': self.size,
            'orders': self.orders,
        }


@dataclass
class OrderBookUpdate:
    """Orderbook update event with full or delta data."""
    market_id: str
    token_id: str
    bids: List[PriceLevel]
    asks: List[PriceLevel]
    timestamp: float
    sequence: int
    is_snapshot: bool = False
    
    # Derived metrics (calculated on-demand)
    _best_bid: Optional[PriceLevel] = field(default=None, repr=False)
    _best_ask: Optional[PriceLevel] = field(default=None, repr=False)
    
    def __post_init__(self):
        self.timestamp = float(self.timestamp)
        self.sequence = int(self.sequence)
        # Sort bids descending, asks ascending
        self.bids = sorted([b if isinstance(b, PriceLevel) else PriceLevel(**b) 
                           for b in self.bids], reverse=True)
        self.asks = sorted([a if isinstance(a, PriceLevel) else PriceLevel(**a) 
                           for a in self.asks])
    
    @property
    def best_bid(self) -> Optional[PriceLevel]:
        """Get best bid (highest price)."""
        if self._best_bid is None and self.bids:
            self._best_bid = self.bids[0]
        return self._best_bid
    
    @property
    def best_ask(self) -> Optional[PriceLevel]:
        """Get best ask (lowest price)."""
        if self._best_ask is None and self.asks:
            self._best_ask = self.asks[0]
        return self._best_ask
    
    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None
    
    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None
    
    @property
    def bid_depth(self) -> float:
        """Total bid size."""
        return sum(b.size for b in self.bids)
    
    @property
    def ask_depth(self) -> float:
        """Total ask size."""
        return sum(a.size for a in self.asks)
    
    @property
    def imbalance(self) -> Optional[float]:
        """Calculate orderbook imbalance (-1 to 1, positive = more bids)."""
        bid_d = self.bid_depth
        ask_d = self.ask_depth
        total = bid_d + ask_d
        if total > 0:
            return (bid_d - ask_d) / total
        return None
    
    def get_bid_depth_at(self, price_levels: int = 5) -> float:
        """Get bid depth for top N price levels."""
        return sum(b.size for b in self.bids[:price_levels])
    
    def get_ask_depth_at(self, price_levels: int = 5) -> float:
        """Get ask depth for top N price levels."""
        return sum(a.size for a in self.asks[:price_levels])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'market_id': self.market_id,
            'token_id': self.token_id,
            'bids': [b.to_dict() for b in self.bids],
            'asks': [a.to_dict() for a in self.asks],
            'timestamp': self.timestamp,
            'sequence': self.sequence,
            'is_snapshot': self.is_snapshot,
            'spread': self.spread,
            'mid_price': self.mid_price,
            'imbalance': self.imbalance,
        }


@dataclass
class TradeEvent:
    """Real-time trade event."""
    trade_id: str
    market_id: str
    token_id: str
    price: float
    size: float
    side: str  # 'buy' or 'sell' (taker side)
    timestamp: float
    maker_address: Optional[str] = None
    taker_address: Optional[str] = None
    transaction_hash: Optional[str] = None
    
    def __post_init__(self):
        self.price = float(self.price)
        self.size = float(self.size)
        self.timestamp = float(self.timestamp)
    
    @property
    def notional(self) -> float:
        """Calculate notional value of trade."""
        return self.price * self.size
    
    def is_whale(self, threshold: float = 10000.0) -> bool:
        """Check if this is a whale trade based on notional."""
        return self.notional >= threshold
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'trade_id': self.trade_id,
            'market_id': self.market_id,
            'token_id': self.token_id,
            'price': self.price,
            'size': self.size,
            'side': self.side,
            'timestamp': self.timestamp,
            'maker_address': self.maker_address,
            'taker_address': self.taker_address,
            'transaction_hash': self.transaction_hash,
            'notional': self.notional,
        }


@dataclass
class TickerEvent:
    """Price ticker event."""
    market_id: str
    token_id: str
    price: float
    change_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float
    timestamp: float
    
    def __post_init__(self):
        self.price = float(self.price)
        self.change_24h = float(self.change_24h)
        self.volume_24h = float(self.volume_24h)
        self.high_24h = float(self.high_24h)
        self.low_24h = float(self.low_24h)
        self.timestamp = float(self.timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'market_id': self.market_id,
            'token_id': self.token_id,
            'price': self.price,
            'change_24h': self.change_24h,
            'volume_24h': self.volume_24h,
            'high_24h': self.high_24h,
            'low_24h': self.low_24h,
            'timestamp': self.timestamp,
        }


@dataclass
class ConnectionStats:
    """Connection performance statistics."""
    connected_at: Optional[float] = None
    disconnected_at: Optional[float] = None
    reconnect_count: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    errors_count: int = 0
    
    # Latency tracking (microseconds)
    latency_samples: List[int] = field(default_factory=list)
    max_latency_samples: int = 1000
    
    def record_latency(self, latency_us: int):
        """Record a latency sample in microseconds."""
        self.latency_samples.append(latency_us)
        if len(self.latency_samples) > self.max_latency_samples:
            self.latency_samples.pop(0)
    
    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.latency_samples:
            return (sum(self.latency_samples) / len(self.latency_samples)) / 1000
        return 0.0
    
    @property
    def min_latency_ms(self) -> float:
        """Minimum latency in milliseconds."""
        if self.latency_samples:
            return min(self.latency_samples) / 1000
        return 0.0
    
    @property
    def max_latency_ms(self) -> float:
        """Maximum latency in milliseconds."""
        if self.latency_samples:
            return max(self.latency_samples) / 1000
        return 0.0
    
    @property
    def messages_per_second(self) -> float:
        """Calculate message rate."""
        if self.connected_at:
            elapsed = time.time() - self.connected_at
            if elapsed > 0:
                return self.messages_received / elapsed
        return 0.0
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.connected_at is not None and self.disconnected_at is None
    
    @property
    def connection_duration(self) -> float:
        """Get connection duration in seconds."""
        if self.connected_at:
            end = self.disconnected_at or time.time()
            return end - self.connected_at
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'is_connected': self.is_connected,
            'connected_at': self.connected_at,
            'disconnected_at': self.disconnected_at,
            'connection_duration': self.connection_duration,
            'reconnect_count': self.reconnect_count,
            'messages_received': self.messages_received,
            'messages_sent': self.messages_sent,
            'messages_per_second': self.messages_per_second,
            'bytes_received': self.bytes_received,
            'bytes_sent': self.bytes_sent,
            'errors_count': self.errors_count,
            'avg_latency_ms': self.avg_latency_ms,
            'min_latency_ms': self.min_latency_ms,
            'max_latency_ms': self.max_latency_ms,
        }


# ============================================================================
# Subscription Types
# ============================================================================

class SubscriptionType(Enum):
    """WebSocket subscription types."""
    ORDERBOOK = "orderbook"
    TRADES = "trades"
    TICKER = "ticker"
    ALL_MARKETS = "all_markets"


@dataclass
class Subscription:
    """Represents an active subscription."""
    sub_type: SubscriptionType
    market_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    subscribed_at: float = field(default_factory=time.time)
    
    @property
    def channel(self) -> str:
        """Get the channel identifier."""
        if self.market_id:
            return f"{self.sub_type.value}:{self.market_id}"
        return self.sub_type.value


# ============================================================================
# Main WebSocket Client
# ============================================================================

class PolymarketWebSocket:
    """
    High-performance WebSocket client for Polymarket CLOB.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Connection health monitoring (heartbeat/ping-pong)
    - Multiple connection strategies (fallback endpoints)
    - Async/await throughout
    - Message batching
    - Latency tracking (microsecond precision)
    
    Example:
        >>> client = PolymarketWebSocket()
        >>> 
        >>> @client.on_trade
        ... def handle_trade(trade: TradeEvent):
        ...     print(f"Trade: {trade.size} @ ${trade.price:.3f}")
        >>> 
        >>> await client.connect()
        >>> await client.subscribe_trades("0x123...")
        >>> await client.run()
    """
    
    # WebSocket endpoints (primary + fallbacks)
    ENDPOINTS = [
        "wss://clob.polymarket.com/ws",
        "wss://clob.polymarket.com/ws/market",
    ]
    
    # Connection settings
    DEFAULT_HEARTBEAT_INTERVAL = 30.0  # seconds
    DEFAULT_RECONNECT_DELAY = 1.0  # initial delay
    MAX_RECONNECT_DELAY = 60.0  # max delay
    RECONNECT_BACKOFF_MULTIPLIER = 2.0
    MAX_RECONNECT_ATTEMPTS = 0  # 0 = infinite
    MESSAGE_TIMEOUT = 60.0  # seconds
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS,
        message_queue_size: int = 10000,
        enable_compression: bool = True,
    ):
        """
        Initialize WebSocket client.
        
        Args:
            endpoint: WebSocket endpoint URL (None for auto-selection)
            heartbeat_interval: Heartbeat interval in seconds
            auto_reconnect: Enable automatic reconnection
            max_reconnect_attempts: Max reconnection attempts (0 = infinite)
            message_queue_size: Size of internal message queue
            enable_compression: Enable per-message deflate compression
        """
        self.endpoint = endpoint or self.ENDPOINTS[0]
        self.fallback_endpoints = [e for e in self.ENDPOINTS if e != self.endpoint]
        self.heartbeat_interval = heartbeat_interval
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.enable_compression = enable_compression
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._connection_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._reconnect_attempts = 0
        self._current_endpoint_index = 0
        
        # Subscriptions
        self._subscriptions: Dict[str, Subscription] = {}
        self._pending_subscriptions: List[Subscription] = []
        
        # Orderbook state (maintained locally)
        self._orderbooks: Dict[str, OrderBookUpdate] = {}
        
        # Message queue for batching
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=message_queue_size)
        self._batch_size = 100
        self._batch_timeout = 0.001  # 1ms
        
        # Statistics
        self.stats = ConnectionStats()
        
        # Latency tracking
        self._ping_sent_at: Optional[float] = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'orderbook': [],
            'trade': [],
            'price_change': [],
            'whale_trade': [],
            'connection_change': [],
            'ticker': [],
            'error': [],
        }
        
        # Whale detection threshold
        self._whale_threshold = 10000.0  # $10k notional
        
        # Background tasks
        self._tasks: Set[asyncio.Task] = set()
        
        logger.info(f"PolymarketWebSocket initialized (endpoint: {self.endpoint})")
    
    # ========================================================================
    # Connection Management
    # ========================================================================
    
    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        
        Returns:
            True if connection successful
        """
        if self._connected:
            logger.warning("Already connected")
            return True
        
        endpoint = self._get_current_endpoint()
        
        try:
            logger.info(f"Connecting to {endpoint}...")
            
            # Connection options
            options = {
                'ping_interval': self.heartbeat_interval,
                'ping_timeout': self.heartbeat_interval * 2,
                'close_timeout': 10,
            }
            
            if self.enable_compression:
                options['compression'] = 'deflate'
            
            self.websocket = await websockets.connect(endpoint, **options)
            self._connected = True
            self._connection_event.set()
            self.stats.connected_at = time.time()
            self.stats.disconnected_at = None
            self._reconnect_attempts = 0
            
            logger.info(f"Connected to {endpoint}")
            
            # Notify connection change
            self._notify_connection_change(True)
            
            # Resubscribe to previous subscriptions
            await self._resubscribe_all()
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.stats.errors_count += 1
            return False
    
    async def disconnect(self):
        """Close WebSocket connection gracefully."""
        self._stop_event.set()
        self._connection_event.clear()
        
        # Cancel all background tasks
        for task in self._tasks:
            task.cancel()
        
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.debug(f"Error closing websocket: {e}")
            finally:
                self.websocket = None
        
        self._connected = False
        self.stats.disconnected_at = time.time()
        
        self._notify_connection_change(False)
        logger.info("Disconnected")
    
    async def _reconnect(self):
        """Reconnect with exponential backoff."""
        if not self.auto_reconnect:
            return
        
        if self.max_reconnect_attempts > 0 and \
           self._reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return
        
        self._reconnect_attempts += 1
        self.stats.reconnect_count += 1
        
        # Calculate backoff delay
        delay = min(
            self.DEFAULT_RECONNECT_DELAY * (self.RECONNECT_BACKOFF_MULTIPLIER ** (self._reconnect_attempts - 1)),
            self.MAX_RECONNECT_DELAY
        )
        
        # Try fallback endpoint after 3 failed attempts
        if self._reconnect_attempts % 3 == 0 and self.fallback_endpoints:
            self._current_endpoint_index = (self._current_endpoint_index + 1) % \
                                           (len(self.fallback_endpoints) + 1)
            logger.info(f"Switching to fallback endpoint index {self._current_endpoint_index}")
        
        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})...")
        await asyncio.sleep(delay)
        
        # Attempt reconnection
        if await self.connect():
            logger.info("Reconnected successfully")
        else:
            # Schedule another reconnection attempt
            asyncio.create_task(self._reconnect())
    
    def _get_current_endpoint(self) -> str:
        """Get current endpoint based on fallback strategy."""
        if self._current_endpoint_index == 0:
            return self.endpoint
        return self.fallback_endpoints[self._current_endpoint_index - 1]
    
    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected and self.websocket is not None
    
    # ========================================================================
    # Subscription Methods
    # ========================================================================
    
    async def subscribe_orderbook(self, market_id: str, token_id: Optional[str] = None) -> bool:
        """
        Subscribe to Level 2 orderbook updates.
        
        Args:
            market_id: Market ID to subscribe
            token_id: Optional token ID for specific outcome
            
        Returns:
            True if subscription successful
        """
        subscription = Subscription(
            sub_type=SubscriptionType.ORDERBOOK,
            market_id=market_id,
            params={'token_id': token_id} if token_id else {}
        )
        return await self._subscribe(subscription)
    
    async def subscribe_trades(self, market_id: str, token_id: Optional[str] = None) -> bool:
        """
        Subscribe to real-time trade stream.
        
        Args:
            market_id: Market ID to subscribe
            token_id: Optional token ID for specific outcome
            
        Returns:
            True if subscription successful
        """
        subscription = Subscription(
            sub_type=SubscriptionType.TRADES,
            market_id=market_id,
            params={'token_id': token_id} if token_id else {}
        )
        return await self._subscribe(subscription)
    
    async def subscribe_ticker(self, market_id: str, token_id: Optional[str] = None) -> bool:
        """
        Subscribe to price ticker updates.
        
        Args:
            market_id: Market ID to subscribe
            token_id: Optional token ID for specific outcome
            
        Returns:
            True if subscription successful
        """
        subscription = Subscription(
            sub_type=SubscriptionType.TICKER,
            market_id=market_id,
            params={'token_id': token_id} if token_id else {}
        )
        return await self._subscribe(subscription)
    
    async def subscribe_all_markets(self) -> bool:
        """
        Subscribe to all active markets.
        
        Returns:
            True if subscription successful
        """
        subscription = Subscription(
            sub_type=SubscriptionType.ALL_MARKETS,
        )
        return await self._subscribe(subscription)
    
    async def subscribe_whale_trades(self, min_size: float = 10000.0) -> bool:
        """
        Set threshold for whale trade detection.
        
        Args:
            min_size: Minimum notional value for whale trades
            
        Returns:
            True (just updates threshold)
        """
        self._whale_threshold = min_size
        logger.info(f"Whale threshold set to ${min_size:,.2f}")
        return True
    
    async def unsubscribe(self, market_id: str, sub_type: Optional[SubscriptionType] = None) -> bool:
        """
        Unsubscribe from a market.
        
        Args:
            market_id: Market ID to unsubscribe
            sub_type: Specific subscription type (None = all)
            
        Returns:
            True if unsubscription successful
        """
        channels_to_remove = []
        
        for channel, sub in list(self._subscriptions.items()):
            if sub.market_id == market_id:
                if sub_type is None or sub.sub_type == sub_type:
                    channels_to_remove.append(channel)
        
        for channel in channels_to_remove:
            del self._subscriptions[channel]
            
            if self.is_connected:
                try:
                    await self._send({
                        'type': 'unsubscribe',
                        'channel': channel,
                    })
                except Exception as e:
                    logger.error(f"Unsubscribe error: {e}")
        
        return True
    
    async def _subscribe(self, subscription: Subscription) -> bool:
        """Internal subscribe method."""
        channel = subscription.channel
        
        # Store subscription
        self._subscriptions[channel] = subscription
        
        if not self.is_connected:
            # Queue for when connected
            self._pending_subscriptions.append(subscription)
            return True
        
        # Send subscription message
        message = self._build_subscribe_message(subscription)
        
        try:
            await self._send(message)
            logger.debug(f"Subscribed to {channel}")
            return True
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return False
    
    def _build_subscribe_message(self, subscription: Subscription) -> Dict[str, Any]:
        """Build subscription message."""
        message = {
            'type': 'subscribe',
            'channel': subscription.sub_type.value,
        }
        
        if subscription.market_id:
            message['market'] = subscription.market_id
        
        message.update(subscription.params)
        
        return message
    
    async def _resubscribe_all(self):
        """Resubscribe to all active subscriptions after reconnection."""
        # Combine active and pending subscriptions
        all_subs = list(self._subscriptions.values()) + self._pending_subscriptions
        self._pending_subscriptions = []
        
        for subscription in all_subs:
            message = self._build_subscribe_message(subscription)
            try:
                await self._send(message)
                logger.debug(f"Resubscribed to {subscription.channel}")
            except Exception as e:
                logger.error(f"Resubscribe error: {e}")
                self._pending_subscriptions.append(subscription)
    
    # ========================================================================
    # Event Handlers (Decorators)
    # ========================================================================
    
    def on_orderbook_update(self, callback: Callable[[OrderBookUpdate], None]):
        """
        Register callback for orderbook updates.
        
        Args:
            callback: Function receiving OrderBookUpdate
            
        Example:
            >>> @client.on_orderbook_update
            ... def handle_book(update: OrderBookUpdate):
            ...     print(f"Spread: {update.spread}")
        """
        self._callbacks['orderbook'].append(callback)
        return callback
    
    def on_trade(self, callback: Callable[[TradeEvent], None]):
        """
        Register callback for trade events.
        
        Args:
            callback: Function receiving TradeEvent
            
        Example:
            >>> @client.on_trade
            ... def handle_trade(trade: TradeEvent):
            ...     print(f"Trade: {trade.size} @ ${trade.price:.3f}")
        """
        self._callbacks['trade'].append(callback)
        return callback
    
    def on_price_change(self, callback: Callable[[str, float, float], None]):
        """
        Register callback for price changes.
        
        Args:
            callback: Function receiving (market_id, old_price, new_price)
            
        Example:
            >>> @client.on_price_change
            ... def handle_price(market_id, old_price, new_price):
            ...     change = (new_price - old_price) / old_price * 100
            ...     print(f"Price changed: {change:+.2f}%")
        """
        self._callbacks['price_change'].append(callback)
        return callback
    
    def on_whale_trade(self, callback: Callable[[TradeEvent], None]):
        """
        Register callback for whale trades.
        
        Args:
            callback: Function receiving TradeEvent
            
        Example:
            >>> @client.on_whale_trade
            ... def handle_whale(trade: TradeEvent):
            ...     print(f"WHALE: ${trade.notional:,.2f}")
        """
        self._callbacks['whale_trade'].append(callback)
        return callback
    
    def on_connection_change(self, callback: Callable[[bool], None]):
        """
        Register callback for connection status changes.
        
        Args:
            callback: Function receiving (is_connected)
            
        Example:
            >>> @client.on_connection_change
            ... def handle_connection(connected):
            ...     print(f"Connected: {connected}")
        """
        self._callbacks['connection_change'].append(callback)
        return callback
    
    def on_ticker(self, callback: Callable[[TickerEvent], None]):
        """
        Register callback for ticker updates.
        
        Args:
            callback: Function receiving TickerEvent
        """
        self._callbacks['ticker'].append(callback)
        return callback
    
    def on_error(self, callback: Callable[[Exception], None]):
        """
        Register callback for errors.
        
        Args:
            callback: Function receiving Exception
        """
        self._callbacks['error'].append(callback)
        return callback
    
    def _notify(self, event_type: str, *args, **kwargs):
        """Notify all callbacks for an event type."""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _notify_connection_change(self, connected: bool):
        """Notify connection change callbacks."""
        self._notify('connection_change', connected)
    
    # ========================================================================
    # Message Processing
    # ========================================================================
    
    async def _send(self, message: Dict[str, Any]):
        """Send message to WebSocket."""
        if not self.websocket:
            raise ConnectionError("Not connected")
        
        data = json.dumps(message)
        await self.websocket.send(data)
        self.stats.messages_sent += 1
        self.stats.bytes_sent += len(data.encode())
    
    async def _receive_loop(self):
        """Main message receive loop."""
        while not self._stop_event.is_set():
            try:
                if not self.websocket:
                    await asyncio.sleep(0.1)
                    continue
                
                # Receive message with timeout
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=self.MESSAGE_TIMEOUT
                )
                
                # Track statistics
                receive_time = time.time()
                self.stats.messages_received += 1
                self.stats.bytes_received += len(message.encode()) if isinstance(message, str) else len(message)
                
                # Parse and process
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                
                await self._process_message(message, receive_time)
                
            except asyncio.TimeoutError:
                logger.warning("Message receive timeout")
                continue
            except ConnectionClosed:
                logger.warning("Connection closed")
                self._connected = False
                if self.auto_reconnect:
                    asyncio.create_task(self._reconnect())
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                self.stats.errors_count += 1
                self._notify('error', e)
    
    async def _process_message(self, raw_message: str, receive_time: float):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            msg_type = data.get('type', 'unknown')
            
            # Calculate latency if ping response
            if msg_type == 'pong' and self._ping_sent_at:
                latency_us = int((receive_time - self._ping_sent_at) * 1_000_000)
                self.stats.record_latency(latency_us)
                self._ping_sent_at = None
                return
            
            # Route to appropriate handler
            if msg_type == 'orderbook':
                await self._handle_orderbook(data, receive_time)
            elif msg_type == 'trade':
                await self._handle_trade(data, receive_time)
            elif msg_type == 'ticker':
                await self._handle_ticker(data, receive_time)
            elif msg_type == 'error':
                logger.error(f"Server error: {data}")
                self.stats.errors_count += 1
            elif msg_type == 'subscribed':
                logger.debug(f"Subscription confirmed: {data.get('channel')}")
            elif msg_type == 'unsubscribed':
                logger.debug(f"Unsubscription confirmed: {data.get('channel')}")
            else:
                logger.debug(f"Unknown message type: {msg_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _handle_orderbook(self, data: Dict[str, Any], timestamp: float):
        """Handle orderbook update message."""
        try:
            market_id = data.get('market', data.get('market_id', ''))
            token_id = data.get('token_id', '')
            
            # Parse price levels
            bids_data = data.get('bids', [])
            asks_data = data.get('asks', [])
            
            bids = [PriceLevel(price=b[0], size=b[1], orders=b[2] if len(b) > 2 else 0) 
                   for b in bids_data]
            asks = [PriceLevel(price=a[0], size=a[1], orders=a[2] if len(a) > 2 else 0) 
                   for a in asks_data]
            
            update = OrderBookUpdate(
                market_id=market_id,
                token_id=token_id,
                bids=bids,
                asks=asks,
                timestamp=timestamp,
                sequence=data.get('sequence', 0),
                is_snapshot=data.get('is_snapshot', False),
            )
            
            # Store local orderbook state
            key = f"{market_id}:{token_id}" if token_id else market_id
            self._orderbooks[key] = update
            
            # Notify callbacks
            self._notify('orderbook', update)
            
        except Exception as e:
            logger.error(f"Orderbook handling error: {e}")
    
    async def _handle_trade(self, data: Dict[str, Any], timestamp: float):
        """Handle trade message."""
        try:
            trade = TradeEvent(
                trade_id=data.get('trade_id', data.get('id', '')),
                market_id=data.get('market', data.get('market_id', '')),
                token_id=data.get('token_id', ''),
                price=data.get('price', 0),
                size=data.get('size', data.get('amount', 0)),
                side=data.get('side', 'buy'),
                timestamp=timestamp,
                maker_address=data.get('maker'),
                taker_address=data.get('taker'),
                transaction_hash=data.get('tx_hash', data.get('transaction_hash')),
            )
            
            # Notify trade callbacks
            self._notify('trade', trade)
            
            # Check for whale trade
            if trade.is_whale(self._whale_threshold):
                self._notify('whale_trade', trade)
            
            # Check for price change and notify
            await self._check_price_change(trade)
            
        except Exception as e:
            logger.error(f"Trade handling error: {e}")
    
    async def _handle_ticker(self, data: Dict[str, Any], timestamp: float):
        """Handle ticker message."""
        try:
            ticker = TickerEvent(
                market_id=data.get('market', data.get('market_id', '')),
                token_id=data.get('token_id', ''),
                price=data.get('price', 0),
                change_24h=data.get('change_24h', 0),
                volume_24h=data.get('volume_24h', data.get('volume', 0)),
                high_24h=data.get('high_24h', 0),
                low_24h=data.get('low_24h', 0),
                timestamp=timestamp,
            )
            
            self._notify('ticker', ticker)
            
        except Exception as e:
            logger.error(f"Ticker handling error: {e}")
    
    async def _check_price_change(self, trade: TradeEvent):
        """Check and notify price changes."""
        key = f"{trade.market_id}:{trade.token_id}" if trade.token_id else trade.market_id
        
        if key in self._orderbooks:
            old_book = self._orderbooks[key]
            old_price = old_book.mid_price
            
            if old_price:
                # Update mid price based on trade
                new_price = trade.price
                
                # Only notify significant changes (>0.1%)
                if abs(new_price - old_price) / old_price > 0.001:
                    self._notify('price_change', trade.market_id, old_price, new_price)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat pings."""
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.is_connected and self.websocket:
                    self._ping_sent_at = time.time()
                    await self._send({'type': 'ping'})
                    logger.debug("Heartbeat sent")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Heartbeat error: {e}")
    
    async def _batch_processor(self):
        """Process messages in batches for efficiency."""
        while not self._stop_event.is_set():
            try:
                batch = []
                deadline = asyncio.get_event_loop().time() + self._batch_timeout
                
                while len(batch) < self._batch_size:
                    timeout = deadline - asyncio.get_event_loop().time()
                    if timeout <= 0:
                        break
                    
                    try:
                        msg = await asyncio.wait_for(
                            self._message_queue.get(),
                            timeout=max(0, timeout)
                        )
                        batch.append(msg)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    # Process batch
                    await self._process_batch(batch)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch processing error: {e}")
    
    async def _process_batch(self, batch: List[Dict[str, Any]]):
        """Process a batch of messages."""
        # Group by type for efficient processing
        by_type: Dict[str, List[Dict]] = defaultdict(list)
        
        for msg in batch:
            msg_type = msg.get('type', 'unknown')
            by_type[msg_type].append(msg)
        
        # Process each type
        for msg_type, messages in by_type.items():
            if msg_type == 'orderbook':
                # Merge orderbook updates (keep only latest per market)
                latest = {}
                for msg in messages:
                    market = msg.get('market', 'unknown')
                    latest[market] = msg
                
                for msg in latest.values():
                    await self._handle_orderbook(msg, time.time())
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    async def run(self):
        """
        Run the WebSocket client (blocking).
        
        This method starts all background tasks and runs until disconnect() is called.
        """
        if not self.is_connected:
            if not await self.connect():
                raise ConnectionError("Failed to connect")
        
        # Start background tasks
        self._tasks.add(asyncio.create_task(self._receive_loop()))
        self._tasks.add(asyncio.create_task(self._heartbeat_loop()))
        self._tasks.add(asyncio.create_task(self._batch_processor()))
        
        logger.info("WebSocket client running")
        
        # Wait for stop signal
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect()
    
    def get_orderbook(self, market_id: str, token_id: Optional[str] = None) -> Optional[OrderBookUpdate]:
        """
        Get current orderbook state for a market.
        
        Args:
            market_id: Market ID
            token_id: Optional token ID
            
        Returns:
            Current OrderBookUpdate or None
        """
        key = f"{market_id}:{token_id}" if token_id else market_id
        return self._orderbooks.get(key)
    
    def get_all_orderbooks(self) -> Dict[str, OrderBookUpdate]:
        """Get all cached orderbooks."""
        return self._orderbooks.copy()
    
    async def wait_for_connection(self, timeout: float = 30.0) -> bool:
        """
        Wait for connection to be established.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if connected within timeout
        """
        try:
            await asyncio.wait_for(self._connection_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
    
    # ========================================================================
    # Context Manager
    # ========================================================================
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_websocket_client(
    endpoint: Optional[str] = None,
    auto_reconnect: bool = True,
) -> PolymarketWebSocket:
    """
    Create and connect a WebSocket client.
    
    Args:
        endpoint: WebSocket endpoint URL
        auto_reconnect: Enable automatic reconnection
        
    Returns:
        Connected PolymarketWebSocket instance
    """
    client = PolymarketWebSocket(
        endpoint=endpoint,
        auto_reconnect=auto_reconnect,
    )
    await client.connect()
    return client


async def subscribe_and_listen(
    market_id: str,
    on_trade: Optional[Callable[[TradeEvent], None]] = None,
    on_orderbook: Optional[Callable[[OrderBookUpdate], None]] = None,
    duration: float = 60.0,
):
    """
    Convenience function to subscribe to a market and listen for events.
    
    Args:
        market_id: Market ID to subscribe
        on_trade: Optional trade callback
        on_orderbook: Optional orderbook callback
        duration: How long to listen (seconds)
    """
    async with PolymarketWebSocket() as client:
        # Register callbacks
        if on_trade:
            client.on_trade(on_trade)
        if on_orderbook:
            client.on_orderbook_update(on_orderbook)
        
        # Subscribe
        await client.subscribe_trades(market_id)
        await client.subscribe_orderbook(market_id)
        
        # Run for duration
        await asyncio.sleep(duration)


# ============================================================================
# Main (for testing)
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    async def main():
        """Test the WebSocket client."""
        
        # Example callbacks
        def on_trade(trade: TradeEvent):
            print(f"\n[TRADE] {trade.side.upper()} {trade.size:.4f} @ ${trade.price:.4f} "
                  f"(Notional: ${trade.notional:.2f})")
        
        def on_orderbook(update: OrderBookUpdate):
            spread = update.spread
            if spread:
                print(f"\n[BOOK] {update.market_id[:20]}... "
                      f"Spread: ${spread:.4f}, Imbalance: {update.imbalance:+.2%}")
        
        def on_connection(connected: bool):
            status = "CONNECTED" if connected else "DISCONNECTED"
            print(f"\n[CONN] {status}")
        
        def on_whale(trade: TradeEvent):
            print(f"\n[WHALE] 🐋 ${trade.notional:,.2f} trade!")
        
        # Create client
        client = PolymarketWebSocket()
        
        # Register callbacks
        client.on_trade(on_trade)
        client.on_orderbook_update(on_orderbook)
        client.on_connection_change(on_connection)
        client.on_whale_trade(on_whale)
        
        # Connect and subscribe (example market)
        print("Connecting to Polymarket WebSocket...")
        await client.connect()
        
        # Print stats
        print(f"\nConnection Stats: {client.stats.to_dict()}")
        
        # Keep running
        try:
            await client.run()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            await client.disconnect()
            print(f"\nFinal Stats: {client.stats.to_dict()}")
    
    # Run
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExited.")
        sys.exit(0)
