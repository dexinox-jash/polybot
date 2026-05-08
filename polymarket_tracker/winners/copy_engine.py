"""
Copy Engine - The Replication Execution System

Makes the final decision: SHOULD we copy this bet?

Combines:
- Winner reliability score
- EV calculation
- Risk management constraints
- Portfolio context
- Market conditions
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class CopyDecisionType(Enum):
    """Types of copy decisions."""
    IMMEDIATE_COPY = "immediate_copy"      # Execute now
    STAGED_COPY = "staged_copy"            # DCA over time
    WAIT_FOR_DIP = "wait_for_dip"          # Wait for better price
    SKIP = "skip"                          # Don't copy
    REDUCE_SIZE = "reduce_size"            # Copy smaller
    INCREASE_SIZE = "increase_size"        # Copy larger (high conviction)


@dataclass
class CopyDecision:
    """Final decision on whether/how to copy."""
    # Decision
    decision: CopyDecisionType
    confidence: float  # 0-1
    
    # Winner being copied
    winner_address: str
    winner_reliability: float
    
    # Market
    market_id: str
    direction: str
    
    # Sizing
    target_size: float
    max_size: float
    min_size: float
    
    # Execution plan
    execution_strategy: str  # 'market', 'limit', 'twap'
    entry_price_target: float
    slippage_tolerance: float
    time_in_force: timedelta
    
    # Risk management
    stop_loss: Optional[float]
    take_profit: Optional[float]
    max_hold_time: timedelta
    
    # Context
    portfolio_exposure_before: float
    portfolio_exposure_after: float
    correlated_positions: List[str]
    
    # Reasoning
    primary_reason: str
    supporting_factors: List[str]
    risk_factors: List[str]
    alternate_scenarios: List[str]
    
    # Timestamp
    decided_at: datetime = field(default_factory=datetime.now)
    valid_until: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))


class CopyEngine:
    """
    Makes intelligent copy decisions.
    
    Not all winner bets should be copied!
    This engine filters for the best opportunities.
    """
    
    def __init__(self, ev_calculator, position_manager):
        """
        Initialize copy engine.
        
        Args:
            ev_calculator: EVCalculator instance
            position_manager: PositionManager for risk constraints
        """
        self.ev_calc = ev_calculator
        self.position_manager = position_manager
        
        # Decision thresholds
        self.thresholds = {
            'min_ev_for_copy': 2.0,  # 2% minimum EV
            'min_winner_confidence': 0.6,
            'max_portfolio_exposure': 0.5,  # 50% max
            'max_correlated_exposure': 0.2,  # 20% per theme
            'min_liquidity': 10000,
        }
        
        # Decision history
        self.decisions: List[CopyDecision] = []
        self.outcomes: List[Dict] = []
        
    def evaluate_copy_opportunity(
        self,
        winner_profile,
        winner_bet,
        market_data: Dict,
        portfolio_state: Dict
    ) -> CopyDecision:
        """
        Evaluate whether to copy a specific bet.
        
        Returns CopyDecision with full execution plan.
        """
        # Step 1: Calculate EV
        ev = self.ev_calc.calculate_ev(
            winner_profile=winner_profile,
            market_probability=market_data.get('probability', 0.5),
            our_entry_price=market_data.get('current_price', winner_bet.entry_price),
            bet_size=1000,  # Base size for calculation
            time_to_close=winner_bet.market_close_time - datetime.now(),
            market_liquidity=market_data.get('liquidity', 0),
            market_volatility=market_data.get('volatility', 0.1)
        )
        
        # Step 2: Check constraints
        constraints_passed, constraint_reasons = self._check_constraints(
            winner_profile, winner_bet, market_data, portfolio_state
        )
        
        # Step 3: Score the opportunity
        opportunity_score = self._calculate_opportunity_score(
            winner_profile, ev, market_data
        )
        
        # Step 4: Determine decision
        decision, confidence = self._make_decision(
            ev, opportunity_score, constraints_passed, constraint_reasons
        )
        
        # Step 5: Calculate sizing
        sizing = self._calculate_sizing(
            ev, winner_profile, portfolio_state, decision
        )
        
        # Step 6: Build execution plan
        execution = self._build_execution_plan(
            winner_bet, market_data, sizing, decision
        )
        
        # Step 7: Risk parameters
        risk_params = self._calculate_risk_params(
            winner_bet, ev, sizing
        )
        
        # Build final decision
        copy_decision = CopyDecision(
            decision=decision,
            confidence=confidence,
            winner_address=winner_profile.address,
            winner_reliability=winner_profile.true_win_rate * winner_profile.profit_factor / 3,
            market_id=winner_bet.market_id,
            direction=winner_bet.direction,
            target_size=sizing['target'],
            max_size=sizing['max'],
            min_size=sizing['min'],
            execution_strategy=execution['strategy'],
            entry_price_target=execution['target_price'],
            slippage_tolerance=execution['slippage'],
            time_in_force=execution['time_in_force'],
            stop_loss=risk_params['stop_loss'],
            take_profit=risk_params['take_profit'],
            max_hold_time=risk_params['max_hold'],
            portfolio_exposure_before=portfolio_state.get('exposure', 0),
            portfolio_exposure_after=portfolio_state.get('exposure', 0) + sizing['target'] / portfolio_state.get('bankroll', 10000),
            correlated_positions=self._find_correlated_positions(winner_bet, portfolio_state),
            primary_reason=self._generate_primary_reason(ev, decision, winner_profile),
            supporting_factors=self._generate_supporting_factors(ev, winner_profile, market_data),
            risk_factors=constraint_reasons if not constraints_passed else self._generate_risk_factors(ev, market_data),
            alternate_scenarios=self._generate_scenarios(ev, winner_bet)
        )
        
        # Record decision
        self.decisions.append(copy_decision)
        
        return copy_decision
    
    def _check_constraints(
        self,
        winner_profile,
        winner_bet,
        market_data,
        portfolio_state
    ) -> Tuple[bool, List[str]]:
        """Check if opportunity passes all constraints."""
        passed = True
        reasons = []
        
        # EV constraint
        ev = self.ev_calc.calculate_ev(
            winner_profile, market_data.get('probability', 0.5),
            market_data.get('current_price', 0.5), 1000,
            winner_bet.market_close_time - datetime.now(),
            market_data.get('liquidity', 0), market_data.get('volatility', 0.1)
        )
        
        if ev.adjusted_ev_percent < self.thresholds['min_ev_for_copy']:
            passed = False
            reasons.append(f"EV too low: {ev.adjusted_ev_percent:.1f}%")
        
        # Portfolio exposure
        current_exposure = portfolio_state.get('exposure', 0)
        if current_exposure > self.thresholds['max_portfolio_exposure']:
            passed = False
            reasons.append(f"Max exposure reached: {current_exposure:.1%}")
        
        # Liquidity
        if market_data.get('liquidity', 0) < self.thresholds['min_liquidity']:
            passed = False
            reasons.append("Insufficient liquidity")
        
        # Time to close
        time_to_close = winner_bet.market_close_time - datetime.now()
        if time_to_close.total_seconds() < 300:  # Less than 5 minutes
            passed = False
            reasons.append("Too close to market close")
        
        # Winner reliability
        if winner_profile.confidence_level == 'low':
            passed = False
            reasons.append("Winner has low confidence rating")
        
        return passed, reasons
    
    def _calculate_opportunity_score(
        self,
        winner_profile,
        ev,
        market_data
    ) -> float:
        """Calculate overall opportunity quality score (0-1)."""
        score = 0.0
        
        # EV component (40%)
        ev_score = min(1.0, max(0, ev.adjusted_ev_percent) / 10)
        score += ev_score * 0.4
        
        # Winner reliability (30%)
        reliability = winner_profile.true_win_rate * winner_profile.profit_factor / 3
        reliability = min(1.0, reliability)
        score += reliability * 0.3
        
        # Market conditions (20%)
        liquidity_score = min(1.0, market_data.get('liquidity', 0) / 100000)
        score += liquidity_score * 0.2
        
        # Timing (10%)
        time_score = 1.0  # Would calculate based on time to close
        score += time_score * 0.1
        
        return score
    
    def _make_decision(
        self,
        ev,
        opportunity_score,
        constraints_passed,
        constraint_reasons
    ) -> Tuple[CopyDecisionType, float]:
        """Make final copy decision."""
        if not constraints_passed:
            return CopyDecisionType.SKIP, 0.0
        
        if ev.grade in [ev.grade.EXCELLENT, ev.grade.GOOD] and opportunity_score > 0.7:
            return CopyDecisionType.IMMEDIATE_COPY, opportunity_score
        elif ev.grade == ev.grade.GOOD and opportunity_score > 0.5:
            return CopyDecisionType.STAGED_COPY, opportunity_score * 0.8
        elif ev.grade == ev.grade.MARGINAL:
            return CopyDecisionType.REDUCE_SIZE, opportunity_score * 0.6
        elif ev.adjusted_ev_percent > 0:
            return CopyDecisionType.WAIT_FOR_DIP, opportunity_score * 0.5
        else:
            return CopyDecisionType.SKIP, 0.0
    
    def _calculate_sizing(
        self,
        ev,
        winner_profile,
        portfolio_state,
        decision
    ) -> Dict:
        """Calculate position sizing."""
        bankroll = portfolio_state.get('bankroll', 10000)
        
        # Base Kelly size
        base_size = ev.half_kelly_size
        
        # Adjust based on decision type
        if decision == CopyDecisionType.REDUCE_SIZE:
            base_size *= 0.5
        elif decision == CopyDecisionType.INCREASE_SIZE:
            base_size *= 1.5
        
        # Apply portfolio limits
        max_exposure = bankroll * self.thresholds['max_portfolio_exposure']
        current_exposure = portfolio_state.get('exposure', 0) * bankroll
        available = max_exposure - current_exposure
        
        target = min(base_size, available)
        
        return {
            'target': target,
            'max': min(ev.max_bet_size, available),
            'min': ev.minimum_profitable_size
        }
    
    def _build_execution_plan(
        self,
        winner_bet,
        market_data,
        sizing,
        decision
    ) -> Dict:
        """Build execution strategy."""
        # Determine strategy based on liquidity and urgency
        liquidity = market_data.get('liquidity', 0)
        target_size = sizing['target']
        
        if liquidity > target_size * 10:
            strategy = 'market'  # Can execute immediately
        elif liquidity > target_size * 3:
            strategy = 'limit'  # Use limit orders
        else:
            strategy = 'twap'  # Time-weighted average price
        
        return {
            'strategy': strategy,
            'target_price': market_data.get('current_price', winner_bet.entry_price),
            'slippage': 0.01,  # 1%
            'time_in_force': timedelta(minutes=5)
        }
    
    def _calculate_risk_params(
        self,
        winner_bet,
        ev,
        sizing
    ) -> Dict:
        """Calculate risk management parameters."""
        entry = winner_bet.entry_price
        
        # Stop loss: 50% of expected move against us
        if winner_bet.direction == 'YES':
            stop = entry * 0.95  # 5% stop
            target = entry * 1.1  # 10% target
        else:
            stop = entry * 1.05
            target = entry * 0.9
        
        return {
            'stop_loss': stop,
            'take_profit': target,
            'max_hold': winner_bet.market_close_time - datetime.now()
        }
    
    def _find_correlated_positions(self, winner_bet, portfolio_state) -> List[str]:
        """Find existing positions correlated with this bet."""
        # Simplified - would check market correlations
        return []
    
    def _generate_primary_reason(self, ev, decision, winner_profile) -> str:
        """Generate primary reason for decision."""
        if decision == CopyDecisionType.SKIP:
            return "EV or constraints not met"
        elif decision == CopyDecisionType.IMMEDIATE_COPY:
            return f"High EV ({ev.adjusted_ev_percent:.1f}%) + Reliable winner ({winner_profile.true_win_rate:.0%} WR)"
        elif decision == CopyDecisionType.STAGED_COPY:
            return "Good opportunity - scaling in"
        else:
            return "Marginal opportunity with adjusted sizing"
    
    def _generate_supporting_factors(self, ev, winner_profile, market_data) -> List[str]:
        """Generate list of supporting factors."""
        factors = []
        
        if ev.adjusted_ev_percent > 3:
            factors.append(f"Strong EV: {ev.adjusted_ev_percent:.1f}%")
        
        if winner_profile.true_win_rate > 0.6:
            factors.append(f"Proven winner: {winner_profile.true_win_rate:.0%} true win rate")
        
        if winner_profile.profit_factor > 1.5:
            factors.append(f"Strong profit factor: {winner_profile.profit_factor:.2f}")
        
        if market_data.get('liquidity', 0) > 50000:
            factors.append("Good liquidity")
        
        return factors
    
    def _generate_risk_factors(self, ev, market_data) -> List[str]:
        """Generate risk factors even for approved trades."""
        risks = []
        
        if ev.probability_profit < 0.7:
            risks.append(f"Only {ev.probability_profit:.0%} probability of profit")
        
        if market_data.get('volatility', 0) > 0.2:
            risks.append("High volatility environment")
        
        return risks
    
    def _generate_scenarios(self, ev, winner_bet) -> List[str]:
        """Generate alternate scenarios."""
        return [
            f"Best case: +${ev.best_case_pnl:.0f}",
            f"Expected: +${ev.expected_pnl:.0f}",
            f"Worst case: -${abs(ev.worst_case_pnl):.0f}"
        ]
    
    def get_decision_stats(self) -> Dict:
        """Get statistics on decisions made."""
        if not self.decisions:
            return {'message': 'No decisions yet'}
        
        recent = self.decisions[-100:]
        
        type_counts = {}
        for d in recent:
            type_counts[d.decision.value] = type_counts.get(d.decision.value, 0) + 1
        
        return {
            'total_decisions': len(self.decisions),
            'recent_decisions': len(recent),
            'type_distribution': type_counts,
            'avg_confidence': np.mean([d.confidence for d in recent]),
            'copy_rate': type_counts.get('immediate_copy', 0) / len(recent) if recent else 0
        }
