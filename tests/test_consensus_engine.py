"""Tests for the consensus engine."""

import pytest
import pandas as pd
import numpy as np
from polymarket_tracker.analysis.consensus_engine import (
    ConsensusEngine,
    ConsensusResult
)


class TestConsensusEngine:
    """Test cases for consensus engine."""
    
    def test_init(self):
        """Test engine initialization."""
        engine = ConsensusEngine()
        assert engine is not None
    
    def test_calculate_weights(self):
        """Test weight calculation."""
        profiles = {
            '0x1': {'true_win_rate': 70, 'total_pnl': 100000, 'vanity_gap': 10},
            '0x2': {'true_win_rate': 40, 'total_pnl': -50000, 'vanity_gap': 30},
        }
        
        engine = ConsensusEngine(profiles)
        weights = engine.weights
        
        # Higher win rate should have higher weight
        assert weights['0x1'] > weights['0x2']
    
    def test_calculate_consensus_yes(self):
        """Test YES consensus calculation."""
        engine = ConsensusEngine()
        
        positions = pd.DataFrame({
            'wallet': ['0x1', '0x2', '0x3'],
            'outcomeIndex': [0, 0, 1],  # YES, YES, NO
            'amount': [10000, 5000, 2000]
        })
        
        result = engine.calculate_consensus('market1', positions)
        
        assert result.consensus == 'YES'
        assert result.confidence > 0
        assert result.total_whale_volume == 17000
    
    def test_calculate_consensus_no(self):
        """Test NO consensus calculation."""
        engine = ConsensusEngine()
        
        positions = pd.DataFrame({
            'wallet': ['0x1', '0x2', '0x3'],
            'outcomeIndex': [1, 1, 0],  # NO, NO, YES
            'amount': [10000, 8000, 1000]
        })
        
        result = engine.calculate_consensus('market1', positions)
        
        assert result.consensus == 'NO'
        assert result.confidence > 0
    
    def test_empty_positions(self):
        """Test with empty positions."""
        engine = ConsensusEngine()
        
        result = engine.calculate_consensus('market1', pd.DataFrame())
        
        assert result.consensus is None
        assert result.confidence == 0
    
    def test_calculate_kelly(self):
        """Test Kelly Criterion calculation."""
        engine = ConsensusEngine()
        
        result = ConsensusResult(
            market_id='m1',
            consensus='YES',
            confidence=0.8,
            whale_probability=0.7,
            market_probability=0.5,
            divergence=0.2,
            total_whale_volume=10000,
            num_whales=3,
            whale_positions=[]
        )
        
        kelly = engine._calculate_kelly(result)
        
        # Should be positive for favorable odds
        assert kelly > 0
        assert kelly < 1  # Should be less than full bankroll
    
    def test_detect_disagreement(self):
        """Test disagreement detection."""
        engine = ConsensusEngine()
        
        positions = pd.DataFrame({
            'market_id': ['m1', 'm1', 'm1', 'm2', 'm2'],
            'wallet': ['0x1', '0x2', '0x3', '0x1', '0x2'],
            'outcomeIndex': [0, 1, 0, 0, 0]  # m1 has disagreement
        })
        
        disagreements = engine.detect_disagreement(positions, min_whale_count=2)
        
        assert len(disagreements) >= 1
        # m1 should have disagreement (YES and NO)
        m1_disagreement = [d for d in disagreements if d['market_id'] == 'm1']
        assert len(m1_disagreement) == 1
    
    def test_has_edge(self):
        """Test edge detection."""
        result_with_edge = ConsensusResult(
            market_id='m1',
            consensus='YES',
            confidence=0.8,
            whale_probability=0.7,
            market_probability=0.5,
            divergence=0.2,
            total_whale_volume=10000,
            num_whales=3,
            whale_positions=[]
        )
        
        result_no_edge = ConsensusResult(
            market_id='m2',
            consensus='YES',
            confidence=0.8,
            whale_probability=0.52,
            market_probability=0.5,
            divergence=0.02,
            total_whale_volume=10000,
            num_whales=3,
            whale_positions=[]
        )
        
        assert result_with_edge.has_edge(threshold=0.1) is True
        assert result_no_edge.has_edge(threshold=0.1) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
