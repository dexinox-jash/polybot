"""
Paper Trading Engine - Educational Trade Simulation

Simulates real-time trade execution with comprehensive timing analysis:
- Entry/exit timing vs whale
- Price slippage tracking
- Execution quality scoring
- Educational performance reports
- Dynamic position sizing based on Kelly Criterion
"""

import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

# Import dynamic position sizer
try:
    from ..position.dynamic_sizer import DynamicPositionSizer, SizingResult, PositionSizingConfig
except ImportError:
    DynamicPositionSizer = None
    SizingResult = None
    PositionSizingConfig = None

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Paper position status."""
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass
class TimingMetrics:
    """Timing analysis for a paper trade."""
    # Whale reference
    whale_entry_time: datetime
    our_entry_time: datetime
    entry_delay_seconds: float
    
    # Speed score
    speed_score: float  # 0-1 (1 = matched whale speed)
    
    # Price delta
    whale_entry_price: float
    our_entry_price: float
    price_slippage_percent: float  # How much worse we got
    
    # Market conditions
    market_liquidity_at_entry: float
    price_volatility_1min: float
    
    # Benchmark
    whale_pnl_percent: Optional[float] = None
    our_pnl_percent: Optional[float] = None
    pnl_delta: Optional[float] = None  # How we performed vs whale


@dataclass
class PaperPosition:
    """A paper trading position."""
    # Identity
    position_id: str
    signal_id: str
    
    # Whale reference
    whale_address: str
    whale_pattern_type: str
    whale_confidence: float
    
    # Market
    market_id: str
    market_question: str
    direction: str  # 'YES' or 'NO'
    
    # Entry
    entry_price: float
    intended_entry_price: float
    size_usd: float
    entry_time: datetime
    
    # Targets
    stop_loss_price: float
    take_profit_price: float
    time_exit_at: datetime
    
    # Timing analysis
    timing_metrics: TimingMetrics
    
    # Exit (optional, set when closing)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None  # 'stop_loss', 'take_profit', 'time_exit', 'manual'
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    
    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    
    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized P&L based on current price."""
        if self.direction == 'YES':
            pnl = (current_price - self.entry_price) * self.size_usd
        else:
            pnl = (self.entry_price - current_price) * self.size_usd
        
        self.unrealized_pnl = pnl - self.fees_paid
    
    def close_position(self, exit_price: float, reason: str):
        """Close the position."""
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.exit_reason = reason
        self.status = PositionStatus.CLOSED
        
        # Calculate realized P&L
        if self.direction == 'YES':
            self.realized_pnl = (exit_price - self.entry_price) * self.size_usd
        else:
            self.realized_pnl = (self.entry_price - exit_price) * self.size_usd
        
        self.realized_pnl -= self.fees_paid
        self.unrealized_pnl = 0.0


class PaperTradingEngine:
    """
    Paper trading engine with timing analysis and dynamic position sizing.
    
    Tracks educational metrics:
    - How fast we are vs whales
    - Slippage costs
    - Pattern accuracy
    - P&L benchmarking
    - Dynamic position sizing decisions
    """
    
    def __init__(
        self,
        initial_balance: float = 10000.0,
        use_dynamic_sizing: bool = True,
        sizing_config: str = 'moderate',
        win_rate: float = 0.55,
        profit_factor: float = 1.5
    ):
        """
        Initialize paper trading engine.
        
        Args:
            initial_balance: Starting paper balance (default $10,000)
            use_dynamic_sizing: Whether to use dynamic position sizing
            sizing_config: 'conservative', 'moderate', or 'aggressive'
            win_rate: Historical win rate for Kelly calculations
            profit_factor: Historical profit factor for Kelly calculations
        """
        self.balance = initial_balance
        self.initial_balance = initial_balance
        
        # Positions
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_positions: List[PaperPosition] = []
        
        # Timing tracking
        self.total_delay_seconds: float = 0.0
        self.total_slippage_percent: float = 0.0
        self.trade_count: int = 0
        
        # Pattern tracking
        self.pattern_performance: Dict[str, Dict] = {}
        
        # Dynamic position sizing
        self.use_dynamic_sizing = use_dynamic_sizing and DynamicPositionSizer is not None
        self._win_rate = win_rate
        self._profit_factor = profit_factor
        self._current_drawdown = 0.0
        
        if self.use_dynamic_sizing:
            # Initialize sizer based on config
            if sizing_config == 'conservative' and PositionSizingConfig:
                self.position_sizer = PositionSizingConfig.conservative()
            elif sizing_config == 'aggressive' and PositionSizingConfig:
                self.position_sizer = PositionSizingConfig.aggressive()
            else:
                self.position_sizer = PositionSizingConfig.moderate() if PositionSizingConfig else None
            
            logger.info(f"Dynamic sizing enabled ({sizing_config}): "
                       f"Kelly fraction={self.position_sizer.kelly_fraction}, "
                       f"Risk={self.position_sizer.risk_per_trade:.1%}")
        else:
            self.position_sizer = None
            logger.info("Dynamic sizing disabled - using fixed position sizes")
        
        # Sizing decision history
        self.sizing_history: List[Dict] = []
        
        logger.info(f"PaperTradingEngine initialized: ${initial_balance:,.2f}")
    
    def _calculate_position_size(
        self,
        signal,
        market_data: Dict
    ) -> tuple:
        """
        Calculate position size using dynamic sizing or fallback to fixed.
        
        Returns:
            Tuple of (position_size, sizing_result_dict)
        """
        # Get whale size from signal
        trade = signal.trade
        whale_size = getattr(trade, 'amount', getattr(trade, 'size', 50000.0))
        
        # Get confidence from signal
        confidence = getattr(signal, 'pattern_confidence', 0.7)
        
        # Get market liquidity
        market_liquidity = market_data.get('liquidity', 1000000.0)
        
        if self.use_dynamic_sizing and self.position_sizer:
            # Calculate dynamic position size
            sizing_result = self.position_sizer.calculate_position_size(
                whale_size=whale_size,
                confidence=confidence,
                current_balance=self.balance,
                market_liquidity=market_liquidity,
                win_rate=self._win_rate,
                profit_factor=self._profit_factor,
                current_drawdown=self._current_drawdown
            )
            
            # Build sizing record
            sizing_record = {
                'timestamp': datetime.now().isoformat(),
                'position_size': sizing_result.position_size,
                'decision': sizing_result.decision.value,
                'confidence_tier': sizing_result.confidence_tier,
                'base_size': sizing_result.base_size,
                'kelly_adjusted_size': sizing_result.kelly_adjusted_size,
                'confidence_multiplier': sizing_result.confidence_multiplier,
                'liquidity_cap': sizing_result.liquidity_cap,
                'risk_adjusted_size': sizing_result.risk_adjusted_size,
                'risk_amount': sizing_result.risk_amount,
                'risk_percent': sizing_result.risk_percent,
                'whale_size_tier': sizing_result.whale_size_tier,
                'market_liquidity_percent': sizing_result.market_liquidity_percent,
                'reasoning': sizing_result.reasoning,
                'warnings': sizing_result.warnings
            }
            
            return sizing_result.position_size, sizing_record
        else:
            # Fallback to fixed sizing (legacy behavior)
            fixed_size = min(signal.suggested_size, self.balance * 0.02)
            sizing_record = {
                'timestamp': datetime.now().isoformat(),
                'position_size': fixed_size,
                'decision': 'fixed_size',
                'reasoning': ['Dynamic sizing disabled, using fixed size'],
                'note': f'Max 2% of ${self.balance:,.2f} = ${self.balance * 0.02:,.2f}'
            }
            return fixed_size, sizing_record
    
    def _update_drawdown(self):
        """Update current drawdown calculation."""
        peak = self.initial_balance
        current = self.balance
        
        # Find peak from closed positions
        for pos in self.closed_positions:
            temp_balance = self.initial_balance + sum(
                p.realized_pnl for p in self.closed_positions[:self.closed_positions.index(pos) + 1]
            )
            if temp_balance > peak:
                peak = temp_balance
        
        if peak > 0:
            self._current_drawdown = max(0, (peak - current) / peak)
    
    def execute_paper_trade(
        self,
        signal,
        delay_seconds: int,
        market_data: Dict
    ) -> Optional[PaperPosition]:
        """
        Execute a paper trade with timing tracking and dynamic sizing.
        
        Args:
            signal: WhaleSignal with trade details
            delay_seconds: How long after whale we executed
            market_data: Current market data for slippage calc
            
        Returns:
            PaperPosition with full tracking, or None if sizing resulted in skip
        """
        trade = signal.trade
        whale_entry_time = trade.timestamp
        our_entry_time = datetime.now()
        
        # Calculate actual delay
        actual_delay = (our_entry_time - whale_entry_time).total_seconds()
        
        # Get prices
        whale_price = trade.price
        current_price = market_data.get('current_price', whale_price)
        
        # Calculate slippage
        slippage = ((current_price - whale_price) / whale_price) * 100
        if trade.outcome == 'NO':
            slippage = -slippage  # Inverse for NO positions
        
        # Calculate speed score (0-1)
        speed_score = max(0, 1 - (actual_delay / 300))  # 5 min = 0 score
        
        # Create timing metrics
        timing = TimingMetrics(
            whale_entry_time=whale_entry_time,
            our_entry_time=our_entry_time,
            entry_delay_seconds=actual_delay,
            speed_score=speed_score,
            whale_entry_price=whale_price,
            our_entry_price=current_price,
            price_slippage_percent=slippage,
            market_liquidity_at_entry=market_data.get('liquidity', 0),
            price_volatility_1min=market_data.get('volatility_1min', 0),
            whale_pnl_percent=None,
            our_pnl_percent=None,
            pnl_delta=None
        )
        
        # Determine position size using dynamic sizing
        size, sizing_record = self._calculate_position_size(signal, market_data)
        
        # Store sizing decision
        self.sizing_history.append(sizing_record)
        
        # Check if trade should be skipped
        if size <= 0:
            logger.info(f"Trade skipped: {sizing_record.get('decision', 'unknown reason')}")
            return None
        
        # Log sizing decision
        if 'reasoning' in sizing_record:
            for reason in sizing_record['reasoning'][-3:]:  # Log last 3 reasoning items
                logger.debug(f"Sizing: {reason}")
        
        # Calculate stop/target prices
        if trade.outcome == 'YES':
            stop_loss = current_price * 0.95  # 5% stop
            take_profit = current_price * 1.10  # 10% target
        else:
            stop_loss = current_price * 1.05
            take_profit = current_price * 0.90
        
        # Create position
        position = PaperPosition(
            position_id=str(uuid.uuid4())[:8],
            signal_id=trade.tx_hash[:8],
            whale_address=trade.whale_address,
            whale_pattern_type=signal.whale_pattern_profile,
            whale_confidence=signal.pattern_confidence,
            market_id=trade.market_id,
            market_question=trade.market_question[:50],
            direction=trade.outcome,
            entry_price=current_price,
            intended_entry_price=whale_price,
            size_usd=size,
            entry_time=our_entry_time,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            time_exit_at=our_entry_time + timedelta(hours=24),
            timing_metrics=timing
        )
        
        # Track position
        self.positions[position.position_id] = position
        
        # Update stats
        self.total_delay_seconds += actual_delay
        self.total_slippage_percent += slippage
        self.trade_count += 1
        
        # Update pattern tracking
        self._update_pattern_stats(signal.whale_pattern_profile, size)
        
        logger.info(f"Paper trade executed: {position.position_id} | "
                   f"{trade.outcome} ${size:.0f} | "
                   f"Delay: {actual_delay:.1f}s | Slippage: {slippage:.2f}%")
        
        # Log dynamic sizing info
        if self.use_dynamic_sizing and 'decision' in sizing_record:
            logger.info(f"  Sizing: {sizing_record['decision']} | "
                       f"Kelly: ${sizing_record.get('kelly_adjusted_size', 0):.0f} | "
                       f"Risk: {sizing_record.get('risk_percent', 0):.2%}")
        
        return position
    
    def update_positions(self, market_prices: Dict[str, float]):
        """
        Update all open positions with current prices.
        
        Args:
            market_prices: Dict of market_id -> current_price
        """
        for position in self.positions.values():
            if position.status != PositionStatus.OPEN:
                continue
            
            current_price = market_prices.get(position.market_id)
            if not current_price:
                continue
            
            # Update unrealized P&L
            position.update_unrealized_pnl(current_price)
            
            # Check stop loss
            if position.direction == 'YES' and current_price <= position.stop_loss_price:
                self.close_position(position.position_id, current_price, 'stop_loss')
            elif position.direction == 'NO' and current_price >= position.stop_loss_price:
                self.close_position(position.position_id, current_price, 'stop_loss')
            
            # Check take profit
            elif position.direction == 'YES' and current_price >= position.take_profit_price:
                self.close_position(position.position_id, current_price, 'take_profit')
            elif position.direction == 'NO' and current_price <= position.take_profit_price:
                self.close_position(position.position_id, current_price, 'take_profit')
            
            # Check time exit
            elif datetime.now() >= position.time_exit_at:
                self.close_position(position.position_id, current_price, 'time_exit')
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str
    ) -> Optional[PaperPosition]:
        """
        Close a position.
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Why closing (stop_loss, take_profit, time_exit)
            
        Returns:
            Closed position or None if not found
        """
        position = self.positions.get(position_id)
        if not position:
            return None
        
        position.close_position(exit_price, reason)
        
        # Move to closed
        self.closed_positions.append(position)
        del self.positions[position_id]
        
        # Update balance
        self.balance += position.realized_pnl
        
        # Update drawdown tracking
        self._update_drawdown()
        
        logger.info(f"Position closed: {position_id} | Reason: {reason} | "
                   f"P&L: ${position.realized_pnl:+.2f} | "
                   f"Balance: ${self.balance:,.2f} | "
                   f"Drawdown: {self._current_drawdown:.1%}")
        
        return position
    
    def _update_pattern_stats(self, pattern_type: str, size: float):
        """Update pattern performance tracking."""
        if pattern_type not in self.pattern_performance:
            self.pattern_performance[pattern_type] = {
                'trade_count': 0,
                'total_size': 0.0,
                'wins': 0,
                'losses': 0
            }
        
        stats = self.pattern_performance[pattern_type]
        stats['trade_count'] += 1
        stats['total_size'] += size
    
    def get_timing_summary(self) -> Dict:
        """Get summary of timing performance."""
        if self.trade_count == 0:
            return {
                'avg_delay_seconds': 0,
                'avg_slippage_percent': 0,
                'avg_speed_score': 0,
                'timing_grade': 'N/A'
            }
        
        avg_delay = self.total_delay_seconds / self.trade_count
        avg_slippage = self.total_slippage_percent / self.trade_count
        avg_speed = sum(p.timing_metrics.speed_score for p in self.closed_positions) / len(self.closed_positions) if self.closed_positions else 0
        
        # Grade timing
        if avg_delay < 30:
            grade = 'A+'
        elif avg_delay < 60:
            grade = 'A'
        elif avg_delay < 120:
            grade = 'B'
        elif avg_delay < 300:
            grade = 'C'
        else:
            grade = 'D'
        
        return {
            'avg_delay_seconds': avg_delay,
            'avg_slippage_percent': avg_slippage,
            'avg_speed_score': avg_speed,
            'timing_grade': grade,
            'total_trades': self.trade_count
        }
    
    def get_sizing_report(self) -> Dict:
        """Get report on position sizing decisions."""
        if not self.sizing_history:
            return {'message': 'No sizing decisions yet'}
        
        # Recent sizing decisions
        recent = self.sizing_history[-50:]
        
        # Calculate metrics
        accepted = [s for s in recent if s.get('position_size', 0) > 0]
        skipped = [s for s in recent if s.get('position_size', 0) == 0]
        
        report = {
            'total_decisions': len(self.sizing_history),
            'recent_decisions': len(recent),
            'trades_accepted': len(accepted),
            'trades_skipped': len(skipped),
            'acceptance_rate': len(accepted) / len(recent) if recent else 0,
            'avg_position_size': sum(s['position_size'] for s in accepted) / len(accepted) if accepted else 0,
            'avg_risk_percent': sum(s.get('risk_percent', 0) for s in accepted) / len(accepted) if accepted else 0,
        }
        
        # Decision type breakdown
        decision_types = {}
        for s in recent:
            decision = s.get('decision', 'unknown')
            decision_types[decision] = decision_types.get(decision, 0) + 1
        report['decision_types'] = decision_types
        
        # Recent warnings
        all_warnings = []
        for s in recent:
            warnings = s.get('warnings', [])
            all_warnings.extend(warnings)
        if all_warnings:
            report['recent_warnings'] = list(set(all_warnings))[:5]  # Unique warnings, max 5
        
        return report
    
    def get_performance_report(self) -> Dict:
        """Generate comprehensive performance report."""
        if not self.closed_positions:
            return {
                'message': 'No completed trades yet',
                'open_positions': len(self.positions)
            }
        
        # Calculate metrics
        total_pnl = sum(p.realized_pnl for p in self.closed_positions)
        wins = sum(1 for p in self.closed_positions if p.realized_pnl > 0)
        losses = len(self.closed_positions) - wins
        win_rate = wins / len(self.closed_positions) if self.closed_positions else 0
        
        gross_profit = sum(p.realized_pnl for p in self.closed_positions if p.realized_pnl > 0)
        gross_loss = abs(sum(p.realized_pnl for p in self.closed_positions if p.realized_pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
        
        # Pattern performance
        pattern_analysis = {}
        for pos in self.closed_positions:
            pattern = pos.whale_pattern_type
            if pattern not in pattern_analysis:
                pattern_analysis[pattern] = {'trades': 0, 'pnl': 0, 'wins': 0}
            
            pattern_analysis[pattern]['trades'] += 1
            pattern_analysis[pattern]['pnl'] += pos.realized_pnl
            if pos.realized_pnl > 0:
                pattern_analysis[pattern]['wins'] += 1
        
        # Find best pattern
        best_pattern = max(pattern_analysis.items(), 
                          key=lambda x: x[1]['pnl']) if pattern_analysis else ('None', {})
        
        # Timing summary
        timing = self.get_timing_summary()
        
        return {
            'summary': {
                'total_trades': len(self.closed_positions),
                'open_positions': len(self.positions),
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_pnl': total_pnl,
                'total_pnl_percent': (total_pnl / self.initial_balance) * 100,
                'current_balance': self.balance
            },
            'timing': timing,
            'pattern_performance': pattern_analysis,
            'best_pattern': {
                'name': best_pattern[0],
                'pnl': best_pattern[1].get('pnl', 0),
                'accuracy': (best_pattern[1].get('wins', 0) / best_pattern[1].get('trades', 1)) * 100 if best_pattern[1] else 0
            },
            'insights': self._generate_insights(timing, pattern_analysis, win_rate)
        }
    
    def _generate_insights(
        self,
        timing: Dict,
        patterns: Dict,
        win_rate: float
    ) -> List[str]:
        """Generate educational insights."""
        insights = []
        
        # Timing insights
        delay = timing.get('avg_delay_seconds', 0)
        if delay < 60:
            insights.append(f"Excellent speed: averaging {delay:.0f}s delay vs whales")
        elif delay < 180:
            insights.append(f"Good speed: {delay:.0f}s average delay (aim for <60s)")
        else:
            insights.append(f"Slow execution: {delay:.0f}s delay is costing you edge")
        
        # Slippage insights
        slippage = timing.get('avg_slippage_percent', 0)
        if abs(slippage) > 2:
            insights.append(f"High slippage: {slippage:.1f}% (improve timing or reduce size)")
        
        # Win rate insights
        if win_rate > 0.6:
            insights.append(f"Strong win rate: {win_rate:.0%} - you're copying good whales")
        elif win_rate < 0.4:
            insights.append(f"Low win rate: {win_rate:.0%} - review whale selection criteria")
        
        # Pattern insights
        if patterns:
            best = max(patterns.items(), key=lambda x: x[1].get('pnl', 0))
            insights.append(f"Best pattern to copy: {best[0]} (${best[1].get('pnl', 0):+.2f})")
        
        return insights
    
    def get_open_positions_table(self) -> str:
        """Get formatted table of open positions."""
        if not self.positions:
            return "No open positions"
        
        lines = ["\n[OPEN POSITIONS]"]
        lines.append("-" * 80)
        lines.append(f"{'ID':<8} {'Market':<25} {'Dir':<5} {'Size':<8} {'Entry':<8} {'P&L':<10} {'Pattern'}")
        lines.append("-" * 80)
        
        for pos in self.positions.values():
            lines.append(
                f"{pos.position_id:<8} "
                f"{pos.market_question[:24]:<25} "
                f"{pos.direction:<5} "
                f"${pos.size_usd:<7.0f} "
                f"{pos.entry_price:<8.3f} "
                f"${pos.unrealized_pnl:<9.2f} "
                f"{pos.whale_pattern_type}"
            )
        
        return "\n".join(lines)
    
    def export_trade_log(self) -> List[Dict]:
        """Export all trades as list of dictionaries."""
        all_positions = list(self.positions.values()) + self.closed_positions
        
        return [
            {
                'position_id': p.position_id,
                'whale_address': p.whale_address,
                'pattern_type': p.whale_pattern_type,
                'market_id': p.market_id,
                'direction': p.direction,
                'size': p.size_usd,
                'entry_price': p.entry_price,
                'exit_price': p.exit_price,
                'entry_time': p.entry_time.isoformat(),
                'exit_time': p.exit_time.isoformat() if p.exit_time else None,
                'realized_pnl': p.realized_pnl,
                'status': p.status.value,
                'entry_delay_seconds': p.timing_metrics.entry_delay_seconds,
                'speed_score': p.timing_metrics.speed_score,
                'slippage_percent': p.timing_metrics.price_slippage_percent
            }
            for p in all_positions
        ]
