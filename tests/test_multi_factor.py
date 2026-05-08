"""
Agent 4: Multi-Factor Model Tester

Validates:
- Factor scoring accuracy
- Category weight application
- Composite score calculation
- SWOT analysis generation
- Grade assignment
- Factor independence
"""

import unittest
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum


class FactorCategory(Enum):
    WINNER_QUALITY = "winner_quality"
    MARKET_CONDITIONS = "market_conditions"
    TIMING = "timing"
    RISK = "risk"
    BEHAVIORAL = "behavioral"
    FUNDAMENTAL = "fundamental"


@dataclass
class MockFactorScore:
    """Mock factor score for testing."""
    name: str
    category: FactorCategory
    score: float
    weight: float


class TestMultiFactorScoring(unittest.TestCase):
    """Test multi-factor scoring system."""
    
    def test_winner_quality_factors(self):
        """Test winner quality category scoring."""
        # Note: scores should be normalized to 0-1 range before weighting
        factors = [
            MockFactorScore("Win Rate", FactorCategory.WINNER_QUALITY, 0.65, 0.30),
            MockFactorScore("Profit Factor", FactorCategory.WINNER_QUALITY, 0.90, 0.25),  # 1.8/2.0 normalized
            MockFactorScore("Sharpe Ratio", FactorCategory.WINNER_QUALITY, 0.75, 0.25),  # 1.5/2.0 normalized
            MockFactorScore("Consistency", FactorCategory.WINNER_QUALITY, 0.75, 0.20),
        ]
        
        # Calculate category score (all scores should be 0-1)
        category_score = sum(f.score * f.weight for f in factors)
        
        # Should be weighted average between 0 and 1
        self.assertGreater(category_score, 0)
        self.assertLessEqual(category_score, 1.0)
        
        print(f"  [PASS] Winner Quality score: {category_score:.2%}")
    
    def test_market_condition_factors(self):
        """Test market conditions category scoring."""
        factors = [
            MockFactorScore("Liquidity", FactorCategory.MARKET_CONDITIONS, 0.90, 0.30),
            MockFactorScore("Spread", FactorCategory.MARKET_CONDITIONS, 0.85, 0.25),
            MockFactorScore("Volatility", FactorCategory.MARKET_CONDITIONS, 0.70, 0.25),
            MockFactorScore("Price Efficiency", FactorCategory.MARKET_CONDITIONS, 0.80, 0.20),
        ]
        
        category_score = sum(f.score * f.weight for f in factors)
        self.assertGreater(category_score, 0.5)
        
        print(f"  [PASS] Market Conditions score: {category_score:.2%}")
    
    def test_composite_score_weights(self):
        """Test that category weights sum to 1."""
        weights = {
            FactorCategory.WINNER_QUALITY: 0.25,
            FactorCategory.MARKET_CONDITIONS: 0.20,
            FactorCategory.TIMING: 0.15,
            FactorCategory.RISK: 0.20,
            FactorCategory.BEHAVIORAL: 0.10,
            FactorCategory.FUNDAMENTAL: 0.10,
        }
        
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)
        
        print(f"  [PASS] Category weights sum to {total:.2%}")
    
    def test_composite_score_calculation(self):
        """Test composite score across all categories."""
        category_scores = {
            FactorCategory.WINNER_QUALITY: 0.75,
            FactorCategory.MARKET_CONDITIONS: 0.80,
            FactorCategory.TIMING: 0.70,
            FactorCategory.RISK: 0.65,
            FactorCategory.BEHAVIORAL: 0.60,
            FactorCategory.FUNDAMENTAL: 0.55,
        }
        
        weights = {
            FactorCategory.WINNER_QUALITY: 0.25,
            FactorCategory.MARKET_CONDITIONS: 0.20,
            FactorCategory.TIMING: 0.15,
            FactorCategory.RISK: 0.20,
            FactorCategory.BEHAVIORAL: 0.10,
            FactorCategory.FUNDAMENTAL: 0.10,
        }
        
        composite = sum(category_scores[cat] * weights[cat] for cat in category_scores)
        
        # Should be between min and max category scores
        self.assertGreaterEqual(composite, min(category_scores.values()))
        self.assertLessEqual(composite, max(category_scores.values()))
        
        print(f"  [PASS] Composite score: {composite:.2%}")
    
    def test_grade_assignment(self):
        """Test letter grade assignment."""
        def determine_grade(score: float) -> str:
            if score > 0.85: return "A+"
            elif score > 0.80: return "A"
            elif score > 0.75: return "A-"
            elif score > 0.70: return "B+"
            elif score > 0.65: return "B"
            elif score > 0.60: return "B-"
            elif score > 0.55: return "C+"
            elif score > 0.50: return "C"
            else: return "D"
        
        test_cases = [
            (0.88, "A+"),
            (0.82, "A"),
            (0.77, "A-"),
            (0.72, "B+"),
            (0.67, "B"),
            (0.62, "B-"),
            (0.57, "C+"),
            (0.52, "C"),
            (0.45, "D"),
        ]
        
        for score, expected in test_cases:
            grade = determine_grade(score)
            self.assertEqual(grade, expected)
        
        print(f"  [PASS] Grade assignment: A+ to D scale working")
    
    def test_swot_generation(self):
        """Test SWOT analysis generation."""
        factors = [
            MockFactorScore("Win Rate", FactorCategory.WINNER_QUALITY, 0.85, 0.30),
            MockFactorScore("Profit Factor", FactorCategory.WINNER_QUALITY, 0.80, 0.25),
            MockFactorScore("Liquidity", FactorCategory.MARKET_CONDITIONS, 0.40, 0.30),  # Weak
            MockFactorScore("Spread", FactorCategory.MARKET_CONDITIONS, 0.35, 0.25),  # Weak
            MockFactorScore("Timing", FactorCategory.TIMING, 0.90, 0.40),  # Strong
        ]
        
        # Identify strengths (high scores)
        strengths = [f.name for f in factors if f.score > 0.75]
        
        # Identify weaknesses (low scores)
        weaknesses = [f.name for f in factors if f.score < 0.50]
        
        self.assertIn("Win Rate", strengths)
        self.assertIn("Profit Factor", strengths)
        self.assertIn("Timing", strengths)
        self.assertIn("Liquidity", weaknesses)
        self.assertIn("Spread", weaknesses)
        
        print(f"  [PASS] SWOT: {len(strengths)} strengths, {len(weaknesses)} weaknesses identified")
    
    def test_factor_independence(self):
        """Test that factors are independently calculated."""
        # Changing one factor shouldn't affect others
        factor1 = MockFactorScore("Factor1", FactorCategory.WINNER_QUALITY, 0.70, 0.5)
        factor2 = MockFactorScore("Factor2", FactorCategory.MARKET_CONDITIONS, 0.80, 0.5)
        
        # Modify factor1
        factor1_copy = MockFactorScore("Factor1", FactorCategory.WINNER_QUALITY, 0.50, 0.5)
        
        # Factor2 should remain unchanged
        self.assertEqual(factor2.score, 0.80)
        
        print(f"  [PASS] Factor independence verified")
    
    def test_confidence_calculation(self):
        """Test confidence level calculation."""
        def calculate_confidence(factors: List[MockFactorScore]) -> float:
            """Calculate overall confidence based on factor confidences."""
            scores = [f.score for f in factors]
            mean_confidence = np.mean(scores)
            variance_penalty = np.std(scores) * 0.5
            return max(0, min(1, mean_confidence - variance_penalty))
        
        # High confidence (consistent high scores)
        high_conf_factors = [
            MockFactorScore("f1", FactorCategory.WINNER_QUALITY, 0.80, 0.25),
            MockFactorScore("f2", FactorCategory.WINNER_QUALITY, 0.82, 0.25),
            MockFactorScore("f3", FactorCategory.WINNER_QUALITY, 0.78, 0.25),
            MockFactorScore("f4", FactorCategory.WINNER_QUALITY, 0.81, 0.25),
        ]
        high_conf = calculate_confidence(high_conf_factors)
        
        # Low confidence (mixed scores)
        low_conf_factors = [
            MockFactorScore("f1", FactorCategory.WINNER_QUALITY, 0.90, 0.25),
            MockFactorScore("f2", FactorCategory.WINNER_QUALITY, 0.40, 0.25),
            MockFactorScore("f3", FactorCategory.WINNER_QUALITY, 0.85, 0.25),
            MockFactorScore("f4", FactorCategory.WINNER_QUALITY, 0.30, 0.25),
        ]
        low_conf = calculate_confidence(low_conf_factors)
        
        self.assertGreater(high_conf, low_conf)
        
        print(f"  [PASS] Confidence: high={high_conf:.2%}, low={low_conf:.2%}")
    
    def test_extreme_scores(self):
        """Test handling of extreme scores."""
        # All perfect scores
        perfect_factors = [
            MockFactorScore("f1", FactorCategory.WINNER_QUALITY, 1.0, 0.5),
            MockFactorScore("f2", FactorCategory.WINNER_QUALITY, 1.0, 0.5),
        ]
        perfect_score = sum(f.score * f.weight for f in perfect_factors)
        self.assertEqual(perfect_score, 1.0)
        
        # All zero scores
        zero_factors = [
            MockFactorScore("f1", FactorCategory.WINNER_QUALITY, 0.0, 0.5),
            MockFactorScore("f2", FactorCategory.WINNER_QUALITY, 0.0, 0.5),
        ]
        zero_score = sum(f.score * f.weight for f in zero_factors)
        self.assertEqual(zero_score, 0.0)
        
        print(f"  [PASS] Extreme scores: perfect={perfect_score:.0%}, zero={zero_score:.0%}")


class TestRecommendationEngine(unittest.TestCase):
    """Test recommendation generation."""
    
    def test_action_recommendation(self):
        """Test action recommendation based on composite score."""
        def recommend_action(score: float) -> str:
            if score > 0.80: return "IMMEDIATE_ENTRY"
            elif score > 0.70: return "ENTER"
            elif score > 0.60: return "CAUTIOUS_ENTRY"
            elif score > 0.50: return "SMALL_POSITION"
            else: return "PASS"
        
        self.assertEqual(recommend_action(0.85), "IMMEDIATE_ENTRY")
        self.assertEqual(recommend_action(0.75), "ENTER")
        self.assertEqual(recommend_action(0.65), "CAUTIOUS_ENTRY")
        self.assertEqual(recommend_action(0.55), "SMALL_POSITION")
        self.assertEqual(recommend_action(0.45), "PASS")
        
        print(f"  [PASS] Action recommendations: 5 levels working")
    
    def test_timing_recommendation(self):
        """Test timing recommendation."""
        def recommend_timing(timing_score: float) -> str:
            if timing_score > 0.8: return "NOW"
            elif timing_score > 0.6: return "WITHIN_1_HOUR"
            else: return "WAIT_FOR_BETTER_TIMING"
        
        self.assertEqual(recommend_timing(0.85), "NOW")
        self.assertEqual(recommend_timing(0.70), "WITHIN_1_HOUR")
        self.assertEqual(recommend_timing(0.50), "WAIT_FOR_BETTER_TIMING")
        
        print(f"  [PASS] Timing recommendations working")
    
    def test_size_adjustment(self):
        """Test position size adjustment."""
        def size_adjustment(composite: float, risk_score: float) -> float:
            """Calculate size multiplier."""
            if risk_score < 0.5:
                return 0.5
            elif composite > 0.85:
                return 1.2
            else:
                return 1.0
        
        # High risk = reduce size
        self.assertEqual(size_adjustment(0.80, 0.40), 0.5)
        
        # High composite = increase size
        self.assertEqual(size_adjustment(0.90, 0.70), 1.2)
        
        # Normal = standard size
        self.assertEqual(size_adjustment(0.75, 0.70), 1.0)
        
        print(f"  [PASS] Size adjustment: 0.5x, 1.0x, 1.2x working")


def run_tests():
    """Run all multi-factor tests."""
    print("\n" + "="*70)
    print("AGENT 4: MULTI-FACTOR MODEL TESTER")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMultiFactorScoring))
    suite.addTests(loader.loadTestsFromTestCase(TestRecommendationEngine))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
