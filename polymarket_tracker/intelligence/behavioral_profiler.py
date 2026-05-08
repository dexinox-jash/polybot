"""
Behavioral Profiler - Whale Personality Analysis

Analyzes whale personality traits and creates profiles for:
- Trading psychology (FOMO, patience, revenge trading)
- Risk temperament
- Market timing preferences
- Social/copy trading tendencies
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class TradingPsychology(Enum):
    """Trading psychological profiles."""
    PATIENT_HUNTER = "patient_hunter"      # Waits for perfect setups
    FOMO_TRADER = "fomo_trader"            # Chases momentum
    REVENGE_TRADER = "revenge_trader"      # Trades emotionally after losses
    METHODICAL = "methodical"              # Systematic, rule-based
    INTUITIVE = "intuitive"                # Gut-feel, discretionary
    DATA_DRIVEN = "data_driven"            # Heavy on-chain/analysis research


class RiskTemperament(Enum):
    """Risk temperament types."""
    CONSERVATIVE = "conservative"          # Small positions, tight stops
    MODERATE = "moderate"                  # Balanced approach
    AGGRESSIVE = "aggressive"              # Large positions, wide stops
    GAMBLER = "gambler"                    # High risk, all-or-nothing
    CALCULATED = "calculated"              # High risk but researched


@dataclass
class WhalePersonality:
    """Complete personality profile of a whale."""
    # Identity
    whale_address: str
    
    # Psychology
    primary_psychology: TradingPsychology
    risk_temperament: RiskTemperament
    
    # Behavioral traits (0-1 scores)
    patience_score: float                  # Willingness to wait for setups
    discipline_score: float               # Sticks to plan vs chases
    confidence_score: float               # Position sizing consistency
    adaptability_score: float             # Adjusts to market changes
    
    # Timing preferences
    preferred_hours: List[int]             # UTC hours most active
    session_style: str                     # 'early_bird', 'night_owl', 'all_day'
    
    # Social indicators
    follows_crowd: bool                   # Copies other whales
    contrarian_tendency: float            # 0-1, bets against consensus
    herd_leader: bool                     # Others follow them
    
    # Strengths & weaknesses
    strengths: List[str]
    weaknesses: List[str]
    
    # Copy recommendations
    best_copy_conditions: List[str]
    avoid_conditions: List[str]


class BehavioralProfiler:
    """
    Profiles whale trading psychology and behavior.
    """
    
    def __init__(self):
        """Initialize behavioral profiler."""
        self.personality_cache: Dict[str, WhalePersonality] = {}
    
    def profile_whale(
        self,
        whale_address: str,
        trade_history: List[Dict],
        social_data: Optional[Dict] = None
    ) -> WhalePersonality:
        """
        Create complete personality profile for a whale.
        
        Args:
            whale_address: Whale's address
            trade_history: List of historical trades
            social_data: Optional social graph data
            
        Returns:
            WhalePersonality with complete profile
        """
        if len(trade_history) < 5:
            return self._create_default_profile(whale_address)
        
        # Analyze psychology
        psychology = self._analyze_psychology(trade_history)
        
        # Assess risk temperament
        risk = self._assess_risk_temperament(trade_history)
        
        # Calculate trait scores
        traits = self._calculate_traits(trade_history)
        
        # Analyze timing preferences
        timing = self._analyze_timing(trade_history)
        
        # Analyze social behavior
        social = self._analyze_social_behavior(trade_history, social_data)
        
        # Generate insights
        strengths, weaknesses = self._generate_strengths_weaknesses(
            psychology, risk, traits
        )
        
        # Copy recommendations
        best_conditions, avoid_conditions = self._generate_copy_recommendations(
            psychology, risk, traits, timing
        )
        
        return WhalePersonality(
            whale_address=whale_address,
            primary_psychology=psychology,
            risk_temperament=risk,
            patience_score=traits['patience'],
            discipline_score=traits['discipline'],
            confidence_score=traits['confidence'],
            adaptability_score=traits['adaptability'],
            preferred_hours=timing['hours'],
            session_style=timing['style'],
            follows_crowd=social['follows_crowd'],
            contrarian_tendency=social['contrarian'],
            herd_leader=social['herd_leader'],
            strengths=strengths,
            weaknesses=weaknesses,
            best_copy_conditions=best_conditions,
            avoid_conditions=avoid_conditions
        )
    
    def _analyze_psychology(self, trades: List[Dict]) -> TradingPsychology:
        """Determine trading psychology type."""
        if len(trades) < 5:
            return TradingPsychology.METHODICAL
        
        # Analyze trade timing patterns
        entry_times = []
        for trade in trades:
            market_created = trade.get('market_created_at')
            entry = trade.get('timestamp')
            if market_created and entry:
                entry_times.append((entry - market_created).total_seconds())
        
        if entry_times:
            avg_entry_time = sum(entry_times) / len(entry_times)
            
            # Very fast entries = FOMO
            if avg_entry_time < 300:  # 5 minutes
                return TradingPsychology.FOMO_TRADER
            
            # Very patient = Patient hunter
            if avg_entry_time > 3600:  # 1 hour
                return TradingPsychology.PATIENT_HUNTER
        
        # Analyze position sizing consistency
        sizes = [t.get('amount', 0) for t in trades]
        if sizes:
            size_variance = max(sizes) / (min(sizes) + 1)
            if size_variance > 10:
                return TradingPsychology.INTUITIVE  # Inconsistent sizing
        
        # Analyze loss recovery
        losses_followed_by_bigger_bets = 0
        for i in range(1, len(trades)):
            prev_pnl = trades[i-1].get('pnl', 0)
            curr_size = trades[i].get('amount', 0)
            prev_size = trades[i-1].get('amount', 0)
            
            if prev_pnl < 0 and curr_size > prev_size * 1.5:
                losses_followed_by_bigger_bets += 1
        
        if losses_followed_by_bigger_bets >= 2:
            return TradingPsychology.REVENGE_TRADER
        
        # Check for research indicators
        research_indicators = sum(1 for t in trades if t.get('time_spent_researching', 0) > 300)
        if research_indicators > len(trades) * 0.5:
            return TradingPsychology.DATA_DRIVEN
        
        return TradingPsychology.METHODICAL
    
    def _assess_risk_temperament(self, trades: List[Dict]) -> RiskTemperament:
        """Assess risk temperament."""
        if not trades:
            return RiskTemperament.MODERATE
        
        # Analyze position sizes relative to bankroll
        sizes = [t.get('amount', 0) for t in trades]
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        max_size = max(sizes) if sizes else 0
        
        # Analyze stop loss usage
        stops_used = sum(1 for t in trades if t.get('stop_loss'))
        stop_ratio = stops_used / len(trades)
        
        # Analyze drawdown recovery
        drawdowns = [t.get('drawdown', 0) for t in trades]
        max_drawdown = max(drawdowns) if drawdowns else 0
        
        if max_size > 50000 and stop_ratio < 0.3:
            return RiskTemperament.GAMBLER
        elif max_size > 20000 and max_drawdown > 0.3:
            return RiskTemperament.AGGRESSIVE
        elif stop_ratio > 0.8 and avg_size < 5000:
            return RiskTemperament.CONSERVATIVE
        elif max_size > 20000 and stop_ratio > 0.6:
            return RiskTemperament.CALCULATED
        
        return RiskTemperament.MODERATE
    
    def _calculate_traits(self, trades: List[Dict]) -> Dict[str, float]:
        """Calculate behavioral trait scores (0-1)."""
        if len(trades) < 5:
            return {
                'patience': 0.5,
                'discipline': 0.5,
                'confidence': 0.5,
                'adaptability': 0.5
            }
        
        # Patience: waiting for good setups
        patience_signals = 0
        for trade in trades:
            market_created = trade.get('market_created_at')
            entry = trade.get('timestamp')
            if market_created and entry:
                wait_time = (entry - market_created).total_seconds()
                if wait_time > 1800:  # Waited >30 min
                    patience_signals += 1
        
        patience = patience_signals / len(trades)
        
        # Discipline: sticking to plan
        planned_exits = sum(1 for t in trades if t.get('planned_exit', False))
        discipline = planned_exits / len(trades)
        
        # Confidence: consistent sizing
        sizes = [t.get('amount', 0) for t in trades]
        if sizes:
            size_std = (sum((s - sum(sizes)/len(sizes))**2 for s in sizes) / len(sizes)) ** 0.5
            size_mean = sum(sizes) / len(sizes)
            cv = size_std / size_mean if size_mean > 0 else 1
            confidence = max(0, 1 - cv)  # Lower variance = higher confidence
        else:
            confidence = 0.5
        
        # Adaptability: changing with market conditions
        adaptations = 0
        for i in range(1, len(trades)):
            if trades[i].get('strategy') != trades[i-1].get('strategy'):
                adaptations += 1
        
        adaptability = adaptations / (len(trades) - 1) if len(trades) > 1 else 0.5
        
        return {
            'patience': patience,
            'discipline': discipline,
            'confidence': confidence,
            'adaptability': adaptability
        }
    
    def _analyze_timing(self, trades: List[Dict]) -> Dict:
        """Analyze timing preferences."""
        hours = []
        for trade in trades:
            ts = trade.get('timestamp')
            if ts:
                hours.append(ts.hour)
        
        if not hours:
            return {'hours': [12], 'style': 'all_day'}
        
        # Find most active hours
        from collections import Counter
        hour_counts = Counter(hours)
        top_hours = [h for h, _ in hour_counts.most_common(3)]
        
        # Determine session style
        avg_hour = sum(hours) / len(hours)
        if 2 <= avg_hour <= 6:
            style = 'early_bird'
        elif 20 <= avg_hour or avg_hour <= 2:
            style = 'night_owl'
        else:
            style = 'all_day'
        
        return {'hours': top_hours, 'style': style}
    
    def _analyze_social_behavior(
        self,
        trades: List[Dict],
        social_data: Optional[Dict]
    ) -> Dict:
        """Analyze social/copy trading behavior."""
        # Simplified analysis
        follows_crowd = False
        contrarian = 0.5
        herd_leader = False
        
        if social_data:
            follows_crowd = social_data.get('follows_others', False)
            herd_leader = social_data.get('others_follow', False)
        
        # Infer from trades
        contrarian_bets = sum(1 for t in trades if t.get('price', 0.5) > 0.7 or t.get('price', 0.5) < 0.3)
        if len(trades) > 0:
            contrarian = contrarian_bets / len(trades)
        
        return {
            'follows_crowd': follows_crowd,
            'contrarian': contrarian,
            'herd_leader': herd_leader
        }
    
    def _generate_strengths_weaknesses(
        self,
        psychology: TradingPsychology,
        risk: RiskTemperament,
        traits: Dict[str, float]
    ) -> tuple:
        """Generate strengths and weaknesses."""
        strengths = []
        weaknesses = []
        
        # Psychology-based
        if psychology == TradingPsychology.PATIENT_HUNTER:
            strengths.append("Waits for high-probability setups")
            weaknesses.append("May miss fast-moving opportunities")
        elif psychology == TradingPsychology.FOMO_TRADER:
            strengths.append("Quick to act on new information")
            weaknesses.append("May chase pumps and buy tops")
        
        # Risk-based
        if risk == RiskTemperament.CONSERVATIVE:
            strengths.append("Preserves capital well")
            weaknesses.append("May miss larger gains")
        elif risk == RiskTemperament.AGGRESSIVE:
            strengths.append("Captures large moves")
            weaknesses.append("Higher drawdown risk")
        
        # Trait-based
        if traits['patience'] > 0.7:
            strengths.append("Exceptional patience")
        if traits['discipline'] < 0.4:
            weaknesses.append("Struggles with discipline")
        
        return strengths or ["Balanced trader"], weaknesses or ["No major weaknesses detected"]
    
    def _generate_copy_recommendations(
        self,
        psychology: TradingPsychology,
        risk: RiskTemperament,
        traits: Dict[str, float],
        timing: Dict
    ) -> tuple:
        """Generate copy trading recommendations."""
        best = []
        avoid = []
        
        # Psychology-based recommendations
        if psychology == TradingPsychology.PATIENT_HUNTER:
            best.append("Copy their early entries on new markets")
            avoid.append("Don't copy if you can't wait for their timing")
        elif psychology == TradingPsychology.FOMO_TRADER:
            best.append("Good for momentum plays")
            avoid.append("Be cautious near market tops")
        
        # Risk-based
        if risk in [RiskTemperament.AGGRESSIVE, RiskTemperament.GAMBLER]:
            best.append("Reduce position size by 50% when copying")
            avoid.append("Avoid during high volatility")
        
        # Timing-based
        preferred_hours = timing.get('hours', [])
        if preferred_hours:
            best.append(f"Best copy window: UTC hours {', '.join(map(str, preferred_hours))}")
        
        return best or ["Copy with standard sizing"], avoid or ["No specific conditions to avoid"]
    
    def _create_default_profile(self, whale_address: str) -> WhalePersonality:
        """Create default profile for insufficient data."""
        return WhalePersonality(
            whale_address=whale_address,
            primary_psychology=TradingPsychology.METHODICAL,
            risk_temperament=RiskTemperament.MODERATE,
            patience_score=0.5,
            discipline_score=0.5,
            confidence_score=0.5,
            adaptability_score=0.5,
            preferred_hours=[12],
            session_style='all_day',
            follows_crowd=False,
            contrarian_tendency=0.5,
            herd_leader=False,
            strengths=["Insufficient data"],
            weaknesses=["Insufficient data"],
            best_copy_conditions=["Use standard risk management"],
            avoid_conditions=["None identified"]
        )
