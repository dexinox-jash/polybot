"""
Micro-Whale Tracker for BTC 5-Minute Markets

Specialized whale tracking for high-frequency, short-term trading.
Focuses on:
- Entry/exit timing precision
- Order flow toxicity
- Latency arbitrage detection
- Micro-structure alpha
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from ..utils.logger import setup_logging
from ..utils.config import Config

logger = setup_logging()


@dataclass
class TradeExecution:
    """Individual trade execution with micro-structure data."""
    timestamp: datetime
    market_id: str
    side: str  # 'yes' or 'no'
    action: str  # 'buy' or 'sell'
    price: float
    size: float
    position_before: float
    position_after: float
    pnl_realized: float = 0.0
    
    # Micro-structure
    slippage: float = 0.0  # Difference from mid-price
    execution_time_ms: int = 0  # Time from decision to fill
    spread_at_entry: float = 0.0
    depth_consumed: float = 0.0  # % of order book depth used


@dataclass
class TradeSession:
    """A continuous trading session."""
    market_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    trades: List[TradeExecution] = field(default_factory=list)
    
    # Performance
    gross_pnl: float = 0.0
    fees_paid: float = 0.0
    net_pnl: float = 0.0
    
    @property
    def duration_seconds(self) -> float:
        """Session duration."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    @property
    def trade_count(self) -> int:
        return len(self.trades)
    
    @property
    def avg_trade_size(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.size for t in self.trades])


@dataclass 
class TraderProfile:
    """Comprehensive trader profile for 5-min BTC markets."""
    address: str
    name: Optional[str] = None
    
    # Performance metrics
    total_sessions: int = 0
    winning_sessions: int = 0
    losing_sessions: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Timing metrics (crucial for 5-min markets)
    avg_entry_timing: float = 0.0  # Seconds from market open
    avg_exit_timing: float = 0.0   # Seconds before market close
    avg_hold_time: float = 0.0     # Average position hold time
    
    # Execution quality
    avg_slippage: float = 0.0
    avg_execution_time_ms: float = 0.0
    
    # Strategy characteristics
    preferred_regimes: List[str] = field(default_factory=list)
    avg_position_size: float = 0.0
    max_position_size: float = 0.0
    size_consistency: float = 0.0  # Coefficient of variation
    
    # Edge detection
    alpha_sources: Dict[str, float] = field(default_factory=dict)
    
    # Recent activity (last 24h)
    recent_sessions: deque = field(default_factory=lambda: deque(maxlen=100))
    recent_pnl: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update_performance(self):
        """Recalculate performance metrics."""
        if self.total_sessions > 0:
            self.win_rate = self.winning_sessions / self.total_sessions
        
        # Calculate profit factor
        winning_pnl = sum(s.gross_pnl for s in self.recent_sessions if s.gross_pnl > 0)
        losing_pnl = abs(sum(s.gross_pnl for s in self.recent_sessions if s.gross_pnl < 0))
        
        if losing_pnl > 0:
            self.profit_factor = winning_pnl / losing_pnl
        else:
            self.profit_factor = float('inf') if winning_pnl > 0 else 0
    
    @property
    def is_hot(self) -> bool:
        """Check if trader is currently performing well."""
        if len(self.recent_pnl) < 5:
            return False
        recent_wr = sum(1 for p in list(self.recent_pnl)[-5:] if p > 0) / 5
        return recent_wr >= 0.6 and self.profit_factor > 1.5
    
    @property
    def is_dangerous(self) -> bool:
        """Check if trader might be toxic/smart money."""
        # Low slippage + fast execution = likely informed
        return (self.avg_slippage < 0.001 and 
                self.avg_execution_time_ms < 500 and
                self.win_rate > 0.55)


class MicroWhaleTracker:
    """
    High-frequency whale tracker for BTC 5-minute markets.
    
    Tracks micro-structure, execution quality, and timing precision
    to identify the most sophisticated short-term traders.
    """
    
    # Thresholds for whale classification in 5-min markets
    WHALE_MIN_SIZE = 500  # Minimum trade size to be considered
    WHALE_MIN_VOLUME = 5000  # Minimum daily volume
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize micro-whale tracker."""
        self.config = config or Config.from_env()
        self.traders: Dict[str, TraderProfile] = {}
        self.active_sessions: Dict[str, TradeSession] = {}
        self.market_participants: Dict[str, set] = defaultdict(set)
        
        # Real-time buffers
        self.recent_trades: deque = deque(maxlen=10000)
        
        logger.info("Micro-Whale Tracker initialized")
    
    def add_trader(self, address: str, name: Optional[str] = None):
        """Add a trader to track."""
        address = address.lower()
        if address not in self.traders:
            self.traders[address] = TraderProfile(address=address, name=name)
            logger.info(f"Added trader: {name or address[:10]}")
    
    def process_trade(self, market_id: str, trade_data: Dict) -> Optional[TradeExecution]:
        """
        Process a trade and update trader profile.
        
        Args:
            market_id: Market condition ID
            trade_data: Trade information
            
        Returns:
            TradeExecution if processed, None if ignored
        """
        wallet = trade_data.get('maker', '').lower()
        size = float(trade_data.get('size', 0))
        
        # Filter small trades
        if size < self.WHALE_MIN_SIZE:
            return None
        
        # Add trader if new
        if wallet not in self.traders:
            self.add_trader(wallet)
        
        trader = self.traders[wallet]
        
        # Create execution record
        execution = TradeExecution(
            timestamp=datetime.now(),
            market_id=market_id,
            side=trade_data.get('side', 'yes'),
            action=trade_data.get('action', 'buy'),
            price=float(trade_data.get('price', 0.5)),
            size=size,
            position_before=0.0,  # Would need position tracking
            position_after=size,
            slippage=float(trade_data.get('slippage', 0)),
            execution_time_ms=int(trade_data.get('exec_time', 0)),
            spread_at_entry=float(trade_data.get('spread', 0.01)),
        )
        
        # Update or create session
        session_key = f"{wallet}:{market_id}"
        
        if session_key not in self.active_sessions:
            self.active_sessions[session_key] = TradeSession(
                market_id=market_id,
                start_time=execution.timestamp,
            )
        
        session = self.active_sessions[session_key]
        session.trades.append(execution)
        
        # Update trader metrics
        self._update_trader_metrics(trader, execution)
        
        # Track market participation
        self.market_participants[market_id].add(wallet)
        
        # Store recent trade
        self.recent_trades.append({
            'timestamp': execution.timestamp,
            'wallet': wallet,
            'market': market_id,
            'size': size,
            'price': execution.price,
        })
        
        return execution
    
    def _update_trader_metrics(self, trader: TraderProfile, execution: TradeExecution):
        """Update trader metrics from execution."""
        # Execution quality
        trader.avg_slippage = (
            trader.avg_slippage * (trader.total_sessions) + execution.slippage
        ) / (trader.total_sessions + 1)
        
        trader.avg_execution_time_ms = (
            trader.avg_execution_time_ms * (trader.total_sessions) + execution.execution_time_ms
        ) / (trader.total_sessions + 1)
        
        # Position sizing
        trader.avg_position_size = (
            trader.avg_position_size * (trader.total_sessions) + execution.size
        ) / (trader.total_sessions + 1)
        
        trader.max_position_size = max(trader.max_position_size, execution.size)
    
    def close_session(self, wallet: str, market_id: str, final_pnl: float):
        """
        Close a trading session and update performance.
        
        Args:
            wallet: Trader address
            market_id: Market ID
            final_pnl: Final realized PnL
        """
        session_key = f"{wallet}:{market_id}"
        
        if session_key not in self.active_sessions:
            return
        
        session = self.active_sessions[session_key]
        session.end_time = datetime.now()
        session.gross_pnl = final_pnl
        session.net_pnl = final_pnl - session.fees_paid
        
        # Update trader
        trader = self.traders[wallet]
        trader.total_sessions += 1
        trader.total_pnl += session.net_pnl
        
        if session.net_pnl > 0:
            trader.winning_sessions += 1
        else:
            trader.losing_sessions += 1
        
        # Update recent activity
        trader.recent_sessions.append(session)
        trader.recent_pnl.append(session.net_pnl)
        
        # Recalculate performance
        trader.update_performance()
        
        # Clean up
        del self.active_sessions[session_key]
        
        logger.debug(f"Closed session for {wallet}: PnL=${final_pnl:.2f}")
    
    def detect_timing_alpha(self, wallet: str) -> Dict:
        """
        Detect if trader has timing alpha (good entry/exit).
        
        Args:
            wallet: Trader address
            
        Returns:
            Timing analysis results
        """
        if wallet not in self.traders:
            return {}
        
        trader = self.traders[wallet]
        sessions = list(trader.recent_sessions)
        
        if len(sessions) < 10:
            return {'confidence': 'low', 'sample_size': len(sessions)}
        
        # Analyze entry timing
        entry_times = []
        exit_times = []
        
        for session in sessions:
            if session.trades:
                first_trade = session.trades[0]
                last_trade = session.trades[-1]
                
                entry_times.append(first_trade.execution_time_ms)
                
                # Exit timing (if session closed)
                if session.end_time:
                    market_duration = 300  # 5 minutes in seconds
                    session_duration = session.duration_seconds
                    exit_time_before_close = market_duration - session_duration
                    exit_times.append(exit_time_before_close)
        
        analysis = {
            'confidence': 'medium' if len(sessions) >= 20 else 'low',
            'sample_size': len(sessions),
            'avg_entry_speed_ms': np.mean(entry_times) if entry_times else 0,
            'entry_consistency': 1 - (np.std(entry_times) / np.mean(entry_times)) if entry_times and np.mean(entry_times) > 0 else 0,
            'avg_exit_buffer_sec': np.mean(exit_times) if exit_times else 0,
        }
        
        # Determine if they have timing edge
        if analysis['entry_consistency'] > 0.7 and analysis['avg_entry_speed_ms'] < 1000:
            analysis['timing_edge'] = True
            analysis['edge_type'] = 'speed'
        elif analysis['avg_exit_buffer_sec'] > 30:
            analysis['timing_edge'] = True
            analysis['edge_type'] = 'patience'
        else:
            analysis['timing_edge'] = False
        
        return analysis
    
    def detect_order_flow_toxicity(self, market_id: str, lookback_seconds: int = 60) -> Dict:
        """
        Detect toxic/smart order flow in a market.
        
        Args:
            market_id: Market to analyze
            lookback_seconds: Time window
            
        Returns:
            Toxicity metrics
        """
        cutoff = datetime.now() - timedelta(seconds=lookback_seconds)
        
        # Filter recent trades for this market
        market_trades = [
            t for t in self.recent_trades
            if t['market'] == market_id and t['timestamp'] > cutoff
        ]
        
        if len(market_trades) < 5:
            return {'toxicity_score': 0, 'confidence': 'low'}
        
        # Analyze by wallet
        wallet_stats = defaultdict(lambda: {'count': 0, 'size': 0, 'avg_price': []})
        
        for trade in market_trades:
            wallet = trade['wallet']
            wallet_stats[wallet]['count'] += 1
            wallet_stats[wallet]['size'] += trade['size']
            wallet_stats[wallet]['avg_price'].append(trade['price'])
        
        # Detect toxicity signals
        toxicity_signals = []
        
        for wallet, stats in wallet_stats.items():
            if wallet in self.traders:
                trader = self.traders[wallet]
                
                # Signal 1: Known hot trader entering
                if trader.is_hot and stats['size'] > trader.avg_position_size * 1.5:
                    toxicity_signals.append({
                        'type': 'hot_trader',
                        'wallet': wallet,
                        'severity': 'high',
                        'size': stats['size']
                    })
                
                # Signal 2: Dangerous trader (low slippage, fast)
                if trader.is_dangerous:
                    toxicity_signals.append({
                        'type': 'informed_trader',
                        'wallet': wallet,
                        'severity': 'medium',
                        'info': 'fast_execution'
                    })
        
        # Calculate aggregate toxicity score
        toxicity_score = sum(
            3 if s['severity'] == 'high' else 1
            for s in toxicity_signals
        )
        
        return {
            'toxicity_score': min(10, toxicity_score),
            'signals': toxicity_signals,
            'trade_count': len(market_trades),
            'unique_traders': len(wallet_stats),
            'confidence': 'high' if len(market_trades) > 20 else 'medium'
        }
    
    def get_top_performers(self, min_sessions: int = 10) -> pd.DataFrame:
        """
        Get top performing traders.
        
        Args:
            min_sessions: Minimum sessions for qualification
            
        Returns:
            DataFrame of top traders
        """
        qualified = [
            t for t in self.traders.values()
            if t.total_sessions >= min_sessions
        ]
        
        if not qualified:
            return pd.DataFrame()
        
        data = []
        for trader in qualified:
            data.append({
                'address': trader.address,
                'name': trader.name,
                'win_rate': trader.win_rate,
                'profit_factor': trader.profit_factor,
                'total_pnl': trader.total_pnl,
                'total_sessions': trader.total_sessions,
                'is_hot': trader.is_hot,
                'is_dangerous': trader.is_dangerous,
                'avg_position': trader.avg_position_size,
                'avg_slippage': trader.avg_slippage,
                'avg_exec_time_ms': trader.avg_execution_time_ms,
            })
        
        df = pd.DataFrame(data)
        
        # Score calculation (composite)
        df['score'] = (
            df['win_rate'] * 0.3 +
            (df['profit_factor'] / 5).clip(0, 1) * 0.3 +
            (df['total_pnl'] / df['total_pnl'].max()).fillna(0) * 0.2 +
            (1 - df['avg_slippage'] * 100) * 0.1 +
            (1 - df['avg_exec_time_ms'] / 2000) * 0.1
        )
        
        return df.sort_values('score', ascending=False)
    
    def get_leaderboard(self, timeframe_hours: int = 24) -> pd.DataFrame:
        """
        Get leaderboard for recent performance.
        
        Args:
            timeframe_hours: Time window for recent performance
            
        Returns:
            Leaderboard DataFrame
        """
        cutoff = datetime.now() - timedelta(hours=timeframe_hours)
        
        recent_performers = []
        
        for trader in self.traders.values():
            recent_sessions = [
                s for s in trader.recent_sessions
                if s.start_time > cutoff
            ]
            
            if len(recent_sessions) < 2:
                continue
            
            recent_pnl = sum(s.net_pnl for s in recent_sessions)
            recent_wr = sum(1 for s in recent_sessions if s.net_pnl > 0) / len(recent_sessions)
            
            recent_performers.append({
                'address': trader.address,
                'name': trader.name,
                'recent_pnl': recent_pnl,
                'recent_wr': recent_wr,
                'sessions': len(recent_sessions),
                'avg_session_pnl': recent_pnl / len(recent_sessions),
            })
        
        df = pd.DataFrame(recent_performers)
        if not df.empty:
            df = df.sort_values('recent_pnl', ascending=False)
        
        return df
