"""
Comprehensive Backtesting Framework for PolyBot

Allows testing copy-trading strategies on historical data with:
- Realistic fee modeling (2% per trade)
- Slippage modeling
- Multiple strategy types
- Monte Carlo simulation
- Risk analysis
- Async data loading
"""

import asyncio
import json
import uuid
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
from pathlib import Path
import logging

# Type checking imports for optional dependencies
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ..analysis.pattern_engine import SignalType, PatternConfidence, PatternSignal
from ..winners.ev_calculator import EVCalculator, CopyEV, EVGrade
from ..utils.logger import setup_logging

logger = setup_logging()


class StrategyType(Enum):
    """Types of copy-trading strategies."""
    COPY_ALL_WHALE = "copy_all_whale"                    # Copy every whale trade
    COPY_HIGH_CONFIDENCE = "copy_high_confidence"        # Only > 70% confidence
    COPY_LARGE_TRADES = "copy_large_trades"              # Only > $10k trades
    COPY_CRYPTO_ONLY = "copy_crypto_only"                # Only crypto markets
    COPY_TOP_WINNERS = "copy_top_winners"                # Only top 10% performers
    COPY_PATTERN_ALIGNED = "copy_pattern_aligned"        # Align with detected patterns
    COPY_KELLY_SIZED = "copy_kelly_sized"                # Kelly criterion sizing
    CUSTOM_FILTER = "custom_filter"                      # User-defined filters


class TradeStatus(Enum):
    """Status of a backtest trade."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class BacktestTrade:
    """A single trade in the backtest."""
    # Identification (required)
    trade_id: str
    timestamp: datetime
    market_id: str
    whale_address: str
    whale_confidence: float
    direction: str  # 'YES' or 'NO'
    entry_price: float
    
    # Market info (optional)
    market_question: str = ""
    pattern_type: Optional[SignalType] = None
    
    # Trade details (optional)
    exit_price: Optional[float] = None
    size: float = 0.0
    
    # Execution (optional)
    intended_entry_price: float = 0.0
    slippage: float = 0.0
    fees_paid: float = 0.0
    
    # Exit (optional)
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None  # 'take_profit', 'stop_loss', 'time_exit', 'market_close'
    
    # P&L (optional)
    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Status (optional)
    status: TradeStatus = TradeStatus.PENDING
    
    # Risk metrics (optional)
    r_multiple: float = 0.0
    max_drawdown_during_trade: float = 0.0
    
    # Metadata (optional)
    market_liquidity: float = 0.0
    market_volatility: float = 0.0
    holding_period_hours: float = 0.0


@dataclass
class EquityPoint:
    """A point on the equity curve."""
    timestamp: datetime
    equity: float
    drawdown: float
    drawdown_percent: float
    open_positions: int
    trade_id: Optional[str] = None  # If point is from a trade


@dataclass
class BacktestResult:
    """Complete backtest results."""
    # Basic info
    strategy_name: str
    strategy_type: StrategyType
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    # Returns
    total_return: float
    total_return_percent: float
    annualized_return: float
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk (95%)
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    # Trade metrics
    avg_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_trade_duration: float = 0.0
    
    # R-multiples
    avg_r_multiple: float = 0.0
    r_expectancy: float = 0.0
    
    # Advanced metrics
    skewness: float = 0.0
    kurtosis: float = 0.0
    
    # Data
    equity_curve: List[EquityPoint] = field(default_factory=list)
    trade_log: List[BacktestTrade] = field(default_factory=list)
    
    # By category
    performance_by_pattern: Dict[str, Dict] = field(default_factory=dict)
    performance_by_whale: Dict[str, Dict] = field(default_factory=dict)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    config: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'strategy_name': self.strategy_name,
            'strategy_type': self.strategy_type.value,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'total_return_percent': self.total_return_percent,
            'annualized_return': self.annualized_return,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_percent': self.max_drawdown_percent,
            'calmar_ratio': self.calmar_ratio,
            'volatility': self.volatility,
            'var_95': self.var_95,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'avg_trade': self.avg_trade,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'avg_trade_duration': self.avg_trade_duration,
            'avg_r_multiple': self.avg_r_multiple,
            'r_expectancy': self.r_expectancy,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
        }


@dataclass
class StrategyConfig:
    """Configuration for a backtest strategy."""
    strategy_type: StrategyType
    name: str = "Unnamed Strategy"
    
    # Filters
    min_whale_confidence: float = 0.6
    min_trade_size: float = 0.0
    max_trade_size: float = float('inf')
    min_market_liquidity: float = 10000.0
    allowed_patterns: List[SignalType] = field(default_factory=list)
    excluded_patterns: List[SignalType] = field(default_factory=list)
    allowed_whales: List[str] = field(default_factory=list)
    excluded_whales: List[str] = field(default_factory=list)
    market_categories: List[str] = field(default_factory=list)  # Empty = all
    
    # Risk management
    position_size_percent: float = 0.02  # 2% per trade
    max_positions: int = 5
    use_kelly_sizing: bool = False
    kelly_fraction: float = 0.5
    max_risk_per_trade: float = 0.02
    
    # Execution
    slippage_model: str = "liquidity_based"  # 'fixed', 'liquidity_based', 'volatility_based'
    fixed_slippage: float = 0.001  # 0.1%
    fee_percent: float = 0.02  # 2% per trade
    
    # Exit conditions
    use_stop_loss: bool = True
    stop_loss_percent: float = 0.05  # 5%
    use_take_profit: bool = True
    take_profit_percent: float = 0.10  # 10%
    max_holding_hours: float = 24.0
    
    # Custom filter function
    custom_filter_fn: Optional[Callable[[Dict], bool]] = None


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    num_simulations: int
    confidence_level: float
    
    # Return statistics
    mean_return: float
    median_return: float
    std_return: float
    min_return: float
    max_return: float
    
    # Percentiles
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    
    # Drawdown
    mean_max_drawdown: float
    worst_case_drawdown: float
    
    # Probability metrics
    prob_profit: float  # P(return > 0)
    prob_double: float  # P(return > 100%)
    prob_ruin: float    # P(drawdown > 50%)
    
    # Worst case scenarios
    worst_cases: List[Dict] = field(default_factory=list)


class BacktestEngine:
    """
    Comprehensive backtesting engine for PolyBot copy-trading strategies.
    
    Features:
    - Historical data loading from subgraph/database
    - Multiple strategy types with customizable filters
    - Realistic fee and slippage modeling
    - Risk-adjusted position sizing
    - Monte Carlo simulation
    - Comprehensive performance metrics
    - Export capabilities
    """
    
    # Default fee structure (Polymarket)
    DEFAULT_FEE_PERCENT = 0.02  # 2% per trade
    DEFAULT_SLIPPAGE_MODEL = "liquidity_based"
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize the backtest engine.
        
        Args:
            initial_capital: Starting capital for the backtest
            start_date: Start date for historical data
            end_date: End date for historical data
            config: Additional configuration options
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.start_date = start_date or (datetime.now() - timedelta(days=90))
        self.end_date = end_date or datetime.now()
        self.config = config or {}
        
        # Data storage
        self.historical_trades: List[Dict] = []
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.whale_profiles: Dict[str, Dict] = {}
        
        # Backtest state
        self.equity_curve: List[EquityPoint] = []
        self.trade_log: List[BacktestTrade] = []
        self.open_positions: Dict[str, BacktestTrade] = {}
        self.peak_capital = initial_capital
        self.current_drawdown = 0.0
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        self._progress = 0.0
        
        # Cache for calculations
        self._returns_cache: Optional[List[float]] = None
        
        logger.info(f"BacktestEngine initialized: ${initial_capital:,.2f} capital, "
                   f"period: {self.start_date.date()} to {self.end_date.date()}")
    
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set a callback for progress updates."""
        self.progress_callback = callback
    
    def _update_progress(self, progress: float, message: str = ""):
        """Update progress."""
        self._progress = min(1.0, max(0.0, progress))
        if self.progress_callback:
            self.progress_callback(self._progress, message)
        logger.debug(f"Backtest progress: {self._progress:.1%} - {message}")
    
    # =========================================================================
    # Data Loading Methods
    # =========================================================================
    
    async def load_historical_data(
        self,
        whale_addresses: List[str],
        markets: Optional[List[str]] = None,
        data_source: str = "subgraph"
    ) -> int:
        """
        Load historical trade data asynchronously.
        
        Args:
            whale_addresses: List of whale addresses to track
            markets: Optional list of market IDs to filter
            data_source: 'subgraph', 'database', or 'csv'
            
        Returns:
            Number of trades loaded
        """
        self._update_progress(0.0, "Loading historical data...")
        
        if data_source == "subgraph":
            return await self._load_from_subgraph(whale_addresses, markets)
        elif data_source == "database":
            return await self._load_from_database(whale_addresses, markets)
        elif data_source == "csv":
            return self._load_from_csv(whale_addresses, markets)
        else:
            raise ValueError(f"Unknown data source: {data_source}")
    
    async def _load_from_subgraph(
        self,
        whale_addresses: List[str],
        markets: Optional[List[str]]
    ) -> int:
        """Load data from The Graph subgraph."""
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, falling back to synchronous loading")
            return self._load_from_subgraph_sync(whale_addresses, markets)
        
        try:
            from ..data.subgraph_client import SubgraphClient
            from ..utils.config import Config
            
            config = Config.from_env()
            client = SubgraphClient(config.thegraph_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize subgraph client: {e}")
            return 0
        
        all_trades = []
        total = len(whale_addresses)
        
        for i, address in enumerate(whale_addresses):
            try:
                # Run synchronous subgraph call in thread pool
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None, client.get_all_trades, address
                )
                
                if not df.empty:
                    # Filter by date
                    df = df[
                        (df['timestamp'] >= self.start_date) &
                        (df['timestamp'] <= self.end_date)
                    ]
                    
                    # Filter by markets if specified
                    if markets:
                        df = df[df['market'].isin(markets)]
                    
                    # Convert to dict records
                    trades = df.to_dict('records')
                    for trade in trades:
                        trade['whale_address'] = address
                    
                    all_trades.extend(trades)
                
                self._update_progress((i + 1) / total, f"Loaded {address[:10]}...")
                
            except Exception as e:
                logger.error(f"Error loading trades for {address}: {e}")
        
        self.historical_trades = all_trades
        logger.info(f"Loaded {len(all_trades)} trades from subgraph")
        return len(all_trades)
    
    def _load_from_subgraph_sync(
        self,
        whale_addresses: List[str],
        markets: Optional[List[str]]
    ) -> int:
        """Synchronous fallback for subgraph loading."""
        try:
            from ..data.subgraph_client import SubgraphClient
            from ..utils.config import Config
            
            config = Config.from_env()
            client = SubgraphClient(config.thegraph_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize subgraph client: {e}")
            return 0
        
        all_trades = []
        
        for address in whale_addresses:
            try:
                df = client.get_all_trades(address)
                
                if not df.empty:
                    df = df[
                        (df['timestamp'] >= self.start_date) &
                        (df['timestamp'] <= self.end_date)
                    ]
                    
                    if markets:
                        df = df[df['market'].isin(markets)]
                    
                    trades = df.to_dict('records')
                    for trade in trades:
                        trade['whale_address'] = address
                    
                    all_trades.extend(trades)
                    
            except Exception as e:
                logger.error(f"Error loading trades for {address}: {e}")
        
        self.historical_trades = all_trades
        logger.info(f"Loaded {len(all_trades)} trades from subgraph (sync)")
        return len(all_trades)
    
    async def _load_from_database(
        self,
        whale_addresses: List[str],
        markets: Optional[List[str]]
    ) -> int:
        """Load data from local database."""
        # This would connect to your database
        # For now, placeholder implementation
        logger.warning("Database loading not yet implemented")
        return 0
    
    def _load_from_csv(
        self,
        whale_addresses: List[str],
        markets: Optional[List[str]]
    ) -> int:
        """Load data from CSV files."""
        csv_path = self.config.get('csv_path', 'data/trades.csv')
        
        try:
            df = pd.read_csv(csv_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter by date
            df = df[
                (df['timestamp'] >= self.start_date) &
                (df['timestamp'] <= self.end_date)
            ]
            
            # Filter by whales
            df = df[df['whale_address'].isin([a.lower() for a in whale_addresses])]
            
            if markets:
                df = df[df['market_id'].isin(markets)]
            
            self.historical_trades = df.to_dict('records')
            logger.info(f"Loaded {len(self.historical_trades)} trades from CSV")
            return len(self.historical_trades)
            
        except Exception as e:
            logger.error(f"Error loading CSV: {e}")
            return 0
    
    def load_market_data(
        self,
        market_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load market price data for a specific market.
        
        Args:
            market_id: Market condition ID
            start: Start date (default: backtest start)
            end: End date (default: backtest end)
            
        Returns:
            DataFrame with price data
        """
        start = start or self.start_date
        end = end or self.end_date
        
        # This would load from your data source
        # For now, create synthetic data structure
        dates = pd.date_range(start=start, end=end, freq='1H')
        df = pd.DataFrame({
            'timestamp': dates,
            'price': np.random.uniform(0.3, 0.7, len(dates)),  # Placeholder
            'volume': np.random.exponential(10000, len(dates)),
            'liquidity': np.random.exponential(50000, len(dates)),
        })
        
        self.market_data[market_id] = df
        return df
    
    def filter_by_pattern(self, pattern_type: SignalType) -> List[Dict]:
        """
        Filter loaded trades by pattern type.
        
        Args:
            pattern_type: Pattern to filter by
            
        Returns:
            Filtered list of trades
        """
        if not self.historical_trades:
            return []
        
        # This would check pattern classification from data
        # For now, simple filtering based on metadata
        filtered = [
            trade for trade in self.historical_trades
            if trade.get('pattern_type') == pattern_type.value
        ]
        
        logger.info(f"Filtered {len(filtered)} trades by pattern {pattern_type.value}")
        return filtered
    
    # =========================================================================
    # Strategy Execution Methods
    # =========================================================================
    
    def run_backtest(self, strategy_config: StrategyConfig) -> BacktestResult:
        """
        Run a complete backtest with the given strategy configuration.
        
        Args:
            strategy_config: Strategy configuration
            
        Returns:
            BacktestResult with full results
        """
        logger.info(f"Starting backtest: {strategy_config.name}")
        self._update_progress(0.0, "Initializing backtest...")
        
        # Reset state
        self.current_capital = self.initial_capital
        self.equity_curve = []
        self.trade_log = []
        self.open_positions = {}
        self.peak_capital = self.initial_capital
        self.current_drawdown = 0.0
        
        # Record initial equity point
        self.equity_curve.append(EquityPoint(
            timestamp=self.start_date,
            equity=self.initial_capital,
            drawdown=0.0,
            drawdown_percent=0.0,
            open_positions=0
        ))
        
        # Filter trades by strategy criteria
        eligible_trades = self._filter_trades(strategy_config)
        total_trades = len(eligible_trades)
        
        logger.info(f"Processing {total_trades} eligible trades")
        
        # Sort trades by timestamp
        eligible_trades.sort(key=lambda x: x.get('timestamp', self.start_date))
        
        # Process each trade
        for i, trade_data in enumerate(eligible_trades):
            try:
                self._process_trade(trade_data, strategy_config)
                
                if i % 10 == 0:
                    self._update_progress(
                        (i + 1) / total_trades,
                        f"Processing trade {i+1}/{total_trades}"
                    )
                    
            except Exception as e:
                logger.error(f"Error processing trade: {e}")
                continue
        
        # Close any remaining open positions at last known price
        self._close_all_positions(strategy_config)
        
        # Calculate final results
        self._update_progress(1.0, "Calculating results...")
        result = self._calculate_result(strategy_config)
        
        logger.info(f"Backtest complete: {result.total_return_percent:+.2%} return, "
                   f"{result.total_trades} trades")
        
        return result
    
    def _filter_trades(self, config: StrategyConfig) -> List[Dict]:
        """Filter trades based on strategy configuration."""
        filtered = []
        
        for trade in self.historical_trades:
            # Check whale confidence
            whale_conf = trade.get('whale_confidence', 0.5)
            if whale_conf < config.min_whale_confidence:
                continue
            
            # Check trade size
            trade_size = trade.get('size', 0)
            if trade_size < config.min_trade_size:
                continue
            if trade_size > config.max_trade_size:
                continue
            
            # Check whale allowlist/blocklist
            whale = trade.get('whale_address', '').lower()
            if config.allowed_whales and whale not in [w.lower() for w in config.allowed_whales]:
                continue
            if whale in [w.lower() for w in config.excluded_whales]:
                continue
            
            # Check pattern
            pattern = trade.get('pattern_type')
            if config.allowed_patterns and pattern not in [p.value for p in config.allowed_patterns]:
                continue
            if pattern in [p.value for p in config.excluded_patterns]:
                continue
            
            # Check custom filter
            if config.custom_filter_fn and not config.custom_filter_fn(trade):
                continue
            
            filtered.append(trade)
        
        return filtered
    
    def _process_trade(self, trade_data: Dict, config: StrategyConfig):
        """Process a single trade through the backtest."""
        # Check position limits
        if len(self.open_positions) >= config.max_positions:
            # Close oldest position if needed
            if config.max_positions > 0:
                oldest = min(self.open_positions.values(), key=lambda x: x.timestamp)
                self._close_position(oldest.trade_id, trade_data.get('timestamp'), 'position_limit')
        
        # Simulate the trade
        trade = self.simulate_trade(trade_data, config)
        
        if trade:
            self.trade_log.append(trade)
            self.open_positions[trade.trade_id] = trade
            
            # Update equity after entry
            self._update_equity(trade.timestamp, trade.trade_id)
            
            # Check if position should be closed immediately (stop/target)
            self._check_exit_conditions(trade, trade_data, config)
    
    def simulate_trade(
        self,
        signal: Dict,
        config: StrategyConfig
    ) -> Optional[BacktestTrade]:
        """
        Simulate a single trade execution.
        
        Args:
            signal: Trade signal data
            config: Strategy configuration
            
        Returns:
            BacktestTrade if executed, None if rejected
        """
        timestamp = signal.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = pd.to_datetime(timestamp)
        
        # Get market data
        market_id = signal.get('market_id') or signal.get('market', {}).get('id', 'unknown')
        
        # Calculate position size
        if config.use_kelly_sizing:
            size = self._calculate_kelly_size(signal, config)
        else:
            size = self.current_capital * config.position_size_percent
        
        # Apply min/max constraints
        size = max(size, 100)  # Minimum $100
        size = min(size, self.current_capital * 0.5)  # Max 50% of capital
        
        # Get entry price with slippage
        intended_price = float(signal.get('price', 0.5))
        market_liquidity = signal.get('market', {}).get('liquidity', 50000)
        market_volatility = signal.get('volatility', 0.1)
        
        slippage = self.apply_slippage(size, market_liquidity, market_volatility, config)
        entry_price = intended_price * (1 + slippage)
        
        # Calculate fees
        fees = size * config.fee_percent
        
        # Create trade record
        trade = BacktestTrade(
            trade_id=str(uuid.uuid4())[:8],
            timestamp=timestamp,
            market_id=market_id,
            market_question=signal.get('market', {}).get('question', ''),
            whale_address=signal.get('whale_address', ''),
            whale_confidence=signal.get('whale_confidence', 0.5),
            pattern_type=SignalType(signal.get('pattern_type')) if signal.get('pattern_type') else None,
            direction='YES' if signal.get('side') == 'buy' or signal.get('outcomeIndex') == 0 else 'NO',
            entry_price=entry_price,
            intended_entry_price=intended_price,
            size=size,
            slippage=slippage,
            fees_paid=fees,
            status=TradeStatus.OPEN,
            market_liquidity=market_liquidity,
            market_volatility=market_volatility,
        )
        
        return trade
    
    def apply_slippage(
        self,
        size: float,
        liquidity: float,
        volatility: float,
        config: StrategyConfig
    ) -> float:
        """
        Apply realistic slippage based on market conditions.
        
        Args:
            size: Trade size in USD
            liquidity: Market liquidity
            volatility: Current volatility
            config: Strategy configuration
            
        Returns:
            Slippage as a percentage (positive = worse fill)
        """
        if config.slippage_model == "fixed":
            return config.fixed_slippage
        
        elif config.slippage_model == "liquidity_based":
            # Slippage increases with size/liquidity ratio
            if liquidity <= 0:
                return 0.02  # 2% if no liquidity
            
            size_ratio = size / liquidity
            base_slippage = min(0.02, size_ratio * 0.05)  # Max 2%
            
            # Add volatility adjustment
            vol_adjustment = 1 + (volatility * 2)
            
            return base_slippage * vol_adjustment
        
        elif config.slippage_model == "volatility_based":
            # Slippage based on volatility
            base = 0.001  # 0.1% base
            vol_component = volatility * 0.01
            return min(0.05, base + vol_component)  # Max 5%
        
        else:
            return config.fixed_slippage
    
    def _calculate_kelly_size(self, signal: Dict, config: StrategyConfig) -> float:
        """Calculate position size using Kelly Criterion."""
        win_prob = signal.get('win_probability', 0.55)
        
        # Estimate payoff ratio
        if signal.get('avg_win') and signal.get('avg_loss'):
            payoff = abs(signal['avg_win'] / signal['avg_loss'])
        else:
            payoff = 2.0  # Assume 2:1
        
        # Kelly formula: f = (bp - q) / b
        p = win_prob
        q = 1 - p
        b = payoff
        
        if b > 0:
            kelly = (b * p - q) / b
        else:
            kelly = 0
        
        kelly = max(0, min(1, kelly))
        
        # Apply fraction for safety
        return self.current_capital * kelly * config.kelly_fraction
    
    def _check_exit_conditions(
        self,
        trade: BacktestTrade,
        market_data: Dict,
        config: StrategyConfig
    ):
        """Check if position should be closed based on exit conditions."""
        # This would check against historical price data
        # For now, simplified logic
        
        current_price = market_data.get('exit_price', trade.entry_price)
        
        if config.use_stop_loss:
            if trade.direction == 'YES':
                stop_price = trade.entry_price * (1 - config.stop_loss_percent)
                if current_price <= stop_price:
                    self._close_position(trade.trade_id, market_data.get('timestamp'), 'stop_loss')
                    return
            else:
                stop_price = trade.entry_price * (1 + config.stop_loss_percent)
                if current_price >= stop_price:
                    self._close_position(trade.trade_id, market_data.get('timestamp'), 'stop_loss')
                    return
        
        if config.use_take_profit:
            if trade.direction == 'YES':
                target_price = trade.entry_price * (1 + config.take_profit_percent)
                if current_price >= target_price:
                    self._close_position(trade.trade_id, market_data.get('timestamp'), 'take_profit')
                    return
            else:
                target_price = trade.entry_price * (1 - config.take_profit_percent)
                if current_price <= target_price:
                    self._close_position(trade.trade_id, market_data.get('timestamp'), 'take_profit')
                    return
    
    def _close_position(
        self,
        trade_id: str,
        exit_time: Optional[datetime],
        reason: str,
        exit_price: Optional[float] = None
    ):
        """Close an open position."""
        if trade_id not in self.open_positions:
            return
        
        trade = self.open_positions[trade_id]
        
        # Determine exit price
        if exit_price is None:
            # This would look up historical price
            exit_price = trade.entry_price * (1 + np.random.uniform(-0.05, 0.1))
        
        trade.exit_price = exit_price
        trade.exit_time = exit_time or datetime.now()
        trade.exit_reason = reason
        trade.status = TradeStatus.CLOSED
        
        # Calculate P&L
        if trade.direction == 'YES':
            gross_pnl = (exit_price - trade.entry_price) * trade.size
        else:
            gross_pnl = (trade.entry_price - exit_price) * trade.size
        
        net_pnl = gross_pnl - trade.fees_paid
        
        trade.gross_pnl = gross_pnl
        trade.net_pnl = net_pnl
        trade.pnl_percent = (net_pnl / trade.size) * 100 if trade.size > 0 else 0
        
        # Calculate R-multiple
        risk_amount = trade.size * 0.05  # Assuming 5% stop
        trade.r_multiple = net_pnl / risk_amount if risk_amount > 0 else 0
        
        # Update capital
        self.current_capital += net_pnl
        
        # Remove from open positions
        del self.open_positions[trade_id]
        
        # Update equity
        self._update_equity(trade.exit_time, trade_id)
        
        logger.debug(f"Closed position {trade_id}: ${net_pnl:+.2f} ({reason})")
    
    def _close_all_positions(self, config: StrategyConfig):
        """Close all remaining open positions at end of backtest."""
        for trade_id in list(self.open_positions.keys()):
            self._close_position(trade_id, self.end_date, 'backtest_end')
    
    def _update_equity(self, timestamp: datetime, trade_id: Optional[str] = None):
        """Update equity curve."""
        # Calculate unrealized P&L
        unrealized = sum(
            trade.unrealized_pnl for trade in self.open_positions.values()
        )
        
        total_equity = self.current_capital + unrealized
        
        # Update peak and drawdown
        if total_equity > self.peak_capital:
            self.peak_capital = total_equity
        
        drawdown = self.peak_capital - total_equity
        drawdown_pct = (drawdown / self.peak_capital) * 100 if self.peak_capital > 0 else 0
        
        self.current_drawdown = drawdown_pct
        
        self.equity_curve.append(EquityPoint(
            timestamp=timestamp,
            equity=total_equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_pct,
            open_positions=len(self.open_positions),
            trade_id=trade_id
        ))
    
    def calculate_pnl(
        self,
        entry: float,
        exit: float,
        size: float,
        fees: float,
        direction: str = 'YES'
    ) -> Tuple[float, float]:
        """
        Calculate trade P&L.
        
        Args:
            entry: Entry price
            exit: Exit price
            size: Position size
            fees: Total fees paid
            direction: 'YES' or 'NO'
            
        Returns:
            (gross_pnl, net_pnl)
        """
        if direction == 'YES':
            gross_pnl = (exit - entry) * size
        else:
            gross_pnl = (entry - exit) * size
        
        net_pnl = gross_pnl - fees
        return gross_pnl, net_pnl
    
    # =========================================================================
    # Results Analysis Methods
    # =========================================================================
    
    def _calculate_result(self, config: StrategyConfig) -> BacktestResult:
        """Calculate final backtest results."""
        closed_trades = [t for t in self.trade_log if t.status == TradeStatus.CLOSED]
        
        if not closed_trades:
            return BacktestResult(
                strategy_name=config.name,
                strategy_type=config.strategy_type,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                final_capital=self.current_capital,
                total_return=0.0,
                total_return_percent=0.0,
                annualized_return=0.0,
                equity_curve=self.equity_curve,
                trade_log=self.trade_log,
                config=asdict(config)
            )
        
        # Basic metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.net_pnl > 0]
        losing_trades = [t for t in closed_trades if t.net_pnl <= 0]
        
        wins = len(winning_trades)
        losses = len(losing_trades)
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        # P&L metrics
        gross_profit = sum(t.net_pnl for t in winning_trades)
        gross_loss = abs(sum(t.net_pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        pnls = [t.net_pnl for t in closed_trades]
        avg_trade = np.mean(pnls)
        avg_win = np.mean([t.net_pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.net_pnl for t in losing_trades]) if losing_trades else 0
        
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0
        
        # Expectancy
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss)) if total_trades > 0 else 0
        
        # R-multiples
        r_multiples = [t.r_multiple for t in closed_trades if t.r_multiple != 0]
        avg_r_multiple = np.mean(r_multiples) if r_multiples else 0
        r_expectancy = win_rate * np.mean([r for r in r_multiples if r > 0]) if r_multiples and winning_trades else 0
        
        # Duration
        durations = []
        for t in closed_trades:
            if t.exit_time and t.timestamp:
                duration = (t.exit_time - t.timestamp).total_seconds() / 3600
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0
        
        # Returns
        total_return = self.current_capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        days = max(1, (self.end_date - self.start_date).days)
        annualized_return = ((self.current_capital / self.initial_capital) ** (365.25 / days) - 1) * 100
        
        # Drawdown
        max_dd = max((p.drawdown for p in self.equity_curve), default=0)
        max_dd_pct = max((p.drawdown_percent for p in self.equity_curve), default=0)
        
        # Volatility (daily returns)
        equity_values = [p.equity for p in self.equity_curve]
        if len(equity_values) > 1:
            returns = np.diff(equity_values) / equity_values[:-1]
            volatility = np.std(returns) * np.sqrt(365) * 100  # Annualized
        else:
            volatility = 0
        
        # Sharpe ratio (assuming 0% risk-free rate for simplicity)
        if volatility > 0:
            sharpe = annualized_return / volatility
        else:
            sharpe = 0
        
        # Sortino ratio (downside deviation)
        if len(equity_values) > 1:
            negative_returns = [r for r in np.diff(equity_values) / equity_values[:-1] if r < 0]
            downside_dev = np.std(negative_returns) * np.sqrt(365) if negative_returns else 0.0001
            sortino = annualized_return / downside_dev if downside_dev > 0 else 0
        else:
            sortino = 0
        
        # Calmar ratio
        calmar = annualized_return / max_dd_pct if max_dd_pct > 0 else 0
        
        # VaR 95%
        if pnls:
            var_95 = np.percentile(pnls, 5)
        else:
            var_95 = 0
        
        # Distribution statistics
        skewness = stats.skew(pnls) if SCIPY_AVAILABLE and len(pnls) > 2 else 0
        kurtosis = stats.kurtosis(pnls) if SCIPY_AVAILABLE and len(pnls) > 2 else 0
        
        # Performance by pattern
        pattern_perf = self._calculate_pattern_performance(closed_trades)
        
        # Performance by whale
        whale_perf = self._calculate_whale_performance(closed_trades)
        
        # Monthly returns
        monthly_returns = self._calculate_monthly_returns()
        
        return BacktestResult(
            strategy_name=config.name,
            strategy_type=config.strategy_type,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            final_capital=self.current_capital,
            total_return=total_return,
            total_return_percent=total_return_pct,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_percent=max_dd_pct,
            calmar_ratio=calmar,
            volatility=volatility,
            var_95=var_95,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=win_rate,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_trade=avg_trade,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_trade_duration=avg_duration,
            avg_r_multiple=avg_r_multiple,
            r_expectancy=r_expectancy,
            skewness=skewness,
            kurtosis=kurtosis,
            equity_curve=self.equity_curve,
            trade_log=self.trade_log,
            performance_by_pattern=pattern_perf,
            performance_by_whale=whale_perf,
            monthly_returns=monthly_returns,
            config=asdict(config)
        )
    
    def _calculate_pattern_performance(self, trades: List[BacktestTrade]) -> Dict[str, Dict]:
        """Calculate performance breakdown by pattern."""
        pattern_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0.0})
        
        for trade in trades:
            pattern = trade.pattern_type.value if trade.pattern_type else 'unknown'
            pattern_stats[pattern]['trades'] += 1
            pattern_stats[pattern]['pnl'] += trade.net_pnl
            if trade.net_pnl > 0:
                pattern_stats[pattern]['wins'] += 1
        
        # Calculate win rates
        result = {}
        for pattern, stats in pattern_stats.items():
            result[pattern] = {
                'trades': stats['trades'],
                'win_rate': stats['wins'] / stats['trades'] if stats['trades'] > 0 else 0,
                'total_pnl': stats['pnl'],
                'avg_pnl': stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
            }
        
        return result
    
    def _calculate_whale_performance(self, trades: List[BacktestTrade]) -> Dict[str, Dict]:
        """Calculate performance breakdown by whale."""
        whale_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0.0})
        
        for trade in trades:
            whale = trade.whale_address
            whale_stats[whale]['trades'] += 1
            whale_stats[whale]['pnl'] += trade.net_pnl
            if trade.net_pnl > 0:
                whale_stats[whale]['wins'] += 1
        
        result = {}
        for whale, stats in whale_stats.items():
            result[whale] = {
                'trades': stats['trades'],
                'win_rate': stats['wins'] / stats['trades'] if stats['trades'] > 0 else 0,
                'total_pnl': stats['pnl'],
                'avg_pnl': stats['pnl'] / stats['trades'] if stats['trades'] > 0 else 0
            }
        
        return result
    
    def _calculate_monthly_returns(self) -> Dict[str, float]:
        """Calculate monthly return series."""
        if not self.equity_curve:
            return {}
        
        monthly = {}
        
        for point in self.equity_curve:
            month_key = point.timestamp.strftime('%Y-%m')
            if month_key not in monthly:
                monthly[month_key] = point.equity
        
        # Calculate returns
        months = sorted(monthly.keys())
        returns = {}
        
        for i, month in enumerate(months[1:], 1):
            prev_equity = monthly[months[i-1]]
            curr_equity = monthly[month]
            ret = (curr_equity - prev_equity) / prev_equity * 100
            returns[month] = ret
        
        return returns
    
    def calculate_metrics(self, trades: List[BacktestTrade]) -> Dict:
        """
        Calculate comprehensive performance metrics from trades.
        
        Args:
            trades: List of completed trades
            
        Returns:
            Dictionary of metrics
        """
        if not trades:
            return {'error': 'No trades provided'}
        
        closed_trades = [t for t in trades if t.status == TradeStatus.CLOSED]
        
        if not closed_trades:
            return {'error': 'No closed trades'}
        
        pnls = [t.net_pnl for t in closed_trades]
        
        return {
            'total_trades': len(closed_trades),
            'win_rate': len([t for t in closed_trades if t.net_pnl > 0]) / len(closed_trades),
            'profit_factor': self._calculate_profit_factor(closed_trades),
            'avg_trade': np.mean(pnls),
            'sharpe_ratio': self._calculate_sharpe_from_trades(closed_trades),
            'max_drawdown': self._calculate_max_drawdown_from_trades(closed_trades),
            'expectancy': np.mean(pnls) if pnls else 0,
        }
    
    def _calculate_profit_factor(self, trades: List[BacktestTrade]) -> float:
        """Calculate profit factor."""
        gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    def _calculate_sharpe_from_trades(self, trades: List[BacktestTrade]) -> float:
        """Calculate Sharpe ratio from trade returns."""
        returns = [t.net_pnl / t.size for t in trades if t.size > 0]
        if not returns or np.std(returns) == 0:
            return 0
        return np.mean(returns) / np.std(returns) * np.sqrt(len(returns))
    
    def _calculate_max_drawdown_from_trades(self, trades: List[BacktestTrade]) -> float:
        """Calculate max drawdown from trade sequence."""
        cumulative = np.cumsum([t.net_pnl for t in trades])
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / (self.initial_capital + peak)
        return abs(min(drawdown)) if len(drawdown) > 0 else 0
    
    def generate_report(self, result: BacktestResult) -> str:
        """
        Generate a formatted text report.
        
        Args:
            result: BacktestResult to report on
            
        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"BACKTEST REPORT: {result.strategy_name}")
        lines.append("=" * 80)
        lines.append("")
        
        # Overview
        lines.append("PERFORMANCE OVERVIEW")
        lines.append("-" * 40)
        lines.append(f"Period: {result.start_date.date()} to {result.end_date.date()}")
        lines.append(f"Initial Capital: ${result.initial_capital:,.2f}")
        lines.append(f"Final Capital: ${result.final_capital:,.2f}")
        lines.append(f"Total Return: {result.total_return:+.2f} ({result.total_return_percent:+.2f}%)")
        lines.append(f"Annualized Return: {result.annualized_return:+.2f}%")
        lines.append("")
        
        # Risk Metrics
        lines.append("RISK METRICS")
        lines.append("-" * 40)
        lines.append(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        lines.append(f"Sortino Ratio: {result.sortino_ratio:.2f}")
        lines.append(f"Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_percent:.2f}%)")
        lines.append(f"Calmar Ratio: {result.calmar_ratio:.2f}")
        lines.append(f"Volatility: {result.volatility:.2f}%")
        lines.append(f"VaR (95%): ${result.var_95:,.2f}")
        lines.append("")
        
        # Trade Statistics
        lines.append("TRADE STATISTICS")
        lines.append("-" * 40)
        lines.append(f"Total Trades: {result.total_trades}")
        lines.append(f"Winning Trades: {result.winning_trades}")
        lines.append(f"Losing Trades: {result.losing_trades}")
        lines.append(f"Win Rate: {result.win_rate:.1%}")
        lines.append(f"Profit Factor: {result.profit_factor:.2f}")
        lines.append(f"Expectancy: ${result.expectancy:.2f}")
        lines.append("")
        
        # Trade Metrics
        lines.append("TRADE METRICS")
        lines.append("-" * 40)
        lines.append(f"Average Trade: ${result.avg_trade:.2f}")
        lines.append(f"Average Win: ${result.avg_win:.2f}")
        lines.append(f"Average Loss: ${result.avg_loss:.2f}")
        lines.append(f"Largest Win: ${result.largest_win:.2f}")
        lines.append(f"Largest Loss: ${result.largest_loss:.2f}")
        lines.append(f"Avg Trade Duration: {result.avg_trade_duration:.1f} hours")
        lines.append("")
        
        # R-Multiples
        lines.append("R-MULTIPLES")
        lines.append("-" * 40)
        lines.append(f"Average R: {result.avg_r_multiple:.2f}R")
        lines.append(f"R Expectancy: {result.r_expectancy:.2f}R")
        lines.append("")
        
        # Pattern Performance
        if result.performance_by_pattern:
            lines.append("PERFORMANCE BY PATTERN")
            lines.append("-" * 40)
            for pattern, stats in sorted(
                result.performance_by_pattern.items(),
                key=lambda x: x[1]['total_pnl'],
                reverse=True
            ):
                lines.append(f"{pattern:20s} Trades: {stats['trades']:3d} | "
                           f"WR: {stats['win_rate']:.1%} | "
                           f"PnL: ${stats['total_pnl']:+.2f}")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def plot_equity_curve(self, result: BacktestResult) -> Dict:
        """
        Generate data for plotting equity curve.
        
        Args:
            result: BacktestResult
            
        Returns:
            Dictionary with plotting data
        """
        if not result.equity_curve:
            return {'timestamps': [], 'equity': [], 'drawdown': []}
        
        return {
            'timestamps': [p.timestamp.isoformat() for p in result.equity_curve],
            'equity': [p.equity for p in result.equity_curve],
            'drawdown': [p.drawdown_percent for p in result.equity_curve],
            'open_positions': [p.open_positions for p in result.equity_curve],
        }
    
    @staticmethod
    def compare_strategies(results: List[BacktestResult]) -> pd.DataFrame:
        """
        Compare multiple strategy results.
        
        Args:
            results: List of BacktestResults
            
        Returns:
            DataFrame with comparison
        """
        data = []
        for r in results:
            data.append({
                'Strategy': r.strategy_name,
                'Type': r.strategy_type.value,
                'Return %': r.total_return_percent,
                'Sharpe': r.sharpe_ratio,
                'Max DD %': r.max_drawdown_percent,
                'Trades': r.total_trades,
                'Win Rate': r.win_rate,
                'Profit Factor': r.profit_factor,
                'Expectancy': r.expectancy,
                'Calmar': r.calmar_ratio,
            })
        
        df = pd.DataFrame(data)
        
        # Rank by composite score (higher is better)
        df['Score'] = (
            df['Return %'] * 0.3 +
            df['Sharpe'] * 10 * 0.25 +
            (100 - df['Max DD %']) * 0.2 +
            df['Win Rate'] * 100 * 0.15 +
            (df['Profit Factor'] - 1) * 20 * 0.1
        )
        
        return df.sort_values('Score', ascending=False)
    
    # =========================================================================
    # Risk Simulation Methods
    # =========================================================================
    
    def run_monte_carlo(
        self,
        result: BacktestResult,
        num_simulations: int = 1000,
        confidence_level: float = 0.95
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation on backtest results.
        
        Args:
            result: BacktestResult to simulate
            num_simulations: Number of simulations to run
            confidence_level: Confidence level for intervals
            
        Returns:
            MonteCarloResult with simulation statistics
        """
        logger.info(f"Running {num_simulations} Monte Carlo simulations...")
        
        closed_trades = [t for t in result.trade_log if t.status == TradeStatus.CLOSED]
        
        if not closed_trades:
            return MonteCarloResult(
                num_simulations=num_simulations,
                confidence_level=confidence_level,
                mean_return=0,
                median_return=0,
                std_return=0,
                min_return=0,
                max_return=0,
                percentile_5=0,
                percentile_25=0,
                percentile_75=0,
                percentile_95=0,
                mean_max_drawdown=0,
                worst_case_drawdown=0,
                prob_profit=0,
                prob_double=0,
                prob_ruin=0
            )
        
        # Extract trade returns
        returns = [t.net_pnl / result.initial_capital for t in closed_trades]
        
        simulations = []
        
        for _ in range(num_simulations):
            # Resample trades with replacement
            sim_returns = np.random.choice(returns, size=len(returns), replace=True)
            
            # Calculate equity curve
            equity = result.initial_capital
            equity_curve = [equity]
            
            for ret in sim_returns:
                equity *= (1 + ret)
                equity_curve.append(equity)
            
            # Calculate metrics
            total_return = (equity - result.initial_capital) / result.initial_capital
            
            # Calculate drawdown
            peak = result.initial_capital
            max_dd = 0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak
                max_dd = max(max_dd, dd)
            
            simulations.append({
                'return': total_return,
                'max_drawdown': max_dd,
                'final_equity': equity
            })
        
        # Calculate statistics
        sim_returns_arr = np.array([s['return'] for s in simulations])
        sim_drawdowns = np.array([s['max_drawdown'] for s in simulations])
        
        alpha = 1 - confidence_level
        
        # Worst cases
        worst_cases = sorted(simulations, key=lambda x: x['return'])[:5]
        
        return MonteCarloResult(
            num_simulations=num_simulations,
            confidence_level=confidence_level,
            mean_return=np.mean(sim_returns_arr),
            median_return=np.median(sim_returns_arr),
            std_return=np.std(sim_returns_arr),
            min_return=np.min(sim_returns_arr),
            max_return=np.max(sim_returns_arr),
            percentile_5=np.percentile(sim_returns_arr, 5),
            percentile_25=np.percentile(sim_returns_arr, 25),
            percentile_75=np.percentile(sim_returns_arr, 75),
            percentile_95=np.percentile(sim_returns_arr, 95),
            mean_max_drawdown=np.mean(sim_drawdowns),
            worst_case_drawdown=np.max(sim_drawdowns),
            prob_profit=np.mean(sim_returns_arr > 0),
            prob_double=np.mean(sim_returns_arr > 1.0),
            prob_ruin=np.mean(sim_drawdowns > 0.5),
            worst_cases=worst_cases
        )
    
    def analyze_worst_case(
        self,
        result: BacktestResult,
        percentile: float = 5.0
    ) -> Dict:
        """
        Analyze worst-case scenarios.
        
        Args:
            result: BacktestResult
            percentile: Percentile to analyze (e.g., 5 = 5th percentile)
            
        Returns:
            Worst case analysis
        """
        closed_trades = [t for t in result.trade_log if t.status == TradeStatus.CLOSED]
        
        if not closed_trades:
            return {}
        
        # Sort trades by P&L
        sorted_trades = sorted(closed_trades, key=lambda x: x.net_pnl)
        
        # Get worst percentile
        n = int(len(sorted_trades) * percentile / 100)
        worst_trades = sorted_trades[:max(1, n)]
        
        total_loss = sum(t.net_pnl for t in worst_trades)
        
        return {
            'percentile': percentile,
            'num_trades': len(worst_trades),
            'total_loss': total_loss,
            'avg_loss_per_trade': total_loss / len(worst_trades) if worst_trades else 0,
            'consecutive_losses': self._analyze_consecutive_losses(closed_trades),
            'worst_drawdown_period': self._analyze_worst_drawdown_period(result.equity_curve),
        }
    
    def _analyze_consecutive_losses(self, trades: List[BacktestTrade]) -> Dict:
        """Analyze consecutive losing streaks."""
        max_streak = 0
        current_streak = 0
        streaks = []
        
        for trade in trades:
            if trade.net_pnl < 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                if current_streak > 0:
                    streaks.append(current_streak)
                current_streak = 0
        
        return {
            'max_consecutive_losses': max_streak,
            'avg_streak_length': np.mean(streaks) if streaks else 0,
            'num_streaks': len(streaks)
        }
    
    def _analyze_worst_drawdown_period(self, equity_curve: List[EquityPoint]) -> Dict:
        """Find the worst drawdown period."""
        if not equity_curve:
            return {}
        
        max_dd = 0
        start_idx = 0
        end_idx = 0
        peak_idx = 0
        
        for i, point in enumerate(equity_curve):
            if point.drawdown_percent > max_dd:
                max_dd = point.drawdown_percent
                end_idx = i
                # Find the peak before this drawdown
                for j in range(i, -1, -1):
                    if equity_curve[j].drawdown_percent == 0:
                        peak_idx = j
                        break
                start_idx = peak_idx
        
        if start_idx < len(equity_curve) and end_idx < len(equity_curve):
            return {
                'max_drawdown': max_dd,
                'start_date': equity_curve[start_idx].timestamp.isoformat(),
                'end_date': equity_curve[end_idx].timestamp.isoformat(),
                'duration_days': (equity_curve[end_idx].timestamp - 
                                equity_curve[start_idx].timestamp).days
            }
        
        return {}
    
    def calculate_portfolio_heat(
        self,
        result: BacktestResult,
        lookback_days: int = 30
    ) -> Dict:
        """
        Calculate portfolio heat (risk exposure over time).
        
        Args:
            result: BacktestResult
            lookback_days: Days to look back
            
        Returns:
            Portfolio heat metrics
        """
        if not result.equity_curve:
            return {}
        
        cutoff = result.end_date - timedelta(days=lookback_days)
        recent_points = [p for p in result.equity_curve if p.timestamp >= cutoff]
        
        if not recent_points:
            return {}
        
        open_positions = [p.open_positions for p in recent_points]
        
        return {
            'avg_open_positions': np.mean(open_positions),
            'max_open_positions': max(open_positions),
            'exposure_heatmap': self._calculate_exposure_heatmap(recent_points, result.trade_log),
            'risk_concentration': self._calculate_risk_concentration(result.trade_log, lookback_days)
        }
    
    def _calculate_exposure_heatmap(
        self,
        equity_points: List[EquityPoint],
        trades: List[BacktestTrade]
    ) -> Dict:
        """Calculate exposure by time of day/day of week."""
        # Simplified - would need timestamp analysis
        return {}
    
    def _calculate_risk_concentration(
        self,
        trades: List[BacktestTrade],
        lookback_days: int
    ) -> Dict:
        """Calculate risk concentration by whale/pattern."""
        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_trades = [t for t in trades if t.timestamp >= cutoff]
        
        if not recent_trades:
            return {}
        
        # By whale
        whale_exposure = defaultdict(float)
        for t in recent_trades:
            whale_exposure[t.whale_address] += t.size
        
        # By pattern
        pattern_exposure = defaultdict(float)
        for t in recent_trades:
            pattern = t.pattern_type.value if t.pattern_type else 'unknown'
            pattern_exposure[pattern] += t.size
        
        total = sum(t.size for t in recent_trades)
        
        return {
            'whale_concentration': {
                k: v/total for k, v in sorted(whale_exposure.items(), key=lambda x: x[1], reverse=True)[:5]
            },
            'pattern_concentration': {
                k: v/total for k, v in sorted(pattern_exposure.items(), key=lambda x: x[1], reverse=True)
            }
        }
    
    # =========================================================================
    # Export Methods
    # =========================================================================
    
    def export_to_csv(self, result: BacktestResult, filename: str):
        """
        Export trade log to CSV.
        
        Args:
            result: BacktestResult
            filename: Output filename
        """
        trades = result.trade_log
        
        if not trades:
            logger.warning("No trades to export")
            return
        
        data = []
        for t in trades:
            data.append({
                'trade_id': t.trade_id,
                'timestamp': t.timestamp.isoformat() if t.timestamp else '',
                'market_id': t.market_id,
                'whale_address': t.whale_address,
                'direction': t.direction,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'size': t.size,
                'slippage': t.slippage,
                'fees': t.fees_paid,
                'gross_pnl': t.gross_pnl,
                'net_pnl': t.net_pnl,
                'exit_reason': t.exit_reason,
                'r_multiple': t.r_multiple,
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Exported {len(data)} trades to {filename}")
    
    def export_report_json(self, result: BacktestResult, filename: Optional[str] = None) -> str:
        """
        Export full report to JSON.
        
        Args:
            result: BacktestResult
            filename: Optional output filename
            
        Returns:
            JSON string
        """
        report = {
            'summary': result.to_dict(),
            'trades': [
                {
                    'trade_id': t.trade_id,
                    'timestamp': t.timestamp.isoformat() if t.timestamp else None,
                    'market_id': t.market_id,
                    'direction': t.direction,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'size': t.size,
                    'net_pnl': t.net_pnl,
                    'exit_reason': t.exit_reason,
                }
                for t in result.trade_log
            ],
            'equity_curve': [
                {
                    'timestamp': p.timestamp.isoformat(),
                    'equity': p.equity,
                    'drawdown': p.drawdown_percent,
                }
                for p in result.equity_curve
            ],
            'performance_by_pattern': result.performance_by_pattern,
            'monthly_returns': result.monthly_returns,
        }
        
        json_str = json.dumps(report, indent=2, default=str)
        
        if filename:
            with open(filename, 'w') as f:
                f.write(json_str)
            logger.info(f"Exported report to {filename}")
        
        return json_str
    
    def export_chart_data(self, result: BacktestResult) -> Dict:
        """
        Export data formatted for charting.
        
        Args:
            result: BacktestResult
            
        Returns:
            Dictionary with chart-ready data
        """
        return {
            'equity_curve': {
                'x': [p.timestamp.isoformat() for p in result.equity_curve],
                'y': [p.equity for p in result.equity_curve],
                'type': 'scatter',
                'name': 'Equity'
            },
            'drawdown': {
                'x': [p.timestamp.isoformat() for p in result.equity_curve],
                'y': [p.drawdown_percent for p in result.equity_curve],
                'type': 'scatter',
                'name': 'Drawdown %',
                'fill': 'tozeroy'
            },
            'trade_distribution': {
                'pnl': [t.net_pnl for t in result.trade_log if t.status == TradeStatus.CLOSED],
                'r_multiples': [t.r_multiple for t in result.trade_log 
                               if t.status == TradeStatus.CLOSED and t.r_multiple != 0],
            },
            'monthly_returns': {
                'months': list(result.monthly_returns.keys()),
                'returns': list(result.monthly_returns.values()),
            },
            'pattern_performance': [
                {
                    'pattern': k,
                    'trades': v['trades'],
                    'win_rate': v['win_rate'],
                    'pnl': v['total_pnl']
                }
                for k, v in result.performance_by_pattern.items()
            ]
        }


# =========================================================================
# Pre-built Strategy Configurations
# =========================================================================

def create_copy_all_strategy() -> StrategyConfig:
    """Create a strategy that copies all whale trades."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_ALL_WHALE,
        name="Copy All Whales",
        min_whale_confidence=0.5,
        position_size_percent=0.02,
    )


def create_high_confidence_strategy(min_confidence: float = 0.7) -> StrategyConfig:
    """Create a strategy that only copies high-confidence trades."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_HIGH_CONFIDENCE,
        name=f"High Confidence (>{min_confidence:.0%})",
        min_whale_confidence=min_confidence,
        position_size_percent=0.03,
        use_take_profit=True,
        take_profit_percent=0.15,
    )


def create_large_trades_strategy(min_size: float = 10000) -> StrategyConfig:
    """Create a strategy that only copies large whale trades."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_LARGE_TRADES,
        name=f"Large Trades (>${min_size:,.0f})",
        min_trade_size=min_size,
        position_size_percent=0.025,
    )


def create_crypto_only_strategy() -> StrategyConfig:
    """Create a strategy that only trades crypto markets."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_CRYPTO_ONLY,
        name="Crypto Markets Only",
        market_categories=['crypto', 'bitcoin', 'ethereum', 'cryptocurrency'],
        position_size_percent=0.02,
    )


def create_kelly_strategy(fraction: float = 0.5) -> StrategyConfig:
    """Create a strategy using Kelly Criterion sizing."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_KELLY_SIZED,
        name=f"Kelly Sizing ({fraction:.0%})",
        use_kelly_sizing=True,
        kelly_fraction=fraction,
        min_whale_confidence=0.6,
    )


def create_top_winners_strategy(top_n: int = 10) -> StrategyConfig:
    """Create a strategy that only copies top N winners."""
    return StrategyConfig(
        strategy_type=StrategyType.COPY_TOP_WINNERS,
        name=f"Top {top_n} Winners",
        min_whale_confidence=0.6,
        position_size_percent=0.03,
        # allowed_whales would be populated after analysis
    )


# =========================================================================
# Utility Functions
# =========================================================================

def run_strategy_comparison(
    engine: BacktestEngine,
    strategies: List[StrategyConfig]
) -> pd.DataFrame:
    """
    Run multiple strategies and compare results.
    
    Args:
        engine: BacktestEngine instance
        strategies: List of strategy configurations
        
    Returns:
        DataFrame with comparison
    """
    results = []
    
    for config in strategies:
        logger.info(f"Running strategy: {config.name}")
        result = engine.run_backtest(config)
        results.append(result)
    
    return BacktestEngine.compare_strategies(results)


def optimize_strategy(
    engine: BacktestEngine,
    base_config: StrategyConfig,
    param_grid: Dict[str, List],
    metric: str = 'sharpe_ratio'
) -> Tuple[StrategyConfig, BacktestResult]:
    """
    Simple grid search optimization for strategy parameters.
    
    Args:
        engine: BacktestEngine instance
        base_config: Base strategy configuration
        param_grid: Dictionary of parameter -> list of values
        metric: Metric to optimize
        
    Returns:
        Best configuration and result
    """
    from itertools import product
    
    # Generate all combinations
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    best_result = None
    best_config = None
    best_metric = float('-inf')
    
    for combination in product(*values):
        # Create config with these parameters
        config_params = dict(zip(keys, combination))
        config = StrategyConfig(
            strategy_type=base_config.strategy_type,
            name=f"Optimized {base_config.name}",
            **config_params
        )
        
        # Run backtest
        result = engine.run_backtest(config)
        
        # Check if better
        current_metric = getattr(result, metric, 0)
        if current_metric > best_metric:
            best_metric = current_metric
            best_result = result
            best_config = config
    
    return best_config, best_result


# =========================================================================
# Example Usage
# =========================================================================

async def example_usage():
    """Example of how to use the backtest engine."""
    
    # Initialize engine
    engine = BacktestEngine(
        initial_capital=10000.0,
        start_date=datetime.now() - timedelta(days=90),
        end_date=datetime.now()
    )
    
    # Load historical data (example whale addresses)
    whale_addresses = [
        "0x1234...",  # Replace with actual addresses
        "0x5678...",
    ]
    
    await engine.load_historical_data(
        whale_addresses=whale_addresses,
        data_source="subgraph"
    )
    
    # Create strategy configuration
    config = StrategyConfig(
        strategy_type=StrategyType.COPY_HIGH_CONFIDENCE,
        name="My Strategy",
        min_whale_confidence=0.7,
        position_size_percent=0.02,
        max_positions=5,
        fee_percent=0.02,
    )
    
    # Run backtest
    result = engine.run_backtest(config)
    
    # Print report
    print(engine.generate_report(result))
    
    # Run Monte Carlo
    mc_result = engine.run_monte_carlo(result, num_simulations=1000)
    print(f"\nMonte Carlo: Mean return {mc_result.mean_return:.2%}, "
          f"P(profit) = {mc_result.prob_profit:.1%}")
    
    # Export results
    engine.export_report_json(result, "backtest_report.json")
    engine.export_to_csv(result, "trades.csv")


if __name__ == "__main__":
    asyncio.run(example_usage())
