"""
Signal Generator for BTC 5-Minute Trading

Combines pattern recognition, whale analysis, and market micro-structure
to generate high-probability trading signals with precise entry/exit timing.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..utils.logger import setup_logging
from .pattern_engine import PatternEngine, PatternSignal, SignalType, PatternConfidence

logger = setup_logging()


class TradeDirection(Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class SignalStatus(Enum):
    """Signal lifecycle status."""
    GENERATED = "generated"
    ACTIVE = "active"
    FILLED = "filled"
    TARGET_HIT = "target_hit"
    STOPPED = "stopped"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class TradeSignal:
    """
    Complete trading signal with full execution plan.
    """
    # Identification
    signal_id: str
    timestamp: datetime
    market_id: str
    market_question: str
    
    # Signal direction
    direction: TradeDirection
    primary_pattern: SignalType
    
    # Entry plan
    entry_type: str  # 'market', 'limit', 'stop'
    entry_price: float
    entry_price_min: float  # For limit orders
    entry_price_max: float
    
    # Exit plan
    target_price: float
    stop_loss: float
    time_exit: datetime  # Exit before expiration
    
    # Position sizing
    suggested_size: float
    max_size: float
    risk_percent: float
    
    # Signal quality
    confidence_score: float  # 0-1
    expected_return: float
    risk_reward: float
    win_probability: float
    
    # Analysis
    pattern_signals: List[PatternSignal] = field(default_factory=list)
    whale_confluence: Dict = field(default_factory=dict)
    market_regime: str = ""
    
    # Execution tracking
    status: SignalStatus = SignalStatus.GENERATED
    fill_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl_realized: float = 0.0
    
    # Metadata
    reasoning: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if signal is still valid."""
        if self.status != SignalStatus.GENERATED:
            return False
        
        # Check time validity (must enter within 60 seconds for 5-min markets)
        age = (datetime.now() - self.timestamp).total_seconds()
        return age < 60
    
    @property
    def time_to_expiration(self) -> float:
        """Seconds until market expiration."""
        return (self.time_exit - datetime.now()).total_seconds()
    
    def calculate_position_size(self, bankroll: float, kelly_fraction: float = 0.5) -> float:
        """
        Calculate position size using Kelly Criterion.
        
        Args:
            bankroll: Total available capital
            kelly_fraction: Conservative Kelly (0.5 = half-Kelly)
            
        Returns:
            Position size in USD
        """
        # Kelly formula: f = (bp - q) / b
        # where: b = odds, p = win probability, q = loss probability
        
        p = self.win_probability
        q = 1 - p
        
        if self.risk_reward > 0:
            b = self.risk_reward
            kelly = (b * p - q) / b
        else:
            kelly = 0
        
        # Apply fraction and cap
        position = bankroll * kelly * kelly_fraction
        
        # Cap at suggested max
        return min(position, self.max_size)


class SignalGenerator:
    """
    Advanced signal generator for BTC 5-minute markets.
    
    Combines multiple analytical layers:
    1. Pattern recognition (momentum, mean reversion, breakouts)
    2. Whale confluence (top performer alignment)
    3. Market regime detection
    4. Risk-adjusted position sizing
    """
    
    # Minimum thresholds
    MIN_CONFIDENCE = 0.6
    MIN_RISK_REWARD = 1.5
    MIN_WIN_PROBABILITY = 0.55
    
    def __init__(self, pattern_engine: Optional[PatternEngine] = None):
        """Initialize signal generator."""
        self.pattern_engine = pattern_engine or PatternEngine()
        self.active_signals: Dict[str, TradeSignal] = {}
        self.signal_history: List[TradeSignal] = []
        
        # Performance tracking
        self.performance_log: List[Dict] = []
        
        logger.info("Signal Generator initialized")
    
    def generate_signal(
        self,
        market_data: Dict,
        tick_data: pd.DataFrame,
        whale_data: Dict,
        trader_confluence: Dict
    ) -> Optional[TradeSignal]:
        """
        Generate a complete trading signal.
        
        Args:
            market_data: Current market state
            tick_data: Recent price/volume data
            whale_data: Whale activity data
            trader_confluence: Top trader positions
            
        Returns:
            TradeSignal if conditions met, None otherwise
        """
        # Step 1: Pattern Analysis
        pattern_signals = self.pattern_engine.analyze_market(market_data, tick_data)
        
        if not pattern_signals:
            return None
        
        # Step 2: Filter by confidence
        high_conf_patterns = [
            p for p in pattern_signals
            if p.confidence_score >= self.MIN_CONFIDENCE
        ]
        
        if not high_conf_patterns:
            return None
        
        # Step 3: Check whale confluence
        whale_confluence = self._calculate_whale_confluence(
            high_conf_patterns[0], whale_data
        )
        
        # Step 4: Calculate composite score
        composite = self._calculate_composite_score(
            high_conf_patterns[0],
            whale_confluence,
            trader_confluence,
            market_data
        )
        
        if composite['score'] < self.MIN_CONFIDENCE:
            logger.debug(f"Signal rejected: score {composite['score']:.2f} below threshold")
            return None
        
        # Step 5: Build complete signal
        signal = self._build_signal(
            market_data,
            high_conf_patterns[0],
            composite,
            whale_confluence,
            trader_confluence
        )
        
        # Store signal
        self.active_signals[signal.signal_id] = signal
        self.signal_history.append(signal)
        
        logger.info(f"Generated {signal.direction.value} signal for {market_data.get('market_id', 'unknown')}: "
                   f"confidence={signal.confidence_score:.2f}, R:R={signal.risk_reward:.2f}")
        
        return signal
    
    def _calculate_whale_confluence(
        self,
        pattern: PatternSignal,
        whale_data: Dict
    ) -> Dict:
        """Calculate whale confluence with pattern direction."""
        confluence = {
            'aligned_whales': [],
            'opposed_whales': [],
            'confluence_score': 0.0,
            'total_whale_volume': 0.0,
        }
        
        if not whale_data:
            return confluence
        
        whale_positions = whale_data.get('positions', [])
        pattern_direction = pattern.direction
        
        for pos in whale_positions:
            wallet = pos.get('wallet', '')
            outcome = pos.get('outcomeIndex', 0)  # 0 = YES, 1 = NO
            size = pos.get('amount', 0)
            
            # Determine whale direction
            if outcome == 0:  # YES = LONG
                whale_direction = TradeDirection.LONG
            else:
                whale_direction = TradeDirection.SHORT
            
            if whale_direction == pattern_direction:
                confluence['aligned_whales'].append({
                    'wallet': wallet,
                    'size': size,
                    'direction': whale_direction.value
                })
            else:
                confluence['opposed_whales'].append({
                    'wallet': wallet,
                    'size': size,
                    'direction': whale_direction.value
                })
            
            confluence['total_whale_volume'] += size
        
        # Calculate confluence score
        aligned_volume = sum(w['size'] for w in confluence['aligned_whales'])
        opposed_volume = sum(w['size'] for w in confluence['opposed_whales'])
        total = aligned_volume + opposed_volume
        
        if total > 0:
            confluence['confluence_score'] = aligned_volume / total
        
        return confluence
    
    def _calculate_composite_score(
        self,
        pattern: PatternSignal,
        whale_confluence: Dict,
        trader_confluence: Dict,
        market_data: Dict
    ) -> Dict:
        """Calculate composite signal score."""
        scores = {
            'pattern': pattern.confidence_score,
            'whale': whale_confluence.get('confluence_score', 0),
            'trader': trader_confluence.get('agreement_ratio', 0),
            'timing': self._calculate_timing_score(market_data),
        }
        
        # Weighted average
        weights = {
            'pattern': 0.40,
            'whale': 0.30,
            'trader': 0.20,
            'timing': 0.10,
        }
        
        composite_score = sum(scores[k] * weights[k] for k in scores)
        
        # Adjust for risk/reward
        if pattern.risk_reward < 1.5:
            composite_score *= 0.8
        elif pattern.risk_reward > 2.5:
            composite_score = min(1.0, composite_score * 1.1)
        
        return {
            'score': composite_score,
            'components': scores,
            'weights': weights,
        }
    
    def _calculate_timing_score(self, market_data: Dict) -> float:
        """Calculate timing quality score."""
        expires_at = market_data.get('expires_at')
        if not expires_at:
            return 0.5
        
        remaining = (expires_at - datetime.now()).total_seconds()
        
        # Optimal entry: 2-4 minutes before expiration
        if 120 < remaining < 240:
            return 1.0
        elif 60 < remaining < 300:
            return 0.8
        elif remaining < 60:
            return 0.3  # Too late
        else:
            return 0.6  # Too early
    
    def _build_signal(
        self,
        market_data: Dict,
        pattern: PatternSignal,
        composite: Dict,
        whale_confluence: Dict,
        trader_confluence: Dict
    ) -> TradeSignal:
        """Build complete trading signal."""
        # Generate unique ID
        signal_id = f"{market_data.get('market_id', 'unknown')}_{datetime.now().strftime('%H%M%S')}"
        
        # Determine direction
        if 'LONG' in pattern.signal_type.value:
            direction = TradeDirection.LONG
        elif 'SHORT' in pattern.signal_type.value:
            direction = TradeDirection.SHORT
        else:
            direction = TradeDirection.NEUTRAL
        
        # Calculate win probability
        base_prob = composite['score']
        
        # Adjust for whale confluence
        whale_score = whale_confluence.get('confluence_score', 0.5)
        win_prob = (base_prob * 0.7) + (whale_score * 0.3)
        
        # Build reasoning
        reasoning = pattern.supporting_evidence.copy()
        reasoning.append(f"Composite confidence: {composite['score']:.1%}")
        
        if whale_confluence['aligned_whales']:
            reasoning.append(f"Whale confluence: {len(whale_confluence['aligned_whales'])} aligned")
        
        # Risk factors
        risk_factors = pattern.contradictory_evidence.copy()
        
        if whale_confluence['opposed_whales']:
            risk_factors.append(f"{len(whale_confluence['opposed_whales'])} whales opposed")
        
        # Time exit (exit 30s before expiration)
        time_exit = market_data.get('expires_at', datetime.now() + timedelta(minutes=5))
        time_exit = time_exit - timedelta(seconds=30)
        
        return TradeSignal(
            signal_id=signal_id,
            timestamp=datetime.now(),
            market_id=market_data.get('market_id', ''),
            market_question=market_data.get('question', ''),
            direction=direction,
            primary_pattern=pattern.signal_type,
            entry_type='limit',  # Use limit orders for better fills
            entry_price=pattern.entry_price,
            entry_price_min=pattern.entry_price * 0.998,
            entry_price_max=pattern.entry_price * 1.002,
            target_price=pattern.target_price,
            stop_loss=pattern.stop_loss,
            time_exit=time_exit,
            suggested_size=1000,  # Base size
            max_size=5000,
            risk_percent=0.02,  # 2% risk per trade
            confidence_score=composite['score'],
            expected_return=pattern.expected_return,
            risk_reward=pattern.risk_reward,
            win_probability=win_prob,
            pattern_signals=[pattern],
            whale_confluence=whale_confluence,
            market_regime=market_data.get('regime', 'unknown'),
            reasoning=reasoning,
            risk_factors=risk_factors,
        )
    
    def update_signal_status(
        self,
        signal_id: str,
        status: SignalStatus,
        fill_price: Optional[float] = None,
        exit_price: Optional[float] = None,
        pnl: float = 0.0
    ):
        """Update signal status and track performance."""
        if signal_id not in self.active_signals:
            return
        
        signal = self.active_signals[signal_id]
        signal.status = status
        
        if fill_price:
            signal.fill_price = fill_price
        if exit_price:
            signal.exit_price = exit_price
        if pnl:
            signal.pnl_realized = pnl
        
        # Log performance
        if status in [SignalStatus.TARGET_HIT, SignalStatus.STOPPED]:
            self.performance_log.append({
                'signal_id': signal_id,
                'pattern': signal.primary_pattern.value,
                'direction': signal.direction.value,
                'confidence': signal.confidence_score,
                'result': 'win' if pnl > 0 else 'loss',
                'pnl': pnl,
                'risk_reward': signal.risk_reward,
            })
            
            # Remove from active
            del self.active_signals[signal_id]
    
    def get_active_signals(self) -> List[TradeSignal]:
        """Get all currently active signals."""
        # Filter out expired signals
        current_time = datetime.now()
        active = []
        
        for signal in self.active_signals.values():
            if signal.status == SignalStatus.GENERATED and signal.is_valid:
                active.append(signal)
        
        return sorted(active, key=lambda s: s.confidence_score, reverse=True)
    
    def get_performance_report(self) -> Dict:
        """Generate performance report."""
        if not self.performance_log:
            return {'message': 'No completed trades yet'}
        
        df = pd.DataFrame(self.performance_log)
        
        total_trades = len(df)
        wins = len(df[df['result'] == 'win'])
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        avg_pnl = df['pnl'].mean()
        total_pnl = df['pnl'].sum()
        
        # By pattern
        pattern_stats = df.groupby('pattern').agg({
            'result': lambda x: (x == 'win').mean(),
            'pnl': 'sum',
        }).rename(columns={'result': 'win_rate'})
        
        # By confidence level
        df['confidence_bucket'] = pd.cut(df['confidence'], bins=[0, 0.6, 0.75, 0.9, 1.0])
        confidence_stats = df.groupby('confidence_bucket')['result'].apply(
            lambda x: (x == 'win').mean()
        )
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'total_pnl': total_pnl,
            'profit_factor': abs(df[df['pnl'] > 0]['pnl'].sum() / df[df['pnl'] < 0]['pnl'].sum()) if df[df['pnl'] < 0]['pnl'].sum() != 0 else float('inf'),
            'pattern_performance': pattern_stats.to_dict(),
            'confidence_calibration': confidence_stats.to_dict(),
        }
    
    def get_signal_summary(self) -> pd.DataFrame:
        """Get summary of all signals."""
        if not self.signal_history:
            return pd.DataFrame()
        
        data = []
        for signal in self.signal_history:
            data.append({
                'signal_id': signal.signal_id,
                'timestamp': signal.timestamp,
                'market': signal.market_id[:10],
                'direction': signal.direction.value,
                'pattern': signal.primary_pattern.value,
                'confidence': signal.confidence_score,
                'risk_reward': signal.risk_reward,
                'status': signal.status.value,
                'pnl': signal.pnl_realized,
            })
        
        return pd.DataFrame(data)
