"""
Enhanced Risk Manager - Comprehensive Risk Management for Paper Trading

Features:
- Per-trade risk controls (max loss, stop loss, take profit targets)
- Portfolio risk controls (heat, concurrent positions, drawdown)
- Circuit breakers (daily loss, consecutive losses, volatility, API errors)
- Automatic position management and exit logic
- Real-time risk monitoring and reporting

This module implements institutional-grade risk management suitable for
high-frequency paper trading on prediction markets.
"""

import uuid
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class CircuitBreakerType(Enum):
    """Types of circuit breakers that can halt trading."""
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    HIGH_VOLATILITY = "high_volatility"
    API_ERROR = "api_error"
    TOTAL_DRAWDOWN = "total_drawdown"
    MANUAL = "manual"


class ExitReason(Enum):
    """Reasons for position exit."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT_TIER1 = "take_profit_tier1"  # 50% at +10%
    TAKE_PROFIT_TIER2 = "take_profit_tier2"  # Remaining at +20%
    TIME_EXIT = "time_exit"
    TRAILING_STOP = "trailing_stop"
    MANUAL = "manual"
    CIRCUIT_BREAKER = "circuit_breaker"


class RiskStatus(Enum):
    """Current risk status of the trading system."""
    NORMAL = "normal"
    CAUTION = "caution"  # Approaching limits
    RESTRICTED = "restricted"  # Some limits hit, reduced sizing
    HALTED = "halted"  # Trading stopped


@dataclass
class TakeProfitLevels:
    """Take profit configuration with tiered exits."""
    tier1_pct: float = 0.10  # 10% profit
    tier1_size: float = 0.50  # Close 50% of position
    tier2_pct: float = 0.20  # 20% profit
    tier2_size: float = 1.0  # Close remaining 100%
    
    trailing_stop_activation: float = 0.15  # Activate trailing stop at 15%
    trailing_stop_distance: float = 0.05  # 5% trailing distance


@dataclass
class PositionRiskProfile:
    """Risk profile for an individual position."""
    position_id: str
    entry_price: float
    direction: str  # 'YES' or 'NO'
    size_usd: float
    entry_time: datetime
    
    # Risk levels
    stop_loss_price: float
    take_profit: TakeProfitLevels = field(default_factory=TakeProfitLevels)
    
    # Tiered exit tracking
    tier1_exited: bool = False
    tier1_exit_price: Optional[float] = None
    tier1_exit_time: Optional[datetime] = None
    original_size: float = 0.0
    
    # Trailing stop
    highest_price: float = 0.0  # For YES positions
    lowest_price: float = float('inf')  # For NO positions
    trailing_stop_active: bool = False
    trailing_stop_price: Optional[float] = None
    
    # Time-based exit
    max_hold_hours: float = 24.0
    time_exit_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.original_size == 0:
            self.original_size = self.size_usd
        if self.time_exit_at is None:
            self.time_exit_at = self.entry_time + timedelta(hours=self.max_hold_hours)
        
        # Initialize price tracking
        if self.direction == 'YES':
            self.highest_price = self.entry_price
        else:
            self.lowest_price = self.entry_price


@dataclass
class DailyStats:
    """Daily trading statistics and tracking."""
    date: datetime = field(default_factory=lambda: datetime.now().date())
    starting_balance: float = 0.0
    current_balance: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Consecutive tracking
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    
    # Circuit breaker state
    circuit_breaker_active: bool = False
    circuit_breaker_type: Optional[CircuitBreakerType] = None
    circuit_breaker_until: Optional[datetime] = None
    
    # Drawdown tracking
    peak_balance: float = 0.0
    current_drawdown: float = 0.0
    
    def update_drawdown(self):
        """Update drawdown calculations."""
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        if self.peak_balance > 0:
            self.current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance


@dataclass
class VolatilityMetrics:
    """Track market volatility for risk adjustments."""
    window_size: int = 20  # Number of price changes to track
    price_changes: deque = field(default_factory=lambda: deque(maxlen=20))
    current_volatility: float = 0.0  # Standard deviation of returns
    volatility_regime: str = "normal"  # low, normal, high, extreme
    
    def add_price_change(self, price_change_pct: float):
        """Add a price change and recalculate volatility."""
        self.price_changes.append(price_change_pct)
        if len(self.price_changes) >= 2:
            import statistics
            try:
                self.current_volatility = statistics.stdev(self.price_changes)
            except statistics.StatisticsError:
                self.current_volatility = 0.0
            self._update_regime()
    
    def _update_regime(self):
        """Update volatility regime based on current volatility."""
        # Need at least 2 samples for meaningful standard deviation
        if len(self.price_changes) < 2:
            self.volatility_regime = "normal"
            return
            
        if self.current_volatility < 0.5:
            self.volatility_regime = "low"
        elif self.current_volatility < 2.0:
            self.volatility_regime = "normal"
        elif self.current_volatility < 5.0:
            self.volatility_regime = "high"
        else:
            self.volatility_regime = "extreme"
    
    def get_position_size_multiplier(self) -> float:
        """Get position size multiplier based on volatility regime."""
        multipliers = {
            "low": 1.2,
            "normal": 1.0,
            "high": 0.6,
            "extreme": 0.3
        }
        # Default to normal multiplier if no data
        if len(self.price_changes) < 2:
            return 1.0
        return multipliers.get(self.volatility_regime, 0.5)


@dataclass
class APIErrorTracker:
    """Track API errors for circuit breaker decisions."""
    error_window_minutes: int = 5
    max_errors_in_window: int = 5  # Circuit break after 5 errors in window
    
    errors: deque = field(default_factory=lambda: deque())
    last_error_time: Optional[datetime] = None
    consecutive_errors: int = 0
    
    def record_error(self, error_type: str = "unknown"):
        """Record an API error."""
        now = datetime.now()
        self.errors.append({"time": now, "type": error_type})
        self.last_error_time = now
        self.consecutive_errors += 1
        
        # Clean old errors
        cutoff = now - timedelta(minutes=self.error_window_minutes)
        while self.errors and self.errors[0]["time"] < cutoff:
            self.errors.popleft()
    
    def record_success(self):
        """Record a successful API call."""
        self.consecutive_errors = 0
    
    def should_circuit_break(self) -> bool:
        """Check if circuit breaker should trigger due to API errors."""
        # Too many errors in window
        if len(self.errors) >= self.max_errors_in_window:
            return True
        # Too many consecutive errors
        if self.consecutive_errors >= 5:
            return True
        return False
    
    def get_error_count(self) -> int:
        """Get count of errors in current window."""
        return len(self.errors)


class EnhancedRiskManager:
    """
    Comprehensive risk manager for paper trading system.
    
    Implements:
    - Per-trade risk controls
    - Portfolio-level risk management
    - Multiple circuit breakers
    - Tiered take-profit system
    - Volatility-adjusted position sizing
    - Comprehensive risk reporting
    
    Usage:
        risk_manager = EnhancedRiskManager(initial_balance=10000.0)
        
        # Before opening position
        can_trade, reason = risk_manager.can_open_position(
            size=1000, current_balance=10000, open_positions=[]
        )
        
        # After position opened
        risk_profile = risk_manager.register_position(
            entry_price=0.5, direction='YES', size_usd=1000
        )
        
        # Periodically check exits
        should_exit, exit_reason = risk_manager.check_exit_conditions(
            position_id, current_price=0.55
        )
        
        # On position close
        risk_manager.close_position(position_id, pnl=100)
    """
    
    # Risk Parameters - Per Trade
    MAX_TRADE_LOSS_PCT: float = 0.02  # 2% max loss per trade
    STOP_LOSS_PCT: float = 0.05  # 5% stop loss from entry
    
    # Risk Parameters - Portfolio
    MAX_PORTFOLIO_HEAT_PCT: float = 0.50  # 50% max in open positions
    MAX_CONCURRENT_POSITIONS: int = 5
    
    # Risk Parameters - Drawdown
    MAX_DAILY_DRAWDOWN_PCT: float = 0.10  # 10% daily loss limit
    MAX_TOTAL_DRAWDOWN_PCT: float = 0.20  # 20% total drawdown stop
    
    # Circuit Breaker Parameters
    CONSECUTIVE_LOSSES_THRESHOLD: int = 3
    CONSECUTIVE_LOSSES_PAUSE_MINUTES: int = 60
    HIGH_VOLATILITY_PAUSE_MINUTES: int = 30
    API_ERROR_PAUSE_MINUTES: int = 15
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        max_trade_loss_pct: float = None,
        max_portfolio_heat_pct: float = None,
        max_daily_drawdown_pct: float = None,
        max_total_drawdown_pct: float = None,
        max_positions: int = None
    ):
        """
        Initialize Enhanced Risk Manager.
        
        Args:
            initial_balance: Starting paper balance
            max_trade_loss_pct: Override default max loss per trade
            max_portfolio_heat_pct: Override default portfolio heat limit
            max_daily_drawdown_pct: Override default daily drawdown
            max_total_drawdown_pct: Override default total drawdown
            max_positions: Override default max concurrent positions
        """
        # Balance tracking
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.daily_starting_balance = initial_balance
        
        # Override risk parameters if provided
        self.max_trade_loss_pct = max_trade_loss_pct or self.MAX_TRADE_LOSS_PCT
        self.max_portfolio_heat_pct = max_portfolio_heat_pct or self.MAX_PORTFOLIO_HEAT_PCT
        self.max_daily_drawdown_pct = max_daily_drawdown_pct or self.MAX_DAILY_DRAWDOWN_PCT
        self.max_total_drawdown_pct = max_total_drawdown_pct or self.MAX_TOTAL_DRAWDOWN_PCT
        self.max_positions = max_positions or self.MAX_CONCURRENT_POSITIONS
        
        # Daily statistics
        self.daily_stats = DailyStats(starting_balance=initial_balance)
        self.daily_stats.current_balance = initial_balance
        self.daily_stats.peak_balance = initial_balance
        
        # Position tracking
        self.position_risk_profiles: Dict[str, PositionRiskProfile] = {}
        self.closed_positions: List[PositionRiskProfile] = []
        
        # Circuit breaker state
        self.circuit_breaker_active = False
        self.circuit_breaker_type: Optional[CircuitBreakerType] = None
        self.circuit_breaker_until: Optional[datetime] = None
        
        # Volatility tracking
        self.volatility_metrics = VolatilityMetrics()
        
        # API error tracking
        self.api_tracker = APIErrorTracker()
        
        # Risk status
        self.risk_status = RiskStatus.NORMAL
        
        # Trade history for analysis
        self.trade_history: deque = deque(maxlen=100)
        
        logger.info(
            f"EnhancedRiskManager initialized | Balance: ${initial_balance:,.2f} | "
            f"Max Trade Loss: {self.max_trade_loss_pct:.1%} | "
            f"Max Heat: {self.max_portfolio_heat_pct:.1%} | "
            f"Max Positions: {self.max_positions}"
        )
    
    def can_open_position(
        self,
        size: float,
        current_balance: float,
        open_positions: List[Any],
        market_volatility: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be opened based on all risk limits.
        
        Args:
            size: Proposed position size in USD
            current_balance: Current account balance
            open_positions: List of currently open positions
            market_volatility: Optional current market volatility measure
            
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        self.current_balance = current_balance
        
        # Check if circuit breaker is active
        if self.circuit_breaker_active:
            if self.circuit_breaker_until and datetime.now() < self.circuit_breaker_until:
                remaining = (self.circuit_breaker_until - datetime.now()).total_seconds() / 60
                return False, f"Circuit breaker active ({self.circuit_breaker_type.value}), {remaining:.0f}m remaining"
            else:
                # Circuit breaker expired, reset it
                self._reset_circuit_breaker()
        
        # Check daily drawdown circuit breaker
        if self._check_daily_drawdown():
            return False, f"Daily drawdown limit hit: {self.daily_stats.current_drawdown:.1%}"
        
        # Check total drawdown
        total_drawdown = (self.initial_balance - current_balance) / self.initial_balance
        if total_drawdown >= self.max_total_drawdown_pct:
            self._activate_circuit_breaker(
                CircuitBreakerType.TOTAL_DRAWDOWN,
                timedelta(hours=24)
            )
            return False, f"Total drawdown limit hit: {total_drawdown:.1%}"
        
        # Check max concurrent positions
        open_count = len(open_positions) + len(self.position_risk_profiles)
        if open_count >= self.max_positions:
            return False, f"Max positions reached: {open_count}/{self.max_positions}"
        
        # Check portfolio heat (total exposure)
        current_heat = sum(pos.size_usd for pos in self.position_risk_profiles.values())
        potential_heat = current_heat + size
        max_heat = current_balance * self.max_portfolio_heat_pct
        
        if potential_heat > max_heat:
            available = max_heat - current_heat
            return False, f"Portfolio heat limit: ${potential_heat:.0f}/${max_heat:.0f} (available: ${available:.0f})"
        
        # Check max trade loss
        max_trade_risk = current_balance * self.max_trade_loss_pct
        if size > max_trade_risk * 20:  # With 5% stop, this equals max trade loss
            max_size = max_trade_risk * 20
            return False, f"Position size exceeds max risk: ${size:.0f} > ${max_size:.0f}"
        
        # Check consecutive losses circuit breaker
        if self.daily_stats.consecutive_losses >= self.CONSECUTIVE_LOSSES_THRESHOLD:
            if not self.circuit_breaker_active:
                self._activate_circuit_breaker(
                    CircuitBreakerType.CONSECUTIVE_LOSSES,
                    timedelta(minutes=self.CONSECUTIVE_LOSSES_PAUSE_MINUTES)
                )
                return False, f"Circuit breaker: {self.CONSECUTIVE_LOSSES_THRESHOLD} consecutive losses"
        
        # Check API error circuit breaker
        if self.api_tracker.should_circuit_break():
            self._activate_circuit_breaker(
                CircuitBreakerType.API_ERROR,
                timedelta(minutes=self.API_ERROR_PAUSE_MINUTES)
            )
            return False, f"Circuit breaker: API errors ({self.api_tracker.get_error_count()} in window)"
        
        # Check volatility-based sizing
        if market_volatility:
            self.volatility_metrics.add_price_change(market_volatility)
            if self.volatility_metrics.volatility_regime == "extreme":
                self._activate_circuit_breaker(
                    CircuitBreakerType.HIGH_VOLATILITY,
                    timedelta(minutes=self.HIGH_VOLATILITY_PAUSE_MINUTES)
                )
                return False, "Circuit breaker: Extreme volatility detected"
        
        # Update risk status
        self._update_risk_status()
        
        return True, "OK"
    
    def register_position(
        self,
        entry_price: float,
        direction: str,
        size_usd: float,
        custom_stop_loss: Optional[float] = None,
        custom_take_profit: Optional[TakeProfitLevels] = None,
        max_hold_hours: float = 24.0
    ) -> PositionRiskProfile:
        """
        Register a new position with the risk manager.
        
        Args:
            entry_price: Entry price for the position
            direction: 'YES' or 'NO'
            size_usd: Position size in USD
            custom_stop_loss: Optional custom stop loss price
            custom_take_profit: Optional custom take profit levels
            max_hold_hours: Maximum time to hold position
            
        Returns:
            PositionRiskProfile for the new position
        """
        position_id = f"pos_{uuid.uuid4().hex[:8]}"
        
        # Calculate stop loss price
        if custom_stop_loss:
            stop_loss = custom_stop_loss
        elif direction == 'YES':
            stop_loss = entry_price * (1 - self.STOP_LOSS_PCT)
        else:
            stop_loss = entry_price * (1 + self.STOP_LOSS_PCT)
        
        # Create risk profile
        risk_profile = PositionRiskProfile(
            position_id=position_id,
            entry_price=entry_price,
            direction=direction,
            size_usd=size_usd,
            entry_time=datetime.now(),
            stop_loss_price=stop_loss,
            take_profit=custom_take_profit or TakeProfitLevels(),
            max_hold_hours=max_hold_hours
        )
        
        self.position_risk_profiles[position_id] = risk_profile
        self.daily_stats.total_trades += 1
        
        logger.info(
            f"Position registered: {position_id} | {direction} ${size_usd:.0f} | "
            f"Entry: {entry_price:.4f} | Stop: {stop_loss:.4f}"
        )
        
        return risk_profile
    
    def check_exit_conditions(
        self,
        position_id: str,
        current_price: float
    ) -> Tuple[bool, Optional[ExitReason], Optional[Dict]]:
        """
        Check if position should be exited based on risk rules.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            
        Returns:
            Tuple of (should_exit: bool, reason: ExitReason, details: dict)
        """
        if position_id not in self.position_risk_profiles:
            return False, None, None
        
        profile = self.position_risk_profiles[position_id]
        
        # Update price tracking for trailing stop
        if profile.direction == 'YES':
            profile.highest_price = max(profile.highest_price, current_price)
        else:
            profile.lowest_price = min(profile.lowest_price, current_price)
        
        # Check stop loss
        if profile.direction == 'YES' and current_price <= profile.stop_loss_price:
            return True, ExitReason.STOP_LOSS, {
                'exit_price': current_price,
                'pnl_pct': (current_price - profile.entry_price) / profile.entry_price
            }
        elif profile.direction == 'NO' and current_price >= profile.stop_loss_price:
            return True, ExitReason.STOP_LOSS, {
                'exit_price': current_price,
                'pnl_pct': (profile.entry_price - current_price) / profile.entry_price
            }
        
        # Check tiered take profits
        if not profile.tier1_exited:
            # Check tier 1 take profit
            if profile.direction == 'YES':
                target = profile.entry_price * (1 + profile.take_profit.tier1_pct)
                if current_price >= target:
                    return True, ExitReason.TAKE_PROFIT_TIER1, {
                        'exit_price': current_price,
                        'pnl_pct': profile.take_profit.tier1_pct,
                        'size_to_close': profile.size_usd * profile.take_profit.tier1_size,
                        'remaining_size': profile.size_usd * (1 - profile.take_profit.tier1_size)
                    }
            else:
                target = profile.entry_price * (1 - profile.take_profit.tier1_pct)
                if current_price <= target:
                    return True, ExitReason.TAKE_PROFIT_TIER1, {
                        'exit_price': current_price,
                        'pnl_pct': profile.take_profit.tier1_pct,
                        'size_to_close': profile.size_usd * profile.take_profit.tier1_size,
                        'remaining_size': profile.size_usd * (1 - profile.take_profit.tier1_size)
                    }
        else:
            # Check tier 2 take profit (already exited tier 1)
            if profile.direction == 'YES':
                target = profile.entry_price * (1 + profile.take_profit.tier2_pct)
                if current_price >= target:
                    return True, ExitReason.TAKE_PROFIT_TIER2, {
                        'exit_price': current_price,
                        'pnl_pct': profile.take_profit.tier2_pct,
                        'size_to_close': profile.size_usd  # Close remaining
                    }
            else:
                target = profile.entry_price * (1 - profile.take_profit.tier2_pct)
                if current_price <= target:
                    return True, ExitReason.TAKE_PROFIT_TIER2, {
                        'exit_price': current_price,
                        'pnl_pct': profile.take_profit.tier2_pct,
                        'size_to_close': profile.size_usd  # Close remaining
                    }
            
            # Check trailing stop (only after tier 1 hit)
            if not profile.trailing_stop_active:
                # Activate trailing stop
                activation_level = profile.entry_price * (1 + profile.take_profit.trailing_stop_activation)
                if profile.direction == 'YES' and current_price >= activation_level:
                    profile.trailing_stop_active = True
                    profile.trailing_stop_price = current_price * (1 - profile.take_profit.trailing_stop_distance)
                elif profile.direction == 'NO' and current_price <= activation_level:
                    profile.trailing_stop_active = True
                    profile.trailing_stop_price = current_price * (1 + profile.take_profit.trailing_stop_distance)
            else:
                # Update trailing stop price
                if profile.direction == 'YES':
                    new_stop = profile.highest_price * (1 - profile.take_profit.trailing_stop_distance)
                    profile.trailing_stop_price = max(profile.trailing_stop_price or 0, new_stop)
                    if current_price <= profile.trailing_stop_price:
                        return True, ExitReason.TRAILING_STOP, {
                            'exit_price': current_price,
                            'pnl_pct': (current_price - profile.entry_price) / profile.entry_price
                        }
                else:
                    new_stop = profile.lowest_price * (1 + profile.take_profit.trailing_stop_distance)
                    profile.trailing_stop_price = min(profile.trailing_stop_price or float('inf'), new_stop)
                    if current_price >= profile.trailing_stop_price:
                        return True, ExitReason.TRAILING_STOP, {
                            'exit_price': current_price,
                            'pnl_pct': (profile.entry_price - current_price) / profile.entry_price
                        }
        
        # Check time-based exit
        if datetime.now() >= profile.time_exit_at:
            return True, ExitReason.TIME_EXIT, {
                'exit_price': current_price,
                'pnl_pct': (current_price - profile.entry_price) / profile.entry_price
                if profile.direction == 'YES'
                else (profile.entry_price - current_price) / profile.entry_price
            }
        
        return False, None, None
    
    def check_stop_loss(self, position_id: str, current_price: float) -> bool:
        """
        Quick check if stop loss is hit.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            
        Returns:
            True if stop loss should be triggered
        """
        should_exit, reason, _ = self.check_exit_conditions(position_id, current_price)
        return should_exit and reason == ExitReason.STOP_LOSS
    
    def check_take_profit(self, position_id: str, current_price: float) -> Tuple[bool, Optional[str]]:
        """
        Quick check if take profit is hit.
        
        Args:
            position_id: Position identifier
            current_price: Current market price
            
        Returns:
            Tuple of (should_exit: bool, tier: str)
        """
        should_exit, reason, details = self.check_exit_conditions(position_id, current_price)
        if should_exit and reason in (ExitReason.TAKE_PROFIT_TIER1, ExitReason.TAKE_PROFIT_TIER2):
            tier = "tier1" if reason == ExitReason.TAKE_PROFIT_TIER1 else "tier2"
            return True, tier
        return False, None
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        pnl: float,
        exit_reason: Optional[ExitReason] = None
    ) -> Dict:
        """
        Close a position and update risk statistics.
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            pnl: Realized P&L
            exit_reason: Reason for exit
            
        Returns:
            Trade summary dict
        """
        if position_id not in self.position_risk_profiles:
            logger.warning(f"Attempted to close unknown position: {position_id}")
            return {}
        
        profile = self.position_risk_profiles[position_id]
        
        # Update tier tracking if tier 1 exit
        if exit_reason == ExitReason.TAKE_PROFIT_TIER1:
            profile.tier1_exited = True
            profile.tier1_exit_price = exit_price
            profile.tier1_exit_time = datetime.now()
            profile.size_usd *= (1 - profile.take_profit.tier1_size)
            
            # Don't fully close yet, just reduce size
            logger.info(f"Tier 1 take profit executed for {position_id}, reduced to ${profile.size_usd:.0f}")
            return {
                'position_id': position_id,
                'partial_exit': True,
                'tier': 1,
                'remaining_size': profile.size_usd
            }
        
        # Full close
        profile.closed = True
        self.closed_positions.append(profile)
        del self.position_risk_profiles[position_id]
        
        # Update daily stats
        self.daily_stats.realized_pnl += pnl
        self.daily_stats.current_balance += pnl
        self.daily_stats.update_drawdown()
        
        # Update win/loss tracking
        if pnl > 0:
            self.daily_stats.winning_trades += 1
            self.daily_stats.consecutive_wins += 1
            self.daily_stats.consecutive_losses = 0
        else:
            self.daily_stats.losing_trades += 1
            self.daily_stats.consecutive_losses += 1
            self.daily_stats.consecutive_wins = 0
        
        # Update total balance
        self.current_balance += pnl
        
        # Record trade
        trade_record = {
            'position_id': position_id,
            'entry_price': profile.entry_price,
            'exit_price': exit_price,
            'direction': profile.direction,
            'size': profile.original_size,
            'pnl': pnl,
            'pnl_pct': pnl / profile.original_size if profile.original_size > 0 else 0,
            'exit_reason': exit_reason.value if exit_reason else 'unknown',
            'duration_hours': (datetime.now() - profile.entry_time).total_seconds() / 3600,
            'timestamp': datetime.now()
        }
        self.trade_history.append(trade_record)
        
        # Check if we need to activate circuit breaker
        self._check_circuit_breakers()
        
        logger.info(
            f"Position closed: {position_id} | P&L: ${pnl:+.2f} | "
            f"Reason: {exit_reason.value if exit_reason else 'unknown'}"
        )
        
        return trade_record
    
    def update_daily_stats(self, pnl: float, is_unrealized: bool = False):
        """
        Update daily statistics with P&L.
        
        Args:
            pnl: Profit/loss amount
            is_unrealized: Whether this is unrealized P&L
        """
        if is_unrealized:
            self.daily_stats.unrealized_pnl = pnl
        else:
            self.daily_stats.realized_pnl += pnl
            self.daily_stats.current_balance += pnl
            self.daily_stats.update_drawdown()
            self.current_balance = self.daily_stats.current_balance
    
    def get_status(self) -> Dict:
        """
        Get current risk status summary.
        
        Returns:
            Dict with comprehensive risk status
        """
        current_heat = sum(pos.size_usd for pos in self.position_risk_profiles.values())
        heat_pct = current_heat / self.current_balance if self.current_balance > 0 else 0
        
        total_drawdown = (self.initial_balance - self.current_balance) / self.initial_balance
        
        return {
            'risk_status': self.risk_status.value,
            'circuit_breaker': {
                'active': self.circuit_breaker_active,
                'type': self.circuit_breaker_type.value if self.circuit_breaker_type else None,
                'until': self.circuit_breaker_until.isoformat() if self.circuit_breaker_until else None,
                'remaining_minutes': (
                    (self.circuit_breaker_until - datetime.now()).total_seconds() / 60
                    if self.circuit_breaker_active and self.circuit_breaker_until
                    else 0
                )
            },
            'balance': {
                'initial': self.initial_balance,
                'current': self.current_balance,
                'daily_starting': self.daily_starting_balance,
                'peak': self.daily_stats.peak_balance
            },
            'drawdown': {
                'current': self.daily_stats.current_drawdown,
                'daily': (self.daily_starting_balance - self.current_balance) / self.daily_starting_balance,
                'total': total_drawdown,
                'max_allowed': self.max_total_drawdown_pct
            },
            'positions': {
                'open_count': len(self.position_risk_profiles),
                'max_allowed': self.max_positions,
                'heat': current_heat,
                'heat_pct': heat_pct,
                'max_heat_pct': self.max_portfolio_heat_pct
            },
            'daily_stats': {
                'total_trades': self.daily_stats.total_trades,
                'winning_trades': self.daily_stats.winning_trades,
                'losing_trades': self.daily_stats.losing_trades,
                'win_rate': (
                    self.daily_stats.winning_trades / self.daily_stats.total_trades
                    if self.daily_stats.total_trades > 0 else 0
                ),
                'consecutive_losses': self.daily_stats.consecutive_losses,
                'realized_pnl': self.daily_stats.realized_pnl,
                'unrealized_pnl': self.daily_stats.unrealized_pnl
            },
            'volatility': {
                'regime': self.volatility_metrics.volatility_regime,
                'current': self.volatility_metrics.current_volatility,
                'position_size_multiplier': self.volatility_metrics.get_position_size_multiplier()
            },
            'api_health': {
                'errors_in_window': self.api_tracker.get_error_count(),
                'consecutive_errors': self.api_tracker.consecutive_errors,
                'last_error': self.api_tracker.last_error_time.isoformat() if self.api_tracker.last_error_time else None
            }
        }
    
    def get_position_risk_summary(self, position_id: str) -> Optional[Dict]:
        """
        Get risk summary for a specific position.
        
        Args:
            position_id: Position identifier
            
        Returns:
            Dict with position risk details or None if not found
        """
        if position_id not in self.position_risk_profiles:
            return None
        
        profile = self.position_risk_profiles[position_id]
        
        return {
            'position_id': profile.position_id,
            'direction': profile.direction,
            'entry_price': profile.entry_price,
            'current_size': profile.size_usd,
            'original_size': profile.original_size,
            'stop_loss': profile.stop_loss_price,
            'tier1_exited': profile.tier1_exited,
            'tier1_exit_price': profile.tier1_exit_price,
            'time_to_exit_hours': (
                (profile.time_exit_at - datetime.now()).total_seconds() / 3600
            ),
            'trailing_stop_active': profile.trailing_stop_active,
            'trailing_stop_price': profile.trailing_stop_price,
            'highest_price': profile.highest_price if profile.direction == 'YES' else None,
            'lowest_price': profile.lowest_price if profile.direction == 'NO' else None
        }
    
    def reset_daily_stats(self, new_starting_balance: Optional[float] = None):
        """
        Reset daily statistics (call at start of new trading day).
        
        Args:
            new_starting_balance: Optional new starting balance
        """
        self.daily_starting_balance = new_starting_balance or self.current_balance
        self.daily_stats = DailyStats(
            date=datetime.now().date(),
            starting_balance=self.daily_starting_balance,
            current_balance=self.current_balance,
            peak_balance=self.current_balance
        )
        self._reset_circuit_breaker()
        logger.info(f"Daily stats reset. Starting balance: ${self.daily_starting_balance:,.2f}")
    
    def record_api_error(self, error_type: str = "unknown"):
        """Record an API error for circuit breaker tracking."""
        self.api_tracker.record_error(error_type)
    
    def record_api_success(self):
        """Record a successful API call."""
        self.api_tracker.record_success()
    
    def record_volatility(self, price_change_pct: float):
        """Record a price change for volatility tracking."""
        self.volatility_metrics.add_price_change(price_change_pct)
    
    def _check_daily_drawdown(self) -> bool:
        """Check if daily drawdown limit is hit."""
        daily_pnl = self.daily_starting_balance - self.current_balance
        daily_drawdown_pct = daily_pnl / self.daily_starting_balance if self.daily_starting_balance > 0 else 0
        
        if daily_drawdown_pct >= self.max_daily_drawdown_pct:
            if not self.circuit_breaker_active:
                self._activate_circuit_breaker(
                    CircuitBreakerType.DAILY_LOSS_LIMIT,
                    timedelta(hours=24)
                )
            return True
        return False
    
    def _check_circuit_breakers(self):
        """Check and activate circuit breakers based on current state."""
        # Check consecutive losses
        if self.daily_stats.consecutive_losses >= self.CONSECUTIVE_LOSSES_THRESHOLD:
            if not self.circuit_breaker_active:
                self._activate_circuit_breaker(
                    CircuitBreakerType.CONSECUTIVE_LOSSES,
                    timedelta(minutes=self.CONSECUTIVE_LOSSES_PAUSE_MINUTES)
                )
    
    def _activate_circuit_breaker(self, breaker_type: CircuitBreakerType, duration: timedelta):
        """Activate a circuit breaker."""
        self.circuit_breaker_active = True
        self.circuit_breaker_type = breaker_type
        self.circuit_breaker_until = datetime.now() + duration
        self.daily_stats.circuit_breaker_active = True
        self.daily_stats.circuit_breaker_type = breaker_type
        self.daily_stats.circuit_breaker_until = self.circuit_breaker_until
        
        self.risk_status = RiskStatus.HALTED
        
        logger.warning(
            f"CIRCUIT BREAKER ACTIVATED: {breaker_type.value} | "
            f"Duration: {duration} | Until: {self.circuit_breaker_until}"
        )
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker state."""
        self.circuit_breaker_active = False
        self.circuit_breaker_type = None
        self.circuit_breaker_until = None
        self.daily_stats.circuit_breaker_active = False
        self.daily_stats.circuit_breaker_type = None
        self.daily_stats.circuit_breaker_until = None
        
        self._update_risk_status()
        logger.info("Circuit breaker reset - trading resumed")
    
    def _update_risk_status(self):
        """Update overall risk status based on current conditions."""
        if self.circuit_breaker_active:
            self.risk_status = RiskStatus.HALTED
            return
        
        # Calculate various risk metrics
        heat = sum(pos.size_usd for pos in self.position_risk_profiles.values())
        heat_pct = heat / self.current_balance if self.current_balance > 0 else 0
        
        daily_drawdown = (self.daily_starting_balance - self.current_balance) / self.daily_starting_balance
        
        # Check for restricted status (approaching limits)
        if (heat_pct >= self.max_portfolio_heat_pct * 0.9 or
            daily_drawdown >= self.max_daily_drawdown_pct * 0.8 or
            self.daily_stats.consecutive_losses >= 2):
            self.risk_status = RiskStatus.RESTRICTED
            return
        
        # Check for caution status
        if (heat_pct >= self.max_portfolio_heat_pct * 0.7 or
            daily_drawdown >= self.max_daily_drawdown_pct * 0.5 or
            self.volatility_metrics.volatility_regime == "high"):
            self.risk_status = RiskStatus.CAUTION
            return
        
        self.risk_status = RiskStatus.NORMAL
    
    def get_recommended_position_size(
        self,
        signal_confidence: float,
        base_size: float,
        current_balance: Optional[float] = None
    ) -> float:
        """
        Calculate recommended position size based on risk parameters.
        
        Args:
            signal_confidence: Signal confidence score (0-1)
            base_size: Base position size
            current_balance: Current account balance
            
        Returns:
            Recommended position size
        """
        balance = current_balance or self.current_balance
        
        # Start with max risk per trade
        max_risk_amount = balance * self.max_trade_loss_pct
        
        # Apply volatility adjustment
        vol_multiplier = self.volatility_metrics.get_position_size_multiplier()
        
        # Apply risk status adjustment
        status_multipliers = {
            RiskStatus.NORMAL: 1.0,
            RiskStatus.CAUTION: 0.7,
            RiskStatus.RESTRICTED: 0.4,
            RiskStatus.HALTED: 0.0
        }
        status_multiplier = status_multipliers.get(self.risk_status, 0.5)
        
        # Apply confidence adjustment
        confidence_multiplier = 0.5 + (signal_confidence * 0.5)  # 0.5 to 1.0
        
        # Calculate adjusted size
        adjusted_size = base_size * vol_multiplier * status_multiplier * confidence_multiplier
        
        # Cap at max risk amount (assuming 5% stop loss)
        max_size_by_risk = max_risk_amount / self.STOP_LOSS_PCT
        
        final_size = min(adjusted_size, max_size_by_risk)
        
        # Ensure we don't exceed available heat
        current_heat = sum(pos.size_usd for pos in self.position_risk_profiles.values())
        available_heat = (balance * self.max_portfolio_heat_pct) - current_heat
        final_size = min(final_size, available_heat)
        
        return max(0, final_size)


class RiskManagedPaperTradingSession:
    """
    Paper trading session with integrated enhanced risk management.
    
    This class wraps the existing paper trading engine with comprehensive
    risk management features including circuit breakers, tiered exits,
    and volatility-adjusted sizing.
    
    Usage:
        session = RiskManagedPaperTradingSession(initial_balance=10000.0)
        
        # Before executing trade
        if session.can_trade():
            position = session.open_position(signal, market_data)
        
        # Periodically update
        session.update_positions(market_prices)
        
        # Get status
        status = session.get_risk_status()
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_manager: Optional[EnhancedRiskManager] = None,
        **risk_kwargs
    ):
        """
        Initialize risk-managed paper trading session.
        
        Args:
            initial_balance: Starting paper balance
            risk_manager: Optional existing EnhancedRiskManager instance
            **risk_kwargs: Additional kwargs for EnhancedRiskManager
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        
        # Initialize or use provided risk manager
        if risk_manager:
            self.risk_manager = risk_manager
        else:
            self.risk_manager = EnhancedRiskManager(
                initial_balance=initial_balance,
                **risk_kwargs
            )
        
        # Position tracking
        self.positions: Dict[str, Dict] = {}
        self.closed_positions: List[Dict] = []
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        
        logger.info(f"RiskManagedPaperTradingSession initialized: ${initial_balance:,.2f}")
    
    def can_trade(self, proposed_size: float = 0) -> Tuple[bool, str]:
        """
        Check if trading is currently allowed.
        
        Args:
            proposed_size: Optional proposed trade size to check
            
        Returns:
            Tuple of (can_trade: bool, reason: str)
        """
        return self.risk_manager.can_open_position(
            size=proposed_size,
            current_balance=self.balance,
            open_positions=list(self.positions.values())
        )
    
    def open_position(
        self,
        signal: Any,
        market_data: Dict,
        delay_seconds: float = 0.0
    ) -> Optional[Dict]:
        """
        Open a new position with full risk checks.
        
        Args:
            signal: Trading signal
            market_data: Current market data
            delay_seconds: Execution delay after signal
            
        Returns:
            Position dict or None if rejected
        """
        # Extract signal details
        trade = getattr(signal, 'trade', signal)
        direction = getattr(trade, 'outcome', 'YES')
        market_id = getattr(trade, 'market_id', 'unknown')
        market_question = getattr(trade, 'market_question', 'Unknown Market')[:50]
        
        # Get entry price with slippage
        intended_price = getattr(trade, 'price', market_data.get('current_price', 0.5))
        current_price = market_data.get('current_price', intended_price)
        
        # Calculate slippage
        slippage = ((current_price - intended_price) / intended_price) * 100
        if direction == 'NO':
            slippage = -slippage
        
        # Get signal confidence
        confidence = getattr(signal, 'pattern_confidence', 0.5)
        suggested_size = getattr(signal, 'suggested_size', self.balance * 0.02)
        
        # Apply risk-adjusted sizing
        position_size = self.risk_manager.get_recommended_position_size(
            signal_confidence=confidence,
            base_size=suggested_size,
            current_balance=self.balance
        )
        
        # Check if we can trade
        can_trade, reason = self.can_trade(position_size)
        if not can_trade:
            logger.warning(f"Trade rejected: {reason}")
            return None
        
        # Register position with risk manager
        risk_profile = self.risk_manager.register_position(
            entry_price=current_price,
            direction=direction,
            size_usd=position_size
        )
        
        # Create position record
        position = {
            'position_id': risk_profile.position_id,
            'signal_id': getattr(trade, 'tx_hash', str(self.total_trades))[:8],
            'market_id': market_id,
            'market_question': market_question,
            'direction': direction,
            'entry_price': current_price,
            'intended_entry_price': intended_price,
            'size_usd': position_size,
            'entry_time': datetime.now(),
            'stop_loss': risk_profile.stop_loss_price,
            'status': 'open',
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'whale_address': getattr(trade, 'whale_address', 'unknown'),
            'pattern_type': getattr(signal, 'whale_pattern_profile', 'unknown'),
            'slippage_pct': slippage,
            'delay_seconds': delay_seconds,
            'risk_profile': risk_profile
        }
        
        self.positions[risk_profile.position_id] = position
        self.total_trades += 1
        
        logger.info(
            f"Position opened: {risk_profile.position_id} | {direction} ${position_size:.0f} | "
            f"Entry: {current_price:.4f} | Stop: {risk_profile.stop_loss_price:.4f}"
        )
        
        return position
    
    def update_positions(self, market_prices: Dict[str, float]):
        """
        Update all positions with current prices and check exits.
        
        Args:
            market_prices: Dict of market_id -> current_price
        """
        for position_id, position in list(self.positions.items()):
            market_id = position['market_id']
            if market_id not in market_prices:
                continue
            
            current_price = market_prices[market_id]
            
            # Calculate unrealized P&L
            if position['direction'] == 'YES':
                position['unrealized_pnl'] = (current_price - position['entry_price']) * position['size_usd']
            else:
                position['unrealized_pnl'] = (position['entry_price'] - current_price) * position['size_usd']
            
            # Check exit conditions
            should_exit, exit_reason, details = self.risk_manager.check_exit_conditions(
                position_id, current_price
            )
            
            if should_exit and exit_reason:
                # Handle tiered exits
                if exit_reason == ExitReason.TAKE_PROFIT_TIER1 and details:
                    # Partial exit
                    self._execute_partial_exit(position_id, details)
                else:
                    # Full exit
                    self.close_position(position_id, current_price, exit_reason)
            
            # Check time-based exit separately
            elif datetime.now() >= position['risk_profile'].time_exit_at:
                self.close_position(position_id, current_price, ExitReason.TIME_EXIT)
    
    def _execute_partial_exit(self, position_id: str, details: Dict):
        """Execute a partial position exit (tier 1 take profit)."""
        position = self.positions.get(position_id)
        if not position:
            return
        
        # Update position size
        old_size = position['size_usd']
        position['size_usd'] = details.get('remaining_size', old_size * 0.5)
        
        # Calculate realized P&L for closed portion
        closed_pct = details.get('size_to_close', old_size * 0.5) / old_size
        realized_pnl = position['unrealized_pnl'] * closed_pct
        position['realized_pnl'] += realized_pnl
        self.balance += realized_pnl
        
        logger.info(
            f"Partial exit: {position_id} | Closed {closed_pct:.0%} | "
            f"Realized: ${realized_pnl:+.2f} | Remaining: ${position['size_usd']:.0f}"
        )
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: ExitReason
    ) -> Optional[Dict]:
        """
        Close a position.
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            exit_reason: Reason for closing
            
        Returns:
            Closed position record or None
        """
        if position_id not in self.positions:
            return None
        
        position = self.positions[position_id]
        
        # Calculate final P&L
        if position['direction'] == 'YES':
            pnl = (exit_price - position['entry_price']) * position['size_usd']
        else:
            pnl = (position['entry_price'] - exit_price) * position['size_usd']
        
        # Update position
        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now()
        position['exit_reason'] = exit_reason.value
        position['status'] = 'closed'
        position['realized_pnl'] += pnl
        
        # Update balance
        self.balance += pnl
        self.total_pnl += pnl
        
        # Update statistics
        if pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
        
        # Update risk manager
        self.risk_manager.close_position(position_id, exit_price, pnl, exit_reason)
        
        # Move to closed
        self.closed_positions.append(position)
        del self.positions[position_id]
        
        result_emoji = "✅" if pnl > 0 else "❌"
        logger.info(
            f"{result_emoji} Position closed: {position_id} | "
            f"P&L: ${pnl:+.2f} | Reason: {exit_reason.value}"
        )
        
        return position
    
    def get_risk_status(self) -> Dict:
        """Get comprehensive risk status."""
        base_status = self.risk_manager.get_status()
        
        # Add session-specific info
        base_status['session'] = {
            'open_positions': len(self.positions),
            'closed_positions': len(self.closed_positions),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0,
            'total_pnl': self.total_pnl,
            'current_balance': self.balance,
            'total_return_pct': (self.balance - self.initial_balance) / self.initial_balance
        }
        
        return base_status
    
    def get_open_positions_table(self) -> str:
        """Get formatted table of open positions."""
        if not self.positions:
            return "No open positions"
        
        lines = ["\n[OPEN POSITIONS]"]
        lines.append("-" * 90)
        lines.append(
            f"{'ID':<8} {'Market':<25} {'Dir':<5} {'Size':<10} {'Entry':<8} "
            f"{'Current':<10} {'P&L':<10} {'Stop':<8}"
        )
        lines.append("-" * 90)
        
        for pos in self.positions.values():
            unrealized = pos.get('unrealized_pnl', 0)
            lines.append(
                f"{pos['position_id']:<8} "
                f"{pos['market_question'][:24]:<25} "
                f"{pos['direction']:<5} "
                f"${pos['size_usd']:<9.0f} "
                f"{pos['entry_price']:<8.3f} "
                f"${pos.get('current_price', 0):<9.3f} "
                f"${unrealized:<9.2f} "
                f"{pos['stop_loss']:<8.3f}"
            )
        
        return "\n".join(lines)
    
    def manual_close_all(self, reason: str = "manual"):
        """Close all open positions manually."""
        for position_id in list(self.positions.keys()):
            position = self.positions[position_id]
            current_price = position.get('current_price', position['entry_price'])
            self.close_position(position_id, current_price, ExitReason.MANUAL)
        
        logger.info(f"All positions closed manually: {reason}")
    
    def reset_daily(self):
        """Reset daily statistics."""
        self.risk_manager.reset_daily_stats(self.balance)
        logger.info("Daily statistics reset")
