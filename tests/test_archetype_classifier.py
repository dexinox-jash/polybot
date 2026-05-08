"""Tests for the archetype classifier."""

import pytest
import pandas as pd
from polymarket_tracker.analysis.archetype_classifier import (
    ArchetypeClassifier,
    ArchetypeFeatures,
    TraderArchetype
)


class TestArchetypeClassifier:
    """Test cases for archetype classification."""
    
    def test_init(self):
        """Test classifier initialization."""
        classifier = ArchetypeClassifier()
        assert classifier is not None
        assert len(classifier.archetype_profiles) == 6
    
    def test_classify_hedger(self):
        """Test hedger classification."""
        classifier = ArchetypeClassifier()
        
        features = ArchetypeFeatures(
            hedge_ratio=0.5,
            num_directions_per_event=5,
            trades_per_day=2
        )
        
        archetype, scores = classifier.classify(features)
        
        # Should be either hedger or probability transformer
        assert archetype in [TraderArchetype.HEDGER, TraderArchetype.PROBABILITY_TRANSFORMER]
    
    def test_classify_speed_trader(self):
        """Test speed trader classification."""
        classifier = ArchetypeClassifier()
        
        features = ArchetypeFeatures(
            trades_per_day=20,
            hedge_ratio=0.1
        )
        
        archetype, scores = classifier.classify(features)
        
        assert archetype == TraderArchetype.SPEED_TRADER
    
    def test_classify_domain_expert(self):
        """Test domain expert classification."""
        classifier = ArchetypeClassifier()
        
        features = ArchetypeFeatures(
            trades_per_day=0.5,
            category_concentration=0.8
        )
        
        archetype, scores = classifier.classify(features)
        
        assert archetype == TraderArchetype.DOMAIN_EXPERT
    
    def test_get_archetype_description(self):
        """Test getting archetype descriptions."""
        classifier = ArchetypeClassifier()
        
        desc = classifier.get_archetype_description(TraderArchetype.HEDGER)
        
        assert 'description' in desc
        assert 'key_traits' in desc
        assert len(desc['key_traits']) > 0
    
    def test_extract_features(self):
        """Test feature extraction."""
        classifier = ArchetypeClassifier()
        
        trades = pd.DataFrame({
            'size': [100, 200, 300]
        })
        
        positions = pd.DataFrame()
        
        wallet_profile = {
            'trades_per_day': 5.0,
            'hedge_ratio': 0.3
        }
        
        features = classifier.extract_features(trades, positions, wallet_profile)
        
        assert features.trades_per_day == 5.0
        assert features.hedge_ratio == 0.3
        assert features.avg_position_size == 200.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
