"""
Risk Management & Position Manager for BTC 5-Minute Trading

Handles:
- Position sizing with Kelly Criterion
- Portfolio heat management
- Correlation risk
- Drawdown protection
- Exposure limits
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..utils.logger import setup_logging

logger = setup_logging()


class RiskLevel(Enum):
    """Risk level classifications."""
    CONSERVATIVE = "conservative"  # Max 1% risk per trade
    MODERATE = "moderate"          # Max 2% risk per trade
    AGGRESSIVE = "aggressive"      # Max 3% risk per trade


@dataclass
class RiskParameters:
    """Risk management parameters."""
    # Per-trade limits
    max_risk_per_trade: float = 0.02  # 2% of bankroll
    max_position_size: float = 5000   # USD
    min_position_size: float = 100    # USD
    
    # Portfolio limits
    max_correlated_exposure: float = 0.10  # 10% in correlated trades
    max_total_exposure: float = 0.50       # 50% total portfolio
    max_open_positions: int = 5
    
    # Drawdown protection
    max_daily_drawdown: float = 0.10  # 10% daily loss limit
    max_total_drawdown: float = 0.20  # 20% total drawdown
    
    # Kelly Criterion
    kelly_fraction: float = 0.5  # Half-Kelly for safety
    
    # Time-based
    min_time_between_trades: int = 30  # seconds
    max_hold_time: int = 240  # 4 minutes for 5-min markets
    
    @classmethod
    def from_risk_level(cls, level: RiskLevel) -> 'RiskParameters':
        """Create parameters from risk level."""
        if level == RiskLevel.CONSERVATIVE:
            return cls(
                max_risk_per_trade=0.01,
                max_position_size=3000,
                kelly_fraction=0.3,
            )
        elif level == RiskLevel.AGGRESSIVE:
            return cls(
                max_risk_per_trade=0.03,
                max_position_size=10000,
                kelly_fraction=0.7,
            )
        return cls()  # MODERATE (default)


@dataclass
class Position:
    """Active position tracking."""
    position_id: str
    signal_id: str
    market_id: str
    direction: str  # 'long' or 'short'
    
    # Entry
    entry_price: float
    entry_time: datetime
    size: float
    
    # Exit plan
    target_price: float
    stop_loss: float
    time_exit: datetime
    
    # Current state
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    # Risk metrics
    risk_amount: float = 0.0  # USD at risk
    risk_percent: float = 0.0  # % of bankroll
    
    def update_price(self, price: float):
        """Update position with current price."""
        self.current_price = price
        
        if self.direction == 'long':
            self.unrealized_pnl = (price - self.entry_price) * self.size
            self.unrealized_pnl_pct = (price / self.entry_price) - 1
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size
            self.unrealized_pnl_pct = 1 - (price / self.entry_price)
    
    @property
    def is_stop_hit(self) -> bool:
        """Check if stop loss is hit."""
        if self.direction == 'long':
            return self.current_price <= self.stop_loss
        return self.current_price >= self.stop_loss
    
    @property
    def is_target_hit(self) -> bool:
        """Check if target is hit."""
        if self.direction == 'long':
            return self.current_price >= self.target_price
        return self.current_price <= self.target_price
    
    @property
    def is_time_expired(self) -> bool:
        """Check if time exit reached."""
        return datetime.now() >= self.time_exit
    
    @property
    def should_exit(self) -> Tuple[bool, str]:
        """Check if position should be exited."""
        if self.is_stop_hit:
            return True, 'stop_loss'
        if self.is_target_hit:
            return True, 'target'
        if self.is_time_expired:
            return True, 'time_exit'
        return False, ''


@dataclass
class PortfolioState:
    """Current portfolio state."""
    bankroll: float
    available_balance: float
    total_exposure: float
    open_positions: Dict[str, Position] = field(default_factory=dict)
    
    # Performance tracking
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    peak_bankroll: float = 0.0
    current_drawdown: float = 0.0
    
    def __post_init__(self):
        if self.peak_bankroll == 0:
            self.peak_bankroll = self.bankroll
    
    def update_drawdown(self):
        """Update drawdown calculations."""
        if self.bankroll > self.peak_bankroll:
            self.peak_bankroll = self.bankroll
        
        self.current_drawdown = 1 - (self.bankroll / self.peak_bankroll)


class PositionManager:
    """
    Advanced position manager for BTC 5-minute trading.
    
    Manages risk across multiple dimensions:
    - Per-trade risk limits
    - Portfolio concentration
    - Drawdown protection
    - Correlation exposure
    """
    
    def __init__(
        self,
        initial_bankroll: float = 10000,
        risk_params: Optional[RiskParameters] = None
    ):
        """Initialize position manager."""
        self.risk_params = risk_params or RiskParameters()
        self.portfolio = PortfolioState(
            bankroll=initial_bankroll,
            available_balance=initial_bankroll,
            total_exposure=0.0,
        )
        self.trade_history: List[Dict] = []
        self.last_trade_time: Optional[datetime] = None
        
        logger.info(f"Position Manager initialized: ${initial_bankroll:,.0f} bankroll")
    
    def can_take_signal(self, signal) -> Tuple[bool, str]:
        """
        Check if signal can be taken based on risk rules.
        
        Args:
            signal: TradeSignal to evaluate
            
        Returns:
            (can_trade, reason)
        """
        # Check drawdown limits
        if self.portfolio.current_drawdown >= self.risk_params.max_total_drawdown:
            return False, f"Max drawdown hit: {self.portfolio.current_drawdown:.1%}"
        
        # Check daily loss limit
        daily_loss = -min(0, self.portfolio.daily_pnl)
        daily_loss_pct = daily_loss / self.portfolio.bankroll
        if daily_loss_pct >= self.risk_params.max_daily_drawdown:
            return False, f"Daily loss limit hit: {daily_loss_pct:.1%}"
        
        # Check max positions
        if len(self.portfolio.open_positions) >= self.risk_params.max_open_positions:
            return False, f"Max positions open: {self.risk_params.max_open_positions}"
        
        # Check time between trades
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
            if time_since_last < self.risk_params.min_time_between_trades:
                return False, f"Trade cooldown: {time_since_last:.0f}s"
        
        # Check available balance
        required_margin = signal.suggested_size * 0.5  # 50% margin requirement
        if required_margin > self.portfolio.available_balance:
            return False, f"Insufficient balance: ${self.portfolio.available_balance:.0f}"
        
        # Check for correlated exposure
        correlated_exposure = self._calculate_correlated_exposure(signal)
        if correlated_exposure > self.risk_params.max_correlated_exposure * self.portfolio.bankroll:
            return False, f"Correlated exposure limit: ${correlated_exposure:.0f}"
        
        return True, "OK"
    
    def calculate_position_size(self, signal, current_price: float) -> float:
        """
        Calculate optimal position size using Kelly Criterion.
        
        Args:
            signal: TradeSignal
            current_price: Current market price
            
        Returns:
            Position size in USD
        """
        # Base Kelly calculation
        kelly_size = signal.calculate_position_size(
            self.portfolio.bankroll,
            self.risk_params.kelly_fraction
        )
        
        # Apply risk limits
        # Limit 1: Max risk per trade
        stop_distance = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        if stop_distance > 0:
            max_size_by_risk = (self.portfolio.bankroll * self.risk_params.max_risk_per_trade) / stop_distance
        else:
            max_size_by_risk = self.risk_params.max_position_size
        
        # Limit 2: Max position size
        max_size = min(
            kelly_size,
            max_size_by_risk,
            self.risk_params.max_position_size,
            self.portfolio.available_balance
        )
        
        # Limit 3: Min position size
        max_size = max(max_size, self.risk_params.min_position_size)
        
        return max_size
    
    def open_position(self, signal, fill_price: float) -> Optional[Position]:
        """
        Open a new position.
        
        Args:
            signal: TradeSignal
            fill_price: Actual fill price
            
        Returns:
            Position if opened successfully
        """
        # Check if we can take this signal
        can_trade, reason = self.can_take_signal(signal)
        if not can_trade:
            logger.warning(f"Signal rejected: {reason}")
            return None
        
        # Calculate position size
        size = self.calculate_position_size(signal, fill_price)
        
        if size < self.risk_params.min_position_size:
            logger.warning(f"Position size too small: ${size:.0f}")
            return None
        
        # Calculate risk
        stop_distance = abs(fill_price - signal.stop_loss) / fill_price
        risk_amount = size * stop_distance
        risk_percent = risk_amount / self.portfolio.bankroll
        
        # Create position
        position = Position(
            position_id=f"pos_{datetime.now().strftime('%H%M%S')}_{signal.market_id[:6]}",
            signal_id=signal.signal_id,
            market_id=signal.market_id,
            direction=signal.direction.value,
            entry_price=fill_price,
            entry_time=datetime.now(),
            size=size,
            target_price=signal.target_price,
            stop_loss=signal.stop_loss,
            time_exit=signal.time_exit,
            current_price=fill_price,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
        )
        
        # Update portfolio
        margin_required = size * 0.5
        self.portfolio.open_positions[position.position_id] = position
        self.portfolio.available_balance -= margin_required
        self.portfolio.total_exposure += size
        self.last_trade_time = datetime.now()
        
        logger.info(f"Opened {position.direction} position: ${size:.0f} "
                   f"at {fill_price:.4f} (risk: {risk_percent:.2%})")
        
        return position
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str
    ) -> Dict:
        """
        Close a position and update portfolio.
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Exit reason
            
        Returns:
            Trade summary
        """
        if position_id not in self.portfolio.open_positions:
            return {}
        
        position = self.portfolio.open_positions[position_id]
        
        # Calculate PnL
        if position.direction == 'long':
            pnl = (exit_price - position.entry_price) * position.size
            pnl_pct = (exit_price / position.entry_price) - 1
        else:
            pnl = (position.entry_price - exit_price) * position.size
            pnl_pct = 1 - (exit_price / position.entry_price)
        
        # Update portfolio
        margin_released = position.size * 0.5
        self.portfolio.available_balance += margin_released + pnl
        self.portfolio.bankroll += pnl
        self.portfolio.total_exposure -= position.size
        self.portfolio.daily_pnl += pnl
        self.portfolio.total_pnl += pnl
        self.portfolio.update_drawdown()
        
        # Record trade
        trade_record = {
            'position_id': position_id,
            'market_id': position.market_id,
            'direction': position.direction,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'size': position.size,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_reason': reason,
            'duration_seconds': (datetime.now() - position.entry_time).total_seconds(),
            'risk_amount': position.risk_amount,
            'r_multiple': pnl / position.risk_amount if position.risk_amount > 0 else 0,
        }
        
        self.trade_history.append(trade_record)
        
        # Remove position
        del self.portfolio.open_positions[position_id]
        
        # Log result
        result_emoji = "✅" if pnl > 0 else "❌"
        logger.info(f"{result_emoji} Closed {position.direction}: ${pnl:+.2f} "
                   f"({pnl_pct:+.2%}) via {reason}")
        
        return trade_record
    
    def update_positions(self, market_prices: Dict[str, float]):
        """
        Update all positions with current prices.
        
        Args:
            market_prices: Dict of market_id -> current_price
            
        Returns:
            List of positions that need action
        """
        actions_needed = []
        
        for position in list(self.portfolio.open_positions.values()):
            if position.market_id in market_prices:
                position.update_price(market_prices[position.market_id])
                
                # Check for exit conditions
                should_exit, exit_reason = position.should_exit
                if should_exit:
                    actions_needed.append({
                        'position': position,
                        'reason': exit_reason,
                        'exit_price': position.current_price,
                    })
        
        return actions_needed
    
    def _calculate_correlated_exposure(self, signal) -> float:
        """Calculate exposure to correlated markets."""
        # For BTC 5-min markets, assume high correlation
        # Sum up all open position sizes in same direction
        correlated_size = 0
        
        for pos in self.portfolio.open_positions.values():
            if pos.direction == signal.direction.value:
                correlated_size += pos.size
        
        return correlated_size
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary."""
        return {
            'bankroll': self.portfolio.bankroll,
            'available_balance': self.portfolio.available_balance,
            'total_exposure': self.portfolio.total_exposure,
            'exposure_pct': self.portfolio.total_exposure / self.portfolio.bankroll,
            'open_positions': len(self.portfolio.open_positions),
            'daily_pnl': self.portfolio.daily_pnl,
            'total_pnl': self.portfolio.total_pnl,
            'current_drawdown': self.portfolio.current_drawdown,
            'peak_bankroll': self.portfolio.peak_bankroll,
        }
    
    def get_position_report(self) -> pd.DataFrame:
        """Get report of all open positions."""
        if not self.portfolio.open_positions:
            return pd.DataFrame()
        
        data = []
        for pos in self.portfolio.open_positions.values():
            data.append({
                'position_id': pos.position_id,
                'market': pos.market_id[:15],
                'direction': pos.direction,
                'entry': pos.entry_price,
                'current': pos.current_price,
                'size': pos.size,
                'unrealized_pnl': pos.unrealized_pnl,
                'unrealized_pct': pos.unrealized_pnl_pct,
                'stop': pos.stop_loss,
                'target': pos.target_price,
                'time_remaining': (pos.time_exit - datetime.now()).total_seconds(),
            })
        
        return pd.DataFrame(data)
    
    def get_trade_statistics(self) -> Dict:
        """Get comprehensive trade statistics."""
        if not self.trade_history:
            return {'message': 'No trades yet'}
        
        df = pd.DataFrame(self.trade_history)
        
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]
        
        return {
            'total_trades': len(df),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(df) if len(df) > 0 else 0,
            'avg_win': wins['pnl'].mean() if len(wins) > 0 else 0,
            'avg_loss': losses['pnl'].mean() if len(losses) > 0 else 0,
            'largest_win': df['pnl'].max(),
            'largest_loss': df['pnl'].min(),
            'avg_r_multiple': df['r_multiple'].mean(),
            'profit_factor': abs(wins['pnl'].sum() / losses['pnl'].sum()) if losses['pnl'].sum() != 0 else float('inf'),
            'avg_trade_duration': df['duration_seconds'].mean(),
        }
