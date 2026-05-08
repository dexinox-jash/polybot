"""
Research Engine - Comprehensive Bet Analysis

Produces institutional-grade research reports combining:
- Deep winner intelligence
- Advanced EV calculations
- Multi-factor scoring
- Market microstructure
- Risk analysis
- Execution recommendations
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class ResearchReport:
    """Comprehensive research report for a copy opportunity."""
    
    # Report metadata
    report_id: str
    generated_at: datetime
    
    # Subject
    winner_address: str
    winner_name: Optional[str]
    market_id: str
    market_question: str
    
    # Executive Summary
    recommendation: str
    confidence_level: str
    grade: str
    expected_return: float
    risk_rating: str
    
    # Deep Analysis Sections
    winner_intelligence: Dict
    advanced_ev: Dict
    multi_factor_score: Dict
    scenario_analysis: Dict
    risk_assessment: Dict
    
    # Execution Plan
    entry_strategy: str
    position_size: float
    stop_loss: float
    take_profit: float
    time_exit: datetime
    
    # Comparative Analysis
    vs_historical_average: str
    vs_market_consensus: str
    vs_portfolio: str
    
    # Risk Factors
    key_risks: List[str]
    mitigation_strategies: List[str]
    
    # Appendices
    raw_data: Dict
    methodology: str
    disclaimers: List[str]
    
    # Version (with default, must be last)
    version: str = "1.0"


class ResearchEngine:
    """
    Produces comprehensive research reports for copy opportunities.
    
    This is the 'master analyst' that combines all analysis modules
    into a single, actionable research report.
    """
    
    def __init__(self, winner_intel, ev_calc, factor_model):
        """
        Initialize research engine.
        
        Args:
            winner_intel: WinnerIntelligence instance
            ev_calc: AdvancedEVCalculator instance
            factor_model: MultiFactorModel instance
        """
        self.winner_intel = winner_intel
        self.ev_calc = ev_calc
        self.factor_model = factor_model
        
    def generate_research_report(
        self,
        winner_address: str,
        market_data: Dict,
        timing_data: Dict,
        portfolio_context: Dict
    ) -> ResearchReport:
        """
        Generate comprehensive research report.
        
        This is the main function that performs ALL analysis
        and produces the final research report.
        """
        print(f"\n[RESEARCH] Generating comprehensive report...")
        print(f"  Subject: {winner_address[:16]}... on {market_data.get('question', 'Unknown')[:40]}")
        
        # Step 1: Deep Winner Intelligence
        print(f"  → Analyzing winner profile...")
        winner_profile = self.winner_intel.profiles.get(winner_address)
        if not winner_profile:
            # Analyze if not cached
            # In real implementation, fetch trade history and analyze
            return None
        
        # Step 2: Advanced EV Calculation
        print(f"  → Calculating advanced EV with scenarios...")
        advanced_ev = self.ev_calc.calculate_advanced_ev(
            winner_profile=winner_profile,
            market_probability=market_data.get('probability', 0.5),
            our_entry_price=market_data.get('current_price', 0.5),
            market_liquidity=market_data.get('liquidity', 0),
            time_to_close=timing_data.get('time_to_close', timedelta(hours=24)),
            market_volatility=market_data.get('volatility', 0.1),
            bankroll=portfolio_context.get('bankroll', 10000)
        )
        
        # Step 3: Multi-Factor Scoring
        print(f"  → Running multi-factor model...")
        factor_score = self.factor_model.calculate_score(
            winner_profile=winner_profile,
            market_data=market_data,
            timing_data=timing_data,
            portfolio_context=portfolio_context
        )
        
        # Step 4: Synthesize findings
        print(f"  → Synthesizing research findings...")
        report = self._synthesize_report(
            winner_profile, advanced_ev, factor_score,
            winner_address, market_data, timing_data, portfolio_context
        )
        
        print(f"  ✓ Research report complete")
        
        return report
    
    def _synthesize_report(
        self,
        winner_profile,
        advanced_ev,
        factor_score,
        winner_address: str,
        market_data: Dict,
        timing_data: Dict,
        portfolio_context: Dict
    ) -> ResearchReport:
        """Synthesize all analysis into final report."""
        
        # Determine overall recommendation
        if factor_score.composite_score > 0.80 and advanced_ev.base_ev_percent > 5:
            recommendation = "STRONG BUY - High conviction opportunity"
        elif factor_score.composite_score > 0.70 and advanced_ev.base_ev_percent > 3:
            recommendation = "BUY - Quality opportunity"
        elif factor_score.composite_score > 0.60 and advanced_ev.base_ev_percent > 1:
            recommendation = "MODERATE BUY - Acceptable risk/reward"
        elif factor_score.composite_score > 0.50:
            recommendation = "SPECULATIVE - Reduce position size"
        else:
            recommendation = "PASS - Risk/reward unfavorable"
        
        # Risk rating
        if advanced_ev.risk_of_ruin < 0.01 and factor_score.category_scores.get('risk', 0) > 0.7:
            risk_rating = "LOW"
        elif advanced_ev.risk_of_ruin < 0.05 and factor_score.category_scores.get('risk', 0) > 0.5:
            risk_rating = "MODERATE"
        elif advanced_ev.risk_of_ruin < 0.10:
            risk_rating = "ELEVATED"
        else:
            risk_rating = "HIGH"
        
        # Position sizing
        base_size = portfolio_context.get('bankroll', 10000) * 0.02  # 2% base
        size_adjustment = factor_score.position_size_adjustment
        kelly_adjustment = advanced_ev.optimal_kelly / (portfolio_context.get('bankroll', 10000) * 0.02) if advanced_ev.optimal_kelly > 0 else 1.0
        
        position_size = base_size * size_adjustment * min(kelly_adjustment, 1.5)
        
        # Stop loss and take profit
        entry_price = market_data.get('current_price', 0.5)
        if market_data.get('direction') == 'YES':
            stop_loss = entry_price * 0.95
            take_profit = entry_price * 1.10
        else:
            stop_loss = entry_price * 1.05
            take_profit = entry_price * 0.90
        
        # Key risks
        key_risks = []
        if advanced_ev.scenarios[advanced_ev.scenarios.keys()[0]].expected_value_percent < -5:
            key_risks.append("Severe downside in worst-case scenario")
        if factor_score.category_scores.get('timing', 0) < 0.5:
            key_risks.append("Suboptimal entry timing")
        if market_data.get('liquidity', 0) < 50000:
            key_risks.append("Limited market liquidity")
        if winner_profile.vanity_gap > 0.1:
            key_risks.append("Winner may have inflated statistics")
        
        # Mitigation strategies
        mitigations = []
        if advanced_ev.risk_of_ruin > 0.05:
            mitigations.append(f"Reduce position to ${position_size * 0.5:.0f}")
        if factor_score.category_scores.get('timing', 0) < 0.6:
            mitigations.append("Wait 15-30 minutes for better entry")
        if market_data.get('liquidity', 0) < 100000:
            mitigations.append("Use limit orders to minimize slippage")
        
        return ResearchReport(
            report_id=f"research_{int(datetime.now().timestamp())}",
            generated_at=datetime.now(),
            winner_address=winner_address,
            winner_name=winner_profile.ens_name,
            market_id=market_data.get('id', 'unknown'),
            market_question=market_data.get('question', 'Unknown'),
            recommendation=recommendation,
            confidence_level=factor_score.copy_confidence.upper(),
            grade=factor_score.grade,
            expected_return=advanced_ev.base_ev_percent,
            risk_rating=risk_rating,
            winner_intelligence={
                "true_win_rate": winner_profile.overall_win_rate,
                "profit_factor": winner_profile.profit_factor,
                "sharpe_ratio": winner_profile.sharpe_ratio,
                "copy_score": winner_profile.copy_score,
                "best_category": winner_profile.best_category,
                "avg_hold_time": str(winner_profile.avg_hold_time),
                "information_advantage": winner_profile.information_advantage_score
            },
            advanced_ev={
                "base_ev_percent": advanced_ev.base_ev_percent,
                "monte_carlo_ev": advanced_ev.monte_carlo_ev,
                "probability_of_profit": advanced_ev.probability_of_profit,
                "risk_of_ruin": advanced_ev.risk_of_ruin,
                "kelly_fraction": advanced_ev.optimal_kelly / portfolio_context.get('bankroll', 10000),
                "var_95": advanced_ev.monte_carlo_var_95,
                "confidence_95": advanced_ev.ev_confidence_95
            },
            multi_factor_score={
                "composite": factor_score.composite_score,
                "category_scores": {k.value: v for k, v in factor_score.category_scores.items()},
                "strengths": factor_score.strengths,
                "weaknesses": factor_score.weaknesses
            },
            scenario_analysis={
                "best_case": advanced_ev.scenarios.get('best_case', {}).get('expected_value_percent', 0),
                "base_case": advanced_ev.base_ev_percent,
                "worst_case": advanced_ev.scenarios.get('worst_case', {}).get('expected_value_percent', 0)
            },
            risk_assessment={
                "risk_rating": risk_rating,
                "max_drawdown_potential": advanced_ev.expected_max_drawdown,
                "ulcer_index": advanced_ev.ulcer_index,
                "break_even_win_rate": advanced_ev.break_even_win_rate
            },
            entry_strategy="Market order with limit fallback" if market_data.get('liquidity', 0) > 100000 else "Limit order only",
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_exit=datetime.now() + market_data.get('time_to_close', timedelta(hours=24)),
            vs_historical_average="Above average" if advanced_ev.base_ev_percent > 5 else "Average",
            vs_market_consensus="Contrarian" if abs(market_data.get('probability', 0.5) - winner_profile.overall_win_rate) > 0.1 else "Aligned",
            vs_portfolio="Diversifying" if factor_score.category_scores.get('risk', 0) > 0.6 else "Concentrated",
            key_risks=key_risks,
            mitigation_strategies=mitigations,
            raw_data={
                "winner_profile": winner_profile.address,
                "market_data": market_data,
                "timestamp": datetime.now().isoformat()
            },
            methodology="Multi-factor quantitative analysis with Monte Carlo simulation",
            disclaimers=[
                "Past performance does not guarantee future results",
                "All investments carry risk of loss",
                "This analysis is for informational purposes only",
                "Copy trading involves execution risk and slippage"
            ]
        )
    
    def generate_executive_summary(self, report: ResearchReport) -> str:
        """Generate one-page executive summary."""
        lines = []
        lines.append("=" * 80)
        lines.append("EXECUTIVE SUMMARY - COPY TRADING OPPORTUNITY")
        lines.append("=" * 80)
        lines.append(f"\nGenerated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Report ID: {report.report_id}")
        
        lines.append(f"\n{'='*80}")
        lines.append("RECOMMENDATION")
        lines.append(f"{'='*80}")
        lines.append(f"  {report.recommendation}")
        lines.append(f"  Grade: {report.grade} | Confidence: {report.confidence_level}")
        lines.append(f"  Expected Return: {report.expected_return:+.1f}%")
        lines.append(f"  Risk Rating: {report.risk_rating}")
        
        lines.append(f"\n{'='*80}")
        lines.append("OPPORTUNITY")
        lines.append(f"{'='*80}")
        lines.append(f"  Winner: {report.winner_name or report.winner_address[:16]}...")
        lines.append(f"  Market: {report.market_question[:60]}...")
        lines.append(f"  Position Size: ${report.position_size:.0f}")
        lines.append(f"  Stop Loss: ${report.stop_loss:.2f}")
        lines.append(f"  Take Profit: ${report.take_profit:.2f}")
        
        lines.append(f"\n{'='*80}")
        lines.append("KEY METRICS")
        lines.append(f"{'='*80}")
        
        wi = report.winner_intelligence
        lines.append(f"  Winner Win Rate: {wi.get('true_win_rate', 0):.1%}")
        lines.append(f"  Profit Factor: {wi.get('profit_factor', 0):.2f}")
        lines.append(f"  Sharpe Ratio: {wi.get('sharpe_ratio', 0):.2f}")
        
        ev = report.advanced_ev
        lines.append(f"  Probability of Profit: {ev.get('probability_of_profit', 0):.1%}")
        lines.append(f"  Risk of Ruin: {ev.get('risk_of_ruin', 0):.2%}")
        lines.append(f"  VaR (95%): ${ev.get('var_95', 0):.0f}")
        
        lines.append(f"\n{'='*80}")
        lines.append("RISKS & MITIGATION")
        lines.append(f"{'='*80}")
        
        if report.key_risks:
            lines.append("  Key Risks:")
            for risk in report.key_risks[:3]:
                lines.append(f"    - {risk}")
        
        if report.mitigation_strategies:
            lines.append("  Mitigation:")
            for mit in report.mitigation_strategies[:3]:
                lines.append(f"    + {mit}")
        
        lines.append(f"\n{'='*80}")
        lines.append("ACTION REQUIRED")
        lines.append(f"{'='*80}")
        
        if "BUY" in report.recommendation.upper():
            lines.append(f"  1. Execute trade: ${report.position_size:.0f}")
            lines.append(f"  2. Set stop loss at ${report.stop_loss:.2f}")
            lines.append(f"  3. Set take profit at ${report.take_profit:.2f}")
            lines.append(f"  4. Monitor until {report.time_exit.strftime('%Y-%m-%d %H:%M')}")
        else:
            lines.append("  NO ACTION - Opportunity does not meet criteria")
        
        lines.append(f"\n{'='*80}")
        
        return "\n".join(lines)
    
    def export_report_json(self, report: ResearchReport) -> str:
        """Export report as JSON."""
        data = {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "recommendation": report.recommendation,
            "grade": report.grade,
            "confidence": report.confidence_level,
            "expected_return": report.expected_return,
            "risk_rating": report.risk_rating,
            "position_size": report.position_size,
            "winner": {
                "address": report.winner_address,
                "name": report.winner_name
            },
            "market": {
                "id": report.market_id,
                "question": report.market_question
            }
        }
        return json.dumps(data, indent=2)
