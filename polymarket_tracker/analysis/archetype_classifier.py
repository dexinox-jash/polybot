"""
Strategy Archetype Classifier for Polymarket Whales.

Implements the six archetypes from research:
1. Hedger (SeriouslySirius) - Complex quantitative hedging
2. ProbabilityTransformer (DrPufferfish) - Probability transformation
3. SpeedTrader (gmanas) - High-frequency automation
4. SwingTrader (simonbanza) - Swing trading on probability moves
5. MicroArbitrageur (Swisstony) - Micro-arbitrage
6. DomainExpert (0xafEe) - Specialized information
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import setup_logging

logger = setup_logging()


class TraderArchetype(Enum):
    """Trader archetype classifications."""
    HEDGER = "hedger"
    PROBABILITY_TRANSFORMER = "probability_transformer"
    SPEED_TRADER = "speed_trader"
    SWING_TRADER = "swing_trader"
    MICRO_ARBITRAGEUR = "micro_arbitrageur"
    DOMAIN_EXPERT = "domain_expert"
    UNKNOWN = "unknown"


@dataclass
class ArchetypeFeatures:
    """Features used for archetype classification."""
    # Trading frequency
    trades_per_day: float = 0.0
    avg_hold_time_hours: float = 0.0
    
    # Strategy indicators
    hedge_ratio: float = 0.0  # Multi-directional / total bets
    num_directions_per_event: float = 0.0
    
    # Risk metrics
    risk_reward_ratio: float = 0.0
    avg_position_size: float = 0.0
    position_size_variance: float = 0.0
    
    # Category concentration
    category_concentration: float = 0.0  # Herfindahl index
    primary_category: Optional[str] = None
    
    # Win metrics
    true_win_rate: float = 0.0
    win_rate_variance: float = 0.0
    
    # Arbitrage indicators
    arbitrage_frequency: float = 0.0  # Bets where YES+NO < 1.0


class ArchetypeClassifier:
    """
    Classifier for identifying whale trading archetypes.
    
    Based on research of 27,000+ transactions from top performers.
    """
    
    # Thresholds for classification
    THRESHOLDS = {
        'hedger': {
            'min_hedge_ratio': 0.3,
            'min_directions_per_event': 3,
        },
        'speed_trader': {
            'min_trades_per_day': 10,
            'max_avg_hold_hours': 24,
        },
        'swing_trader': {
            'min_hold_hours': 1,
            'max_hold_hours': 168,  # 1 week
            'max_hedge_ratio': 0.2,
        },
        'micro_arbitrageur': {
            'min_arbitrage_freq': 0.2,
            'min_trades_per_day': 5,
        },
        'probability_transformer': {
            'min_hedge_ratio': 0.5,
            'min_directions_per_event': 10,
        },
        'domain_expert': {
            'min_category_concentration': 0.7,
            'max_trades_per_day': 5,
        },
    }
    
    def __init__(self):
        """Initialize the archetype classifier."""
        self.archetype_profiles = self._init_archetype_profiles()
    
    def _init_archetype_profiles(self) -> Dict:
        """Initialize reference profiles for each archetype."""
        return {
            TraderArchetype.HEDGER: {
                'description': 'Complex quantitative hedging across multiple outcomes',
                'key_traits': [
                    'Bets on 3+ directions per event simultaneously',
                    'Automated arbitrage when sum of probabilities < 1.0',
                    'Leaves losing positions open (zombie orders)',
                ],
                'typical_win_rate': 0.73,
                'typical_vanity_gap': 0.20,  # Displayed - True
            },
            TraderArchetype.PROBABILITY_TRANSFORMER: {
                'description': 'Transforms low-probability bets into synthetic high-probability positions',
                'key_traits': [
                    'Bets on 10+ low-probability outcomes simultaneously',
                    'Strict risk/reward management (high ratio)',
                    'Cuts losses early',
                ],
                'typical_win_rate': 0.835,
                'typical_vanity_gap': 0.326,
            },
            TraderArchetype.SPEED_TRADER: {
                'description': 'High-frequency algorithmic execution',
                'key_traits': [
                    '2400+ predictions via algorithm',
                    'Assembly-line approach',
                    'Low individual trade size',
                ],
                'typical_win_rate': 0.52,
                'typical_vanity_gap': 0.02,
            },
            TraderArchetype.SWING_TRADER: {
                'description': 'Treats probability like candlestick charts',
                'key_traits': [
                    'Takes profits at probability swings',
                    'Does not wait for settlement',
                    'Minimal zombie orders',
                ],
                'typical_win_rate': 0.576,
                'typical_vanity_gap': 0.05,
            },
            TraderArchetype.MICRO_ARBITRAGEUR: {
                'description': 'Mathematical edge from YES+NO < $1.00',
                'key_traits': [
                    'Highest trade frequency (5000+)',
                    'Small avg profit per trade (~$156)',
                    '"Ant-moving" strategy',
                ],
                'typical_win_rate': 0.51,
                'typical_vanity_gap': 0.01,
            },
            TraderArchetype.DOMAIN_EXPERT: {
                'description': 'Specialized information in narrow categories',
                'key_traits': [
                    'Only 0.4 trades/day',
                    'Specializes in specific category (sports/crypto/politics)',
                    'Contrarian to majority',
                ],
                'typical_win_rate': 0.695,
                'typical_vanity_gap': 0.15,
            },
        }
    
    def extract_features(
        self,
        trades: pd.DataFrame,
        positions: pd.DataFrame,
        wallet_profile: Dict
    ) -> ArchetypeFeatures:
        """
        Extract features from wallet data for classification.
        
        Args:
            trades: DataFrame of trades
            positions: DataFrame of positions
            wallet_profile: Wallet profile data
            
        Returns:
            ArchetypeFeatures object
        """
        features = ArchetypeFeatures()
        
        if trades.empty:
            return features
        
        # Trading frequency
        features.trades_per_day = wallet_profile.get('trades_per_day', 0)
        
        # Hedge ratio
        features.hedge_ratio = wallet_profile.get('hedge_ratio', 0)
        
        # Calculate directions per event
        if not trades.empty and 'market' in trades.columns:
            market_sides = {}
            for _, trade in trades.iterrows():
                market = trade.get('market', {}) if isinstance(trade.get('market'), dict) else {}
                market_id = market.get('id', '')
                side = trade.get('side', '')
                
                if market_id not in market_sides:
                    market_sides[market_id] = set()
                market_sides[market_id].add(side)
            
            if market_sides:
                features.num_directions_per_event = np.mean([
                    len(sides) for sides in market_sides.values()
                ])
        
        # Average position size
        if 'size' in trades.columns:
            features.avg_position_size = trades['size'].mean()
            features.position_size_variance = trades['size'].var()
        
        # Win rate
        features.true_win_rate = wallet_profile.get('true_win_rate', 0) / 100
        
        return features
    
    def classify(self, features: ArchetypeFeatures) -> Tuple[TraderArchetype, Dict]:
        """
        Classify a trader based on their features.
        
        Args:
            features: Extracted features
            
        Returns:
            Tuple of (archetype, confidence scores)
        """
        scores = {}
        
        # Hedger score
        if (features.hedge_ratio >= self.THRESHOLDS['hedger']['min_hedge_ratio'] and
            features.num_directions_per_event >= self.THRESHOLDS['hedger']['min_directions_per_event']):
            scores[TraderArchetype.HEDGER] = 0.9
        else:
            scores[TraderArchetype.HEDGER] = features.hedge_ratio * 0.5
        
        # Probability Transformer score
        if (features.hedge_ratio >= self.THRESHOLDS['probability_transformer']['min_hedge_ratio'] and
            features.num_directions_per_event >= self.THRESHOLDS['probability_transformer']['min_directions_per_event']):
            scores[TraderArchetype.PROBABILITY_TRANSFORMER] = 0.95
        else:
            scores[TraderArchetype.PROBABILITY_TRANSFORMER] = features.hedge_ratio * 0.3
        
        # Speed Trader score
        if (features.trades_per_day >= self.THRESHOLDS['speed_trader']['min_trades_per_day']):
            scores[TraderArchetype.SPEED_TRADER] = min(0.95, features.trades_per_day / 50)
        else:
            scores[TraderArchetype.SPEED_TRADER] = features.trades_per_day / 100
        
        # Swing Trader score
        if (self.THRESHOLDS['swing_trader']['min_hold_hours'] <= features.avg_hold_time_hours <= 
            self.THRESHOLDS['swing_trader']['max_hold_hours']):
            if features.hedge_ratio < self.THRESHOLDS['swing_trader']['max_hedge_ratio']:
                scores[TraderArchetype.SWING_TRADER] = 0.7
            else:
                scores[TraderArchetype.SWING_TRADER] = 0.3
        else:
            scores[TraderArchetype.SWING_TRADER] = 0.1
        
        # Micro Arbitrageur score
        if features.trades_per_day >= self.THRESHOLDS['micro_arbitrageur']['min_trades_per_day']:
            scores[TraderArchetype.MICRO_ARBITRAGEUR] = min(0.9, features.trades_per_day / 100)
        else:
            scores[TraderArchetype.MICRO_ARBITRAGEUR] = 0.1
        
        # Domain Expert score
        if features.category_concentration >= self.THRESHOLDS['domain_expert']['min_category_concentration']:
            if features.trades_per_day <= self.THRESHOLDS['domain_expert']['max_trades_per_day']:
                scores[TraderArchetype.DOMAIN_EXPERT] = 0.85
            else:
                scores[TraderArchetype.DOMAIN_EXPERT] = 0.4
        else:
            scores[TraderArchetype.DOMAIN_EXPERT] = 0.2
        
        # Find highest scoring archetype
        if scores:
            best_archetype = max(scores, key=scores.get)
            best_score = scores[best_archetype]
            
            # Only return if confidence is high enough
            if best_score >= 0.5:
                return best_archetype, scores
        
        return TraderArchetype.UNKNOWN, scores
    
    def get_archetype_description(self, archetype: TraderArchetype) -> Dict:
        """
        Get description and traits for an archetype.
        
        Args:
            archetype: The archetype to describe
            
        Returns:
            Dictionary with description and traits
        """
        return self.archetype_profiles.get(archetype, {
            'description': 'Unknown trading pattern',
            'key_traits': [],
            'typical_win_rate': 0.5,
            'typical_vanity_gap': 0.0,
        })
    
    def analyze_wallet(
        self,
        trades: pd.DataFrame,
        positions: pd.DataFrame,
        wallet_profile: Dict
    ) -> Dict:
        """
        Full analysis of a wallet's archetype.
        
        Args:
            trades: DataFrame of trades
            positions: DataFrame of positions
            wallet_profile: Wallet profile data
            
        Returns:
            Analysis results
        """
        features = self.extract_features(trades, positions, wallet_profile)
        archetype, confidence_scores = self.classify(features)
        profile = self.get_archetype_description(archetype)
        
        return {
            'archetype': archetype.value,
            'confidence': confidence_scores.get(archetype, 0),
            'all_scores': {k.value: v for k, v in confidence_scores.items()},
            'description': profile['description'],
            'key_traits': profile['key_traits'],
            'typical_win_rate': profile['typical_win_rate'],
            'typical_vanity_gap': profile['typical_vanity_gap'],
            'features': {
                'trades_per_day': features.trades_per_day,
                'hedge_ratio': features.hedge_ratio,
                'num_directions_per_event': features.num_directions_per_event,
                'avg_position_size': features.avg_position_size,
            }
        }
