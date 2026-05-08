"""
Expected Value (EV) Calculator for Copy Trading

Calculates if copying a specific bet is +EV based on:
1. Winner's historical performance
2. Market conditions
3. Timing
4. Our replication quality (slippage, fill rate)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class EVGrade(Enum):
    """EV quality grades."""
    EXCELLENT = "excellent"    # > 5% EV
    GOOD = "good"              # 3-5% EV
    MARGINAL = "marginal"      # 1-3% EV
    NEGATIVE = "negative"      # < 1% EV
    AVOID = "avoid"            # Negative EV


@dataclass
class CopyEV:
    """Expected Value calculation for copying a bet."""
    # Core EV
    raw_ev_percent: float
    adjusted_ev_percent: float
    grade: EVGrade
    
    # Components
    winner_edge: float
    market_efficiency_penalty: float
    slippage_estimate: float
    timing_penalty: float
    
    # Confidence
    confidence_interval: Tuple[float, float]  # 95% CI
    probability_profit: float  # P(EV > 0)
    
    # Kelly Criterion
    kelly_fraction: float
    half_kelly_size: float
    quarter_kelly_size: float
    
    # Scenario analysis
    best_case_pnl: float
    expected_pnl: float
    worst_case_pnl: float
    
    # Recommendation
    max_bet_size: float
    recommended_size: float
    minimum_profitable_size: float


class EVCalculator:
    """
    Calculates Expected Value of copying a winner's bet.
    
    Formula:
    EV = (Winner's Win Rate × Potential Win) - 
         (Loser's Rate × Potential Loss) - 
         Slippage - Opportunity Cost
    """
    
    def __init__(self, subgraph_client=None):
        """Initialize EV calculator."""
        self.subgraph = subgraph_client
        self.historical_slippage = 0.001  # 0.1% average
        self.opportunity_cost_annual = 0.05  # 5% risk-free
        
    def calculate_ev(
        self,
        winner_profile,
        market_probability: float,
        our_entry_price: float,
        bet_size: float,
        time_to_close: timedelta,
        market_liquidity: float,
        market_volatility: float
    ) -> CopyEV:
        """
        Calculate EV of copying a specific bet.
        
        Args:
            winner_profile: TraderPerformance of the winner
            market_probability: Current market-implied probability
            our_entry_price: Price we'll pay (may differ from winner's)
            bet_size: Size of our intended bet
            time_to_close: Time until market resolution
            market_liquidity: Available liquidity
            market_volatility: Current volatility
            
        Returns:
            CopyEV with detailed analysis
        """
        # Winner's historical edge
        winner_win_rate = winner_profile.true_win_rate
        winner_edge = winner_win_rate - 0.5
        
        # Market-implied probability (if we disagree, that's our edge)
        # If winner bets YES at 0.45, market is 0.45, but winner wins 60%
        # Then edge = 60% - 45% = 15%
        
        # Calculate potential outcomes
        if winner_profile.best_category:
            # Winner performs better in some categories
            category_boost = 1.1  # 10% boost in best category
        else:
            category_boost = 1.0
        
        # Adjusted win rate
        adjusted_win_rate = min(0.95, winner_win_rate * category_boost)
        
        # Potential profit/loss
        if winner_profile.monthly_returns:
            avg_win = np.mean([r for r in winner_profile.monthly_returns if r > 0]) if any(r > 0 for r in winner_profile.monthly_returns) else bet_size * 0.1
            avg_loss = abs(np.mean([r for r in winner_profile.monthly_returns if r < 0])) if any(r < 0 for r in winner_profile.monthly_returns) else bet_size * 0.05
        else:
            avg_win = bet_size * 0.08  # Assume 8% avg win
            avg_loss = bet_size * 0.04  # Assume 4% avg loss
        
        # Raw EV calculation
        win_prob = adjusted_win_rate
        loss_prob = 1 - win_prob
        
        raw_ev = (win_prob * avg_win) - (loss_prob * avg_loss)
        raw_ev_percent = (raw_ev / bet_size) * 100
        
        # Adjustments
        # 1. Slippage (we pay worse price than winner)
        slippage = self._estimate_slippage(market_liquidity, bet_size, market_volatility)
        
        # 2. Market efficiency penalty (winner's edge decays)
        time_hours = time_to_close.total_seconds() / 3600
        efficiency_penalty = 0.001 * max(0, 24 - time_hours)  # Higher penalty for longer holds
        
        # 3. Timing penalty (late copies are worse)
        timing_penalty = self._calculate_timing_penalty(time_to_close)
        
        # 4. Replication quality (we're not as good as the winner)
        replication_factor = 0.85  # We capture 85% of winner's edge
        
        # Adjusted EV
        adjusted_ev = raw_ev * replication_factor - (slippage + efficiency_penalty + timing_penalty) * bet_size
        adjusted_ev_percent = (adjusted_ev / bet_size) * 100
        
        # Confidence interval (Monte Carlo-ish)
        std_dev = np.std(winner_profile.monthly_returns) if winner_profile.monthly_returns else bet_size * 0.03
        n_samples = winner_profile.total_bets
        
        if n_samples >= 30:
            margin_error = 1.96 * (std_dev / np.sqrt(n_samples))
            ci_lower = adjusted_ev - margin_error
            ci_upper = adjusted_ev + margin_error
        else:
            ci_lower = adjusted_ev * 0.5  # Wider CI for small samples
            ci_upper = adjusted_ev * 1.5
        
        confidence_interval = (ci_lower, ci_upper)
        probability_profit = self._calculate_p_profit(adjusted_ev, std_dev)
        
        # Kelly Criterion
        # f = (bp - q) / b
        # where b = avg win / avg loss, p = win rate, q = 1-p
        b = avg_win / avg_loss if avg_loss > 0 else 1
        p = win_prob
        q = 1 - p
        
        if b > 0:
            kelly = (b * p - q) / b
        else:
            kelly = 0
        
        kelly = max(0, min(1, kelly))
        
        # Position sizing
        bankroll = 10000  # Assuming $10k
        half_kelly = bankroll * kelly * 0.5
        quarter_kelly = bankroll * kelly * 0.25
        
        # Grade
        if adjusted_ev_percent > 5:
            grade = EVGrade.EXCELLENT
        elif adjusted_ev_percent > 3:
            grade = EVGrade.GOOD
        elif adjusted_ev_percent > 1:
            grade = EVGrade.MARGINAL
        elif adjusted_ev_percent > 0:
            grade = EVGrade.NEGATIVE
        else:
            grade = EVGrade.AVOID
        
        # Scenario analysis
        best_case = avg_win * 1.5  # Outlier win
        expected = adjusted_ev
        worst_case = -avg_loss * 1.5  # Outlier loss
        
        return CopyEV(
            raw_ev_percent=raw_ev_percent,
            adjusted_ev_percent=adjusted_ev_percent,
            grade=grade,
            winner_edge=winner_edge,
            market_efficiency_penalty=efficiency_penalty * 100,
            slippage_estimate=slippage * 100,
            timing_penalty=timing_penalty * 100,
            confidence_interval=confidence_interval,
            probability_profit=probability_profit,
            kelly_fraction=kelly,
            half_kelly_size=half_kelly,
            quarter_kelly_size=quarter_kelly,
            best_case_pnl=best_case,
            expected_pnl=expected,
            worst_case_pnl=worst_case,
            max_bet_size=half_kelly,
            recommended_size=quarter_kelly if grade in [EVGrade.MARGINAL, EVGrade.NEGATIVE] else half_kelly,
            minimum_profitable_size=bankroll * 0.01  # Min 1% of bankroll
        )
    
    def _estimate_slippage(
        self,
        liquidity: float,
        bet_size: float,
        volatility: float
    ) -> float:
        """Estimate slippage as percentage."""
        if liquidity <= 0:
            return 0.05  # 5% if no liquidity data
        
        # Slippage increases with bet size relative to liquidity
        size_ratio = bet_size / liquidity
        base_slippage = min(0.02, size_ratio * 0.1)  # Max 2%
        
        # Volatility increases slippage
        vol_adjustment = 1 + (volatility * 2)
        
        return base_slippage * vol_adjustment
    
    def _calculate_timing_penalty(self, time_to_close: timedelta) -> float:
        """Penalty for copying late."""
        hours = time_to_close.total_seconds() / 3600
        
        if hours < 1:
            return 0.02  # 2% penalty for very late
        elif hours < 6:
            return 0.01
        elif hours < 24:
            return 0.005
        else:
            return 0.0  # No penalty for early copies
    
    def _calculate_p_profit(self, ev: float, std_dev: float) -> float:
        """Calculate probability that trade is profitable."""
        if std_dev <= 0:
            return 1.0 if ev > 0 else 0.0
        
        # P(X > 0) where X ~ N(ev, std_dev^2)
        z_score = ev / std_dev
        from scipy import stats
        return 1 - stats.norm.cdf(-z_score)
    
    def batch_calculate_ev(
        self,
        opportunities: List[Dict]
    ) -> List[Tuple[Dict, CopyEV]]:
        """Calculate EV for multiple opportunities."""
        results = []
        for opp in opportunities:
            ev = self.calculate_ev(**opp)
            results.append((opp, ev))
        
        # Sort by EV
        results.sort(key=lambda x: x[1].adjusted_ev_percent, reverse=True)
        return results
    
    def get_ev_report(self, ev_results: List[CopyEV]) -> str:
        """Generate EV report."""
        lines = []
        lines.append("=" * 70)
        lines.append("EXPECTED VALUE ANALYSIS")
        lines.append("=" * 70)
        
        # Summary stats
        evs = [ev.adjusted_ev_percent for ev in ev_results]
        lines.append(f"\nOpportunities Analyzed: {len(ev_results)}")
        lines.append(f"Average EV: {np.mean(evs):.2f}%")
        lines.append(f"Best EV: {max(evs):.2f}%")
        lines.append(f"Worst EV: {min(evs):.2f}%")
        
        # Grade distribution
        grades = {}
        for ev in ev_results:
            grades[ev.grade.value] = grades.get(ev.grade.value, 0) + 1
        
        lines.append(f"\nGrade Distribution:")
        for grade, count in sorted(grades.items()):
            lines.append(f"   {grade}: {count}")
        
        # Top opportunities
        lines.append(f"\nTop 5 Opportunities:")
        for i, ev in enumerate(sorted(ev_results, key=lambda x: x.adjusted_ev_percent, reverse=True)[:5], 1):
            lines.append(f"   {i}. EV: {ev.adjusted_ev_percent:+.2f}% | "
                       f"Grade: {ev.grade.value} | "
                       f"Kelly: {ev.kelly_fraction:.2f}")
        
        return "\n".join(lines)
