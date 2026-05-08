"""
Pattern Engine - Behavioral Pattern Recognition

Identifies whale trading patterns:
1. THE SNIPER: Enters within 5min of market creation with >$5k
2. THE ACCUMULATOR: Gradual position building over 24h (averaging down)
3. THE SWINGER: Exits at 20% profit consistently (profit-taking pattern)
4. THE CONTRARIAN: Bets against momentum when price >70% or <30%
5. THE HEDGER: Balanced YES/NO positions (risk-off mode)
6. THE NEWS TRADER: Sudden large bet after period of inactivity (event-driven)

Provides timing analysis and predictive insights.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class PatternType(Enum):
    """Trading behavior patterns."""
    SNIPER = "sniper"               # Fast entry on new markets
    ACCUMULATOR = "accumulator"     # Gradual position building
    SWINGER = "swinger"             # Quick profit taking
    CONTRARIAN = "contrarian"       # Bets against extremes
    HEDGER = "hedger"               # Balanced positions
    NEWS_TRADER = "news_trader"     # Event-driven spikes
    MOMENTUM = "momentum"           # Follows price momentum
    SCALPER = "scalper"             # Frequent small trades
    UNKNOWN = "unknown"


@dataclass
class PatternProfile:
    """Complete pattern analysis for a whale."""
    # Identity
    whale_address: str
    
    # Primary pattern
    primary_pattern: PatternType
    secondary_patterns: List[PatternType]
    pattern_confidence: float  # 0-1
    
    # Timing characteristics
    avg_time_to_enter: timedelta      # After market creation
    avg_hold_duration: timedelta      # How long positions held
    avg_exit_profit_percent: float    # Typical profit taking level
    
    # Risk appetite
    risk_appetite: str  # aggressive, moderate, conservative
    max_position_size: float
    avg_position_size: float
    
    # Current stance
    current_stance: str  # accumulating, distributing, hedging, neutral
    recent_activity_level: str  # high, medium, low
    
    # Performance in this pattern
    pattern_win_rate: float
    pattern_profit_factor: float
    
    # Insights
    insights: List[str] = field(default_factory=list)
    best_market_conditions: List[str] = field(default_factory=list)


@dataclass
class TradeSequence:
    """A sequence of related trades."""
    market_id: str
    trades: List[Dict]
    start_time: datetime
    end_time: datetime
    total_amount: float
    average_price: float
    final_position: str  # YES, NO, or BALANCED


class PatternEngine:
    """
    Analyzes whale trading patterns for behavioral profiling.
    """
    
    def __init__(self):
        """Initialize pattern engine."""
        self.pattern_history: Dict[str, List[PatternType]] = defaultdict(list)
        self.sequence_cache: Dict[str, List[TradeSequence]] = {}
        
        # Pattern detection thresholds
        self.thresholds = {
            'sniper_time': timedelta(minutes=5),
            'sniper_size': 5000,
            'accumulation_trades': 5,
            'accumulation_window': timedelta(hours=24),
            'swinger_profit': 0.20,
            'contrarian_threshold': 0.70,
            'news_inactivity': timedelta(hours=48),
            'news_size_multiplier': 3.0,
        }
    
    def analyze_whale_pattern(
        self,
        whale_address: str,
        trade_history: List[Dict]
    ) -> PatternProfile:
        """
        Analyze complete pattern profile for a whale.
        
        Args:
            whale_address: Whale's wallet address
            trade_history: List of historical trades
            
        Returns:
            PatternProfile with complete behavioral analysis
        """
        if len(trade_history) < 10:
            return self._create_unknown_profile(whale_address)
        
        # Analyze different patterns
        pattern_scores = {}
        
        pattern_scores[PatternType.SNIPER] = self._score_sniper_pattern(trade_history)
        pattern_scores[PatternType.ACCUMULATOR] = self._score_accumulator_pattern(trade_history)
        pattern_scores[PatternType.SWINGER] = self._score_swinger_pattern(trade_history)
        pattern_scores[PatternType.CONTRARIAN] = self._score_contrarian_pattern(trade_history)
        pattern_scores[PatternType.HEDGER] = self._score_hedger_pattern(trade_history)
        pattern_scores[PatternType.NEWS_TRADER] = self._score_news_trader_pattern(trade_history)
        pattern_scores[PatternType.MOMENTUM] = self._score_momentum_pattern(trade_history)
        
        # Determine primary pattern
        sorted_patterns = sorted(pattern_scores.items(), key=lambda x: x[1], reverse=True)
        primary_pattern = sorted_patterns[0][0]
        primary_confidence = sorted_patterns[0][1]
        
        # Secondary patterns (>0.5 confidence)
        secondary = [p for p, s in sorted_patterns[1:] if s > 0.5]
        
        # Calculate timing characteristics
        timing = self._analyze_timing(trade_history)
        
        # Determine risk appetite
        risk = self._assess_risk_appetite(trade_history)
        
        # Current stance
        stance = self._determine_current_stance(trade_history)
        
        # Calculate pattern-specific performance
        performance = self._calculate_pattern_performance(trade_history, primary_pattern)
        
        # Generate insights
        insights = self._generate_insights(trade_history, primary_pattern, timing)
        
        return PatternProfile(
            whale_address=whale_address,
            primary_pattern=primary_pattern,
            secondary_patterns=secondary,
            pattern_confidence=primary_confidence,
            avg_time_to_enter=timing['avg_entry_time'],
            avg_hold_duration=timing['avg_hold_time'],
            avg_exit_profit_percent=timing['avg_profit'],
            risk_appetite=risk['appetite'],
            max_position_size=risk['max_size'],
            avg_position_size=risk['avg_size'],
            current_stance=stance['stance'],
            recent_activity_level=stance['activity'],
            pattern_win_rate=performance['win_rate'],
            pattern_profit_factor=performance['profit_factor'],
            insights=insights,
            best_market_conditions=self._determine_best_conditions(trade_history)
        )
    
    def calculate_speed_score(
        self,
        whale_trade: Dict,
        market_context: Dict
    ) -> float:
        """
        Calculate how fast whale reacted vs market conditions.
        
        Returns:
            Speed score 0-1 (1 = fastest)
        """
        scores = []
        
        # Time since market creation
        market_created = market_context.get('created_at')
        trade_time = whale_trade.get('timestamp')
        
        if market_created and trade_time:
            time_diff = trade_time - market_created
            if time_diff < timedelta(minutes=2):
                scores.append(1.0)
            elif time_diff < timedelta(minutes=5):
                scores.append(0.8)
            elif time_diff < timedelta(minutes=15):
                scores.append(0.6)
            else:
                scores.append(0.3)
        
        # Time since last price movement
        last_price_move = market_context.get('last_price_movement')
        if last_price_move and trade_time:
            reaction_time = trade_time - last_price_move
            if reaction_time < timedelta(minutes=1):
                scores.append(1.0)
            elif reaction_time < timedelta(minutes=5):
                scores.append(0.7)
            else:
                scores.append(0.4)
        
        # Trade size vs whale's average (urgency indicator)
        whale_avg = whale_trade.get('whale_avg_size', 5000)
        trade_size = whale_trade.get('amount', 0)
        if whale_avg > 0:
            size_ratio = trade_size / whale_avg
            if size_ratio > 2:
                scores.append(1.0)  # Double normal size = urgent
            elif size_ratio > 1.5:
                scores.append(0.8)
            else:
                scores.append(0.5)
        
        return np.mean(scores) if scores else 0.5
    
    def detect_pattern_shift(
        self,
        whale_address: str,
        recent_trades: List[Dict]
    ) -> Optional[str]:
        """
        Detect if whale has shifted to a new pattern.
        
        Returns:
            Alert message if shift detected, None otherwise
        """
        if len(recent_trades) < 5:
            return None
        
        # Analyze last 20 trades vs previous 20
        recent = recent_trades[-20:]
        previous = recent_trades[-40:-20] if len(recent_trades) >= 40 else []
        
        if not previous:
            return None
        
        recent_pattern = self._detect_dominant_pattern(recent)
        previous_pattern = self._detect_dominant_pattern(previous)
        
        if recent_pattern != previous_pattern:
            return (f"PATTERN SHIFT: {whale_address[:8]}... changed from "
                   f"{previous_pattern.value} to {recent_pattern.value}")
        
        return None
    
    def _score_sniper_pattern(self, trades: List[Dict]) -> float:
        """Score for SNIPER pattern (fast entry on new markets)."""
        early_entries = 0
        qualifying_trades = 0
        
        for trade in trades:
            market_created = trade.get('market_created_at')
            trade_time = trade.get('timestamp')
            size = trade.get('amount', 0)
            
            if market_created and trade_time and size >= self.thresholds['sniper_size']:
                time_to_entry = trade_time - market_created
                if time_to_entry < self.thresholds['sniper_time']:
                    early_entries += 1
                qualifying_trades += 1
        
        if qualifying_trades < 3:
            return 0.0
        
        return min(1.0, early_entries / qualifying_trades)
    
    def _score_accumulator_pattern(self, trades: List[Dict]) -> float:
        """Score for ACCUMULATOR pattern (gradual building)."""
        # Group trades by market
        market_sequences = defaultdict(list)
        for trade in trades:
            market_sequences[trade.get('market_id')].append(trade)
        
        accumulation_count = 0
        
        for market_id, market_trades in market_sequences.items():
            if len(market_trades) >= self.thresholds['accumulation_trades']:
                # Check if spread over 24h
                times = sorted([t.get('timestamp') for t in market_trades if t.get('timestamp')])
                if times and (times[-1] - times[0]) < self.thresholds['accumulation_window']:
                    # Check if increasing amounts (averaging down pattern)
                    amounts = [t.get('amount', 0) for t in sorted(market_trades, key=lambda x: x.get('timestamp'))]
                    if amounts == sorted(amounts):  # Increasing
                        accumulation_count += 1
        
        total_markets = len(market_sequences)
        if total_markets < 3:
            return 0.0
        
        return min(1.0, accumulation_count / total_markets * 2)
    
    def _score_swinger_pattern(self, trades: List[Dict]) -> float:
        """Score for SWINGER pattern (quick profit taking)."""
        profitable_exits = 0
        total_exits = 0
        
        for i, trade in enumerate(trades):
            if trade.get('is_exit', False):
                total_exits += 1
                pnl = trade.get('pnl', 0)
                entry_cost = trade.get('entry_cost', 1)
                profit_pct = pnl / entry_cost if entry_cost > 0 else 0
                
                if 0.15 <= profit_pct <= 0.30:  # 15-30% profit range
                    profitable_exits += 1
        
        if total_exits < 3:
            return 0.0
        
        return min(1.0, profitable_exits / total_exits)
    
    def _score_contrarian_pattern(self, trades: List[Dict]) -> float:
        """Score for CONTRARIAN pattern (bets against extremes)."""
        contrarian_bets = 0
        total_bets = 0
        
        for trade in trades:
            if not trade.get('is_exit', False):
                total_bets += 1
                price = trade.get('price', 0.5)
                
                # Betting against extreme prices
                if price > 0.70 or price < 0.30:
                    contrarian_bets += 1
        
        if total_bets < 5:
            return 0.0
        
        return min(1.0, contrarian_bets / total_bets * 1.5)
    
    def _score_hedger_pattern(self, trades: List[Dict]) -> float:
        """Score for HEDGER pattern (balanced positions)."""
        # Group by market and check for YES/NO balance
        market_positions = defaultdict(lambda: {'YES': 0, 'NO': 0})
        
        for trade in trades:
            market_id = trade.get('market_id')
            outcome = trade.get('outcome')
            amount = trade.get('amount', 0)
            
            if outcome in ['YES', 'NO']:
                market_positions[market_id][outcome] += amount
        
        hedged_markets = 0
        for market_id, positions in market_positions.items():
            yes_size = positions['YES']
            no_size = positions['NO']
            
            if yes_size > 0 and no_size > 0:
                # Check if roughly balanced (within 50% of each other)
                ratio = min(yes_size, no_size) / max(yes_size, no_size)
                if ratio > 0.5:
                    hedged_markets += 1
        
        total_markets = len(market_positions)
        if total_markets < 3:
            return 0.0
        
        return min(1.0, hedged_markets / total_markets * 2)
    
    def _score_news_trader_pattern(self, trades: List[Dict]) -> float:
        """Score for NEWS_TRADER pattern (sudden activity after inactivity)."""
        if len(trades) < 5:
            return 0.0
        
        # Sort by time
        sorted_trades = sorted(trades, key=lambda x: x.get('timestamp'))
        
        news_spikes = 0
        
        for i in range(1, len(sorted_trades)):
            current = sorted_trades[i]
            previous = sorted_trades[i-1]
            
            time_gap = current.get('timestamp') - previous.get('timestamp')
            size_ratio = current.get('amount', 0) / max(previous.get('amount', 1), 100)
            
            # Long inactivity followed by large trade
            if time_gap > self.thresholds['news_inactivity'] and size_ratio > self.thresholds['news_size_multiplier']:
                news_spikes += 1
        
        return min(1.0, news_spikes / len(sorted_trades) * 5)
    
    def _score_momentum_pattern(self, trades: List[Dict]) -> float:
        """Score for MOMENTUM pattern (follows price movement)."""
        momentum_trades = 0
        total_trades = 0
        
        for trade in trades:
            if trade.get('price_direction') and trade.get('outcome'):
                total_trades += 1
                price_dir = trade.get('price_direction')  # 'up' or 'down'
                outcome = trade.get('outcome')
                
                # Buying YES when price is going up (momentum)
                if (price_dir == 'up' and outcome == 'YES') or (price_dir == 'down' and outcome == 'NO'):
                    momentum_trades += 1
        
        if total_trades < 5:
            return 0.0
        
        return momentum_trades / total_trades
    
    def _analyze_timing(self, trades: List[Dict]) -> Dict:
        """Analyze timing characteristics."""
        if not trades:
            return {
                'avg_entry_time': timedelta(minutes=30),
                'avg_hold_time': timedelta(hours=24),
                'avg_profit': 0.15
            }
        
        entry_times = []
        hold_times = []
        profits = []
        
        for trade in trades:
            # Entry time
            market_created = trade.get('market_created_at')
            entry_time = trade.get('timestamp')
            if market_created and entry_time:
                entry_times.append(entry_time - market_created)
            
            # Hold time and profit
            exit_time = trade.get('exit_timestamp')
            if entry_time and exit_time:
                hold_times.append(exit_time - entry_time)
                
                pnl = trade.get('pnl', 0)
                entry_cost = trade.get('entry_cost', 1)
                if entry_cost > 0:
                    profits.append(pnl / entry_cost)
        
        return {
            'avg_entry_time': np.mean(entry_times) if entry_times else timedelta(minutes=30),
            'avg_hold_time': np.mean(hold_times) if hold_times else timedelta(hours=24),
            'avg_profit': np.mean(profits) if profits else 0.15
        }
    
    def _assess_risk_appetite(self, trades: List[Dict]) -> Dict:
        """Assess whale's risk appetite."""
        sizes = [t.get('amount', 0) for t in trades]
        
        if not sizes:
            return {'appetite': 'moderate', 'max_size': 5000, 'avg_size': 2000}
        
        avg_size = np.mean(sizes)
        max_size = np.max(sizes)
        
        if max_size > 50000:
            appetite = 'aggressive'
        elif max_size > 10000:
            appetite = 'moderate'
        else:
            appetite = 'conservative'
        
        return {
            'appetite': appetite,
            'max_size': max_size,
            'avg_size': avg_size
        }
    
    def _determine_current_stance(self, trades: List[Dict]) -> Dict:
        """Determine current trading stance."""
        if not trades:
            return {'stance': 'neutral', 'activity': 'low'}
        
        recent = [t for t in trades if datetime.now() - t.get('timestamp', datetime.min) < timedelta(days=7)]
        
        if len(recent) > 10:
            activity = 'high'
        elif len(recent) > 3:
            activity = 'medium'
        else:
            activity = 'low'
        
        # Determine stance based on recent trade directions
        increasing = sum(1 for t in recent if t.get('amount', 0) > t.get('previous_amount', 0))
        decreasing = sum(1 for t in recent if t.get('amount', 0) < t.get('previous_amount', 0))
        
        if increasing > decreasing * 2:
            stance = 'accumulating'
        elif decreasing > increasing * 2:
            stance = 'distributing'
        elif any(t.get('outcome') == 'YES' for t in recent) and any(t.get('outcome') == 'NO' for t in recent):
            stance = 'hedging'
        else:
            stance = 'neutral'
        
        return {'stance': stance, 'activity': activity}
    
    def _calculate_pattern_performance(self, trades: List[Dict], pattern: PatternType) -> Dict:
        """Calculate performance metrics for a specific pattern."""
        # Filter trades matching the pattern
        # This is simplified - real implementation would filter by pattern indicators
        
        pnls = [t.get('pnl', 0) for t in trades if t.get('settled')]
        
        if not pnls:
            return {'win_rate': 0.5, 'profit_factor': 1.0}
        
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls)
        
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0
        
        return {'win_rate': win_rate, 'profit_factor': profit_factor}
    
    def _generate_insights(
        self,
        trades: List[Dict],
        pattern: PatternType,
        timing: Dict
    ) -> List[str]:
        """Generate educational insights about the whale."""
        insights = []
        
        if pattern == PatternType.SNIPER:
            insights.append(f"Enters markets within {timing['avg_entry_time'].seconds // 60} minutes on average")
            insights.append("Looks for early alpha in newly created markets")
        
        elif pattern == PatternType.ACCUMULATOR:
            insights.append("Builds positions gradually over 24-48 hours")
            insights.append("Often averages down on conviction bets")
        
        elif pattern == PatternType.SWINGER:
            insights.append(f"Takes profits around {timing['avg_profit']:.0%}")
            insights.append("Quick turnaround - doesn't hold losing positions long")
        
        elif pattern == PatternType.CONTRARIAN:
            insights.append("Bets against crowd at price extremes")
            insights.append("Looks for mean reversion opportunities")
        
        # Add timing insight
        if timing['avg_hold_time'] < timedelta(hours=6):
            insights.append("Short-term trader - holds positions <6 hours")
        elif timing['avg_hold_time'] > timedelta(days=3):
            insights.append("Long-term holder - patient for resolution")
        
        return insights
    
    def _determine_best_conditions(self, trades: List[Dict]) -> List[str]:
        """Determine market conditions where whale performs best."""
        # Simplified analysis
        conditions = []
        
        # Check liquidity preference
        avg_liquidity = np.mean([t.get('market_liquidity', 0) for t in trades])
        if avg_liquidity > 100000:
            conditions.append("High liquidity markets (>$100k)")
        elif avg_liquidity < 50000:
            conditions.append("Low liquidity, early markets")
        
        # Check timing patterns
        hours = [t.get('timestamp').hour for t in trades if t.get('timestamp')]
        if hours:
            avg_hour = np.mean(hours)
            if 2 <= avg_hour <= 6:
                conditions.append("Early morning UTC (2-6 AM)")
            elif 14 <= avg_hour <= 18:
                conditions.append("Afternoon UTC (2-6 PM)")
        
        return conditions if conditions else ["All market conditions"]
    
    def _create_unknown_profile(self, whale_address: str) -> PatternProfile:
        """Create profile for unknown/insufficient data."""
        return PatternProfile(
            whale_address=whale_address,
            primary_pattern=PatternType.UNKNOWN,
            secondary_patterns=[],
            pattern_confidence=0.0,
            avg_time_to_enter=timedelta(minutes=30),
            avg_hold_duration=timedelta(hours=24),
            avg_exit_profit_percent=0.15,
            risk_appetite="unknown",
            max_position_size=0,
            avg_position_size=0,
            current_stance="neutral",
            recent_activity_level="low",
            pattern_win_rate=0.5,
            pattern_profit_factor=1.0,
            insights=["Insufficient data for pattern detection"],
            best_market_conditions=[]
        )
    
    def _detect_dominant_pattern(self, trades: List[Dict]) -> PatternType:
        """Quick pattern detection for shift detection."""
        scores = {
            PatternType.SNIPER: self._score_sniper_pattern(trades),
            PatternType.ACCUMULATOR: self._score_accumulator_pattern(trades),
            PatternType.SWINGER: self._score_swinger_pattern(trades),
            PatternType.CONTRARIAN: self._score_contrarian_pattern(trades),
        }
        
        return max(scores.items(), key=lambda x: x[1])[0]
