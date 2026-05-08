"""
BTC 5-Minute Market Scanner

Real-time scanner for Polymarket BTC 5-minute prediction markets.
Detects active markets, analyzes order flow, and identifies trading opportunities.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import websockets
import json

from ..utils.logger import setup_logging
from ..utils.config import Config

logger = setup_logging()


class MarketRegime(Enum):
    """Market regime classifications for BTC 5-min markets."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT_PENDING = "breakout_pending"
    REVERSAL_IMMINENT = "reversal_imminent"


@dataclass
class BTCMarket:
    """BTC 5-minute market data structure."""
    market_id: str
    condition_id: str
    question: str
    created_at: datetime
    expires_at: datetime
    
    # Price data
    yes_price: float = 0.5
    no_price: float = 0.5
    implied_probability: float = 0.5
    
    # Volume metrics
    volume_5min: float = 0.0
    volume_1min: float = 0.0
    trade_count_5min: int = 0
    
    # Order book
    bid_yes: float = 0.0
    ask_yes: float = 0.0
    spread: float = 0.0
    depth_yes: float = 0.0
    depth_no: float = 0.0
    
    # Time-series data (last 5 minutes)
    price_history: List[Dict] = field(default_factory=list)
    volume_history: List[Dict] = field(default_factory=list)
    
    # Whale activity
    whale_buys_yes: float = 0.0
    whale_buys_no: float = 0.0
    whale_sells_yes: float = 0.0
    whale_sells_no: float = 0.0
    
    # Analysis
    regime: MarketRegime = MarketRegime.RANGING
    momentum: float = 0.0
    volatility: float = 0.0
    
    @property
    def time_remaining(self) -> timedelta:
        """Time until market expiration."""
        return self.expires_at - datetime.now()
    
    @property
    def is_active(self) -> bool:
        """Check if market is still tradable."""
        remaining = self.time_remaining
        return timedelta(0) < remaining < timedelta(minutes=5)
    
    @property
    def whale_imbalance(self) -> float:
        """Calculate whale buying imbalance."""
        total_buy = self.whale_buys_yes + self.whale_buys_no
        if total_buy == 0:
            return 0.0
        return (self.whale_buys_yes - self.whale_buys_no) / total_buy


@dataclass
class PriceTick:
    """Individual price tick for micro-analysis."""
    timestamp: datetime
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    wallet: Optional[str] = None
    is_whale: bool = False


class BTCMarketScanner:
    """
    Real-time scanner for BTC 5-minute prediction markets.
    
    Monitors all active BTC 5-min markets, tracks price action,
    detects patterns, and identifies whale activity in real-time.
    """
    
    # Market filters
    BTC_KEYWORDS = ['bitcoin', 'btc', 'crypto']
    TIMEFRAMES = ['5 minute', '5min', '5m']
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the BTC market scanner."""
        self.config = config or Config.from_env()
        self.active_markets: Dict[str, BTCMarket] = {}
        self.price_buffers: Dict[str, List[PriceTick]] = {}
        self.callbacks: List[Callable] = []
        self.running = False
        
        # WebSocket connection
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.ws = None
        
        # Analysis windows
        self.TICK_BUFFER_SIZE = 300  # 5 minutes of 1-second ticks
        self.VOLUME_WINDOW = 60  # 1 minute for volume analysis
        
        logger.info("BTC Market Scanner initialized")
    
    def is_btc_5min_market(self, market_data: Dict) -> bool:
        """
        Check if market is a BTC 5-minute market.
        
        Args:
            market_data: Market metadata from API
            
        Returns:
            True if BTC 5-min market
        """
        question = market_data.get('question', '').lower()
        description = market_data.get('description', '').lower()
        text = f"{question} {description}"
        
        # Check for BTC keywords
        has_btc = any(kw in text for kw in self.BTC_KEYWORDS)
        
        # Check for 5-minute timeframe
        has_5min = any(tf in text for tf in self.TIMEFRAMES)
        
        # Check category
        category = market_data.get('category', '').lower()
        is_crypto = category == 'crypto' or 'cryptocurrency' in category
        
        return has_btc and (has_5min or is_crypto)
    
    async def scan_markets(self) -> List[BTCMarket]:
        """
        Scan for all active BTC 5-minute markets.
        
        Returns:
            List of BTCMarket objects
        """
        from .gamma_client import GammaClient
        
        gamma = GammaClient()
        markets = []
        
        try:
            # Get active crypto markets
            all_markets = gamma.get_markets(
                active=True,
                limit=500,
                category='Crypto'
            )
            
            for _, market in all_markets.iterrows():
                if self.is_btc_5min_market(market.to_dict()):
                    btc_market = self._create_btc_market(market)
                    if btc_market.is_active:
                        markets.append(btc_market)
                        self.active_markets[btc_market.market_id] = btc_market
            
            logger.info(f"Found {len(markets)} active BTC 5-min markets")
            
        except Exception as e:
            logger.error(f"Market scan failed: {e}")
        
        return markets
    
    def _create_btc_market(self, market_data: pd.Series) -> BTCMarket:
        """Create BTCMarket from Gamma API data."""
        # Parse timestamps
        created = pd.to_datetime(market_data.get('createdAt', datetime.now()))
        expires = pd.to_datetime(market_data.get('endDate', datetime.now()))
        
        # Get prices
        outcomes = market_data.get('outcomes', ['Yes', 'No'])
        prices = market_data.get('outcomePrices', [0.5, 0.5])
        
        yes_price = float(prices[0]) if isinstance(prices, list) else 0.5
        
        return BTCMarket(
            market_id=market_data.get('id', ''),
            condition_id=market_data.get('conditionId', ''),
            question=market_data.get('question', ''),
            created_at=created,
            expires_at=expires,
            yes_price=yes_price,
            no_price=1 - yes_price,
            implied_probability=yes_price,
        )
    
    async def subscribe_price_feeds(self):
        """Subscribe to real-time price feeds via WebSocket."""
        try:
            async with websockets.connect(self.ws_url) as ws:
                self.ws = ws
                logger.info("Connected to price feed WebSocket")
                
                # Subscribe to all active markets
                for market_id in self.active_markets:
                    subscribe_msg = {
                        "type": "subscribe",
                        "market": market_id,
                        "channels": ["trades", "orderbook"]
                    }
                    await ws.send(json.dumps(subscribe_msg))
                
                # Process incoming messages
                async for message in ws:
                    await self._process_ws_message(json.loads(message))
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await asyncio.sleep(5)
            await self.subscribe_price_feeds()  # Reconnect
    
    async def _process_ws_message(self, message: Dict):
        """Process WebSocket message."""
        msg_type = message.get('type')
        
        if msg_type == 'trade':
            await self._process_trade(message)
        elif msg_type == 'orderbook':
            await self._process_orderbook(message)
    
    async def _process_trade(self, trade_data: Dict):
        """Process trade update."""
        market_id = trade_data.get('market')
        
        if market_id not in self.active_markets:
            return
        
        market = self.active_markets[market_id]
        
        # Create price tick
        tick = PriceTick(
            timestamp=datetime.now(),
            price=float(trade_data.get('price', 0.5)),
            size=float(trade_data.get('size', 0)),
            side=trade_data.get('side', 'buy'),
            wallet=trade_data.get('maker', '').lower(),
            is_whale=float(trade_data.get('size', 0)) > 1000
        )
        
        # Add to buffer
        if market_id not in self.price_buffers:
            self.price_buffers[market_id] = []
        
        buffer = self.price_buffers[market_id]
        buffer.append(tick)
        
        # Keep only last 5 minutes
        cutoff = datetime.now() - timedelta(minutes=5)
        self.price_buffers[market_id] = [t for t in buffer if t.timestamp > cutoff]
        
        # Update market data
        market.yes_price = tick.price
        market.no_price = 1 - tick.price
        
        # Track whale activity
        if tick.is_whale:
            if tick.side == 'buy':
                if tick.price > 0.5:  # Buying YES
                    market.whale_buys_yes += tick.size
                else:  # Buying NO
                    market.whale_buys_no += tick.size
            else:  # Selling
                if tick.price > 0.5:
                    market.whale_sells_yes += tick.size
                else:
                    market.whale_sells_no += tick.size
        
        # Notify callbacks
        for callback in self.callbacks:
            await callback(market, tick)
    
    async def _process_orderbook(self, ob_data: Dict):
        """Process orderbook update."""
        market_id = ob_data.get('market')
        
        if market_id not in self.active_markets:
            return
        
        market = self.active_markets[market_id]
        
        # Update orderbook metrics
        bids = ob_data.get('bids', [])
        asks = ob_data.get('asks', [])
        
        if bids and asks:
            market.bid_yes = float(bids[0].get('price', 0))
            market.ask_yes = float(asks[0].get('price', 1))
            market.spread = market.ask_yes - market.bid_yes
            
            # Calculate depth
            market.depth_yes = sum(float(b.get('size', 0)) for b in bids)
            market.depth_no = sum(float(a.get('size', 0)) for a in asks)
    
    def calculate_micro_metrics(self, market_id: str) -> Dict:
        """
        Calculate micro-structure metrics for a market.
        
        Args:
            market_id: Market to analyze
            
        Returns:
            Dictionary of metrics
        """
        if market_id not in self.price_buffers:
            return {}
        
        buffer = self.price_buffers[market_id]
        
        if len(buffer) < 10:
            return {}
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'timestamp': t.timestamp,
                'price': t.price,
                'size': t.size,
                'side': t.side,
                'is_whale': t.is_whale
            }
            for t in buffer
        ])
        
        # Calculate metrics
        metrics = {
            'price_change_5min': (df['price'].iloc[-1] - df['price'].iloc[0]) / df['price'].iloc[0],
            'volatility': df['price'].std(),
            'volume': df['size'].sum(),
            'trade_count': len(df),
            'buy_sell_ratio': len(df[df['side'] == 'buy']) / len(df) if len(df) > 0 else 0.5,
            'avg_trade_size': df['size'].mean(),
            'whale_participation': df['is_whale'].mean(),
            'price_momentum': self._calculate_momentum(df['price']),
            'volume_imbalance': self._calculate_volume_imbalance(df),
        }
        
        return metrics
    
    def _calculate_momentum(self, prices: pd.Series) -> float:
        """Calculate price momentum (rate of change)."""
        if len(prices) < 10:
            return 0.0
        
        # Short-term vs long-term moving average
        short_ma = prices.tail(10).mean()
        long_ma = prices.mean()
        
        if long_ma == 0:
            return 0.0
        
        return (short_ma - long_ma) / long_ma
    
    def _calculate_volume_imbalance(self, df: pd.DataFrame) -> float:
        """Calculate buy/sell volume imbalance."""
        buy_volume = df[df['side'] == 'buy']['size'].sum()
        sell_volume = df[df['side'] == 'sell']['size'].sum()
        
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
    
    def detect_regime(self, market_id: str) -> MarketRegime:
        """
        Detect current market regime.
        
        Args:
            market_id: Market to analyze
            
        Returns:
            MarketRegime classification
        """
        metrics = self.calculate_micro_metrics(market_id)
        
        if not metrics:
            return MarketRegime.RANGING
        
        momentum = metrics.get('price_momentum', 0)
        volatility = metrics.get('volatility', 0)
        volume = metrics.get('volume', 0)
        
        # Regime detection logic
        if volatility > 0.1:  # High volatility threshold
            if abs(momentum) > 0.05:
                return MarketRegime.HIGH_VOLATILITY
            return MarketRegime.BREAKOUT_PENDING
        
        if volatility < 0.02:  # Low volatility
            return MarketRegime.LOW_VOLATILITY
        
        if momentum > 0.03:
            return MarketRegime.TRENDING_UP
        elif momentum < -0.03:
            return MarketRegime.TRENDING_DOWN
        
        # Check for reversal signals
        if abs(momentum) > 0.02 and volume > metrics.get('avg_trade_size', 0) * 10:
            return MarketRegime.REVERSAL_IMMINENT
        
        return MarketRegime.RANGING
    
    def register_callback(self, callback: Callable):
        """Register a callback for real-time updates."""
        self.callbacks.append(callback)
    
    async def start(self):
        """Start the market scanner."""
        self.running = True
        
        # Initial scan
        await self.scan_markets()
        
        # Start WebSocket feed
        await self.subscribe_price_feeds()
    
    def stop(self):
        """Stop the scanner."""
        self.running = False
        logger.info("Market scanner stopped")
