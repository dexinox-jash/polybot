"""
Whale Stream Monitor - Real-Time Whale Tracking

Continuously monitors whale wallets via TheGraph polling.
Detects trade urgency patterns and emits signals for speed-matched copying.

Features:
- 30-second polling interval (configurable)
- Circular buffer for recent transactions
- Trade urgency classification (FLASH, MOMENTUM, EXIT, HEDGE)
- Crypto market filtering
- Duplicate detection via TX hash tracking
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque
import logging

from gql import gql

from .crypto_filter import CRYPTO_ONLY_FILTER

logger = logging.getLogger(__name__)


class TradeUrgency(Enum):
    """Classification of trade urgency patterns."""
    FLASH = "flash"           # Position opened <2min after market creation
    MOMENTUM = "momentum"     # Increasing position size over 3+ trades
    EXIT = "exit"             # 50%+ position reduction
    HEDGE = "hedge"           # Opposite side bets opened simultaneously
    ACCUMULATION = "accumulation"  # Gradual position building
    ROUTINE = "routine"       # Normal trading activity


@dataclass
class WhaleTrade:
    """A single whale trade transaction."""
    tx_hash: str
    whale_address: str
    market_id: str
    market_question: str
    outcome: str  # 'YES' or 'NO'
    amount: float  # USD value
    price: float   # Price per share
    timestamp: datetime
    block_number: int
    
    # Derived fields
    market_created_at: Optional[datetime] = None
    market_liquidity: float = 0.0


@dataclass
class WhaleSignal:
    """Processed whale signal with pattern classification."""
    # Trade details
    trade: WhaleTrade
    
    # Pattern classification
    urgency: TradeUrgency
    pattern_confidence: float  # 0-1
    
    # Speed metrics
    time_since_market_created: Optional[timedelta]
    time_since_last_trade: Optional[timedelta]
    
    # Context
    whale_pattern_profile: str  # e.g., "SNIPER", "ACCUMULATOR"
    
    # Recommendation
    recommended_action: str  # 'COPY_IMMEDIATE', 'WAIT_CONFIRM', 'SKIP'
    suggested_size: float
    
    # Optional fields with defaults
    recent_whale_trades: List[WhaleTrade] = field(default_factory=list)
    max_delay_seconds: int = 60


class CircularBuffer:
    """Fixed-size circular buffer for recent trades."""
    
    def __init__(self, size: int = 100):
        self.size = size
        self.buffer: deque = deque(maxlen=size)
    
    def add(self, item):
        """Add item to buffer."""
        self.buffer.append(item)
    
    def get_all(self) -> List:
        """Get all items in buffer (oldest first)."""
        return list(self.buffer)
    
    def get_recent(self, n: int) -> List:
        """Get n most recent items."""
        return list(self.buffer)[-n:] if n <= len(self.buffer) else list(self.buffer)
    
    def clear(self):
        """Clear buffer."""
        self.buffer.clear()


class WhaleStreamMonitor:
    """
    Real-time whale wallet monitor.
    
    Polls TheGraph at configurable intervals to detect
    new whale trades and classify their urgency.
    """
    
    # GraphQL query for fetching new trades from orderFilleds entity
    NEW_TRADES_QUERY = gql("""
        query GetNewTrades(
            $whaleAddresses: [String!]!,
            $timestampGt: BigInt!,
            $first: Int!
        ) {
            orderFilleds(
                where: {
                    maker_in: $whaleAddresses,
                    timestamp_gt: $timestampGt
                }
                first: $first
                orderBy: timestamp
                orderDirection: desc
            ) {
                id
                transactionHash
                maker
                market {
                    id
                    question
                    description
                    createdAt
                    liquidity
                    category
                    subcategory
                }
                outcomeIndex
                outcomeTokens
                filledAmount
                price
                timestamp
                blockNumber
                fee
            }
        }
    """)
    
    def __init__(
        self,
        subgraph_client,
        whale_addresses: List[str],
        poll_interval: int = 30,
        buffer_size: int = 100,
        crypto_only: bool = True
    ):
        """
        Initialize whale stream monitor.
        
        Args:
            subgraph_client: TheGraph client instance
            whale_addresses: List of whale wallet addresses to track
            poll_interval: Seconds between polls (default 30)
            buffer_size: Number of trades to keep per whale
            crypto_only: Only track crypto markets
        """
        self.subgraph = subgraph_client
        self.whale_addresses = [w.lower() for w in whale_addresses]
        self.poll_interval = poll_interval
        self.crypto_only = crypto_only
        
        # State
        self.buffers: Dict[str, CircularBuffer] = {
            w: CircularBuffer(size=buffer_size) for w in self.whale_addresses
        }
        self.last_seen_tx: Dict[str, str] = {}
        self.last_check_time: datetime = datetime.now() - timedelta(minutes=5)
        
        # Running state
        self.is_running: bool = False
        self.callbacks: List[Callable[[WhaleSignal], None]] = []
        
        # Stats
        self.total_trades_detected: int = 0
        self.poll_count: int = 0
        
        logger.info(f"WhaleStreamMonitor initialized: {len(whale_addresses)} whales, "
                   f"{poll_interval}s interval, crypto_only={crypto_only}")
    
    def add_callback(self, callback: Callable[[WhaleSignal], None]):
        """Add callback function to be called on new signals."""
        self.callbacks.append(callback)
        logger.info(f"Callback added: {callback.__name__}")
    
    async def start_monitoring(self):
        """Start the async monitoring loop."""
        self.is_running = True
        logger.info("Whale monitoring started")
        
        while self.is_running:
            try:
                await self._poll_once()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)  # Short retry on error
    
    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.is_running = False
        logger.info("Whale monitoring stopped")
    
    async def _poll_once(self):
        """Single polling iteration."""
        self.poll_count += 1
        
        # Query TheGraph for new trades
        new_trades = await self._fetch_new_trades()
        
        if new_trades:
            logger.info(f"Poll #{self.poll_count}: Detected {len(new_trades)} new trades")
            
            # Process and classify each trade
            for trade in new_trades:
                signal = self._classify_trade(trade)
                
                # Emit to callbacks
                for callback in self.callbacks:
                    try:
                        callback(signal)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                self.total_trades_detected += 1
        
        self.last_check_time = datetime.now()
    
    async def _fetch_new_trades(self) -> List[WhaleTrade]:
        """
        Fetch new trades from TheGraph since last check.
        
        Queries the orderFilleds entity from the Polymarket subgraph,
        filtering by whale addresses and timestamp. Handles crypto-only
        filtering and parses responses into WhaleTrade objects.
        
        Returns:
            List of new WhaleTrade objects
        """
        new_trades = []
        
        # Convert last_check_time to Unix timestamp for subgraph query
        last_check_timestamp = int(self.last_check_time.timestamp())
        
        try:
            # Run the synchronous subgraph query in a thread pool
            # to avoid blocking the async event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Default executor
                self._execute_trades_query,
                last_check_timestamp
            )
            
            if not result or 'orderFilleds' not in result:
                logger.debug("No orderFilleds data in response")
                return []
            
            order_filleds = result.get('orderFilleds', [])
            logger.debug(f"Fetched {len(order_filleds)} raw orderFilleds from subgraph")
            
            for order in order_filleds:
                try:
                    # Parse the order data into a WhaleTrade object
                    trade = self._parse_order_to_trade(order)
                    
                    if not trade:
                        continue
                    
                    # Apply crypto-only filter if enabled
                    if self.crypto_only:
                        market_data = order.get('market', {})
                        relevance = CRYPTO_ONLY_FILTER.classify_market(
                            question=market_data.get('question', ''),
                            description=market_data.get('description', ''),
                            tags=[market_data.get('category', ''), market_data.get('subcategory', '')]
                        )
                        if not relevance.is_crypto:
                            logger.debug(f"Skipping non-crypto market: {trade.market_question[:50]}")
                            continue
                    
                    # Skip duplicates
                    if trade.tx_hash in self.last_seen_tx:
                        logger.debug(f"Skipping duplicate trade: {trade.tx_hash}")
                        continue
                    
                    new_trades.append(trade)
                    logger.debug(f"New whale trade detected: {trade.tx_hash} - "
                               f"{trade.whale_address[:10]}... - ${trade.amount:.2f}")
                    
                except Exception as parse_error:
                    logger.warning(f"Error parsing order: {parse_error}")
                    continue
            
            if new_trades:
                logger.info(f"Found {len(new_trades)} new whale trades after filtering")
            
        except Exception as e:
            logger.error(f"Error fetching trades from TheGraph: {e}")
            # Return empty list on error - will retry on next poll
            return []
        
        return new_trades
    
    def _execute_trades_query(self, last_check_timestamp: int) -> dict:
        """
        Execute the GraphQL query for new trades.
        
        Args:
            last_check_timestamp: Unix timestamp for filtering
            
        Returns:
            GraphQL response dictionary
        """
        try:
            # Use the positions subgraph client for orderFilleds
            result = self.subgraph._execute(
                'positions',
                self.NEW_TRADES_QUERY,
                {
                    'whaleAddresses': self.whale_addresses,
                    'timestampGt': last_check_timestamp,
                    'first': 100  # Limit to prevent overwhelming responses
                }
            )
            return result
        except Exception as e:
            logger.error(f"GraphQL query execution failed: {e}")
            raise
    
    def _parse_order_to_trade(self, order: dict) -> Optional[WhaleTrade]:
        """
        Parse a raw orderFilleds response into a WhaleTrade object.
        
        Args:
            order: Raw order data from subgraph
            
        Returns:
            WhaleTrade object or None if parsing fails
        """
        try:
            # Extract market data
            market = order.get('market', {})
            if not market:
                logger.warning("Order missing market data")
                return None
            
            # Determine outcome from outcomeIndex
            outcome_index = order.get('outcomeIndex', 0)
            outcome = 'YES' if outcome_index == 0 else 'NO'
            
            # Parse amounts - handle both string and numeric types
            filled_amount = order.get('filledAmount', '0')
            amount = float(filled_amount) if filled_amount else 0.0
            
            price_str = order.get('price', '0')
            price = float(price_str) if price_str else 0.0
            
            # Calculate USD value (amount * price)
            usd_value = amount * price
            
            # Parse timestamp
            timestamp_raw = order.get('timestamp', 0)
            timestamp = datetime.fromtimestamp(int(timestamp_raw))
            
            # Parse market creation time if available
            market_created_at = None
            market_created_raw = market.get('createdAt')
            if market_created_raw:
                market_created_at = datetime.fromtimestamp(int(market_created_raw))
            
            # Parse liquidity
            liquidity_raw = market.get('liquidity', '0')
            liquidity = float(liquidity_raw) if liquidity_raw else 0.0
            
            # Parse block number
            block_number = int(order.get('blockNumber', 0))
            
            return WhaleTrade(
                tx_hash=order.get('transactionHash', order.get('id', '')),
                whale_address=order.get('maker', '').lower(),
                market_id=market.get('id', ''),
                market_question=market.get('question', 'Unknown Market'),
                outcome=outcome,
                amount=usd_value,
                price=price,
                timestamp=timestamp,
                block_number=block_number,
                market_created_at=market_created_at,
                market_liquidity=liquidity
            )
            
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse order: {e}")
            return None
    
    def _classify_trade(self, trade: WhaleTrade) -> WhaleSignal:
        """
        Classify trade urgency and create signal.
        
        Args:
            trade: The whale trade to classify
            
        Returns:
            WhaleSignal with classification
        """
        whale_buffer = self.buffers[trade.whale_address]
        recent_trades = whale_buffer.get_recent(10)
        
        # Calculate timing metrics
        time_since_market = None
        if trade.market_created_at:
            time_since_market = trade.timestamp - trade.market_created_at
        
        time_since_last = None
        if recent_trades:
            time_since_last = trade.timestamp - recent_trades[-1].timestamp
        
        # Determine urgency
        urgency = TradeUrgency.ROUTINE
        confidence = 0.5
        
        # FLASH: Entered within 2 minutes of market creation
        if time_since_market and time_since_market < timedelta(minutes=2):
            urgency = TradeUrgency.FLASH
            confidence = 0.9
        
        # MOMENTUM: 3+ increasing trades in last hour
        elif len(recent_trades) >= 3:
            recent_hour = [t for t in recent_trades 
                          if trade.timestamp - t.timestamp < timedelta(hours=1)]
            if len(recent_hour) >= 3:
                amounts = [t.amount for t in recent_hour]
                if amounts == sorted(amounts, reverse=True):  # Decreasing sizes
                    urgency = TradeUrgency.MOMENTUM
                    confidence = 0.8
        
        # ACCUMULATION: Gradual building over 24h
        elif len(recent_trades) >= 5:
            recent_day = [t for t in recent_trades 
                         if trade.timestamp - t.timestamp < timedelta(hours=24)]
            if len(recent_day) >= 5:
                urgency = TradeUrgency.ACCUMULATION
                confidence = 0.75
        
        # Add to buffer
        whale_buffer.add(trade)
        self.last_seen_tx[trade.tx_hash] = trade.timestamp.isoformat()
        
        # Determine action
        action = 'WAIT_CONFIRM'
        if urgency in [TradeUrgency.FLASH, TradeUrgency.MOMENTUM] and confidence > 0.7:
            action = 'COPY_IMMEDIATE'
        elif urgency == TradeUrgency.EXIT:
            action = 'SKIP'
        
        return WhaleSignal(
            trade=trade,
            urgency=urgency,
            pattern_confidence=confidence,
            time_since_market_created=time_since_market,
            time_since_last_trade=time_since_last,
            whale_pattern_profile=self._infer_pattern_profile(recent_trades),
            recent_whale_trades=recent_trades[-5:],
            recommended_action=action,
            suggested_size=min(trade.amount * 0.02, 500),  # 2% of whale size, max $500
            max_delay_seconds=60 if urgency == TradeUrgency.FLASH else 300
        )
    
    def _infer_pattern_profile(self, recent_trades: List[WhaleTrade]) -> str:
        """
        Infer the whale's pattern profile from recent trades.
        
        Returns:
            Pattern profile string (e.g., "SNIPER", "ACCUMULATOR")
        """
        if not recent_trades:
            return "UNKNOWN"
        
        # Analyze timing patterns
        if len(recent_trades) >= 5:
            # Check for early entry pattern (SNIPER)
            early_entries = sum(1 for t in recent_trades if t.market_created_at 
                              and (t.timestamp - t.market_created_at) < timedelta(minutes=5))
            if early_entries >= 3:
                return "SNIPER"
            
            # Check for gradual accumulation
            amounts = [t.amount for t in recent_trades[-5:]]
            if amounts == sorted(amounts):  # Increasing
                return "ACCUMULATOR"
        
        return "ROUTINE"
    
    def get_whale_stats(self, whale_address: str) -> Dict:
        """Get statistics for a specific whale."""
        buffer = self.buffers.get(whale_address.lower())
        if not buffer:
            return {}
        
        trades = buffer.get_all()
        if not trades:
            return {"trade_count": 0}
        
        return {
            "trade_count": len(trades),
            "total_volume": sum(t.amount for t in trades),
            "avg_trade_size": sum(t.amount for t in trades) / len(trades),
            "last_trade": trades[-1].timestamp if trades else None,
            "favorite_markets": self._get_top_markets(trades, 3)
        }
    
    def _get_top_markets(self, trades: List[WhaleTrade], n: int) -> List[str]:
        """Get top n markets by trade count."""
        from collections import Counter
        markets = [t.market_question[:30] for t in trades]
        return [m for m, _ in Counter(markets).most_common(n)]
    
    def get_all_stats(self) -> Dict:
        """Get overall monitoring statistics."""
        return {
            "poll_count": self.poll_count,
            "total_trades_detected": self.total_trades_detected,
            "whales_tracked": len(self.whale_addresses),
            "is_running": self.is_running,
            "uptime_seconds": self.poll_count * self.poll_interval if self.is_running else 0
        }
