"""
Micro-Pattern Recognition Engine for BTC 5-Minute Markets

Detects high-probability patterns in ultra-short timeframes:
- Momentum bursts
- Mean reversion
- Breakout/false breakout
- Order flow imbalances
- Whale footprints
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from scipy import stats
from scipy.signal import find_peaks

from ..utils.logger import setup_logging

logger = setup_logging()


class SignalType(Enum):
    """Types of trading signals."""
    MOMENTUM_LONG = "momentum_long"
    MOMENTUM_SHORT = "momentum_short"
    MEAN_REVERSION_LONG = "mean_reversion_long"
    MEAN_REVERSION_SHORT = "mean_reversion_short"
    BREAKOUT_LONG = "breakout_long"
    BREAKOUT_SHORT = "breakout_short"
    FALSE_BREAKOUT = "false_breakout"
    WHALE_ACCUMULATION = "whale_accumulation"
    WHALE_DISTRIBUTION = "whale_distribution"
    LIQUIDITY_GRAB = "liquidity_grab"
    NO_SIGNAL = "no_signal"


class PatternConfidence(Enum):
    """Confidence levels for pattern detection."""
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.85


@dataclass
class PatternSignal:
    """Detected pattern signal."""
    signal_type: SignalType
    confidence: PatternConfidence
    confidence_score: float  # 0-1
    timestamp: datetime
    market_id: str
    
    # Signal metadata
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_loss: float = 0.0
    expected_return: float = 0.0
    risk_reward: float = 0.0
    
    # Pattern details
    pattern_data: Dict = None
    supporting_evidence: List[str] = None
    contradictory_evidence: List[str] = None
    
    def __post_init__(self):
        if self.pattern_data is None:
            self.pattern_data = {}
        if self.supporting_evidence is None:
            self.supporting_evidence = []
        if self.contradictory_evidence is None:
            self.contradictory_evidence = []
    
    @property
    def direction(self) -> str:
        """Get trade direction."""
        if 'LONG' in self.signal_type.value:
            return 'LONG'
        elif 'SHORT' in self.signal_type.value:
            return 'SHORT'
        return 'NEUTRAL'


class PatternEngine:
    """
    Advanced pattern recognition for BTC 5-minute markets.
    
    Uses multi-factor analysis combining:
    - Price action micro-structure
    - Volume profile analysis
    - Order flow dynamics
    - Whale behavior detection
    - Time-based patterns
    """
    
    def __init__(self):
        """Initialize pattern engine."""
        self.pattern_history: List[PatternSignal] = []
        self.success_rates: Dict[SignalType, Dict] = {}
        
        # Pattern parameters (optimized for 5-min markets)
        self.params = {
            'momentum_threshold': 0.02,  # 2% move in 30 seconds
            'reversion_threshold': 0.015,  # 1.5% deviation for mean reversion
            'volume_surge_threshold': 2.0,  # 2x average volume
            'whale_imbalance_threshold': 0.6,  # 60% whale buying
            'breakout_confirmation_ticks': 3,
        }
        
        logger.info("Pattern Engine initialized")
    
    def analyze_market(self, market_data: Dict, tick_data: pd.DataFrame) -> List[PatternSignal]:
        """
        Run full pattern analysis on a market.
        
        Args:
            market_data: Current market state
            tick_data: Recent price/volume ticks
            
        Returns:
            List of detected pattern signals
        """
        signals = []
        
        if tick_data.empty or len(tick_data) < 10:
            return signals
        
        # Run pattern detectors
        signals.extend(self._detect_momentum_patterns(tick_data, market_data))
        signals.extend(self._detect_mean_reversion(tick_data, market_data))
        signals.extend(self._detect_breakouts(tick_data, market_data))
        signals.extend(self._detect_whale_patterns(tick_data, market_data))
        signals.extend(self._detect_liquidity_grabs(tick_data, market_data))
        
        # Filter and rank signals
        signals = self._filter_signals(signals)
        
        # Store history
        self.pattern_history.extend(signals)
        
        return signals
    
    def _detect_momentum_patterns(self, df: pd.DataFrame, market: Dict) -> List[PatternSignal]:
        """Detect momentum-based patterns."""
        signals = []
        
        if len(df) < 20:
            return signals
        
        # Calculate momentum (rate of change)
        df['returns'] = df['price'].pct_change()
        df['momentum_10'] = df['returns'].rolling(10).sum()
        df['momentum_5'] = df['returns'].rolling(5).sum()
        
        # Current values
        current_price = df['price'].iloc[-1]
        current_momentum = df['momentum_10'].iloc[-1]
        recent_momentum = df['momentum_5'].iloc[-1]
        
        # Acceleration detection (momentum of momentum)
        acceleration = recent_momentum - df['momentum_5'].iloc[-5]
        
        # Volume confirmation
        avg_volume = df['size'].mean()
        recent_volume = df['size'].tail(5).mean()
        volume_confirmed = recent_volume > avg_volume * self.params['volume_surge_threshold']
        
        # Momentum Long
        if (current_momentum > self.params['momentum_threshold'] and 
            acceleration > 0 and volume_confirmed):
            
            confidence = self._calculate_momentum_confidence(df, 'long')
            
            signal = PatternSignal(
                signal_type=SignalType.MOMENTUM_LONG,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=current_price * 1.03,  # 3% target
                stop_loss=current_price * 0.985,    # 1.5% stop
                expected_return=0.03,
                risk_reward=2.0,
                pattern_data={
                    'momentum': current_momentum,
                    'acceleration': acceleration,
                    'volume_ratio': recent_volume / avg_volume,
                },
                supporting_evidence=[
                    f"Strong momentum: {current_momentum:.2%}",
                    f"Positive acceleration: {acceleration:.2%}",
                    f"Volume surge: {recent_volume/avg_volume:.1f}x"
                ]
            )
            signals.append(signal)
        
        # Momentum Short
        elif (current_momentum < -self.params['momentum_threshold'] and 
              acceleration < 0 and volume_confirmed):
            
            confidence = self._calculate_momentum_confidence(df, 'short')
            
            signal = PatternSignal(
                signal_type=SignalType.MOMENTUM_SHORT,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=current_price * 0.97,
                stop_loss=current_price * 1.015,
                expected_return=0.03,
                risk_reward=2.0,
                pattern_data={
                    'momentum': current_momentum,
                    'acceleration': acceleration,
                    'volume_ratio': recent_volume / avg_volume,
                },
                supporting_evidence=[
                    f"Negative momentum: {current_momentum:.2%}",
                    f"Negative acceleration: {acceleration:.2%}",
                    f"Volume surge: {recent_volume/avg_volume:.1f}x"
                ]
            )
            signals.append(signal)
        
        return signals
    
    def _detect_mean_reversion(self, df: pd.DataFrame, market: Dict) -> List[PatternSignal]:
        """Detect mean reversion patterns."""
        signals = []
        
        if len(df) < 30:
            return signals
        
        # Calculate Bollinger Bands
        df['sma_20'] = df['price'].rolling(20).mean()
        df['std_20'] = df['price'].rolling(20).std()
        df['upper_band'] = df['sma_20'] + 2 * df['std_20']
        df['lower_band'] = df['sma_20'] - 2 * df['std_20']
        df['z_score'] = (df['price'] - df['sma_20']) / df['std_20']
        
        current_price = df['price'].iloc[-1]
        z_score = df['z_score'].iloc[-1]
        
        # Check for extreme deviation with reversal signs
        recent_candles = df.tail(5)
        
        # Mean Reversion Long (oversold)
        if z_score < -2 and self._has_reversal_signs(recent_candles, 'long'):
            confidence = min(0.9, abs(z_score) / 3)
            
            signal = PatternSignal(
                signal_type=SignalType.MEAN_REVERSION_LONG,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=df['sma_20'].iloc[-1],  # Target the mean
                stop_loss=current_price * 0.98,
                expected_return=(df['sma_20'].iloc[-1] / current_price) - 1,
                risk_reward=1.5,
                pattern_data={'z_score': z_score},
                supporting_evidence=[
                    f"Extreme oversold: Z-score = {z_score:.2f}",
                    "Reversal candlestick pattern detected"
                ]
            )
            signals.append(signal)
        
        # Mean Reversion Short (overbought)
        elif z_score > 2 and self._has_reversal_signs(recent_candles, 'short'):
            confidence = min(0.9, abs(z_score) / 3)
            
            signal = PatternSignal(
                signal_type=SignalType.MEAN_REVERSION_SHORT,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=df['sma_20'].iloc[-1],
                stop_loss=current_price * 1.02,
                expected_return=1 - (df['sma_20'].iloc[-1] / current_price),
                risk_reward=1.5,
                pattern_data={'z_score': z_score},
                supporting_evidence=[
                    f"Extreme overbought: Z-score = {z_score:.2f}",
                    "Reversal candlestick pattern detected"
                ]
            )
            signals.append(signal)
        
        return signals
    
    def _detect_breakouts(self, df: pd.DataFrame, market: Dict) -> List[PatternSignal]:
        """Detect breakout patterns."""
        signals = []
        
        if len(df) < 50:
            return signals
        
        # Find recent support/resistance levels
        prices = df['price'].values
        
        # Find local peaks (resistance) and troughs (support)
        peaks, _ = find_peaks(prices, distance=10, prominence=0.01)
        troughs, _ = find_peaks(-prices, distance=10, prominence=0.01)
        
        if len(peaks) < 2 or len(troughs) < 2:
            return signals
        
        resistance_levels = prices[peaks]
        support_levels = prices[troughs]
        
        current_price = prices[-1]
        
        # Check for range breakout
        recent_range = prices[-30:]
        range_high = recent_range.max()
        range_low = recent_range.min()
        
        # Breakout Long
        if current_price > range_high * 0.995:  # Within 0.5% of range high
            # Check for confirmation
            confirmation = sum(prices[-5:] > range_high * 0.99) >= 3
            
            if confirmation:
                confidence = 0.7
                
                signal = PatternSignal(
                    signal_type=SignalType.BREAKOUT_LONG,
                    confidence=self._score_to_confidence(confidence),
                    confidence_score=confidence,
                    timestamp=datetime.now(),
                    market_id=market.get('market_id', ''),
                    entry_price=current_price,
                    target_price=current_price + (range_high - range_low),
                    stop_loss=range_high * 0.99,
                    expected_return=(range_high - range_low) / current_price,
                    risk_reward=2.5,
                    pattern_data={
                        'range_high': range_high,
                        'range_low': range_low,
                        'range_size': range_high - range_low
                    },
                    supporting_evidence=[
                        f"Break above range high: ${range_high:.4f}",
                        f"Range size: ${range_high - range_low:.4f}"
                    ]
                )
                signals.append(signal)
        
        # Breakout Short
        elif current_price < range_low * 1.005:
            confirmation = sum(prices[-5:] < range_low * 1.01) >= 3
            
            if confirmation:
                confidence = 0.7
                
                signal = PatternSignal(
                    signal_type=SignalType.BREAKOUT_SHORT,
                    confidence=self._score_to_confidence(confidence),
                    confidence_score=confidence,
                    timestamp=datetime.now(),
                    market_id=market.get('market_id', ''),
                    entry_price=current_price,
                    target_price=current_price - (range_high - range_low),
                    stop_loss=range_low * 1.01,
                    expected_return=(range_high - range_low) / current_price,
                    risk_reward=2.5,
                    pattern_data={
                        'range_high': range_high,
                        'range_low': range_low,
                    },
                    supporting_evidence=[
                        f"Break below range low: ${range_low:.4f}",
                        f"Range size: ${range_high - range_low:.4f}"
                    ]
                )
                signals.append(signal)
        
        return signals
    
    def _detect_whale_patterns(self, df: pd.DataFrame, market: Dict) -> List[PatternSignal]:
        """Detect whale accumulation/distribution patterns."""
        signals = []
        
        if 'is_whale' not in df.columns:
            return signals
        
        whale_trades = df[df['is_whale'] == True]
        
        if len(whale_trades) < 3:
            return signals
        
        current_price = df['price'].iloc[-1]
        
        # Whale buying pressure
        whale_buys = whale_trades[whale_trades['side'] == 'buy']
        whale_sells = whale_trades[whale_trades['side'] == 'sell']
        
        buy_volume = whale_buys['size'].sum() if not whale_buys.empty else 0
        sell_volume = whale_sells['size'].sum() if not whale_sells.empty else 0
        total_whale_volume = buy_volume + sell_volume
        
        if total_whale_volume == 0:
            return signals
        
        buy_ratio = buy_volume / total_whale_volume
        
        # Whale Accumulation
        if buy_ratio > self.params['whale_imbalance_threshold']:
            confidence = buy_ratio
            
            signal = PatternSignal(
                signal_type=SignalType.WHALE_ACCUMULATION,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=current_price * 1.02,
                stop_loss=current_price * 0.99,
                expected_return=0.02,
                risk_reward=2.0,
                pattern_data={
                    'whale_buy_ratio': buy_ratio,
                    'whale_volume': total_whale_volume,
                    'num_whale_trades': len(whale_trades)
                },
                supporting_evidence=[
                    f"Whale buying: {buy_ratio:.1%} of volume",
                    f"{len(whale_trades)} whale trades detected"
                ]
            )
            signals.append(signal)
        
        # Whale Distribution
        elif buy_ratio < (1 - self.params['whale_imbalance_threshold']):
            confidence = 1 - buy_ratio
            
            signal = PatternSignal(
                signal_type=SignalType.WHALE_DISTRIBUTION,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=current_price * 0.98,
                stop_loss=current_price * 1.01,
                expected_return=0.02,
                risk_reward=2.0,
                pattern_data={
                    'whale_sell_ratio': 1 - buy_ratio,
                    'whale_volume': total_whale_volume,
                },
                supporting_evidence=[
                    f"Whale selling: {1-buy_ratio:.1%} of volume",
                    f"{len(whale_trades)} whale trades detected"
                ]
            )
            signals.append(signal)
        
        return signals
    
    def _detect_liquidity_grabs(self, df: pd.DataFrame, market: Dict) -> List[PatternSignal]:
        """Detect liquidity grab patterns (fakeouts)."""
        signals = []
        
        if len(df) < 20:
            return signals
        
        # Look for quick moves that reverse
        recent = df.tail(10)
        
        # Spike followed by immediate reversal
        price_change = (recent['price'].iloc[-1] - recent['price'].iloc[0]) / recent['price'].iloc[0]
        max_move = (recent['price'].max() - recent['price'].min()) / recent['price'].mean()
        
        # Large range but little net change = potential liquidity grab
        if max_move > 0.02 and abs(price_change) < 0.005:
            confidence = 0.6
            
            current_price = df['price'].iloc[-1]
            
            signal = PatternSignal(
                signal_type=SignalType.LIQUIDITY_GRAB,
                confidence=self._score_to_confidence(confidence),
                confidence_score=confidence,
                timestamp=datetime.now(),
                market_id=market.get('market_id', ''),
                entry_price=current_price,
                target_price=current_price * (1.015 if price_change > 0 else 0.985),
                stop_loss=recent['price'].min() if price_change > 0 else recent['price'].max(),
                expected_return=0.015,
                risk_reward=1.5,
                pattern_data={
                    'range': max_move,
                    'net_change': price_change,
                },
                supporting_evidence=[
                    f"Large range: {max_move:.2%}",
                    f"Small net change: {price_change:.2%}",
                    "Potential stop hunt / liquidity grab"
                ]
            )
            signals.append(signal)
        
        return signals
    
    def _has_reversal_signs(self, df: pd.DataFrame, direction: str) -> bool:
        """Check for candlestick reversal patterns."""
        if len(df) < 3:
            return False
        
        prices = df['price'].values
        
        # Simple reversal detection
        if direction == 'long':
            # Higher lows
            return prices[-1] > prices[-2] and prices[-2] > prices[-3]
        else:
            # Lower highs
            return prices[-1] < prices[-2] and prices[-2] < prices[-3]
    
    def _calculate_momentum_confidence(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate confidence score for momentum signal."""
        confidence = 0.5
        
        # Volume confirmation
        avg_volume = df['size'].mean()
        recent_volume = df['size'].tail(5).mean()
        if recent_volume > avg_volume * 2:
            confidence += 0.15
        
        # Trend consistency
        prices = df['price'].tail(10).values
        if direction == 'long':
            consistent = sum(prices[i] < prices[i+1] for i in range(len(prices)-1))
        else:
            consistent = sum(prices[i] > prices[i+1] for i in range(len(prices)-1))
        
        confidence += (consistent / len(prices)) * 0.2
        
        # Whale participation
        if 'is_whale' in df.columns:
            recent_whale_pct = df.tail(5)['is_whale'].mean()
            confidence += recent_whale_pct * 0.15
        
        return min(0.95, confidence)
    
    def _score_to_confidence(self, score: float) -> PatternConfidence:
        """Convert score to confidence level."""
        if score >= 0.85:
            return PatternConfidence.HIGH
        elif score >= 0.6:
            return PatternConfidence.MEDIUM
        return PatternConfidence.LOW
    
    def _filter_signals(self, signals: List[PatternSignal]) -> List[PatternSignal]:
        """Filter and rank signals."""
        if not signals:
            return signals
        
        # Remove conflicting signals
        long_signals = [s for s in signals if s.direction == 'LONG']
        short_signals = [s for s in signals if s.direction == 'SHORT']
        
        # Keep only highest confidence from each direction
        result = []
        
        if long_signals:
            best_long = max(long_signals, key=lambda s: s.confidence_score)
            if best_long.confidence_score > 0.5:
                result.append(best_long)
        
        if short_signals:
            best_short = max(short_signals, key=lambda s: s.confidence_score)
            if best_short.confidence_score > 0.5:
                result.append(best_short)
        
        # Sort by confidence
        result.sort(key=lambda s: s.confidence_score, reverse=True)
        
        return result[:2]  # Return top 2 signals max
    
    def get_pattern_statistics(self, lookback_days: int = 7) -> pd.DataFrame:
        """Get statistics on pattern performance."""
        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent_patterns = [p for p in self.pattern_history if p.timestamp > cutoff]
        
        if not recent_patterns:
            return pd.DataFrame()
        
        stats = []
        for signal_type in SignalType:
            type_patterns = [p for p in recent_patterns if p.signal_type == signal_type]
            if not type_patterns:
                continue
            
            stats.append({
                'pattern': signal_type.value,
                'count': len(type_patterns),
                'avg_confidence': np.mean([p.confidence_score for p in type_patterns]),
            })
        
        return pd.DataFrame(stats).sort_values('count', ascending=False)
