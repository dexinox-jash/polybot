"""
Advanced Expected Value Calculator

Comprehensive EV analysis including:
- Base case EV
- Scenario analysis (best, expected, worst, stress)
- Monte Carlo simulation
- Sensitivity analysis
- Kelly Criterion with fractional sizing
- Risk of ruin calculations
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class ScenarioType(Enum):
    WORST_CASE = "worst_case"      # 95th percentile loss
    PESSIMISTIC = "pessimistic"    # 75th percentile loss
    BASE = "base"                  # Expected value
    OPTIMISTIC = "optimistic"      # 75th percentile win
    BEST_CASE = "best_case"        # 95th percentile win
    STRESS = "stress"              # Black swan event


@dataclass
class ScenarioAnalysis:
    """EV analysis for a specific scenario."""
    scenario_type: ScenarioType
    probability: float  # Probability of this scenario
    win_probability: float
    avg_win: float
    avg_loss: float
    expected_value: float
    expected_value_percent: float
    risk_reward: float
    sharpe_ratio: float
    
    # Position sizing
    kelly_fraction: float
    recommended_size: float
    max_size: float


@dataclass
class AdvancedEV:
    """Comprehensive EV analysis."""
    # Base EV
    base_ev: float
    base_ev_percent: float
    
    # Scenario analysis
    scenarios: Dict[ScenarioType, ScenarioAnalysis]
    
    # Monte Carlo results
    monte_carlo_ev: float
    monte_carlo_std: float
    monte_carlo_var_95: float
    monte_carlo_cvar_95: float
    probability_of_profit: float
    probability_of_loss: float
    probability_of_breakeven: float
    
    # Sensitivity analysis
    sensitivity_to_win_rate: float
    sensitivity_to_edge: float
    sensitivity_to_slippage: float
    break_even_win_rate: float
    break_even_edge: float
    
    # Risk metrics
    risk_of_ruin: float
    expected_max_drawdown: float
    ulcer_index: float
    
    # Kelly sizing recommendations
    full_kelly: float
    half_kelly: float
    quarter_kelly: float
    eighth_kelly: float
    optimal_kelly: float  # Adjusted for uncertainty
    
    # Confidence intervals
    ev_confidence_95: Tuple[float, float]
    ev_confidence_80: Tuple[float, float]
    
    # Qualitative
    ev_grade: str  # A+, A, B+, B, C, D, F
    recommendation: str
    confidence: float


class AdvancedEVCalculator:
    """
    Advanced EV calculator with full scenario and risk analysis.
    """
    
    def __init__(self, subgraph_client=None):
        self.subgraph = subgraph_client
        self.simulation_iterations = 10000
        
    def calculate_advanced_ev(
        self,
        winner_profile,
        market_probability: float,
        our_entry_price: float,
        market_liquidity: float,
        time_to_close: timedelta,
        market_volatility: float,
        correlation_with_portfolio: float = 0.0,
        bankroll: float = 10000
    ) -> AdvancedEV:
        """
        Calculate comprehensive EV with all scenarios.
        """
        # Base parameters
        winner_wr = winner_profile.overall_win_rate
        edge = winner_wr - market_probability
        
        # Average win/loss from winner's history
        avg_win = winner_profile.avg_win if winner_profile.avg_win > 0 else bankroll * 0.05
        avg_loss = abs(winner_profile.avg_loss) if winner_profile.avg_loss < 0 else bankroll * 0.02
        
        # Adjust for our entry (we may pay worse price)
        slippage = self._estimate_slippage(market_liquidity, bankroll * 0.02, market_volatility)
        adjusted_entry = our_entry_price * (1 + slippage)
        
        # Adjust win rate for our entry
        entry_adjustment = (our_entry_price - adjusted_entry) / our_entry_price
        adjusted_wr = winner_wr + entry_adjustment
        adjusted_wr = max(0.01, min(0.99, adjusted_wr))
        
        # Base EV calculation
        win_prob = adjusted_wr
        loss_prob = 1 - win_prob
        
        base_ev = (win_prob * avg_win) - (loss_prob * avg_loss)
        base_ev_percent = (base_ev / (bankroll * 0.02)) * 100
        
        # Scenario analysis
        scenarios = self._calculate_scenarios(
            winner_profile, adjusted_wr, avg_win, avg_loss, 
            bankroll, market_volatility
        )
        
        # Monte Carlo simulation
        mc_results = self._monte_carlo_simulation(
            adjusted_wr, avg_win, avg_loss, bankroll * 0.02
        )
        
        # Sensitivity analysis
        sensitivities = self._sensitivity_analysis(
            winner_profile, market_probability, our_entry_price, avg_win, avg_loss, bankroll
        )
        
        # Kelly calculations
        kelly_sizes = self._calculate_kelly_sizes(
            adjusted_wr, avg_win, avg_loss, bankroll
        )
        
        # Risk of ruin
        risk_of_ruin = self._calculate_risk_of_ruin(
            adjusted_wr, avg_win, avg_loss, kelly_sizes['half_kelly'] / bankroll
        )
        
        # Confidence intervals
        ci_95 = self._calculate_confidence_interval(
            base_ev, winner_profile, confidence=0.95
        )
        ci_80 = self._calculate_confidence_interval(
            base_ev, winner_profile, confidence=0.80
        )
        
        # Grade
        ev_grade = self._grade_ev(base_ev_percent, risk_of_ruin, winner_profile.sharpe_ratio)
        
        # Recommendation
        recommendation = self._generate_recommendation(
            base_ev_percent, ev_grade, risk_of_ruin, scenarios
        )
        
        return AdvancedEV(
            base_ev=base_ev,
            base_ev_percent=base_ev_percent,
            scenarios=scenarios,
            monte_carlo_ev=mc_results['ev'],
            monte_carlo_std=mc_results['std'],
            monte_carlo_var_95=mc_results['var_95'],
            monte_carlo_cvar_95=mc_results['cvar_95'],
            probability_of_profit=mc_results['prob_profit'],
            probability_of_loss=mc_results['prob_loss'],
            probability_of_breakeven=mc_results['prob_breakeven'],
            sensitivity_to_win_rate=sensitivities['win_rate'],
            sensitivity_to_edge=sensitivities['edge'],
            sensitivity_to_slippage=sensitivities['slippage'],
            break_even_win_rate=sensitivities['break_even_wr'],
            break_even_edge=sensitivities['break_even_edge'],
            risk_of_ruin=risk_of_ruin,
            expected_max_drawdown=mc_results['expected_dd'],
            ulcer_index=mc_results['ulcer_index'],
            full_kelly=kelly_sizes['full_kelly'],
            half_kelly=kelly_sizes['half_kelly'],
            quarter_kelly=kelly_sizes['quarter_kelly'],
            eighth_kelly=kelly_sizes['eighth_kelly'],
            optimal_kelly=kelly_sizes['optimal_kelly'],
            ev_confidence_95=ci_95,
            ev_confidence_80=ci_80,
            ev_grade=ev_grade,
            recommendation=recommendation,
            confidence=self._calculate_overall_confidence(winner_profile, base_ev_percent)
        )
    
    def _calculate_scenarios(
        self,
        winner_profile,
        base_wr: float,
        base_win: float,
        base_loss: float,
        bankroll: float,
        volatility: float
    ) -> Dict[ScenarioType, ScenarioAnalysis]:
        """Calculate EV for multiple scenarios."""
        scenarios = {}
        
        # Worst case: Winner underperforms significantly
        worst_wr = max(0.51, base_wr - 2 * (1 - base_wr) * volatility)
        scenarios[ScenarioType.WORST_CASE] = self._create_scenario(
            ScenarioType.WORST_CASE, 0.05, worst_wr, base_win * 0.5, base_loss * 1.5, bankroll
        )
        
        # Pessimistic
        pessimistic_wr = base_wr - (base_wr - 0.5) * 0.3
        scenarios[ScenarioType.PESSIMISTIC] = self._create_scenario(
            ScenarioType.PESSIMISTIC, 0.20, pessimistic_wr, base_win * 0.8, base_loss * 1.2, bankroll
        )
        
        # Base case
        scenarios[ScenarioType.BASE] = self._create_scenario(
            ScenarioType.BASE, 0.50, base_wr, base_win, base_loss, bankroll
        )
        
        # Optimistic
        optimistic_wr = min(0.95, base_wr + (base_wr - 0.5) * 0.3)
        scenarios[ScenarioType.OPTIMISTIC] = self._create_scenario(
            ScenarioType.OPTIMISTIC, 0.20, optimistic_wr, base_win * 1.2, base_loss * 0.8, bankroll
        )
        
        # Best case
        best_wr = min(0.99, base_wr + 2 * (base_wr - 0.5) * volatility)
        scenarios[ScenarioType.BEST_CASE] = self._create_scenario(
            ScenarioType.BEST_CASE, 0.05, best_wr, base_win * 1.5, base_loss * 0.5, bankroll
        )
        
        return scenarios
    
    def _create_scenario(
        self,
        scenario_type: ScenarioType,
        probability: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        bankroll: float
    ) -> ScenarioAnalysis:
        """Create a scenario analysis."""
        win_prob = win_rate
        loss_prob = 1 - win_prob
        
        ev = (win_prob * avg_win) - (loss_prob * avg_loss)
        ev_percent = (ev / (bankroll * 0.02)) * 100
        
        risk_reward = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Sharpe for this scenario
        variance = win_prob * (avg_win - ev)**2 + loss_prob * (-avg_loss - ev)**2
        std = np.sqrt(variance) if variance > 0 else 0.01
        sharpe = ev / std if std > 0 else 0
        
        # Kelly for this scenario
        b = risk_reward
        p = win_prob
        q = 1 - p
        kelly = (b * p - q) / b if b > 0 else 0
        kelly = max(0, kelly)
        
        return ScenarioAnalysis(
            scenario_type=scenario_type,
            probability=probability,
            win_probability=win_prob,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expected_value=ev,
            expected_value_percent=ev_percent,
            risk_reward=risk_reward,
            sharpe_ratio=sharpe,
            kelly_fraction=kelly,
            recommended_size=bankroll * kelly * 0.5,
            max_size=bankroll * kelly
        )
    
    def _monte_carlo_simulation(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        position_size: float,
        iterations: int = 10000
    ) -> Dict:
        """Run Monte Carlo simulation."""
        results = []
        
        for _ in range(iterations):
            # Simulate one trade with some noise
            wr_noise = np.random.normal(0, 0.05)  # 5% std dev in win rate
            actual_wr = max(0, min(1, win_rate + wr_noise))
            
            if np.random.random() < actual_wr:
                # Win with noise
                win_amount = avg_win * np.random.normal(1, 0.2)
                results.append(win_amount)
            else:
                # Loss with noise
                loss_amount = -avg_loss * np.random.normal(1, 0.2)
                results.append(loss_amount)
        
        results = np.array(results)
        
        return {
            'ev': np.mean(results),
            'std': np.std(results),
            'var_95': np.percentile(results, 5),
            'cvar_95': np.mean(results[results <= np.percentile(results, 5)]),
            'prob_profit': np.mean(results > 0),
            'prob_loss': np.mean(results < 0),
            'prob_breakeven': np.mean(abs(results) < 1),
            'expected_dd': abs(np.percentile(results, 10)),
            'ulcer_index': np.sqrt(np.mean(np.minimum(0, np.cumsum(results))**2))
        }
    
    def _sensitivity_analysis(
        self,
        winner_profile,
        market_prob: float,
        entry_price: float,
        avg_win: float,
        avg_loss: float,
        bankroll: float
    ) -> Dict:
        """Analyze sensitivity to key parameters."""
        base_wr = winner_profile.overall_win_rate
        base_ev = (base_wr * avg_win) - ((1 - base_wr) * avg_loss)
        
        # Sensitivity to win rate (1% change)
        wr_plus = base_wr + 0.01
        ev_wr_plus = (wr_plus * avg_win) - ((1 - wr_plus) * avg_loss)
        sensitivity_wr = (ev_wr_plus - base_ev) / base_ev if base_ev != 0 else 0
        
        # Sensitivity to edge (1% change in market prob)
        edge_plus = (base_wr - (market_prob + 0.01))
        ev_edge_plus = base_ev - (0.01 * avg_loss)  # Approximation
        sensitivity_edge = (ev_edge_plus - base_ev) / base_ev if base_ev != 0 else 0
        
        # Sensitivity to slippage
        ev_slippage = base_ev * 0.99  # 1% slippage
        sensitivity_slippage = (ev_slippage - base_ev) / base_ev if base_ev != 0 else 0
        
        # Break-even calculations
        break_even_wr = avg_loss / (avg_win + avg_loss) if (avg_win + avg_loss) > 0 else 0.5
        break_even_edge = break_even_wr - market_prob
        
        return {
            'win_rate': sensitivity_wr,
            'edge': sensitivity_edge,
            'slippage': sensitivity_slippage,
            'break_even_wr': break_even_wr,
            'break_even_edge': break_even_edge
        }
    
    def _calculate_kelly_sizes(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        bankroll: float
    ) -> Dict:
        """Calculate various Kelly position sizes."""
        b = avg_win / avg_loss if avg_loss > 0 else 1
        p = win_rate
        q = 1 - p
        
        if b > 0:
            full_kelly = (b * p - q) / b
        else:
            full_kelly = 0
        
        full_kelly = max(0, full_kelly)
        
        # Adjust for uncertainty (more uncertainty = smaller size)
        uncertainty_adjustment = 1 - (0.1 * (1 - win_rate))  # Higher win rate = more confident
        optimal_kelly = full_kelly * uncertainty_adjustment
        
        return {
            'full_kelly': bankroll * full_kelly,
            'half_kelly': bankroll * full_kelly * 0.5,
            'quarter_kelly': bankroll * full_kelly * 0.25,
            'eighth_kelly': bankroll * full_kelly * 0.125,
            'optimal_kelly': bankroll * optimal_kelly * 0.5  # Conservative
        }
    
    def _calculate_risk_of_ruin(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        kelly_fraction: float
    ) -> float:
        """Calculate probability of ruin."""
        # Simplified formula: RoR ≈ (1 - win_rate) ^ (1 / kelly_fraction)
        if kelly_fraction <= 0:
            return 1.0
        
        # More accurate: Use gambler's ruin formula
        edge = win_rate * avg_win - (1 - win_rate) * avg_loss
        if edge <= 0:
            return 1.0
        
        # Rough approximation
        ror = np.exp(-2 * edge * (1 / kelly_fraction))
        return min(1.0, max(0.0, ror))
    
    def _calculate_confidence_interval(
        self,
        base_ev: float,
        winner_profile,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Calculate confidence interval for EV."""
        z_score = 1.96 if confidence == 0.95 else 1.28  # 80% CI
        
        # Standard error based on sample size
        if winner_profile.total_bets > 0:
            std_error = abs(base_ev) / np.sqrt(winner_profile.total_bets)
        else:
            std_error = abs(base_ev) * 0.5
        
        margin = z_score * std_error
        return (base_ev - margin, base_ev + margin)
    
    def _estimate_slippage(
        self,
        liquidity: float,
        bet_size: float,
        volatility: float
    ) -> float:
        """Estimate slippage."""
        if liquidity <= 0:
            return 0.02
        
        size_ratio = bet_size / liquidity
        base_slippage = min(0.02, size_ratio * 0.1)
        vol_adjustment = 1 + volatility
        
        return base_slippage * vol_adjustment
    
    def _grade_ev(
        self,
        ev_percent: float,
        risk_of_ruin: float,
        sharpe: float
    ) -> str:
        """Grade the EV opportunity."""
        if ev_percent > 10 and risk_of_ruin < 0.01 and sharpe > 2:
            return "A+"
        elif ev_percent > 7 and risk_of_ruin < 0.02 and sharpe > 1.5:
            return "A"
        elif ev_percent > 5 and risk_of_ruin < 0.05:
            return "B+"
        elif ev_percent > 3 and risk_of_ruin < 0.1:
            return "B"
        elif ev_percent > 1 and risk_of_ruin < 0.2:
            return "C"
        elif ev_percent > 0:
            return "D"
        else:
            return "F"
    
    def _generate_recommendation(
        self,
        ev_percent: float,
        grade: str,
        risk_of_ruin: float,
        scenarios: Dict[ScenarioType, ScenarioAnalysis]
    ) -> str:
        """Generate recommendation."""
        if grade in ["A+", "A"]:
            return "STRONG BUY: Exceptional opportunity with low risk"
        elif grade == "B+":
            return "BUY: Good opportunity with acceptable risk"
        elif grade == "B":
            return "MODERATE BUY: Decent edge, standard position size"
        elif grade == "C":
            return "SPECULATIVE: Marginal edge, reduce size"
        elif grade == "D":
            return "WEAK: Very small edge, consider skipping"
        else:
            return "AVOID: Negative expected value"
    
    def _calculate_overall_confidence(
        self,
        winner_profile,
        ev_percent: float
    ) -> float:
        """Calculate overall confidence in the analysis."""
        # Based on sample size
        sample_confidence = min(1.0, winner_profile.total_bets / 200)
        
        # Based on consistency
        consistency_confidence = 1 - min(1.0, winner_profile.daily_volatility / 0.1)
        
        # Based on EV magnitude
        ev_confidence = min(1.0, abs(ev_percent) / 10)
        
        return (sample_confidence * 0.4 + consistency_confidence * 0.3 + ev_confidence * 0.3)
    
    def generate_ev_report(self, ev: AdvancedEV) -> str:
        """Generate detailed EV report."""
        lines = []
        lines.append("=" * 80)
        lines.append("ADVANCED EXPECTED VALUE ANALYSIS")
        lines.append("=" * 80)
        
        lines.append(f"\n[BASE CASE]")
        lines.append(f"  Expected Value: {ev.base_ev:+.2f} ({ev.base_ev_percent:+.2f}%)")
        lines.append(f"  Grade: {ev.ev_grade}")
        lines.append(f"  Recommendation: {ev.recommendation}")
        lines.append(f"  Confidence: {ev.confidence:.0%}")
        
        lines.append(f"\n[SCENARIO ANALYSIS]")
        for scenario_type, scenario in ev.scenarios.items():
            lines.append(f"  {scenario_type.value:15s}: {scenario.expected_value_percent:+6.2f}% "
                       f"(P={scenario.probability:.0%}, WR={scenario.win_probability:.1%})")
        
        lines.append(f"\n[MONTE CARLO SIMULATION]")
        lines.append(f"  Expected Value: ${ev.monte_carlo_ev:+.2f}")
        lines.append(f"  Standard Deviation: ${ev.monte_carlo_std:.2f}")
        lines.append(f"  VaR (95%): ${ev.monte_carlo_var_95:.2f}")
        lines.append(f"  Probability of Profit: {ev.probability_of_profit:.1%}")
        
        lines.append(f"\n[KELLY SIZING RECOMMENDATIONS]")
        lines.append(f"  Full Kelly:    ${ev.full_kelly:.0f}")
        lines.append(f"  Half Kelly:    ${ev.half_kelly:.0f} (RECOMMENDED)")
        lines.append(f"  Quarter Kelly: ${ev.quarter_kelly:.0f}")
        lines.append(f"  Optimal:       ${ev.optimal_kelly:.0f}")
        
        lines.append(f"\n[RISK METRICS]")
        lines.append(f"  Risk of Ruin: {ev.risk_of_ruin:.2%}")
        lines.append(f"  Expected Max Drawdown: ${ev.expected_max_drawdown:.0f}")
        lines.append(f"  Ulcer Index: {ev.ulcer_index:.2f}")
        
        lines.append(f"\n[SENSITIVITY ANALYSIS]")
        lines.append(f"  Break-even Win Rate: {ev.break_even_win_rate:.1%}")
        lines.append(f"  Sensitivity to Win Rate: {ev.sensitivity_to_win_rate:.2f}")
        lines.append(f"  Sensitivity to Slippage: {ev.sensitivity_to_slippage:.2f}")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
