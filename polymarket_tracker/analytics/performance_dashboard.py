"""
Performance Analytics Dashboard Module

Comprehensive analytics and reporting for PolyBot trading performance.
Provides portfolio tracking, trade analysis, whale rankings, risk metrics,
and automated report generation.
"""

import asyncio
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd
from scipy import stats

from ..utils.config import Config
from ..utils.logger import setup_logging

logger = setup_logging()


class ChartType(Enum):
    """Types of charts supported."""
    EQUITY = "equity"
    DRAWDOWN = "drawdown"
    TRADE_DISTRIBUTION = "trade_distribution"
    PATTERN_PIE = "pattern_pie"
    MONTHLY_RETURNS = "monthly_returns"
    WIN_RATE_BY_PATTERN = "win_rate_by_pattern"
    WHALE_PERFORMANCE = "whale_performance"
    RISK_METRICS = "risk_metrics"
    TIMING_ANALYSIS = "timing_analysis"
    LIQUIDITY_SLIPPAGE = "liquidity_slippage"


@dataclass
class PortfolioSummary:
    """Portfolio summary metrics."""
    current_value: float
    initial_value: float
    total_pnl: float
    total_pnl_percent: float
    realized_pnl: float
    unrealized_pnl: float
    open_positions: int
    available_balance: float
    total_exposure: float
    exposure_percent: float
    peak_value: float
    current_drawdown: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DrawdownAnalysis:
    """Comprehensive drawdown analysis."""
    max_drawdown: float
    max_drawdown_start: Optional[datetime] = None
    max_drawdown_end: Optional[datetime] = None
    max_drawdown_duration: timedelta = field(default_factory=lambda: timedelta(0))
    current_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    avg_recovery_time: timedelta = field(default_factory=lambda: timedelta(0))
    drawdowns: List[Dict] = field(default_factory=list)
    recovery_times: List[timedelta] = field(default_factory=list)


@dataclass
class TradeStats:
    """Comprehensive trade statistics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    loss_rate: float
    breakeven_rate: float
    
    avg_win: float
    avg_loss: float
    avg_trade: float
    median_trade: float
    
    largest_win: float
    largest_loss: float
    
    profit_factor: float
    payoff_ratio: float
    expectancy: float
    expectancy_percent: float
    
    avg_r_multiple: float
    max_r_multiple: float
    min_r_multiple: float
    
    avg_trade_duration: timedelta
    median_trade_duration: timedelta
    avg_win_duration: timedelta
    avg_loss_duration: timedelta
    
    gross_profit: float
    gross_loss: float
    net_pnl: float


@dataclass
class WhaleRanking:
    """Whale performance ranking."""
    whale_address: str
    whale_name: Optional[str] = None
    
    # Copy performance
    copy_trades: int = 0
    copy_wins: int = 0
    copy_losses: int = 0
    copy_win_rate: float = 0.0
    copy_pnl: float = 0.0
    copy_profit_factor: float = 0.0
    
    # Correlation
    correlation_with_us: float = 0.0
    correlation_strength: str = "none"  # none, weak, moderate, strong
    
    # Timing
    avg_copy_delay: timedelta = field(default_factory=lambda: timedelta(0))
    avg_slippage: float = 0.0
    
    # Recommendation
    copy_score: float = 0.0
    recommendation: str = "neutral"  # avoid, neutral, good, excellent
    
    # Pattern performance
    pattern_performance: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics."""
    var_95: float  # Value at Risk (95% confidence)
    var_99: float  # Value at Risk (99% confidence)
    cvar_95: float  # Conditional VaR (95%)
    cvar_99: float  # Conditional VaR (99%)
    
    volatility_daily: float
    volatility_monthly: float
    volatility_annual: float
    
    beta: float
    alpha: float
    correlation_to_market: float
    
    skewness: float
    kurtosis: float
    
    max_consecutive_wins: int
    max_consecutive_losses: int
    current_streak: int
    streak_type: str = "none"  # win, loss, none
    
    ulcer_index: float
    serenity_index: float
    
    risk_of_ruin: float
    expected_max_drawdown: float
    
    tail_ratio: float
    upside_potential: float
    downside_risk: float


@dataclass
class MarketPerformance:
    """Performance by market category."""
    category: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl: float
    avg_trade: float
    max_win: float
    max_loss: float
    avg_slippage: float
    avg_liquidity: float


@dataclass
class ChartData:
    """Data formatted for charting."""
    chart_type: ChartType
    labels: List[str]
    datasets: List[Dict[str, Any]]
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyReport:
    """Daily performance report."""
    date: datetime
    
    # Summary
    starting_value: float
    ending_value: float
    daily_pnl: float
    daily_return: float
    
    # Trades
    trades_today: int
    wins: int
    losses: int
    win_rate: float
    
    # Positions
    positions_opened: int
    positions_closed: int
    open_positions: int
    
    # Risk
    max_drawdown_today: float
    var_95_today: float
    
    # Highlights
    best_trade: Optional[Dict] = None
    worst_trade: Optional[Dict] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class WeeklyReport:
    """Weekly performance report."""
    week_start: datetime
    week_end: datetime
    
    # Performance
    starting_value: float
    ending_value: float
    weekly_pnl: float
    weekly_return: float
    
    # Trading activity
    total_trades: int
    win_rate: float
    profit_factor: float
    
    # Daily breakdown
    daily_returns: List[Dict] = field(default_factory=list)
    
    # Pattern performance
    pattern_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # Whale tracking
    top_whales: List[WhaleRanking] = field(default_factory=list)
    
    # Risk metrics
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    
    # Insights
    insights: List[str] = field(default_factory=list)
    areas_for_improvement: List[str] = field(default_factory=list)


@dataclass
class MonthlyReport:
    """Monthly performance report."""
    month: datetime
    
    # Performance summary
    starting_value: float
    ending_value: float
    monthly_pnl: float
    monthly_return: float
    ytd_return: float
    
    # Trading statistics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    
    # Risk analysis
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # Pattern analysis
    pattern_breakdown: Dict[str, Dict] = field(default_factory=dict)
    best_pattern: Optional[str] = None
    worst_pattern: Optional[str] = None
    
    # Whale analysis
    whale_leaderboard: List[WhaleRanking] = field(default_factory=list)
    best_whales_to_copy: List[str] = field(default_factory=list)
    whales_to_avoid: List[str] = field(default_factory=list)
    
    # Market analysis
    market_performance: List[MarketPerformance] = field(default_factory=list)
    best_category: Optional[str] = None
    worst_category: Optional[str] = None
    
    # Comparison
    vs_previous_month: Optional[Dict] = None
    vs_average: Optional[Dict] = None
    
    # Goals
    goals_achieved: List[str] = field(default_factory=list)
    goals_missed: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Charts data
    chart_data: Dict[str, ChartData] = field(default_factory=dict)


class PerformanceDashboard:
    """
    Comprehensive performance analytics dashboard.
    
    Provides:
    - Portfolio analytics (equity curve, drawdown, rolling returns)
    - Trade analytics (statistics, distribution, streaks, timing)
    - Whale performance tracking and rankings
    - Market analytics by category
    - Risk metrics (VaR, CVaR, tail risk)
    - Automated report generation
    - Chart data for visualization
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        cache_ttl: int = 300,  # 5 minutes default cache
        bankroll: float = 10000.0
    ):
        """
        Initialize performance dashboard.
        
        Args:
            db_path: Path to SQLite database (defaults to config)
            cache_ttl: Cache time-to-live in seconds
            bankroll: Initial bankroll for calculations
        """
        self.config = Config.from_env()
        self.db_path = db_path or self.config.database_url.replace("sqlite:///", "")
        self.cache_ttl = cache_ttl
        self.initial_bankroll = bankroll
        
        # In-memory cache
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        
        # Ensure database connection works
        self._init_database()
        
        logger.info(f"PerformanceDashboard initialized with db: {self.db_path}")
    
    def _init_database(self):
        """Initialize database tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Trades table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT UNIQUE,
                        market_id TEXT,
                        market_question TEXT,
                        direction TEXT,
                        entry_price REAL,
                        exit_price REAL,
                        size REAL,
                        entry_time TIMESTAMP,
                        exit_time TIMESTAMP,
                        pnl REAL,
                        pnl_percent REAL,
                        exit_reason TEXT,
                        whale_address TEXT,
                        pattern_type TEXT,
                        slippage REAL,
                        liquidity REAL,
                        r_multiple REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Portfolio snapshots table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_value REAL,
                        available_balance REAL,
                        total_exposure REAL,
                        open_positions INTEGER,
                        daily_pnl REAL,
                        total_pnl REAL,
                        drawdown_percent REAL
                    )
                """)
                
                # Whale copy performance table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS whale_copy_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        whale_address TEXT,
                        trade_id TEXT,
                        our_pnl REAL,
                        whale_pnl REAL,
                        copy_delay_seconds REAL,
                        slippage REAL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(whale_address, trade_id)
                    )
                """)
                
                conn.commit()
                logger.debug("Database tables initialized")
        except Exception as e:
            logger.warning(f"Database initialization error: {e}")
    
    # ==================== Cache Management ====================
    
    def _get_cache_key(self, method_name: str, *args, **kwargs) -> str:
        """Generate cache key for method call."""
        key_data = f"{method_name}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                return value
            else:
                del self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any):
        """Cache a value."""
        self._cache[key] = (value, datetime.now())
    
    def clear_cache(self):
        """Clear all cached data."""
        self._cache.clear()
        logger.debug("Cache cleared")
    
    # ==================== Database Helpers ====================
    
    def _execute_query(self, query: str, params: Tuple = ()) -> pd.DataFrame:
        """Execute SQL query and return DataFrame."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql_query(query, conn, params=params)
        except Exception as e:
            logger.error(f"Query error: {e}")
            return pd.DataFrame()
    
    def _get_trades_df(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> pd.DataFrame:
        """Get trades as DataFrame with optional date filtering."""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date.isoformat())
        
        query += " ORDER BY entry_time"
        
        df = self._execute_query(query, tuple(params))
        
        if not df.empty:
            for col in ['entry_time', 'exit_time', 'created_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df
    
    def _get_portfolio_snapshots(self, days: int = 30) -> pd.DataFrame:
        """Get portfolio snapshots for specified days."""
        query = """
            SELECT * FROM portfolio_snapshots 
            WHERE timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp
        """.format(days)
        
        df = self._execute_query(query)
        
        if not df.empty and 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df


    # ==================== 1. Portfolio Analytics ====================
    
    async def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Get current portfolio summary with P&L and positions.
        
        Returns:
            PortfolioSummary with current metrics
        """
        cache_key = self._get_cache_key("get_portfolio_summary")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get latest portfolio snapshot
            snapshots = self._get_portfolio_snapshots(days=1)
            
            if snapshots.empty:
                # No data yet, return default
                summary = PortfolioSummary(
                    current_value=self.initial_bankroll,
                    initial_value=self.initial_bankroll,
                    total_pnl=0.0,
                    total_pnl_percent=0.0,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    open_positions=0,
                    available_balance=self.initial_bankroll,
                    total_exposure=0.0,
                    exposure_percent=0.0,
                    peak_value=self.initial_bankroll,
                    current_drawdown=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    sortino_ratio=0.0,
                    calmar_ratio=0.0
                )
            else:
                latest = snapshots.iloc[-1]
                
                # Calculate metrics
                total_pnl = latest.get('total_pnl', 0)
                total_pnl_percent = (total_pnl / self.initial_bankroll) * 100
                
                # Get historical data for risk metrics
                historical = self._get_portfolio_snapshots(days=30)
                
                sharpe = 0.0
                sortino = 0.0
                calmar = 0.0
                max_dd = 0.0
                peak = self.initial_bankroll
                
                if len(historical) > 1:
                    returns = historical['total_value'].pct_change().dropna()
                    
                    if len(returns) > 0 and returns.std() > 0:
                        sharpe = (returns.mean() / returns.std()) * np.sqrt(365)
                        
                        # Sortino (downside deviation only)
                        downside = returns[returns < 0]
                        if len(downside) > 0 and downside.std() > 0:
                            sortino = (returns.mean() / downside.std()) * np.sqrt(365)
                    
                    # Max drawdown
                    rolling_max = historical['total_value'].expanding().max()
                    drawdown = (historical['total_value'] - rolling_max) / rolling_max
                    max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
                    peak = rolling_max.max()
                    
                    # Calmar ratio
                    if max_dd > 0:
                        annual_return = (latest['total_value'] / self.initial_bankroll) ** (365 / len(historical)) - 1
                        calmar = annual_return / max_dd
                
                current_dd = 0.0
                if peak > 0 and latest['total_value'] < peak:
                    current_dd = (peak - latest['total_value']) / peak
                
                summary = PortfolioSummary(
                    current_value=latest.get('total_value', self.initial_bankroll),
                    initial_value=self.initial_bankroll,
                    total_pnl=total_pnl,
                    total_pnl_percent=total_pnl_percent,
                    realized_pnl=latest.get('total_pnl', 0) - 0,  # Simplified
                    unrealized_pnl=0,  # Would need position data
                    open_positions=int(latest.get('open_positions', 0)),
                    available_balance=latest.get('available_balance', self.initial_bankroll),
                    total_exposure=latest.get('total_exposure', 0),
                    exposure_percent=latest.get('total_exposure', 0) / latest['total_value'] * 100 if latest['total_value'] > 0 else 0,
                    peak_value=peak,
                    current_drawdown=current_dd,
                    max_drawdown=max_dd,
                    sharpe_ratio=sharpe,
                    sortino_ratio=sortino,
                    calmar_ratio=calmar
                )
            
            self._set_cached(cache_key, summary)
            return summary
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            raise
    
    async def get_equity_curve(self, days: int = 30) -> pd.DataFrame:
        """
        Get daily portfolio value over time.
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with date and portfolio_value columns
        """
        cache_key = self._get_cache_key("get_equity_curve", days)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self._get_portfolio_snapshots(days=days)
            
            if df.empty:
                # Return default curve
                dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
                df = pd.DataFrame({
                    'date': dates,
                    'portfolio_value': [self.initial_bankroll] * days
                })
            else:
                df = df.rename(columns={'timestamp': 'date', 'total_value': 'portfolio_value'})
                df = df[['date', 'portfolio_value']].copy()
            
            # Calculate daily returns
            df['daily_return'] = df['portfolio_value'].pct_change()
            df['cumulative_return'] = (df['portfolio_value'] / self.initial_bankroll - 1) * 100
            
            self._set_cached(cache_key, df)
            return df
            
        except Exception as e:
            logger.error(f"Error getting equity curve: {e}")
            raise
    
    async def get_drawdown_analysis(self) -> DrawdownAnalysis:
        """
        Get comprehensive drawdown analysis.
        
        Returns:
            DrawdownAnalysis with max drawdown, recovery time, etc.
        """
        cache_key = self._get_cache_key("get_drawdown_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_portfolio_snapshots(days=90)  # Get 90 days for analysis
            
            if df.empty or len(df) < 2:
                return DrawdownAnalysis(max_drawdown=0.0)
            
            # Calculate drawdowns
            df['rolling_max'] = df['total_value'].expanding().max()
            df['drawdown'] = (df['total_value'] - df['rolling_max']) / df['rolling_max']
            
            # Find max drawdown
            max_dd_idx = df['drawdown'].idxmin()
            max_dd = abs(df.loc[max_dd_idx, 'drawdown'])
            max_dd_start = None
            max_dd_end = df.loc[max_dd_idx, 'timestamp']
            
            # Find drawdown start (peak before max drawdown)
            for i in range(max_dd_idx - 1, -1, -1):
                if df.loc[i, 'total_value'] >= df.loc[max_dd_idx, 'rolling_max']:
                    max_dd_start = df.loc[i, 'timestamp']
                    break
            
            # Calculate drawdown duration
            duration = timedelta(0)
            if max_dd_start and max_dd_end:
                duration = max_dd_end - max_dd_start
            
            # Find all drawdowns
            drawdowns = []
            in_drawdown = False
            dd_start = None
            dd_peak_value = 0
            
            for idx, row in df.iterrows():
                if row['drawdown'] < -0.01 and not in_drawdown:  # 1% threshold
                    in_drawdown = True
                    dd_start = row['timestamp']
                    dd_peak_value = row['rolling_max']
                elif row['drawdown'] >= 0 and in_drawdown:
                    in_drawdown = False
                    if dd_start:
                        dd_end = row['timestamp']
                        dd_max = (dd_peak_value - df.loc[dd_start:dd_end, 'total_value'].min()) / dd_peak_value
                        drawdowns.append({
                            'start': dd_start,
                            'end': dd_end,
                            'max_drawdown': dd_max,
                            'duration': dd_end - dd_start
                        })
            
            # Calculate average drawdown
            avg_dd = np.mean([d['max_drawdown'] for d in drawdowns]) if drawdowns else 0
            
            # Calculate recovery times
            recovery_times = [d['duration'] for d in drawdowns if d['duration'] > timedelta(0)]
            avg_recovery = np.mean(recovery_times) if recovery_times else timedelta(0)
            
            current_dd = abs(df['drawdown'].iloc[-1]) if not df.empty else 0
            
            analysis = DrawdownAnalysis(
                max_drawdown=max_dd,
                max_drawdown_start=max_dd_start,
                max_drawdown_end=max_dd_end,
                max_drawdown_duration=duration,
                current_drawdown=current_dd,
                avg_drawdown=avg_dd,
                avg_recovery_time=avg_recovery,
                drawdowns=drawdowns,
                recovery_times=recovery_times
            )
            
            self._set_cached(cache_key, analysis)
            return analysis
            
        except Exception as e:
            logger.error(f"Error in drawdown analysis: {e}")
            raise
    
    async def get_rolling_returns(self, window: int = 7) -> pd.DataFrame:
        """
        Get rolling returns over specified window.
        
        Args:
            window: Rolling window in days (7, 30, etc.)
            
        Returns:
            DataFrame with rolling return metrics
        """
        cache_key = self._get_cache_key("get_rolling_returns", window)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = await self.get_equity_curve(days=window * 3)  # Get extra data for rolling calc
            
            if df.empty or len(df) < window:
                return pd.DataFrame()
            
            # Calculate rolling returns
            df[f'{window}d_return'] = df['portfolio_value'].pct_change(window) * 100
            df[f'{window}d_annualized'] = ((1 + df['portfolio_value'].pct_change(window)) ** (365/window) - 1) * 100
            
            # Calculate rolling volatility
            df[f'{window}d_volatility'] = df['daily_return'].rolling(window).std() * np.sqrt(365) * 100
            
            # Calculate rolling Sharpe
            df[f'{window}d_sharpe'] = (df[f'{window}d_annualized'] / 100) / (df[f'{window}d_volatility'] / 100)
            df[f'{window}d_sharpe'] = df[f'{window}d_sharpe'].replace([np.inf, -np.inf], np.nan)
            
            self._set_cached(cache_key, df)
            return df
            
        except Exception as e:
            logger.error(f"Error calculating rolling returns: {e}")
            raise

    # ==================== 2. Trade Analytics ====================
    
    async def get_trade_statistics(self) -> TradeStats:
        """
        Get comprehensive trade statistics.
        
        Returns:
            TradeStats with win rate, avg win/loss, etc.
        """
        cache_key = self._get_cache_key("get_trade_statistics")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty:
                return TradeStats(
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    breakeven_trades=0,
                    win_rate=0.0,
                    loss_rate=0.0,
                    breakeven_rate=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                    avg_trade=0.0,
                    median_trade=0.0,
                    largest_win=0.0,
                    largest_loss=0.0,
                    profit_factor=0.0,
                    payoff_ratio=0.0,
                    expectancy=0.0,
                    expectancy_percent=0.0,
                    avg_r_multiple=0.0,
                    max_r_multiple=0.0,
                    min_r_multiple=0.0,
                    avg_trade_duration=timedelta(0),
                    median_trade_duration=timedelta(0),
                    avg_win_duration=timedelta(0),
                    avg_loss_duration=timedelta(0),
                    gross_profit=0.0,
                    gross_loss=0.0,
                    net_pnl=0.0
                )
            
            # Basic counts
            total = len(df)
            wins = len(df[df['pnl'] > 0])
            losses = len(df[df['pnl'] < 0])
            breakeven = len(df[df['pnl'] == 0])
            
            win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
            
            # P&L calculations
            win_df = df[df['pnl'] > 0]
            loss_df = df[df['pnl'] < 0]
            
            gross_profit = win_df['pnl'].sum() if len(win_df) > 0 else 0
            gross_loss = abs(loss_df['pnl'].sum()) if len(loss_df) > 0 else 0
            net_pnl = df['pnl'].sum()
            
            avg_win = win_df['pnl'].mean() if len(win_df) > 0 else 0
            avg_loss = loss_df['pnl'].mean() if len(loss_df) > 0 else 0
            
            # Profit factor and payoff ratio
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            # Expectancy
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
            expectancy_percent = (expectancy / df['size'].mean() * 100) if df['size'].mean() > 0 else 0
            
            # Durations
            if 'entry_time' in df.columns and 'exit_time' in df.columns:
                df['duration'] = pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])
                avg_duration = df['duration'].mean()
                median_duration = df['duration'].median()
                
                if len(win_df) > 0:
                    win_durations = pd.to_datetime(win_df['exit_time']) - pd.to_datetime(win_df['entry_time'])
                    avg_win_duration = win_durations.mean()
                else:
                    avg_win_duration = timedelta(0)
                
                if len(loss_df) > 0:
                    loss_durations = pd.to_datetime(loss_df['exit_time']) - pd.to_datetime(loss_df['entry_time'])
                    avg_loss_duration = loss_durations.mean()
                else:
                    avg_loss_duration = timedelta(0)
            else:
                avg_duration = median_duration = avg_win_duration = avg_loss_duration = timedelta(0)
            
            # R-multiples
            if 'r_multiple' in df.columns:
                avg_r = df['r_multiple'].mean()
                max_r = df['r_multiple'].max()
                min_r = df['r_multiple'].min()
            else:
                avg_r = max_r = min_r = 0.0
            
            stats = TradeStats(
                total_trades=total,
                winning_trades=wins,
                losing_trades=losses,
                breakeven_trades=breakeven,
                win_rate=win_rate,
                loss_rate=losses / total if total > 0 else 0,
                breakeven_rate=breakeven / total if total > 0 else 0,
                avg_win=avg_win,
                avg_loss=avg_loss,
                avg_trade=df['pnl'].mean(),
                median_trade=df['pnl'].median(),
                largest_win=df['pnl'].max(),
                largest_loss=df['pnl'].min(),
                profit_factor=profit_factor,
                payoff_ratio=payoff_ratio,
                expectancy=expectancy,
                expectancy_percent=expectancy_percent,
                avg_r_multiple=avg_r,
                max_r_multiple=max_r,
                min_r_multiple=min_r,
                avg_trade_duration=avg_duration if pd.notna(avg_duration) else timedelta(0),
                median_trade_duration=median_duration if pd.notna(median_duration) else timedelta(0),
                avg_win_duration=avg_win_duration if pd.notna(avg_win_duration) else timedelta(0),
                avg_loss_duration=avg_loss_duration if pd.notna(avg_loss_duration) else timedelta(0),
                gross_profit=gross_profit,
                gross_loss=gross_loss,
                net_pnl=net_pnl
            )
            
            self._set_cached(cache_key, stats)
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating trade statistics: {e}")
            raise
    
    async def get_trade_distribution(self) -> Dict[str, Any]:
        """
        Get trade size and duration distributions.
        
        Returns:
            Dictionary with distribution data
        """
        cache_key = self._get_cache_key("get_trade_distribution")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty:
                return {
                    'size_distribution': {},
                    'pnl_distribution': {},
                    'duration_distribution': {}
                }
            
            # Size distribution
            size_bins = [0, 100, 500, 1000, 5000, float('inf')]
            size_labels = ['<$100', '$100-500', '$500-1K', '$1K-5K', '>$5K']
            df['size_bucket'] = pd.cut(df['size'], bins=size_bins, labels=size_labels)
            size_dist = df.groupby('size_bucket', observed=True).agg({
                'pnl': ['count', 'sum', 'mean']
            }).to_dict()
            
            # P&L distribution
            pnl_bins = [float('-inf'), -1000, -500, -100, 0, 100, 500, 1000, float('inf')]
            pnl_labels = ['<-1000', '-1000:-500', '-500:-100', '-100:0', '0:100', '100:500', '500:1000', '>1000']
            df['pnl_bucket'] = pd.cut(df['pnl'], bins=pnl_bins, labels=pnl_labels)
            pnl_dist = df['pnl_bucket'].value_counts().to_dict()
            
            # Duration distribution
            if 'entry_time' in df.columns and 'exit_time' in df.columns:
                df['duration_hours'] = (pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])).dt.total_seconds() / 3600
                dur_bins = [0, 1, 6, 24, 168, float('inf')]
                dur_labels = ['<1h', '1-6h', '6-24h', '1-7d', '>7d']
                df['duration_bucket'] = pd.cut(df['duration_hours'], bins=dur_bins, labels=dur_labels)
                dur_dist = df['duration_bucket'].value_counts().to_dict()
            else:
                dur_dist = {}
            
            result = {
                'size_distribution': size_dist,
                'pnl_distribution': pnl_dist,
                'duration_distribution': dur_dist,
                'size_stats': {
                    'mean': df['size'].mean(),
                    'median': df['size'].median(),
                    'std': df['size'].std(),
                    'min': df['size'].min(),
                    'max': df['size'].max()
                }
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error calculating trade distribution: {e}")
            raise
    
    async def get_consecutive_analysis(self) -> Dict[str, Any]:
        """
        Analyze win/loss streaks.
        
        Returns:
            Dictionary with streak analysis
        """
        cache_key = self._get_cache_key("get_consecutive_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty:
                return {
                    'max_win_streak': 0,
                    'max_loss_streak': 0,
                    'current_streak': 0,
                    'streak_type': 'none',
                    'streaks': []
                }
            
            df = df.sort_values('entry_time')
            df['is_win'] = df['pnl'] > 0
            
            # Calculate streaks
            streaks = []
            current_streak = 1
            current_type = 'win' if df['is_win'].iloc[0] else 'loss'
            
            for i in range(1, len(df)):
                if df['is_win'].iloc[i] == df['is_win'].iloc[i-1]:
                    current_streak += 1
                else:
                    streaks.append({
                        'type': current_type,
                        'length': current_streak,
                        'start_date': df['entry_time'].iloc[i - current_streak],
                        'end_date': df['entry_time'].iloc[i - 1]
                    })
                    current_streak = 1
                    current_type = 'win' if df['is_win'].iloc[i] else 'loss'
            
            # Add final streak
            streaks.append({
                'type': current_type,
                'length': current_streak,
                'start_date': df['entry_time'].iloc[-current_streak],
                'end_date': df['entry_time'].iloc[-1]
            })
            
            win_streaks = [s for s in streaks if s['type'] == 'win']
            loss_streaks = [s for s in streaks if s['type'] == 'loss']
            
            max_win_streak = max([s['length'] for s in win_streaks]) if win_streaks else 0
            max_loss_streak = max([s['length'] for s in loss_streaks]) if loss_streaks else 0
            
            result = {
                'max_win_streak': max_win_streak,
                'max_loss_streak': max_loss_streak,
                'current_streak': current_streak,
                'streak_type': current_type,
                'streaks': streaks,
                'avg_win_streak': np.mean([s['length'] for s in win_streaks]) if win_streaks else 0,
                'avg_loss_streak': np.mean([s['length'] for s in loss_streaks]) if loss_streaks else 0,
                'total_streaks': len(streaks)
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in consecutive analysis: {e}")
            raise
    
    async def get_timing_analysis(self) -> Dict[str, Any]:
        """
        Analyze entry/exit timing performance.
        
        Returns:
            Dictionary with timing analysis
        """
        cache_key = self._get_cache_key("get_timing_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty or 'slippage' not in df.columns:
                return {
                    'avg_slippage': 0.0,
                    'slippage_by_hour': {},
                    'slippage_by_pattern': {},
                    'timing_grade': 'N/A'
                }
            
            # Slippage analysis
            avg_slippage = df['slippage'].mean()
            
            # By hour
            if 'entry_time' in df.columns:
                df['hour'] = pd.to_datetime(df['entry_time']).dt.hour
                slippage_by_hour = df.groupby('hour')['slippage'].mean().to_dict()
            else:
                slippage_by_hour = {}
            
            # By pattern
            if 'pattern_type' in df.columns:
                slippage_by_pattern = df.groupby('pattern_type')['slippage'].mean().to_dict()
            else:
                slippage_by_pattern = {}
            
            # Grade timing
            if avg_slippage < 0.5:
                grade = 'A+'
            elif avg_slippage < 1.0:
                grade = 'A'
            elif avg_slippage < 2.0:
                grade = 'B'
            elif avg_slippage < 3.0:
                grade = 'C'
            else:
                grade = 'D'
            
            result = {
                'avg_slippage': avg_slippage,
                'median_slippage': df['slippage'].median(),
                'max_slippage': df['slippage'].max(),
                'min_slippage': df['slippage'].min(),
                'slippage_std': df['slippage'].std(),
                'slippage_by_hour': slippage_by_hour,
                'slippage_by_pattern': slippage_by_pattern,
                'timing_grade': grade,
                'total_trades_analyzed': len(df)
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in timing analysis: {e}")
            raise


    # ==================== 3. Whale Performance ====================
    
    async def get_whale_leaderboard(self, limit: int = 10) -> List[WhaleRanking]:
        """
        Get whale rankings by copy performance.
        
        Args:
            limit: Number of whales to return
            
        Returns:
            List of WhaleRanking sorted by performance
        """
        cache_key = self._get_cache_key("get_whale_leaderboard", limit)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            query = """
                SELECT 
                    whale_address,
                    COUNT(*) as trades,
                    SUM(CASE WHEN our_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(our_pnl) as total_pnl,
                    AVG(our_pnl) as avg_pnl,
                    AVG(copy_delay_seconds) as avg_delay,
                    AVG(slippage) as avg_slippage
                FROM whale_copy_performance
                GROUP BY whale_address
                HAVING trades >= 3
                ORDER BY total_pnl DESC
                LIMIT ?
            """
            
            df = self._execute_query(query, (limit,))
            
            rankings = []
            for _, row in df.iterrows():
                trades = row['trades']
                wins = row['wins']
                win_rate = wins / trades if trades > 0 else 0
                
                # Calculate recommendation
                if win_rate > 0.6 and row['total_pnl'] > 0:
                    recommendation = "excellent"
                elif win_rate > 0.5 and row['total_pnl'] > 0:
                    recommendation = "good"
                elif win_rate < 0.4:
                    recommendation = "avoid"
                else:
                    recommendation = "neutral"
                
                # Calculate copy score (0-100)
                score = (win_rate * 50) + min(50, row['total_pnl'] / 100)
                
                ranking = WhaleRanking(
                    whale_address=row['whale_address'],
                    whale_name=None,  # Would need to fetch from winner discovery
                    copy_trades=int(trades),
                    copy_wins=int(wins),
                    copy_losses=int(trades - wins),
                    copy_win_rate=win_rate,
                    copy_pnl=row['total_pnl'],
                    copy_profit_factor=abs(row['total_pnl'] / (row['total_pnl'] - row['avg_pnl'] * trades)) if trades > 1 else 0,
                    correlation_with_us=0.0,  # Calculated separately
                    avg_copy_delay=timedelta(seconds=row['avg_delay']) if pd.notna(row['avg_delay']) else timedelta(0),
                    avg_slippage=row['avg_slippage'] if pd.notna(row['avg_slippage']) else 0.0,
                    copy_score=score,
                    recommendation=recommendation
                )
                rankings.append(ranking)
            
            self._set_cached(cache_key, rankings)
            return rankings
            
        except Exception as e:
            logger.error(f"Error generating whale leaderboard: {e}")
            raise
    
    async def get_whale_correlation(self, whale_address: str) -> float:
        """
        Calculate correlation with specific whale.
        
        Args:
            whale_address: Whale wallet address
            
        Returns:
            Correlation coefficient (-1 to 1)
        """
        cache_key = self._get_cache_key("get_whale_correlation", whale_address)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            query = """
                SELECT our_pnl, whale_pnl
                FROM whale_copy_performance
                WHERE whale_address = ?
                AND our_pnl IS NOT NULL
                AND whale_pnl IS NOT NULL
            """
            
            df = self._execute_query(query, (whale_address,))
            
            if len(df) < 3:
                return 0.0
            
            correlation = df['our_pnl'].corr(df['whale_pnl'])
            
            if pd.isna(correlation):
                return 0.0
            
            self._set_cached(cache_key, correlation)
            return correlation
            
        except Exception as e:
            logger.error(f"Error calculating whale correlation: {e}")
            return 0.0
    
    async def get_pattern_performance(self) -> Dict[str, Dict]:
        """
        Get performance breakdown by pattern type.
        
        Returns:
            Dictionary with pattern performance metrics
        """
        cache_key = self._get_cache_key("get_pattern_performance")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty or 'pattern_type' not in df.columns:
                return {}
            
            # Group by pattern
            pattern_stats = df.groupby('pattern_type').agg({
                'pnl': ['count', 'sum', 'mean', 'std'],
                'trade_id': 'count'
            }).reset_index()
            
            # Calculate win rates
            pattern_results = {}
            for pattern in df['pattern_type'].unique():
                if pd.isna(pattern):
                    continue
                    
                pattern_df = df[df['pattern_type'] == pattern]
                wins = len(pattern_df[pattern_df['pnl'] > 0])
                total = len(pattern_df)
                win_rate = wins / total if total > 0 else 0
                
                pattern_results[pattern] = {
                    'trades': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': win_rate,
                    'total_pnl': pattern_df['pnl'].sum(),
                    'avg_pnl': pattern_df['pnl'].mean(),
                    'avg_trade_size': pattern_df['size'].mean() if 'size' in pattern_df.columns else 0,
                    'profit_factor': abs(
                        pattern_df[pattern_df['pnl'] > 0]['pnl'].sum() / 
                        pattern_df[pattern_df['pnl'] < 0]['pnl'].sum()
                    ) if len(pattern_df[pattern_df['pnl'] < 0]) > 0 else float('inf'),
                    'reliability_score': win_rate * (1 + pattern_df['pnl'].sum() / 1000)  # Custom metric
                }
            
            self._set_cached(cache_key, pattern_results)
            return pattern_results
            
        except Exception as e:
            logger.error(f"Error analyzing pattern performance: {e}")
            raise
    
    async def get_best_whales_to_copy(self, min_trades: int = 5) -> List[Dict]:
        """
        Get recommendation engine for best whales to copy.
        
        Args:
            min_trades: Minimum number of copy trades required
            
        Returns:
            List of recommended whales with analysis
        """
        cache_key = self._get_cache_key("get_best_whales_to_copy", min_trades)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get all whale performance data
            query = """
                SELECT 
                    whale_address,
                    COUNT(*) as trades,
                    SUM(CASE WHEN our_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(our_pnl) as total_pnl,
                    AVG(our_pnl) as avg_pnl,
                    AVG(copy_delay_seconds) as avg_delay,
                    AVG(slippage) as avg_slippage,
                    MAX(timestamp) as last_trade
                FROM whale_copy_performance
                GROUP BY whale_address
                HAVING trades >= ?
            """
            
            df = self._execute_query(query, (min_trades,))
            
            recommendations = []
            for _, row in df.iterrows():
                trades = row['trades']
                wins = row['wins']
                win_rate = wins / trades if trades > 0 else 0
                total_pnl = row['total_pnl']
                avg_delay = row['avg_delay'] if pd.notna(row['avg_delay']) else 0
                avg_slippage = row['avg_slippage'] if pd.notna(row['avg_slippage']) else 0
                
                # Calculate composite score
                # Win rate (30%), P&L (30%), Consistency (20%), Speed (20%)
                win_rate_score = win_rate * 100
                pnl_score = min(50, total_pnl / 10)  # Cap at 50 points
                consistency_score = 100 - (row['avg_pnl'] / (total_pnl / trades) * 100 if trades > 1 and total_pnl != 0 else 0)
                speed_score = max(0, 100 - avg_delay)  # Lower delay = higher score
                
                composite_score = (
                    win_rate_score * 0.30 +
                    pnl_score * 0.30 +
                    consistency_score * 0.20 +
                    speed_score * 0.20
                )
                
                # Generate recommendation
                if composite_score > 75:
                    rec = "Strong Buy"
                    reason = "Excellent copy performance"
                elif composite_score > 60:
                    rec = "Buy"
                    reason = "Good copy performance"
                elif composite_score > 40:
                    rec = "Hold"
                    reason = "Average performance"
                else:
                    rec = "Avoid"
                    reason = "Poor performance or high slippage"
                
                recommendations.append({
                    'whale_address': row['whale_address'],
                    'trades_copied': int(trades),
                    'win_rate': win_rate,
                    'total_pnl': total_pnl,
                    'avg_slippage': avg_slippage,
                    'avg_copy_delay_seconds': avg_delay,
                    'composite_score': composite_score,
                    'recommendation': rec,
                    'reason': reason,
                    'last_trade': row['last_trade']
                })
            
            # Sort by composite score
            recommendations.sort(key=lambda x: x['composite_score'], reverse=True)
            
            self._set_cached(cache_key, recommendations)
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in whale recommendations: {e}")
            raise

    # ==================== 4. Market Analytics ====================
    
    async def get_market_performance(self) -> List[MarketPerformance]:
        """
        Get performance by market category.
        
        Returns:
            List of MarketPerformance for each category
        """
        cache_key = self._get_cache_key("get_market_performance")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # This would ideally fetch market category from trades
            # For now, we'll use a placeholder approach
            df = self._get_trades_df()
            
            if df.empty:
                return []
            
            # Check if we have market_question to infer category
            if 'market_question' in df.columns:
                # Simple categorization based on keywords
                def categorize(question):
                    q = str(question).lower()
                    if 'btc' in q or 'bitcoin' in q or 'crypto' in q:
                        return 'Crypto'
                    elif 'eth' in q or 'ethereum' in q:
                        return 'Crypto'
                    elif 'election' in q or 'vote' in q or 'trump' in q or 'biden' in q:
                        return 'Politics'
                    elif 'nba' in q or 'nfl' in q or 'soccer' in q or 'football' in q:
                        return 'Sports'
                    else:
                        return 'Other'
                
                df['category'] = df['market_question'].apply(categorize)
            else:
                df['category'] = 'Unknown'
            
            performances = []
            for category in df['category'].unique():
                cat_df = df[df['category'] == category]
                
                wins = len(cat_df[cat_df['pnl'] > 0])
                total = len(cat_df)
                
                perf = MarketPerformance(
                    category=category,
                    trades=total,
                    wins=wins,
                    losses=total - wins,
                    win_rate=wins / total if total > 0 else 0,
                    total_pnl=cat_df['pnl'].sum(),
                    avg_trade=cat_df['pnl'].mean(),
                    max_win=cat_df['pnl'].max(),
                    max_loss=cat_df['pnl'].min(),
                    avg_slippage=cat_df['slippage'].mean() if 'slippage' in cat_df.columns else 0,
                    avg_liquidity=cat_df['liquidity'].mean() if 'liquidity' in cat_df.columns else 0
                )
                performances.append(perf)
            
            # Sort by total P&L
            performances.sort(key=lambda x: x.total_pnl, reverse=True)
            
            self._set_cached(cache_key, performances)
            return performances
            
        except Exception as e:
            logger.error(f"Error analyzing market performance: {e}")
            raise
    
    async def get_liquidity_analysis(self) -> Dict[str, Any]:
        """
        Analyze slippage vs liquidity relationship.
        
        Returns:
            Dictionary with liquidity analysis
        """
        cache_key = self._get_cache_key("get_liquidity_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            df = self._get_trades_df()
            
            if df.empty or 'liquidity' not in df.columns or 'slippage' not in df.columns:
                return {
                    'avg_slippage_by_liquidity': {},
                    'correlation': 0.0,
                    'recommendation': 'Insufficient data'
                }
            
            # Create liquidity buckets
            liq_bins = [0, 10000, 50000, 100000, 500000, float('inf')]
            liq_labels = ['<$10K', '$10K-50K', '$50K-100K', '$100K-500K', '>$500K']
            df['liquidity_bucket'] = pd.cut(df['liquidity'], bins=liq_bins, labels=liq_labels)
            
            # Calculate stats by bucket
            slippage_by_liq = df.groupby('liquidity_bucket', observed=True).agg({
                'slippage': ['mean', 'median', 'count'],
                'pnl': 'mean'
            }).to_dict()
            
            # Calculate correlation
            correlation = df['liquidity'].corr(df['slippage'])
            
            # Generate recommendation
            if correlation < -0.3:
                rec = "Higher liquidity significantly reduces slippage"
            elif correlation < -0.1:
                rec = "Higher liquidity moderately reduces slippage"
            elif correlation > 0.1:
                rec = "Unexpected: liquidity doesn't help slippage (check data)"
            else:
                rec = "No clear relationship between liquidity and slippage"
            
            result = {
                'avg_slippage_by_liquidity': slippage_by_liq,
                'correlation': correlation,
                'recommendation': rec,
                'optimal_liquidity_threshold': 50000 if correlation < -0.2 else 100000
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in liquidity analysis: {e}")
            raise
    
    async def get_volatility_analysis(self) -> Dict[str, Any]:
        """
        Analyze performance in different volatility regimes.
        
        Returns:
            Dictionary with volatility regime analysis
        """
        cache_key = self._get_cache_key("get_volatility_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Get equity curve to calculate volatility
            equity_df = await self.get_equity_curve(days=30)
            
            if equity_df.empty or len(equity_df) < 5:
                return {
                    'low_vol_performance': 0,
                    'med_vol_performance': 0,
                    'high_vol_performance': 0,
                    'regimes': {}
                }
            
            # Calculate rolling volatility
            equity_df['volatility'] = equity_df['daily_return'].rolling(5).std() * np.sqrt(365) * 100
            
            # Classify regimes
            vol_median = equity_df['volatility'].median()
            vol_75 = equity_df['volatility'].quantile(0.75)
            
            def classify_vol(vol):
                if pd.isna(vol):
                    return 'unknown'
                elif vol < vol_median * 0.8:
                    return 'low'
                elif vol < vol_75:
                    return 'medium'
                else:
                    return 'high'
            
            equity_df['regime'] = equity_df['volatility'].apply(classify_vol)
            
            # Calculate performance by regime
            regimes = {}
            for regime in ['low', 'medium', 'high']:
                regime_df = equity_df[equity_df['regime'] == regime]
                if len(regime_df) > 0:
                    regimes[regime] = {
                        'days': len(regime_df),
                        'avg_return': regime_df['daily_return'].mean() * 100,
                        'total_return': ((1 + regime_df['daily_return']).prod() - 1) * 100,
                        'volatility': regime_df['volatility'].mean(),
                        'sharpe': (regime_df['daily_return'].mean() / regime_df['daily_return'].std() * np.sqrt(365)) if regime_df['daily_return'].std() > 0 else 0
                    }
            
            result = {
                'low_vol_performance': regimes.get('low', {}).get('total_return', 0),
                'med_vol_performance': regimes.get('medium', {}).get('total_return', 0),
                'high_vol_performance': regimes.get('high', {}).get('total_return', 0),
                'regimes': regimes,
                'optimal_regime': max(regimes.items(), key=lambda x: x[1].get('total_return', 0))[0] if regimes else 'unknown'
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in volatility analysis: {e}")
            raise


    # ==================== 5. Risk Metrics ====================
    
    async def get_var_confidence(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk at specified confidence level.
        
        Args:
            confidence: Confidence level (0.95 for 95%, etc.)
            
        Returns:
            VaR value (negative number representing potential loss)
        """
        cache_key = self._get_cache_key("get_var_confidence", confidence)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            equity_df = await self.get_equity_curve(days=30)
            
            if equity_df.empty or len(equity_df) < 5:
                return 0.0
            
            returns = equity_df['daily_return'].dropna()
            
            if len(returns) == 0:
                return 0.0
            
            # Historical VaR
            var = np.percentile(returns, (1 - confidence) * 100)
            
            # Scale to portfolio value
            portfolio_value = equity_df['portfolio_value'].iloc[-1]
            var_dollar = var * portfolio_value
            
            self._set_cached(cache_key, var_dollar)
            return var_dollar
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return 0.0
    
    async def get_expected_shortfall(self, confidence: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).
        
        Args:
            confidence: Confidence level
            
        Returns:
            CVaR value (average loss beyond VaR)
        """
        cache_key = self._get_cache_key("get_expected_shortfall", confidence)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        try:
            equity_df = await self.get_equity_curve(days=30)
            
            if equity_df.empty or len(equity_df) < 5:
                return 0.0
            
            returns = equity_df['daily_return'].dropna()
            
            if len(returns) == 0:
                return 0.0
            
            # Calculate VaR threshold
            var_threshold = np.percentile(returns, (1 - confidence) * 100)
            
            # CVaR is the average of returns worse than VaR
            cvar = returns[returns <= var_threshold].mean()
            
            # Scale to portfolio value
            portfolio_value = equity_df['portfolio_value'].iloc[-1]
            cvar_dollar = cvar * portfolio_value
            
            self._set_cached(cache_key, cvar_dollar)
            return cvar_dollar
            
        except Exception as e:
            logger.error(f"Error calculating CVaR: {e}")
            return 0.0
    
    async def get_beta_correlation(self) -> Dict[str, float]:
        """
        Calculate correlation to broader market.
        
        Returns:
            Dictionary with beta, alpha, and correlation
        """
        cache_key = self._get_cache_key("get_beta_correlation")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # In a real implementation, this would compare to a market benchmark
            # For now, we'll use portfolio volatility as a proxy
            equity_df = await self.get_equity_curve(days=30)
            
            if equity_df.empty or len(equity_df) < 5:
                return {
                    'beta': 1.0,
                    'alpha': 0.0,
                    'correlation': 0.0,
                    'r_squared': 0.0
                }
            
            returns = equity_df['daily_return'].dropna()
            
            if len(returns) < 2:
                return {
                    'beta': 1.0,
                    'alpha': 0.0,
                    'correlation': 0.0,
                    'r_squared': 0.0
                }
            
            # Simplified: assume market returns are normally distributed around 0
            # In production, fetch actual market returns
            market_returns = pd.Series(np.random.normal(0, returns.std(), len(returns)))
            
            # Calculate beta and alpha
            covariance = returns.cov(market_returns)
            market_variance = market_returns.var()
            
            beta = covariance / market_variance if market_variance > 0 else 1.0
            alpha = returns.mean() - beta * market_returns.mean()
            correlation = returns.corr(market_returns)
            r_squared = correlation ** 2
            
            result = {
                'beta': beta,
                'alpha': alpha,
                'correlation': correlation,
                'r_squared': r_squared
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error calculating beta: {e}")
            return {
                'beta': 1.0,
                'alpha': 0.0,
                'correlation': 0.0,
                'r_squared': 0.0
            }
    
    async def get_tail_risk_analysis(self) -> Dict[str, Any]:
        """
        Analyze tail risk (extreme events).
        
        Returns:
            Dictionary with tail risk metrics
        """
        cache_key = self._get_cache_key("get_tail_risk_analysis")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            equity_df = await self.get_equity_curve(days=60)
            
            if equity_df.empty or len(equity_df) < 10:
                return {
                    'tail_ratio': 1.0,
                    'skewness': 0.0,
                    'kurtosis': 3.0,
                    'extreme_losses': 0,
                    'extreme_wins': 0,
                    'tail_events': []
                }
            
            returns = equity_df['daily_return'].dropna()
            
            # Calculate statistics
            skew = returns.skew()
            kurt = returns.kurtosis()
            
            # Tail ratio (95th percentile gain / 5th percentile loss)
            tail_95 = np.percentile(returns, 95)
            tail_5 = abs(np.percentile(returns, 5))
            tail_ratio = tail_95 / tail_5 if tail_5 > 0 else 1.0
            
            # Extreme events (>2 std dev)
            std = returns.std()
            mean = returns.mean()
            extreme_losses = len(returns[returns < mean - 2 * std])
            extreme_wins = len(returns[returns > mean + 2 * std])
            
            # Identify tail events
            tail_events = []
            for idx, ret in returns.items():
                if abs(ret) > mean + 2.5 * std:
                    tail_events.append({
                        'date': equity_df.loc[idx, 'date'] if 'date' in equity_df.columns else idx,
                        'return': ret * 100,
                        'severity': 'extreme' if abs(ret) > mean + 3 * std else 'significant'
                    })
            
            result = {
                'tail_ratio': tail_ratio,
                'skewness': skew,
                'kurtosis': kurt,
                'extreme_losses': extreme_losses,
                'extreme_wins': extreme_wins,
                'tail_events': tail_events,
                'tail_risk_assessment': 'high' if tail_ratio < 0.5 else 'moderate' if tail_ratio < 1.0 else 'low'
            }
            
            self._set_cached(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error in tail risk analysis: {e}")
            raise
    
    async def get_risk_metrics(self) -> RiskMetrics:
        """
        Get comprehensive risk metrics.
        
        Returns:
            RiskMetrics with all risk calculations
        """
        cache_key = self._get_cache_key("get_risk_metrics")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            # Gather all risk data
            equity_df = await self.get_equity_curve(days=30)
            trades_df = self._get_trades_df()
            
            if equity_df.empty or len(equity_df) < 5:
                return RiskMetrics(
                    var_95=0.0,
                    var_99=0.0,
                    cvar_95=0.0,
                    cvar_99=0.0,
                    volatility_daily=0.0,
                    volatility_monthly=0.0,
                    volatility_annual=0.0,
                    beta=1.0,
                    alpha=0.0,
                    correlation_to_market=0.0,
                    skewness=0.0,
                    kurtosis=3.0,
                    max_consecutive_wins=0,
                    max_consecutive_losses=0,
                    current_streak=0,
                    streak_type='none',
                    ulcer_index=0.0,
                    serenity_index=0.0,
                    risk_of_ruin=0.0,
                    expected_max_drawdown=0.0,
                    tail_ratio=1.0,
                    upside_potential=0.0,
                    downside_risk=0.0
                )
            
            returns = equity_df['daily_return'].dropna()
            
            # VaR calculations
            var_95 = await self.get_var_confidence(0.95)
            var_99 = await self.get_var_confidence(0.99)
            cvar_95 = await self.get_expected_shortfall(0.95)
            cvar_99 = await self.get_expected_shortfall(0.99)
            
            # Volatility
            daily_vol = returns.std()
            monthly_vol = daily_vol * np.sqrt(30)
            annual_vol = daily_vol * np.sqrt(365)
            
            # Beta and correlation
            beta_data = await self.get_beta_correlation()
            
            # Streak analysis
            streak_data = await self.get_consecutive_analysis()
            
            # Ulcer Index (measure of pain)
            equity_df['rolling_max'] = equity_df['portfolio_value'].expanding().max()
            equity_df['drawdown'] = (equity_df['portfolio_value'] - equity_df['rolling_max']) / equity_df['rolling_max']
            equity_df['squared_drawdown'] = equity_df['drawdown'] ** 2
            ulcer = np.sqrt(equity_df['squared_drawdown'].mean())
            
            # Serenity Index (return / ulcer)
            serenity = (returns.mean() * 365) / ulcer if ulcer > 0 else 0
            
            # Risk of ruin (simplified)
            win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df) if len(trades_df) > 0 else 0.5
            avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if len(trades_df[trades_df['pnl'] > 0]) > 0 else 1
            avg_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].mean()) if len(trades_df[trades_df['pnl'] < 0]) > 0 else 1
            
            b = avg_win / avg_loss if avg_loss > 0 else 1
            p = win_rate
            q = 1 - p
            
            if b > 0 and (b * p - q) / b > 0:
                risk_of_ruin = ((1 - (b * p - q) / b) / (1 + (b * p - q) / b)) ** (len(trades_df) / 10)
                risk_of_ruin = max(0, min(1, risk_of_ruin))
            else:
                risk_of_ruin = 1.0
            
            # Expected max drawdown (Monte Carlo approximation)
            expected_dd = abs(var_95) * 2 if var_95 != 0 else 0
            
            # Tail risk
            tail_data = await self.get_tail_risk_analysis()
            
            metrics = RiskMetrics(
                var_95=var_95,
                var_99=var_99,
                cvar_95=cvar_95,
                cvar_99=cvar_99,
                volatility_daily=daily_vol * 100,
                volatility_monthly=monthly_vol * 100,
                volatility_annual=annual_vol * 100,
                beta=beta_data['beta'],
                alpha=beta_data['alpha'],
                correlation_to_market=beta_data['correlation'],
                skewness=returns.skew(),
                kurtosis=returns.kurtosis(),
                max_consecutive_wins=streak_data.get('max_win_streak', 0),
                max_consecutive_losses=streak_data.get('max_loss_streak', 0),
                current_streak=streak_data.get('current_streak', 0),
                streak_type=streak_data.get('streak_type', 'none'),
                ulcer_index=ulcer,
                serenity_index=serenity,
                risk_of_ruin=risk_of_ruin,
                expected_max_drawdown=expected_dd,
                tail_ratio=tail_data.get('tail_ratio', 1.0),
                upside_potential=np.percentile(returns, 95) * 100,
                downside_risk=abs(np.percentile(returns, 5)) * 100
            )
            
            self._set_cached(cache_key, metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            raise


    # ==================== 6. Reporting ====================
    
    async def generate_daily_report(self, date: Optional[datetime] = None) -> DailyReport:
        """
        Generate daily performance report.
        
        Args:
            date: Date for report (defaults to today)
            
        Returns:
            DailyReport with summary
        """
        try:
            if date is None:
                date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            next_day = date + timedelta(days=1)
            
            # Get trades for the day
            trades_df = self._get_trades_df(start_date=date, end_date=next_day)
            
            # Get portfolio snapshots
            query = """
                SELECT * FROM portfolio_snapshots
                WHERE timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            """
            snapshots = self._execute_query(query, (date.isoformat(), next_day.isoformat()))
            
            # Calculate metrics
            if snapshots.empty:
                start_value = self.initial_bankroll
                end_value = self.initial_bankroll
                daily_pnl = 0.0
            else:
                start_value = snapshots['total_value'].iloc[0]
                end_value = snapshots['total_value'].iloc[-1]
                daily_pnl = end_value - start_value
            
            daily_return = (daily_pnl / start_value) * 100 if start_value > 0 else 0
            
            # Trade counts
            total_trades = len(trades_df)
            wins = len(trades_df[trades_df['pnl'] > 0]) if not trades_df.empty else 0
            losses = len(trades_df[trades_df['pnl'] < 0]) if not trades_df.empty else 0
            win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
            
            # Best and worst trades
            best_trade = None
            worst_trade = None
            if not trades_df.empty:
                best_idx = trades_df['pnl'].idxmax()
                worst_idx = trades_df['pnl'].idxmin()
                
                best_trade = {
                    'market': trades_df.loc[best_idx, 'market_question'] if 'market_question' in trades_df.columns else 'Unknown',
                    'pnl': trades_df.loc[best_idx, 'pnl']
                }
                worst_trade = {
                    'market': trades_df.loc[worst_idx, 'market_question'] if 'market_question' in trades_df.columns else 'Unknown',
                    'pnl': trades_df.loc[worst_idx, 'pnl']
                }
            
            # Generate notes
            notes = []
            if daily_pnl > 0:
                notes.append(f"Profitable day: +${daily_pnl:.2f}")
            elif daily_pnl < 0:
                notes.append(f"Losing day: ${daily_pnl:.2f}")
            else:
                notes.append("Break-even day")
            
            if win_rate > 0.6:
                notes.append(f"Strong win rate: {win_rate:.1%}")
            elif win_rate < 0.4 and total_trades > 0:
                notes.append(f"Low win rate: {win_rate:.1%} - review trade selection")
            
            report = DailyReport(
                date=date,
                starting_value=start_value,
                ending_value=end_value,
                daily_pnl=daily_pnl,
                daily_return=daily_return,
                trades_today=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                positions_opened=total_trades,  # Simplified
                positions_closed=total_trades,
                open_positions=0,  # Would need current positions query
                max_drawdown_today=0.0,  # Would calculate from intraday data
                var_95_today=await self.get_var_confidence(0.95),
                best_trade=best_trade,
                worst_trade=worst_trade,
                notes=notes
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {e}")
            raise
    
    async def generate_weekly_report(self, week_start: Optional[datetime] = None) -> WeeklyReport:
        """
        Generate weekly performance report.
        
        Args:
            week_start: Start of week (defaults to last Monday)
            
        Returns:
            WeeklyReport with comprehensive analysis
        """
        try:
            if week_start is None:
                # Find last Monday
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                week_start = today - timedelta(days=today.weekday())
            
            week_end = week_start + timedelta(days=7)
            
            # Get data
            trades_df = self._get_trades_df(start_date=week_start, end_date=week_end)
            equity_df = await self.get_equity_curve(days=14)  # Get extra for context
            
            # Filter to week
            if not equity_df.empty and 'date' in equity_df.columns:
                equity_df['date'] = pd.to_datetime(equity_df['date'])
                week_equity = equity_df[(equity_df['date'] >= week_start) & (equity_df['date'] < week_end)]
            else:
                week_equity = equity_df
            
            # Calculate metrics
            if week_equity.empty:
                start_value = self.initial_bankroll
                end_value = self.initial_bankroll
            else:
                start_value = week_equity['portfolio_value'].iloc[0]
                end_value = week_equity['portfolio_value'].iloc[-1]
            
            weekly_pnl = end_value - start_value
            weekly_return = (weekly_pnl / start_value) * 100 if start_value > 0 else 0
            
            # Trade statistics
            total_trades = len(trades_df)
            wins = len(trades_df[trades_df['pnl'] > 0]) if not trades_df.empty else 0
            win_rate = wins / total_trades if total_trades > 0 else 0
            
            gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if not trades_df.empty else 0
            gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if not trades_df.empty else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Daily breakdown
            daily_returns = []
            if not week_equity.empty and len(week_equity) > 1:
                for i in range(len(week_equity)):
                    daily_returns.append({
                        'date': week_equity['date'].iloc[i].isoformat() if 'date' in week_equity.columns else None,
                        'value': week_equity['portfolio_value'].iloc[i],
                        'return': week_equity['daily_return'].iloc[i] * 100 if 'daily_return' in week_equity.columns else 0
                    })
            
            # Pattern performance
            pattern_perf = await self.get_pattern_performance()
            
            # Whale tracking
            whale_leaderboard = await self.get_whale_leaderboard(limit=5)
            
            # Risk metrics
            dd_analysis = await self.get_drawdown_analysis()
            
            volatility = 0.0
            sharpe = 0.0
            if not week_equity.empty and len(week_equity) > 1 and 'daily_return' in week_equity.columns:
                returns = week_equity['daily_return'].dropna()
                if len(returns) > 1:
                    volatility = returns.std() * np.sqrt(365) * 100
                    sharpe = (returns.mean() / returns.std()) * np.sqrt(365) if returns.std() > 0 else 0
            
            # Generate insights
            insights = []
            areas_for_improvement = []
            
            if weekly_pnl > 0:
                insights.append(f"Profitable week: +${weekly_pnl:.2f} ({weekly_return:+.2f}%)")
            else:
                insights.append(f"Losing week: ${weekly_pnl:.2f} ({weekly_return:+.2f}%)")
            
            if win_rate > 0.55:
                insights.append(f"Good win rate: {win_rate:.1%}")
            else:
                areas_for_improvement.append(f"Win rate below target: {win_rate:.1%}")
            
            if profit_factor > 1.5:
                insights.append(f"Strong profit factor: {profit_factor:.2f}")
            elif profit_factor < 1.0:
                areas_for_improvement.append(f"Profit factor below 1: {profit_factor:.2f}")
            
            if pattern_perf:
                best_pattern = max(pattern_perf.items(), key=lambda x: x[1].get('total_pnl', 0))
                insights.append(f"Best pattern: {best_pattern[0]} (${best_pattern[1].get('total_pnl', 0):+.2f})")
            
            report = WeeklyReport(
                week_start=week_start,
                week_end=week_end,
                starting_value=start_value,
                ending_value=end_value,
                weekly_pnl=weekly_pnl,
                weekly_return=weekly_return,
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                daily_returns=daily_returns,
                pattern_performance=pattern_perf,
                top_whales=whale_leaderboard,
                max_drawdown=dd_analysis.current_drawdown,
                volatility=volatility,
                sharpe_ratio=sharpe,
                insights=insights,
                areas_for_improvement=areas_for_improvement
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating weekly report: {e}")
            raise
    
    async def generate_monthly_report(self, month: Optional[datetime] = None) -> MonthlyReport:
        """
        Generate comprehensive monthly report.
        
        Args:
            month: Month to report on (defaults to current month)
            
        Returns:
            MonthlyReport with deep analysis
        """
        try:
            if month is None:
                month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate month boundaries
            if month.month == 12:
                next_month = month.replace(year=month.year + 1, month=1)
            else:
                next_month = month.replace(month=month.month + 1)
            
            # Gather all data
            trades_df = self._get_trades_df(start_date=month, end_date=next_month)
            equity_df = await self.get_equity_curve(days=45)
            
            # Filter to month
            if not equity_df.empty and 'date' in equity_df.columns:
                equity_df['date'] = pd.to_datetime(equity_df['date'])
                month_equity = equity_df[(equity_df['date'] >= month) & (equity_df['date'] < next_month)]
            else:
                month_equity = equity_df
            
            # Basic metrics
            if month_equity.empty:
                start_value = self.initial_bankroll
                end_value = self.initial_bankroll
            else:
                start_value = month_equity['portfolio_value'].iloc[0]
                end_value = month_equity['portfolio_value'].iloc[-1]
            
            monthly_pnl = end_value - start_value
            monthly_return = (monthly_pnl / start_value) * 100 if start_value > 0 else 0
            
            # YTD calculation (simplified)
            ytd_return = ((end_value / self.initial_bankroll) - 1) * 100
            
            # Trade statistics
            total_trades = len(trades_df)
            wins = len(trades_df[trades_df['pnl'] > 0]) if not trades_df.empty else 0
            win_rate = wins / total_trades if total_trades > 0 else 0
            
            gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if not trades_df.empty else 0
            gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if not trades_df.empty else 0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            avg_trade = trades_df['pnl'].mean() if not trades_df.empty else 0
            
            # Risk metrics
            risk_metrics = await self.get_risk_metrics()
            dd_analysis = await self.get_drawdown_analysis()
            
            # Pattern analysis
            pattern_perf = await self.get_pattern_performance()
            best_pattern = max(pattern_perf.items(), key=lambda x: x[1].get('total_pnl', 0))[0] if pattern_perf else None
            worst_pattern = min(pattern_perf.items(), key=lambda x: x[1].get('total_pnl', 0))[0] if pattern_perf else None
            
            # Whale analysis
            whale_leaderboard = await self.get_whale_leaderboard(limit=10)
            best_whales = [w.whale_address for w in whale_leaderboard if w.recommendation in ['good', 'excellent']][:3]
            whales_to_avoid = [w.whale_address for w in whale_leaderboard if w.recommendation == 'avoid']
            
            # Market analysis
            market_perf = await self.get_market_performance()
            best_category = max(market_perf, key=lambda x: x.total_pnl).category if market_perf else None
            worst_category = min(market_perf, key=lambda x: x.total_pnl).category if market_perf else None
            
            # Chart data
            chart_data = {}
            for chart_type in [ChartType.EQUITY, ChartType.PATTERN_PIE, ChartType.WHALE_PERFORMANCE]:
                try:
                    chart_data[chart_type.value] = await self.get_chart_data(chart_type)
                except Exception as e:
                    logger.warning(f"Failed to generate {chart_type.value} chart: {e}")
            
            # Goals and recommendations
            goals_achieved = []
            goals_missed = []
            recommendations = []
            
            if monthly_pnl > 0:
                goals_achieved.append("Profitable month")
            else:
                goals_missed.append("Profitable month")
            
            if win_rate > 0.55:
                goals_achieved.append(f"Win rate target: {win_rate:.1%} > 55%")
            else:
                goals_missed.append(f"Win rate target: {win_rate:.1%} < 55%")
            
            if dd_analysis.max_drawdown < 0.20:
                goals_achieved.append("Max drawdown within limits")
            else:
                goals_missed.append(f"Max drawdown exceeded: {dd_analysis.max_drawdown:.1%}")
            
            # Generate recommendations
            if win_rate < 0.5:
                recommendations.append("Review trade selection criteria to improve win rate")
            
            if profit_factor < 1.3:
                recommendations.append("Work on risk management - let winners run, cut losers faster")
            
            if pattern_perf:
                worst_pat = min(pattern_perf.items(), key=lambda x: x[1].get('total_pnl', 0))
                if worst_pat[1].get('total_pnl', 0) < -100:
                    recommendations.append(f"Consider avoiding {worst_pat[0]} pattern")
            
            if best_whales:
                recommendations.append(f"Focus on copying top performers: {', '.join(best_whales[:2])}")
            
            report = MonthlyReport(
                month=month,
                starting_value=start_value,
                ending_value=end_value,
                monthly_pnl=monthly_pnl,
                monthly_return=monthly_return,
                ytd_return=ytd_return,
                total_trades=total_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_trade=avg_trade,
                max_drawdown=dd_analysis.max_drawdown,
                volatility=risk_metrics.volatility_annual,
                sharpe_ratio=risk_metrics.sharpe_ratio if hasattr(risk_metrics, 'sharpe_ratio') else 0,
                sortino_ratio=risk_metrics.sortino_ratio,
                calmar_ratio=risk_metrics.calmar_ratio if hasattr(risk_metrics, 'calmar_ratio') else 0,
                pattern_breakdown=pattern_perf,
                best_pattern=best_pattern,
                worst_pattern=worst_pattern,
                whale_leaderboard=whale_leaderboard,
                best_whales_to_copy=best_whales,
                whales_to_avoid=whales_to_avoid,
                market_performance=market_perf,
                best_category=best_category,
                worst_category=worst_category,
                goals_achieved=goals_achieved,
                goals_missed=goals_missed,
                recommendations=recommendations,
                chart_data=chart_data
            )
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating monthly report: {e}")
            raise
    
    async def export_to_pdf(self, report_data: Any, output_path: Optional[str] = None) -> str:
        """
        Export report to PDF format.
        
        Args:
            report_data: Report data to export
            output_path: Output file path (auto-generated if None)
            
        Returns:
            Path to generated PDF
        """
        try:
            # Since we don't have a PDF library, we'll create a formatted text report
            # In production, use libraries like reportlab, fpdf2, or weasyprint
            
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"report_{timestamp}.txt"
            
            # Format report as text
            lines = []
            lines.append("=" * 80)
            lines.append("POLYBOT PERFORMANCE REPORT")
            lines.append("=" * 80)
            lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            
            if isinstance(report_data, DailyReport):
                lines.append(f"DAILY REPORT - {report_data.date.strftime('%Y-%m-%d')}")
                lines.append("-" * 40)
                lines.append(f"Starting Value: ${report_data.starting_value:,.2f}")
                lines.append(f"Ending Value: ${report_data.ending_value:,.2f}")
                lines.append(f"Daily P&L: ${report_data.daily_pnl:+.2f} ({report_data.daily_return:+.2f}%)")
                lines.append(f"Trades: {report_data.trades_today} (W: {report_data.wins}, L: {report_data.losses})")
                lines.append(f"Win Rate: {report_data.win_rate:.1%}")
                lines.append("")
                lines.append("Notes:")
                for note in report_data.notes:
                    lines.append(f"  • {note}")
            
            elif isinstance(report_data, WeeklyReport):
                lines.append(f"WEEKLY REPORT - {report_data.week_start.strftime('%Y-%m-%d')} to {report_data.week_end.strftime('%Y-%m-%d')}")
                lines.append("-" * 40)
                lines.append(f"Weekly P&L: ${report_data.weekly_pnl:+.2f} ({report_data.weekly_return:+.2f}%)")
                lines.append(f"Total Trades: {report_data.total_trades}")
                lines.append(f"Win Rate: {report_data.win_rate:.1%}")
                lines.append(f"Profit Factor: {report_data.profit_factor:.2f}")
                lines.append("")
                lines.append("Insights:")
                for insight in report_data.insights:
                    lines.append(f"  ✓ {insight}")
                lines.append("")
                lines.append("Areas for Improvement:")
                for area in report_data.areas_for_improvement:
                    lines.append(f"  ⚠ {area}")
            
            elif isinstance(report_data, MonthlyReport):
                lines.append(f"MONTHLY REPORT - {report_data.month.strftime('%B %Y')}")
                lines.append("-" * 40)
                lines.append(f"Monthly P&L: ${report_data.monthly_pnl:+.2f} ({report_data.monthly_return:+.2f}%)")
                lines.append(f"YTD Return: {report_data.ytd_return:+.2f}%")
                lines.append(f"Total Trades: {report_data.total_trades}")
                lines.append(f"Win Rate: {report_data.win_rate:.1%}")
                lines.append(f"Profit Factor: {report_data.profit_factor:.2f}")
                lines.append(f"Sharpe Ratio: {report_data.sharpe_ratio:.2f}")
                lines.append("")
                lines.append("Goals Achieved:")
                for goal in report_data.goals_achieved:
                    lines.append(f"  ✓ {goal}")
                lines.append("")
                lines.append("Goals Missed:")
                for goal in report_data.goals_missed:
                    lines.append(f"  ✗ {goal}")
                lines.append("")
                lines.append("Recommendations:")
                for rec in report_data.recommendations:
                    lines.append(f"  → {rec}")
            
            lines.append("")
            lines.append("=" * 80)
            lines.append("END OF REPORT")
            lines.append("=" * 80)
            
            # Write to file
            with open(output_path, 'w') as f:
                f.write('\n'.join(lines))
            
            logger.info(f"Report exported to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            raise


    # ==================== 7. Visualization Data ====================
    
    async def get_chart_data(self, chart_type: ChartType) -> ChartData:
        """
        Get data formatted for charting.
        
        Args:
            chart_type: Type of chart to generate data for
            
        Returns:
            ChartData with labels and datasets
        """
        cache_key = self._get_cache_key("get_chart_data", chart_type.value)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            if chart_type == ChartType.EQUITY:
                return await self._get_equity_chart_data()
            elif chart_type == ChartType.DRAWDOWN:
                return await self._get_drawdown_chart_data()
            elif chart_type == ChartType.TRADE_DISTRIBUTION:
                return await self._get_trade_distribution_chart_data()
            elif chart_type == ChartType.PATTERN_PIE:
                return await self._get_pattern_pie_chart_data()
            elif chart_type == ChartType.MONTHLY_RETURNS:
                return await self._get_monthly_returns_chart_data()
            elif chart_type == ChartType.WIN_RATE_BY_PATTERN:
                return await self._get_win_rate_pattern_chart_data()
            elif chart_type == ChartType.WHALE_PERFORMANCE:
                return await self._get_whale_performance_chart_data()
            elif chart_type == ChartType.RISK_METRICS:
                return await self._get_risk_metrics_chart_data()
            elif chart_type == ChartType.TIMING_ANALYSIS:
                return await self._get_timing_analysis_chart_data()
            elif chart_type == ChartType.LIQUIDITY_SLIPPAGE:
                return await self._get_liquidity_slippage_chart_data()
            else:
                raise ValueError(f"Unknown chart type: {chart_type}")
                
        except Exception as e:
            logger.error(f"Error generating chart data for {chart_type}: {e}")
            raise
    
    async def _get_equity_chart_data(self) -> ChartData:
        """Generate equity curve chart data."""
        equity_df = await self.get_equity_curve(days=30)
        
        if equity_df.empty:
            return ChartData(
                chart_type=ChartType.EQUITY,
                labels=[],
                datasets=[],
                options={'title': 'Equity Curve', 'yAxisLabel': 'Portfolio Value ($)'}
            )
        
        labels = equity_df['date'].dt.strftime('%m/%d').tolist() if 'date' in equity_df.columns else []
        values = equity_df['portfolio_value'].tolist() if 'portfolio_value' in equity_df.columns else []
        
        return ChartData(
            chart_type=ChartType.EQUITY,
            labels=labels,
            datasets=[{
                'label': 'Portfolio Value',
                'data': values,
                'borderColor': '#10b981',
                'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                'fill': True,
                'tension': 0.4
            }],
            options={
                'title': 'Equity Curve',
                'yAxisLabel': 'Portfolio Value ($)',
                'xAxisLabel': 'Date'
            }
        )
    
    async def _get_drawdown_chart_data(self) -> ChartData:
        """Generate drawdown chart data."""
        equity_df = await self.get_equity_curve(days=30)
        
        if equity_df.empty or len(equity_df) < 2:
            return ChartData(
                chart_type=ChartType.DRAWDOWN,
                labels=[],
                datasets=[],
                options={'title': 'Drawdown', 'yAxisLabel': 'Drawdown %'}
            )
        
        # Calculate drawdown
        equity_df['rolling_max'] = equity_df['portfolio_value'].expanding().max()
        equity_df['drawdown'] = ((equity_df['portfolio_value'] - equity_df['rolling_max']) / equity_df['rolling_max']) * 100
        
        labels = equity_df['date'].dt.strftime('%m/%d').tolist() if 'date' in equity_df.columns else []
        values = equity_df['drawdown'].tolist()
        
        return ChartData(
            chart_type=ChartType.DRAWDOWN,
            labels=labels,
            datasets=[{
                'label': 'Drawdown %',
                'data': values,
                'borderColor': '#ef4444',
                'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                'fill': True,
                'tension': 0.1
            }],
            options={
                'title': 'Portfolio Drawdown',
                'yAxisLabel': 'Drawdown %',
                'xAxisLabel': 'Date'
            }
        )
    
    async def _get_trade_distribution_chart_data(self) -> ChartData:
        """Generate trade distribution chart data."""
        df = self._get_trades_df()
        
        if df.empty:
            return ChartData(
                chart_type=ChartType.TRADE_DISTRIBUTION,
                labels=[],
                datasets=[],
                options={'title': 'Trade P&L Distribution'}
            )
        
        # Create P&L histogram
        pnl_values = df['pnl'].tolist()
        
        # Bin the data
        bins = np.linspace(min(pnl_values), max(pnl_values), 20)
        hist, bin_edges = np.histogram(pnl_values, bins=bins)
        
        labels = [f"${bin_edges[i]:.0f}-${bin_edges[i+1]:.0f}" for i in range(len(bin_edges)-1)]
        
        return ChartData(
            chart_type=ChartType.TRADE_DISTRIBUTION,
            labels=labels,
            datasets=[{
                'label': 'Number of Trades',
                'data': hist.tolist(),
                'backgroundColor': 'rgba(59, 130, 246, 0.6)',
                'borderColor': '#3b82f6',
                'borderWidth': 1
            }],
            options={
                'title': 'Trade P&L Distribution',
                'yAxisLabel': 'Number of Trades',
                'xAxisLabel': 'P&L Range'
            }
        )
    
    async def _get_pattern_pie_chart_data(self) -> ChartData:
        """Generate pattern performance pie chart data."""
        pattern_perf = await self.get_pattern_performance()
        
        if not pattern_perf:
            return ChartData(
                chart_type=ChartType.PATTERN_PIE,
                labels=[],
                datasets=[],
                options={'title': 'Performance by Pattern'}
            )
        
        labels = list(pattern_perf.keys())
        values = [p.get('total_pnl', 0) for p in pattern_perf.values()]
        colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']
        
        return ChartData(
            chart_type=ChartType.PATTERN_PIE,
            labels=labels,
            datasets=[{
                'data': values,
                'backgroundColor': colors[:len(labels)],
                'borderColor': '#ffffff',
                'borderWidth': 2
            }],
            options={
                'title': 'P&L by Pattern Type',
                'chartType': 'pie'
            }
        )
    
    async def _get_monthly_returns_chart_data(self) -> ChartData:
        """Generate monthly returns bar chart data."""
        df = self._get_trades_df()
        
        if df.empty or 'entry_time' not in df.columns:
            return ChartData(
                chart_type=ChartType.MONTHLY_RETURNS,
                labels=[],
                datasets=[],
                options={'title': 'Monthly Returns'}
            )
        
        df['month'] = pd.to_datetime(df['entry_time']).dt.to_period('M')
        monthly = df.groupby('month')['pnl'].sum().reset_index()
        
        labels = [str(m) for m in monthly['month']]
        values = monthly['pnl'].tolist()
        
        colors = ['#10b981' if v >= 0 else '#ef4444' for v in values]
        
        return ChartData(
            chart_type=ChartType.MONTHLY_RETURNS,
            labels=labels,
            datasets=[{
                'label': 'Monthly P&L',
                'data': values,
                'backgroundColor': colors,
                'borderColor': colors,
                'borderWidth': 1
            }],
            options={
                'title': 'Monthly Returns',
                'yAxisLabel': 'P&L ($)',
                'xAxisLabel': 'Month'
            }
        )
    
    async def _get_win_rate_pattern_chart_data(self) -> ChartData:
        """Generate win rate by pattern chart data."""
        pattern_perf = await self.get_pattern_performance()
        
        if not pattern_perf:
            return ChartData(
                chart_type=ChartType.WIN_RATE_BY_PATTERN,
                labels=[],
                datasets=[],
                options={'title': 'Win Rate by Pattern'}
            )
        
        labels = list(pattern_perf.keys())
        win_rates = [p.get('win_rate', 0) * 100 for p in pattern_perf.values()]
        trade_counts = [p.get('trades', 0) for p in pattern_perf.values()]
        
        return ChartData(
            chart_type=ChartType.WIN_RATE_BY_PATTERN,
            labels=labels,
            datasets=[
                {
                    'label': 'Win Rate %',
                    'data': win_rates,
                    'backgroundColor': 'rgba(59, 130, 246, 0.6)',
                    'borderColor': '#3b82f6',
                    'borderWidth': 1,
                    'yAxisID': 'y'
                },
                {
                    'label': 'Trade Count',
                    'data': trade_counts,
                    'backgroundColor': 'rgba(245, 158, 11, 0.6)',
                    'borderColor': '#f59e0b',
                    'borderWidth': 1,
                    'yAxisID': 'y1'
                }
            ],
            options={
                'title': 'Win Rate and Trade Count by Pattern',
                'yAxisLabel': 'Win Rate %',
                'xAxisLabel': 'Pattern Type',
                'dualAxis': True
            }
        )
    
    async def _get_whale_performance_chart_data(self) -> ChartData:
        """Generate whale performance chart data."""
        whale_rankings = await self.get_whale_leaderboard(limit=10)
        
        if not whale_rankings:
            return ChartData(
                chart_type=ChartType.WHALE_PERFORMANCE,
                labels=[],
                datasets=[],
                options={'title': 'Whale Copy Performance'}
            )
        
        labels = [w.whale_address[:8] + '...' for w in whale_rankings]
        pnls = [w.copy_pnl for w in whale_rankings]
        win_rates = [w.copy_win_rate * 100 for w in whale_rankings]
        
        return ChartData(
            chart_type=ChartType.WHALE_PERFORMANCE,
            labels=labels,
            datasets=[
                {
                    'label': 'Total P&L',
                    'data': pnls,
                    'backgroundColor': 'rgba(16, 185, 129, 0.6)',
                    'borderColor': '#10b981',
                    'borderWidth': 1,
                    'yAxisID': 'y'
                },
                {
                    'label': 'Win Rate %',
                    'data': win_rates,
                    'type': 'line',
                    'borderColor': '#f59e0b',
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'pointRadius': 4,
                    'yAxisID': 'y1'
                }
            ],
            options={
                'title': 'Whale Copy Performance',
                'yAxisLabel': 'P&L ($)',
                'xAxisLabel': 'Whale',
                'dualAxis': True
            }
        )
    
    async def _get_risk_metrics_chart_data(self) -> ChartData:
        """Generate risk metrics radar chart data."""
        risk_metrics = await self.get_risk_metrics()
        
        # Normalize metrics to 0-100 scale for radar chart
        labels = [
            'VaR 95%',
            'Volatility',
            'Sharpe',
            'Max Drawdown',
            'Win Streak',
            'Profit Factor'
        ]
        
        values = [
            min(100, abs(risk_metrics.var_95) / 100),
            min(100, risk_metrics.volatility_annual),
            min(100, max(0, getattr(risk_metrics, 'sharpe_ratio', 0)) * 20),
            min(100, risk_metrics.expected_max_drawdown * 100),
            min(100, risk_metrics.max_consecutive_wins * 10),
            min(100, getattr(risk_metrics, 'profit_factor', 1) * 20)
        ]
        
        return ChartData(
            chart_type=ChartType.RISK_METRICS,
            labels=labels,
            datasets=[{
                'label': 'Risk Metrics',
                'data': values,
                'backgroundColor': 'rgba(59, 130, 246, 0.2)',
                'borderColor': '#3b82f6',
                'borderWidth': 2,
                'pointBackgroundColor': '#3b82f6'
            }],
            options={
                'title': 'Risk Metrics Overview',
                'chartType': 'radar',
                'scales': {
                    'r': {
                        'min': 0,
                        'max': 100
                    }
                }
            }
        )
    
    async def _get_timing_analysis_chart_data(self) -> ChartData:
        """Generate timing analysis chart data."""
        timing_data = await self.get_timing_analysis()
        
        slippage_by_hour = timing_data.get('slippage_by_hour', {})
        
        if not slippage_by_hour:
            return ChartData(
                chart_type=ChartType.TIMING_ANALYSIS,
                labels=[],
                datasets=[],
                options={'title': 'Timing Analysis'}
            )
        
        # Sort by hour
        hours = sorted(slippage_by_hour.keys())
        slippages = [slippage_by_hour[h] for h in hours]
        
        labels = [f"{h:02d}:00" for h in hours]
        
        return ChartData(
            chart_type=ChartType.TIMING_ANALYSIS,
            labels=labels,
            datasets=[{
                'label': 'Avg Slippage %',
                'data': slippages,
                'backgroundColor': 'rgba(139, 92, 246, 0.6)',
                'borderColor': '#8b5cf6',
                'borderWidth': 1
            }],
            options={
                'title': 'Slippage by Hour of Day',
                'yAxisLabel': 'Slippage %',
                'xAxisLabel': 'Hour'
            }
        )
    
    async def _get_liquidity_slippage_chart_data(self) -> ChartData:
        """Generate liquidity vs slippage scatter plot data."""
        df = self._get_trades_df()
        
        if df.empty or 'liquidity' not in df.columns or 'slippage' not in df.columns:
            return ChartData(
                chart_type=ChartType.LIQUIDITY_SLIPPAGE,
                labels=[],
                datasets=[],
                options={'title': 'Liquidity vs Slippage'}
            )
        
        # Create scatter data
        data_points = [
            {'x': row['liquidity'], 'y': row['slippage']}
            for _, row in df.iterrows()
            if pd.notna(row['liquidity']) and pd.notna(row['slippage'])
        ]
        
        return ChartData(
            chart_type=ChartType.LIQUIDITY_SLIPPAGE,
            labels=[],
            datasets=[{
                'label': 'Trades',
                'data': data_points,
                'backgroundColor': 'rgba(59, 130, 246, 0.6)',
                'borderColor': '#3b82f6',
                'pointRadius': 5
            }],
            options={
                'title': 'Liquidity vs Slippage',
                'yAxisLabel': 'Slippage %',
                'xAxisLabel': 'Liquidity ($)',
                'chartType': 'scatter'
            }
        )

    # ==================== Utility Methods ====================
    
    def record_trade(
        self,
        trade_id: str,
        market_id: str,
        direction: str,
        entry_price: float,
        exit_price: Optional[float],
        size: float,
        pnl: float,
        **kwargs
    ):
        """
        Record a trade to the database.
        
        Args:
            trade_id: Unique trade identifier
            market_id: Market identifier
            direction: 'YES' or 'NO'
            entry_price: Entry price
            exit_price: Exit price (None if still open)
            size: Position size
            pnl: Realized or unrealized P&L
            **kwargs: Additional fields (whale_address, pattern_type, etc.)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trades (
                        trade_id, market_id, market_question, direction,
                        entry_price, exit_price, size, entry_time, exit_time,
                        pnl, exit_reason, whale_address, pattern_type, slippage, liquidity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    market_id,
                    kwargs.get('market_question', ''),
                    direction,
                    entry_price,
                    exit_price,
                    size,
                    kwargs.get('entry_time', datetime.now().isoformat()),
                    kwargs.get('exit_time'),
                    pnl,
                    kwargs.get('exit_reason'),
                    kwargs.get('whale_address'),
                    kwargs.get('pattern_type'),
                    kwargs.get('slippage', 0),
                    kwargs.get('liquidity', 0)
                ))
                conn.commit()
            
            # Clear relevant caches
            self.clear_cache()
            logger.debug(f"Recorded trade: {trade_id}")
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    def record_portfolio_snapshot(
        self,
        total_value: float,
        available_balance: float,
        total_exposure: float,
        open_positions: int,
        daily_pnl: float,
        total_pnl: float
    ):
        """
        Record portfolio snapshot.
        
        Args:
            total_value: Total portfolio value
            available_balance: Available balance
            total_exposure: Total position exposure
            open_positions: Number of open positions
            daily_pnl: Daily P&L
            total_pnl: Total P&L
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Calculate drawdown
                cursor = conn.execute(
                    "SELECT MAX(total_value) FROM portfolio_snapshots"
                )
                peak = cursor.fetchone()[0] or total_value
                
                if total_value < peak:
                    drawdown = (peak - total_value) / peak
                else:
                    drawdown = 0.0
                
                conn.execute("""
                    INSERT INTO portfolio_snapshots (
                        timestamp, total_value, available_balance,
                        total_exposure, open_positions, daily_pnl, total_pnl, drawdown_percent
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    total_value,
                    available_balance,
                    total_exposure,
                    open_positions,
                    daily_pnl,
                    total_pnl,
                    drawdown
                ))
                conn.commit()
            
            logger.debug(f"Recorded portfolio snapshot: ${total_value:,.2f}")
            
        except Exception as e:
            logger.error(f"Error recording portfolio snapshot: {e}")
    
    def record_whale_copy(
        self,
        whale_address: str,
        trade_id: str,
        our_pnl: float,
        whale_pnl: Optional[float] = None,
        copy_delay_seconds: float = 0,
        slippage: float = 0
    ):
        """
        Record whale copy performance.
        
        Args:
            whale_address: Whale wallet address
            trade_id: Our trade ID
            our_pnl: Our P&L from copying
            whale_pnl: Whale's P&L (if known)
            copy_delay_seconds: Delay in copying
            slippage: Slippage experienced
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO whale_copy_performance (
                        whale_address, trade_id, our_pnl, whale_pnl,
                        copy_delay_seconds, slippage, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    whale_address,
                    trade_id,
                    our_pnl,
                    whale_pnl,
                    copy_delay_seconds,
                    slippage,
                    datetime.now().isoformat()
                ))
                conn.commit()
            
            logger.debug(f"Recorded whale copy: {whale_address[:8]}... trade {trade_id}")
            
        except Exception as e:
            logger.error(f"Error recording whale copy: {e}")
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get quick performance summary for dashboards.
        
        Returns:
            Dictionary with key metrics
        """
        try:
            portfolio = await self.get_portfolio_summary()
            trades = await self.get_trade_statistics()
            risk = await self.get_risk_metrics()
            
            return {
                'portfolio': {
                    'current_value': portfolio.current_value,
                    'total_pnl': portfolio.total_pnl,
                    'total_pnl_percent': portfolio.total_pnl_percent,
                    'current_drawdown': portfolio.current_drawdown,
                    'open_positions': portfolio.open_positions
                },
                'trading': {
                    'total_trades': trades.total_trades,
                    'win_rate': trades.win_rate,
                    'profit_factor': trades.profit_factor,
                    'expectancy': trades.expectancy
                },
                'risk': {
                    'var_95': risk.var_95,
                    'sharpe_ratio': getattr(risk, 'sharpe_ratio', 0),
                    'max_drawdown': portfolio.max_drawdown
                },
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def export_data(self, format: str = 'json', start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> str:
        """
        Export performance data to file.
        
        Args:
            format: Export format ('json' or 'csv')
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Path to exported file
        """
        try:
            # Get trades data
            df = self._get_trades_df(start_date=start_date, end_date=end_date)
            
            if df.empty:
                return ""
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format == 'json':
                filepath = f"trades_export_{timestamp}.json"
                df.to_json(filepath, orient='records', date_format='iso')
            else:
                filepath = f"trades_export_{timestamp}.csv"
                df.to_csv(filepath, index=False)
            
            logger.info(f"Data exported to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return ""


# Convenience function for quick dashboard setup
def create_performance_dashboard(
    db_path: Optional[str] = None,
    cache_ttl: int = 300,
    bankroll: float = 10000.0
) -> PerformanceDashboard:
    """
    Create and configure a PerformanceDashboard instance.
    
    Args:
        db_path: Path to database
        cache_ttl: Cache TTL in seconds
        bankroll: Initial bankroll
        
    Returns:
        Configured PerformanceDashboard
    """
    return PerformanceDashboard(
        db_path=db_path,
        cache_ttl=cache_ttl,
        bankroll=bankroll
    )
