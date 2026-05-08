"""
Consensus Engine for Whale Sentiment Analysis.

Calculates whale confidence scores and generates predictions based on
weighted whale positions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from ..utils.logger import setup_logging

logger = setup_logging()


@dataclass
class ConsensusResult:
    """Result of consensus calculation."""
    market_id: str
    consensus: Optional[str]  # 'YES', 'NO', or None
    confidence: float  # 0.0 to 1.0
    whale_probability: float  # Whale-implied probability
    market_probability: float  # Current market price
    divergence: float  # Difference between whale and market
    total_whale_volume: float
    num_whales: int
    whale_positions: List[Dict]
    
    def has_edge(self, threshold: float = 0.1) -> bool:
        """Check if there's a significant edge vs market."""
        return abs(self.divergence) >= threshold


class ConsensusEngine:
    """
    Engine for calculating whale consensus and generating signals.
    """
    
    def __init__(self, whale_profiles: Dict[str, Dict] = None):
        """
        Initialize consensus engine.
        
        Args:
            whale_profiles: Dictionary of whale addresses to their profiles
        """
        self.whale_profiles = whale_profiles or {}
        self.weights = self._calculate_weights()
    
    def _calculate_weights(self) -> Dict[str, float]:
        """
        Calculate weights for each whale based on historical performance.
        
        Uses Kelly Criterion-inspired weighting:
        - Higher true win rate = higher weight
        - Lower variance = higher weight
        - Recency bias: recent performance weighted more
        
        Returns:
            Dictionary of whale address to weight
        """
        weights = {}
        
        for address, profile in self.whale_profiles.items():
            true_wr = profile.get('true_win_rate', 50) / 100
            
            # Base weight on true win rate (min 0.1, max 2.0)
            base_weight = max(0.1, min(2.0, (true_wr - 0.5) * 4))
            
            # Adjust for PnL (whales with positive PnL get bonus)
            pnl = profile.get('total_pnl', 0)
            pnl_multiplier = 1.0 + (pnl / 100000) if pnl > 0 else 0.8
            pnl_multiplier = max(0.5, min(2.0, pnl_multiplier))
            
            # Adjust for consistency (low vanity gap = more trustworthy)
            vanity_gap = profile.get('vanity_gap', 20)
            consistency_multiplier = 1.0 - (vanity_gap / 100)
            consistency_multiplier = max(0.5, min(1.0, consistency_multiplier))
            
            weight = base_weight * pnl_multiplier * consistency_multiplier
            weights[address] = weight
        
        return weights
    
    def calculate_consensus(
        self,
        market_id: str,
        whale_positions: pd.DataFrame
    ) -> ConsensusResult:
        """
        Calculate whale consensus for a market.
        
        Args:
            market_id: Market condition ID
            whale_positions: DataFrame of whale positions
            
        Returns:
            ConsensusResult
        """
        if whale_positions.empty:
            return ConsensusResult(
                market_id=market_id,
                consensus=None,
                confidence=0,
                whale_probability=0.5,
                market_probability=0.5,
                divergence=0,
                total_whale_volume=0,
                num_whales=0,
                whale_positions=[]
            )
        
        # Calculate weighted positions
        weighted_yes = 0
        weighted_no = 0
        
        for _, pos in whale_positions.iterrows():
            wallet = pos.get('wallet', '').lower()
            weight = self.weights.get(wallet, 1.0)
            amount = pos.get('amount', 0)
            outcome = pos.get('outcomeIndex', 0)
            
            if outcome == 0:  # YES
                weighted_yes += amount * weight
            else:  # NO
                weighted_no += amount * weight
        
        total_weighted = weighted_yes + weighted_no
        
        if total_weighted == 0:
            whale_prob = 0.5
        else:
            whale_prob = weighted_yes / total_weighted
        
        # Get market probability (from latest price)
        # In practice, this would come from market data
        market_prob = self._get_market_probability(market_id)
        
        # Calculate consensus
        if whale_prob > 0.6:
            consensus = 'YES'
            confidence = (whale_prob - 0.5) * 2  # Scale to 0-1
        elif whale_prob < 0.4:
            consensus = 'NO'
            confidence = (0.5 - whale_prob) * 2
        else:
            consensus = None
            confidence = 0
        
        confidence = min(1.0, max(0, confidence))
        
        # Calculate divergence
        divergence = whale_prob - market_prob
        
        return ConsensusResult(
            market_id=market_id,
            consensus=consensus,
            confidence=confidence,
            whale_probability=whale_prob,
            market_probability=market_prob,
            divergence=divergence,
            total_whale_volume=whale_positions['amount'].sum(),
            num_whales=whale_positions['wallet'].nunique(),
            whale_positions=whale_positions.to_dict('records')
        )
    
    def _get_market_probability(self, market_id: str) -> float:
        """
        Get current market probability from price.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Market-implied probability (0-1)
        """
        # This would integrate with market data
        # For now, return 0.5 as default
        return 0.5
    
    def generate_signals(
        self,
        consensus_results: List[ConsensusResult],
        min_confidence: float = 0.6,
        min_divergence: float = 0.1
    ) -> List[Dict]:
        """
        Generate trading signals from consensus results.
        
        Args:
            consensus_results: List of consensus calculations
            min_confidence: Minimum confidence threshold
            min_divergence: Minimum divergence threshold
            
        Returns:
            List of signal dictionaries
        """
        signals = []
        
        for result in consensus_results:
            if result.consensus is None:
                continue
            
            if result.confidence < min_confidence:
                continue
            
            if abs(result.divergence) < min_divergence:
                continue
            
            signal = {
                'market_id': result.market_id,
                'signal': result.consensus,
                'confidence': result.confidence,
                'expected_edge': abs(result.divergence),
                'whale_probability': result.whale_probability,
                'market_probability': result.market_probability,
                'divergence': result.divergence,
                'supporting_whales': result.num_whales,
                'whale_volume': result.total_whale_volume,
                'kelly_criterion': self._calculate_kelly(result),
            }
            
            signals.append(signal)
        
        # Sort by expected edge
        signals.sort(key=lambda x: x['expected_edge'], reverse=True)
        
        return signals
    
    def _calculate_kelly(self, result: ConsensusResult) -> float:
        """
        Calculate Kelly Criterion position sizing.
        
        Kelly % = (bp - q) / b
        where:
        - b = net odds received (decimal odds - 1)
        - p = probability of winning
        - q = probability of losing = 1 - p
        
        Args:
            result: Consensus result
            
        Returns:
            Kelly fraction (0 to 1, negative means don't bet)
        """
        p = result.whale_probability
        q = 1 - p
        
        # Assume fair odds based on whale probability
        if result.consensus == 'YES':
            b = (1 / result.market_probability) - 1 if result.market_probability > 0 else 1
        else:
            b = (1 / (1 - result.market_probability)) - 1 if result.market_probability < 1 else 1
        
        kelly = (b * p - q) / b if b > 0 else 0
        
        # Use half-Kelly for safety
        return max(0, kelly * 0.5)
    
    def detect_disagreement(
        self,
        whale_positions: pd.DataFrame,
        min_whale_count: int = 2
    ) -> List[Dict]:
        """
        Detect markets where whales disagree (indicating uncertainty).
        
        This is often more valuable than consensus - when top whales
        bet against each other, it signals high uncertainty.
        
        Args:
            whale_positions: DataFrame of whale positions
            min_whale_count: Minimum whales to consider
            
        Returns:
            List of disagreement events
        """
        disagreements = []
        
        # Group by market
        market_groups = whale_positions.groupby('market_id')
        
        for market_id, group in market_groups:
            if len(group) < min_whale_count:
                continue
            
            # Count unique whales
            unique_whales = group['wallet'].nunique()
            if unique_whales < min_whale_count:
                continue
            
            # Check for disagreement
            outcomes = group['outcomeIndex'].unique()
            
            if len(outcomes) > 1:
                yes_whales = group[group['outcomeIndex'] == 0]['wallet'].nunique()
                no_whales = group[group['outcomeIndex'] == 1]['wallet'].nunique()
                
                if yes_whales > 0 and no_whales > 0:
                    # Calculate disagreement intensity
                    total = yes_whales + no_whales
                    balance = min(yes_whales, no_whales) / max(yes_whales, no_whales)
                    
                    disagreements.append({
                        'market_id': market_id,
                        'yes_whales': yes_whales,
                        'no_whales': no_whales,
                        'disagreement_score': balance,  # 1.0 = equal split
                        'uncertainty_signal': True,
                    })
        
        # Sort by disagreement score
        disagreements.sort(key=lambda x: x['disagreement_score'], reverse=True)
        
        return disagreements
    
    def smart_money_index(
        self,
        category: str,
        consensus_results: List[ConsensusResult]
    ) -> float:
        """
        Calculate Smart Money Index for a category.
        
        Weighted average of whale positions normalized by historical accuracy.
        
        Args:
            category: Market category (e.g., 'politics', 'sports')
            consensus_results: List of consensus results for category
            
        Returns:
            Smart Money Index (-1 to 1, positive = bullish)
        """
        if not consensus_results:
            return 0
        
        total_weight = 0
        weighted_sum = 0
        
        for result in consensus_results:
            if result.consensus is None:
                continue
            
            # Weight by confidence and volume
            weight = result.confidence * np.log1p(result.total_whale_volume)
            
            if result.consensus == 'YES':
                weighted_sum += weight
            else:
                weighted_sum -= weight
            
            total_weight += weight
        
        if total_weight == 0:
            return 0
        
        # Normalize to -1 to 1
        return weighted_sum / total_weight
