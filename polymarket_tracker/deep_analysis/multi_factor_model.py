"""
Multi-Factor Model for Bet Scoring

Combines multiple factors into a composite score:
- Winner quality factors
- Market condition factors
- Timing factors
- Risk factors
- Behavioral factors
"""

import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FactorCategory(Enum):
    WINNER_QUALITY = "winner_quality"
    MARKET_CONDITIONS = "market_conditions"
    TIMING = "timing"
    RISK = "risk"
    BEHAVIORAL = "behavioral"
    FUNDAMENTAL = "fundamental"


@dataclass
class FactorWeights:
    """Weights for different factor categories."""
    winner_quality: float = 0.25
    market_conditions: float = 0.20
    timing: float = 0.15
    risk: float = 0.20
    behavioral: float = 0.10
    fundamental: float = 0.10
    
    def normalize(self):
        """Ensure weights sum to 1."""
        total = sum([
            self.winner_quality, self.market_conditions, self.timing,
            self.risk, self.behavioral, self.fundamental
        ])
        if total > 0:
            self.winner_quality /= total
            self.market_conditions /= total
            self.timing /= total
            self.risk /= total
            self.behavioral /= total
            self.fundamental /= total


@dataclass
class FactorScore:
    """Score for a specific factor."""
    name: str
    category: FactorCategory
    score: float  # 0-1
    weight: float
    confidence: float
    description: str
    raw_value: float
    benchmark: float
    z_score: float


@dataclass
class MultiFactorScore:
    """Complete multi-factor analysis result."""
    # Overall score
    composite_score: float
    grade: str
    confidence: float
    
    # Individual factors
    factors: List[FactorScore]
    
    # Category scores
    category_scores: Dict[FactorCategory, float]
    
    # Analysis
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    threats: List[str]
    
    # Recommendations
    recommended_action: str
    optimal_timing: str
    position_size_adjustment: float
    risk_adjustment: float


class MultiFactorModel:
    """
    Multi-factor scoring model for evaluating copy opportunities.
    
    Analyzes 20+ factors across 6 categories.
    """
    
    def __init__(self, weights: FactorWeights = None):
        self.weights = weights or FactorWeights()
        self.weights.normalize()
        
    def calculate_score(
        self,
        winner_profile,
        market_data: Dict,
        timing_data: Dict,
        portfolio_context: Dict
    ) -> MultiFactorScore:
        """
        Calculate comprehensive multi-factor score.
        """
        factors = []
        
        # === WINNER QUALITY FACTORS (25%) ===
        winner_factors = self._calculate_winner_factors(winner_profile)
        factors.extend(winner_factors)
        
        # === MARKET CONDITION FACTORS (20%) ===
        market_factors = self._calculate_market_factors(market_data)
        factors.extend(market_factors)
        
        # === TIMING FACTORS (15%) ===
        timing_factors = self._calculate_timing_factors(timing_data, winner_profile)
        factors.extend(timing_factors)
        
        # === RISK FACTORS (20%) ===
        risk_factors = self._calculate_risk_factors(market_data, portfolio_context)
        factors.extend(risk_factors)
        
        # === BEHAVIORAL FACTORS (10%) ===
        behavioral_factors = self._calculate_behavioral_factors(winner_profile, timing_data)
        factors.extend(behavioral_factors)
        
        # === FUNDAMENTAL FACTORS (10%) ===
        fundamental_factors = self._calculate_fundamental_factors(market_data)
        factors.extend(fundamental_factors)
        
        # Calculate category scores
        category_scores = {}
        for category in FactorCategory:
            cat_factors = [f for f in factors if f.category == category]
            if cat_factors:
                category_scores[category] = np.mean([f.score * f.weight for f in cat_factors])
            else:
                category_scores[category] = 0.5
        
        # Calculate composite score
        composite = sum([
            category_scores[FactorCategory.WINNER_QUALITY] * self.weights.winner_quality,
            category_scores[FactorCategory.MARKET_CONDITIONS] * self.weights.market_conditions,
            category_scores[FactorCategory.TIMING] * self.weights.timing,
            category_scores[FactorCategory.RISK] * self.weights.risk,
            category_scores[FactorCategory.BEHAVIORAL] * self.weights.behavioral,
            category_scores[FactorCategory.FUNDAMENTAL] * self.weights.fundamental
        ])
        
        # Calculate confidence
        confidences = [f.confidence for f in factors]
        overall_confidence = np.mean(confidences) * (1 - np.std(confidences))
        
        # Generate SWOT
        strengths, weaknesses, opportunities, threats = self._generate_swot(
            factors, category_scores
        )
        
        # Determine grade
        grade = self._determine_grade(composite, category_scores)
        
        # Generate recommendations
        action, timing, size_adj, risk_adj = self._generate_recommendations(
            composite, category_scores, factors
        )
        
        return MultiFactorScore(
            composite_score=composite,
            grade=grade,
            confidence=overall_confidence,
            factors=factors,
            category_scores=category_scores,
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
            recommended_action=action,
            optimal_timing=timing,
            position_size_adjustment=size_adj,
            risk_adjustment=risk_adj
        )
    
    def _calculate_winner_factors(self, winner_profile) -> List[FactorScore]:
        """Calculate winner quality factors."""
        factors = []
        
        # Win Rate Quality
        factors.append(FactorScore(
            name="Historical Win Rate",
            category=FactorCategory.WINNER_QUALITY,
            score=min(1.0, winner_profile.overall_win_rate / 0.65),
            weight=0.30,
            confidence=min(1.0, winner_profile.total_bets / 100),
            description="Winner's historical win rate vs 65% benchmark",
            raw_value=winner_profile.overall_win_rate,
            benchmark=0.65,
            z_score=(winner_profile.overall_win_rate - 0.55) / 0.10
        ))
        
        # Profit Factor
        factors.append(FactorScore(
            name="Profit Factor",
            category=FactorCategory.WINNER_QUALITY,
            score=min(1.0, winner_profile.profit_factor / 2.0),
            weight=0.25,
            confidence=0.9,
            description="Gross profit / gross loss ratio",
            raw_value=winner_profile.profit_factor,
            benchmark=1.5,
            z_score=(winner_profile.profit_factor - 1.3) / 0.5
        ))
        
        # Sharpe Ratio
        sharpe_score = min(1.0, max(0, winner_profile.sharpe_ratio) / 2.0)
        factors.append(FactorScore(
            name="Risk-Adjusted Return (Sharpe)",
            category=FactorCategory.WINNER_QUALITY,
            score=sharpe_score,
            weight=0.25,
            confidence=0.8,
            description="Return per unit of risk",
            raw_value=winner_profile.sharpe_ratio,
            benchmark=1.5,
            z_score=(winner_profile.sharpe_ratio - 1.0) / 0.5
        ))
        
        # Consistency Score
        if winner_profile.monthly_returns:
            consistency = 1 - min(1.0, np.std(winner_profile.monthly_returns) / 
                                 (abs(np.mean(winner_profile.monthly_returns)) + 0.01))
        else:
            consistency = 0.5
        
        factors.append(FactorScore(
            name="Consistency",
            category=FactorCategory.WINNER_QUALITY,
            score=consistency,
            weight=0.20,
            confidence=min(1.0, len(winner_profile.monthly_returns) / 12),
            description="Stability of returns over time",
            raw_value=consistency,
            benchmark=0.7,
            z_score=(consistency - 0.5) / 0.2
        ))
        
        return factors
    
    def _calculate_market_factors(self, market_data: Dict) -> List[FactorScore]:
        """Calculate market condition factors."""
        factors = []
        
        # Liquidity Score
        liquidity = market_data.get('liquidity', 0)
        trade_size = market_data.get('intended_size', 1000)
        liquidity_score = min(1.0, liquidity / (trade_size * 10))
        
        factors.append(FactorScore(
            name="Market Liquidity",
            category=FactorCategory.MARKET_CONDITIONS,
            score=liquidity_score,
            weight=0.30,
            confidence=0.9,
            description="Available liquidity relative to trade size",
            raw_value=liquidity,
            benchmark=trade_size * 10,
            z_score=(liquidity - trade_size * 5) / (trade_size * 3)
        ))
        
        # Spread Efficiency
        spread = market_data.get('spread', 0.01)
        spread_score = max(0, 1 - (spread / 0.05))  # Penalize wide spreads
        
        factors.append(FactorScore(
            name="Bid-Ask Spread",
            category=FactorCategory.MARKET_CONDITIONS,
            score=spread_score,
            weight=0.25,
            confidence=0.95,
            description="Tightness of bid-ask spread",
            raw_value=spread,
            benchmark=0.01,
            z_score=(0.02 - spread) / 0.01
        ))
        
        # Volatility Environment
        volatility = market_data.get('volatility', 0.1)
        # Sweet spot: moderate volatility
        if volatility < 0.05:
            vol_score = volatility / 0.05  # Too low
        elif volatility < 0.15:
            vol_score = 1.0  # Ideal
        else:
            vol_score = max(0, 1 - (volatility - 0.15) / 0.15)  # Too high
        
        factors.append(FactorScore(
            name="Volatility Environment",
            category=FactorCategory.MARKET_CONDITIONS,
            score=vol_score,
            weight=0.25,
            confidence=0.8,
            description="Current market volatility level",
            raw_value=volatility,
            benchmark=0.10,
            z_score=(0.10 - volatility) / 0.05
        ))
        
        # Price Efficiency
        price = market_data.get('current_price', 0.5)
        # Avoid extreme prices (high vig)
        if price < 0.1 or price > 0.9:
            price_score = 0.3
        elif price < 0.2 or price > 0.8:
            price_score = 0.6
        else:
            price_score = 1.0
        
        factors.append(FactorScore(
            name="Price Efficiency",
            category=FactorCategory.MARKET_CONDITIONS,
            score=price_score,
            weight=0.20,
            confidence=0.9,
            description="Avoiding high-vig price extremes",
            raw_value=price,
            benchmark=0.50,
            z_score=1 - abs(price - 0.5) / 0.5
        ))
        
        return factors
    
    def _calculate_timing_factors(self, timing_data: Dict, winner_profile) -> List[FactorScore]:
        """Calculate timing factors."""
        factors = []
        
        # Time to Close
        time_left = timing_data.get('hours_to_close', 24)
        if time_left < 1:
            time_score = 0.2  # Too late
        elif time_left < 6:
            time_score = 0.6
        elif time_left < 24:
            time_score = 0.9
        else:
            time_score = 1.0
        
        factors.append(FactorScore(
            name="Time to Market Close",
            category=FactorCategory.TIMING,
            score=time_score,
            weight=0.40,
            confidence=1.0,
            description="Sufficient time for edge to play out",
            raw_value=time_left,
            benchmark=12,
            z_score=(time_left - 6) / 6
        ))
        
        # Winner's Preferred Time
        current_hour = datetime.now().hour
        winner_pref = winner_profile.preferred_hours if hasattr(winner_profile, 'preferred_hours') else []
        if winner_pref and current_hour in winner_pref:
            pref_score = 1.0
        elif winner_pref:
            pref_score = 0.7
        else:
            pref_score = 0.8
        
        factors.append(FactorScore(
            name="Winner's Preferred Time",
            category=FactorCategory.TIMING,
            score=pref_score,
            weight=0.35,
            confidence=0.7 if winner_pref else 0.5,
            description="Betting during winner's historically strong hours",
            raw_value=current_hour,
            benchmark=winner_pref[0] if winner_pref else 12,
            z_score=0.5
        ))
        
        # Entry Timing Quality
        entry_timing = timing_data.get('seconds_from_opportunity', 0)
        if entry_timing < 60:
            timing_score = 1.0  # Fast
        elif entry_timing < 300:
            timing_score = 0.8
        elif entry_timing < 900:
            timing_score = 0.6
        else:
            timing_score = 0.4  # Slow
        
        factors.append(FactorScore(
            name="Copy Entry Timing",
            category=FactorCategory.TIMING,
            score=timing_score,
            weight=0.25,
            confidence=0.9,
            description="Speed of replication after winner entry",
            raw_value=entry_timing,
            benchmark=60,
            z_score=(300 - entry_timing) / 200
        ))
        
        return factors
    
    def _calculate_risk_factors(self, market_data: Dict, portfolio: Dict) -> List[FactorScore]:
        """Calculate risk factors."""
        factors = []
        
        # Portfolio Heat
        current_exposure = portfolio.get('current_exposure', 0)
        max_exposure = portfolio.get('max_exposure', 0.5)
        heat_score = max(0, 1 - (current_exposure / max_exposure))
        
        factors.append(FactorScore(
            name="Portfolio Heat",
            category=FactorCategory.RISK,
            score=heat_score,
            weight=0.35,
            confidence=0.95,
            description="Available capacity for new positions",
            raw_value=current_exposure,
            benchmark=max_exposure * 0.5,
            z_score=(max_exposure - current_exposure) / (max_exposure * 0.3)
        ))
        
        # Correlation Risk
        correlation = market_data.get('correlation_with_portfolio', 0)
        corr_score = max(0, 1 - abs(correlation))
        
        factors.append(FactorScore(
            name="Correlation Risk",
            category=FactorCategory.RISK,
            score=corr_score,
            weight=0.35,
            confidence=0.6,
            description="Diversification from existing positions",
            raw_value=correlation,
            benchmark=0,
            z_score=-correlation / 0.3
        ))
        
        # Downside Protection
        # Based on stop loss distance
        stop_distance = market_data.get('stop_distance', 0.05)
        stop_score = min(1.0, stop_distance / 0.03)  # Prefer wider stops
        
        factors.append(FactorScore(
            name="Downside Protection",
            category=FactorCategory.RISK,
            score=stop_score,
            weight=0.30,
            confidence=0.8,
            description="Adequate stop loss protection",
            raw_value=stop_distance,
            benchmark=0.05,
            z_score=(stop_distance - 0.03) / 0.02
        ))
        
        return factors
    
    def _calculate_behavioral_factors(self, winner_profile, timing_data: Dict) -> List[FactorScore]:
        """Calculate behavioral factors."""
        factors = []
        
        # Streak Analysis
        current_streak = winner_profile.current_streak if hasattr(winner_profile, 'current_streak') else 0
        # Mild momentum: slight preference for winners on streaks
        if current_streak > 2:
            streak_score = 0.9
        elif current_streak > 0:
            streak_score = 0.85
        elif current_streak > -2:
            streak_score = 0.75
        else:
            streak_score = 0.6
        
        factors.append(FactorScore(
            name="Winner's Current Streak",
            category=FactorCategory.BEHAVIORAL,
            score=streak_score,
            weight=0.50,
            confidence=0.7,
            description="Recent performance momentum",
            raw_value=current_streak,
            benchmark=1,
            z_score=current_streak / 3
        ))
        
        # Bet Size Consistency
        if hasattr(winner_profile, 'bet_size_volatility'):
            consistency_score = max(0, 1 - winner_profile.bet_size_volatility)
        else:
            consistency_score = 0.7
        
        factors.append(FactorScore(
            name="Bet Sizing Consistency",
            category=FactorCategory.BEHAVIORAL,
            score=consistency_score,
            weight=0.50,
            confidence=0.8,
            description="Consistent position sizing indicates discipline",
            raw_value=1 - consistency_score,
            benchmark=0.2,
            z_score=(0.3 - (1 - consistency_score)) / 0.1
        ))
        
        return factors
    
    def _calculate_fundamental_factors(self, market_data: Dict) -> List[FactorScore]:
        """Calculate fundamental factors."""
        factors = []
        
        # Market Sentiment
        sentiment = market_data.get('sentiment_score', 0.5)
        # Neutral is good (efficient market)
        sentiment_score = 1 - abs(sentiment - 0.5) * 2
        
        factors.append(FactorScore(
            name="Market Sentiment Neutrality",
            category=FactorCategory.FUNDAMENTAL,
            score=sentiment_score,
            weight=0.50,
            confidence=0.6,
            description="Avoiding extreme sentiment bubbles",
            raw_value=sentiment,
            benchmark=0.5,
            z_score=(0.5 - abs(sentiment - 0.5)) / 0.25
        ))
        
        # Volume Trend
        volume_trend = market_data.get('volume_trend', 1.0)
        # Increasing volume is good
        vol_score = min(1.0, volume_trend)
        
        factors.append(FactorScore(
            name="Volume Trend",
            category=FactorCategory.FUNDAMENTAL,
            score=vol_score,
            weight=0.50,
            confidence=0.7,
            description="Increasing market participation",
            raw_value=volume_trend,
            benchmark=1.0,
            z_score=(volume_trend - 0.8) / 0.3
        ))
        
        return factors
    
    def _generate_swot(
        self,
        factors: List[FactorScore],
        category_scores: Dict[FactorCategory, float]
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        """Generate SWOT analysis."""
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []
        
        # Top factors are strengths
        top_factors = sorted(factors, key=lambda x: x.score * x.weight, reverse=True)[:3]
        for f in top_factors:
            if f.score > 0.7:
                strengths.append(f"{f.name}: {f.description}")
        
        # Bottom factors are weaknesses
        bottom_factors = sorted(factors, key=lambda x: x.score * x.weight)[:3]
        for f in bottom_factors:
            if f.score < 0.5:
                weaknesses.append(f"{f.name}: {f.description}")
        
        # Opportunities based on category scores
        if category_scores[FactorCategory.TIMING] > 0.8:
            opportunities.append("Excellent timing alignment")
        if category_scores[FactorCategory.MARKET_CONDITIONS] > 0.8:
            opportunities.append("Favorable market conditions")
        
        # Threats
        if category_scores[FactorCategory.RISK] < 0.5:
            threats.append("High portfolio exposure")
        if category_scores[FactorCategory.MARKET_CONDITIONS] < 0.4:
            threats.append("Poor market conditions")
        
        return strengths, weaknesses, opportunities, threats
    
    def _determine_grade(self, composite: float, category_scores: Dict) -> str:
        """Determine letter grade."""
        if composite > 0.85:
            return "A+"
        elif composite > 0.80:
            return "A"
        elif composite > 0.75:
            return "A-"
        elif composite > 0.70:
            return "B+"
        elif composite > 0.65:
            return "B"
        elif composite > 0.60:
            return "B-"
        elif composite > 0.55:
            return "C+"
        elif composite > 0.50:
            return "C"
        else:
            return "D"
    
    def _generate_recommendations(
        self,
        composite: float,
        category_scores: Dict,
        factors: List[FactorScore]
    ) -> Tuple[str, str, float, float]:
        """Generate recommendations."""
        # Action
        if composite > 0.80:
            action = "IMMEDIATE_ENTRY"
        elif composite > 0.70:
            action = "ENTER"
        elif composite > 0.60:
            action = "CAUTIOUS_ENTRY"
        elif composite > 0.50:
            action = "SMALL_POSITION"
        else:
            action = "PASS"
        
        # Timing
        if category_scores[FactorCategory.TIMING] > 0.8:
            timing = "NOW"
        elif category_scores[FactorCategory.TIMING] > 0.6:
            timing = "WITHIN_1_HOUR"
        else:
            timing = "WAIT_FOR_BETTER_TIMING"
        
        # Size adjustment
        if category_scores[FactorCategory.RISK] < 0.5:
            size_adj = 0.5  # Reduce size
        elif composite > 0.85:
            size_adj = 1.2  # Increase size
        else:
            size_adj = 1.0
        
        # Risk adjustment
        if category_scores[FactorCategory.RISK] < 0.4:
            risk_adj = 0.7  # Tighter stops
        else:
            risk_adj = 1.0
        
        return action, timing, size_adj, risk_adj
    
    def generate_report(self, score: MultiFactorScore) -> str:
        """Generate detailed multi-factor report."""
        lines = []
        lines.append("=" * 80)
        lines.append("MULTI-FACTOR ANALYSIS REPORT")
        lines.append("=" * 80)
        
        lines.append(f"\n[OVERALL SCORE]")
        lines.append(f"  Composite Score: {score.composite_score:.1%}")
        lines.append(f"  Grade: {score.grade}")
        lines.append(f"  Confidence: {score.confidence:.0%}")
        lines.append(f"  Recommendation: {score.recommended_action}")
        lines.append(f"  Optimal Timing: {score.optimal_timing}")
        
        lines.append(f"\n[CATEGORY SCORES]")
        for category, cat_score in score.category_scores.items():
            bar = "█" * int(cat_score * 20)
            lines.append(f"  {category.value:20s}: {cat_score:.1%} {bar}")
        
        lines.append(f"\n[TOP FACTORS]")
        top_factors = sorted(score.factors, key=lambda x: x.score * x.weight, reverse=True)[:5]
        for f in top_factors:
            lines.append(f"  ✓ {f.name}: {f.score:.1%} (weight: {f.weight:.0%})")
        
        lines.append(f"\n[BOTTOM FACTORS]")
        bottom_factors = sorted(score.factors, key=lambda x: x.score * x.weight)[:3]
        for f in bottom_factors:
            lines.append(f"  ✗ {f.name}: {f.score:.1%} (weight: {f.weight:.0%})")
        
        if score.strengths:
            lines.append(f"\n[STRENGTHS]")
            for s in score.strengths:
                lines.append(f"  + {s}")
        
        if score.weaknesses:
            lines.append(f"\n[WEAKNESSES]")
            for w in score.weaknesses:
                lines.append(f"  - {w}")
        
        lines.append(f"\n[POSITION SIZING]")
        lines.append(f"  Size Adjustment: {score.position_size_adjustment:.2f}x")
        lines.append(f"  Risk Adjustment: {score.risk_adjustment:.2f}x")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
