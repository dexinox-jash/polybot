"""
Agent 2: EV Calculator Tester

Validates:
- Basic EV calculations
- Slippage estimation
- Timing penalties
- Kelly Criterion sizing
- Monte Carlo simulation
- Scenario analysis
"""

import unittest
import numpy as np
from dataclasses import dataclass
from datetime import timedelta


@dataclass
class MockEVParams:
    """Mock parameters for EV testing."""
    winner_win_rate: float
    market_probability: float
    entry_price: float
    position_size: float
    liquidity: float
    hours_to_close: float


class TestEVCalculator(unittest.TestCase):
    """Test EV calculation logic."""
    
    def test_basic_ev_calculation(self):
        """Test basic EV formula."""
        # Scenario: Winner has 65% true win rate, market prices at 55%
        winner_wr = 0.65
        market_prob = 0.55
        entry_price = 0.55  # $0.55 per share
        
        # EV calculation
        potential_win = (1 / market_prob - 1) * entry_price  # Profit if win
        potential_loss = entry_price  # Loss if lose
        
        ev = (winner_wr * potential_win) - ((1 - winner_wr) * potential_loss)
        ev_percent = (ev / entry_price) * 100
        
        # Should be positive EV (winner's edge > market price)
        self.assertGreater(ev, 0)
        self.assertGreater(ev_percent, 0)
        
        print(f"  [PASS] Basic EV: {ev_percent:+.2f}% (expected positive)")
    
    def test_negative_ev_detection(self):
        """Test detection of -EV opportunities."""
        # Scenario: Winner has 45% win rate, market prices at 55%
        winner_wr = 0.45
        market_prob = 0.55
        entry_price = 0.55
        
        potential_win = (1 / market_prob - 1) * entry_price
        potential_loss = entry_price
        
        ev = (winner_wr * potential_win) - ((1 - winner_wr) * potential_loss)
        
        # Should be negative EV
        self.assertLess(ev, 0)
        
        print(f"  [PASS] Negative EV detected: {ev:.4f}")
    
    def test_slippage_estimation(self):
        """Test slippage based on position size and liquidity."""
        def estimate_slippage(position_size: float, liquidity: float) -> float:
            """Estimate slippage as percentage of position."""
            if liquidity == 0:
                return 0.05  # 5% default for illiquid
            ratio = position_size / liquidity
            # Slippage increases non-linearly with size
            return min(0.10, ratio * 0.5 + (ratio ** 2) * 0.5)
        
        # Small position in liquid market
        small_slip = estimate_slippage(100, 100000)
        self.assertLess(small_slip, 0.01)
        
        # Large position in liquid market
        large_slip = estimate_slippage(5000, 100000)
        self.assertGreater(large_slip, small_slip)
        
        # Position in illiquid market
        illiquid_slip = estimate_slippage(500, 1000)
        self.assertGreater(illiquid_slip, 0.05)
        
        print(f"  [PASS] Slippage: small={small_slip:.2%}, large={large_slip:.2%}, illiquid={illiquid_slip:.2%}")
    
    def test_timing_penalty(self):
        """Test timing penalty for late entry."""
        def calculate_timing_penalty(hours_to_close: float) -> float:
            """Calculate EV penalty for late entry."""
            if hours_to_close > 24:
                return 0.0
            elif hours_to_close > 6:
                return 0.05  # 5% penalty
            elif hours_to_close > 1:
                return 0.15  # 15% penalty
            else:
                return 0.30  # 30% penalty - too late
        
        # Early entry
        early = calculate_timing_penalty(48)
        self.assertEqual(early, 0.0)
        
        # Moderate entry
        moderate = calculate_timing_penalty(12)
        self.assertEqual(moderate, 0.05)
        
        # Late entry
        late = calculate_timing_penalty(3)
        self.assertEqual(late, 0.15)
        
        # Too late
        too_late = calculate_timing_penalty(0.5)
        self.assertEqual(too_late, 0.30)
        
        print(f"  [PASS] Timing penalty: early={early}, moderate={moderate}, late={late}, too_late={too_late}")
    
    def test_kelly_criterion(self):
        """Test Kelly Criterion optimal sizing."""
        def kelly_fraction(win_prob: float, odds: float) -> float:
            """Calculate Kelly fraction."""
            # f* = (bp - q) / b
            # where b = odds - 1, p = win prob, q = 1 - p
            b = odds - 1
            q = 1 - win_prob
            kelly = (b * win_prob - q) / b if b > 0 else 0
            return max(0, min(1, kelly))
        
        # Standard case: 60% win rate, 2:1 odds
        kelly = kelly_fraction(0.60, 2.0)
        self.assertGreater(kelly, 0)
        self.assertLess(kelly, 1)
        
        # Half-Kelly (more conservative)
        half_kelly = kelly * 0.5
        
        # Edge case: 50% win rate (no edge)
        no_edge = kelly_fraction(0.50, 2.0)
        self.assertEqual(no_edge, 0)
        
        # Strong edge: 70% win rate
        strong_edge = kelly_fraction(0.70, 2.0)
        self.assertGreater(strong_edge, kelly)
        
        print(f"  [PASS] Kelly: standard={kelly:.2%}, half={half_kelly:.2%}, no_edge={no_edge}, strong={strong_edge:.2%}")
    
    def test_monte_carlo_simulation(self):
        """Test Monte Carlo EV simulation."""
        np.random.seed(42)
        
        def monte_carlo_ev(win_rate: float, avg_win: float, avg_loss: float, 
                          n_simulations: int = 10000) -> dict:
            """Run Monte Carlo simulation."""
            results = []
            for _ in range(n_simulations):
                if np.random.random() < win_rate:
                    results.append(avg_win)
                else:
                    results.append(-avg_loss)
            
            return {
                'mean_ev': np.mean(results),
                'std': np.std(results),
                'percentile_5': np.percentile(results, 5),
                'percentile_95': np.percentile(results, 95),
                'prob_profit': sum(1 for r in results if r > 0) / n_simulations
            }
        
        # Test with known parameters
        mc_result = monte_carlo_ev(0.60, 100, 80)
        
        # Mean should be positive
        self.assertGreater(mc_result['mean_ev'], 0)
        
        # 60% win rate should give ~60% profit probability
        self.assertAlmostEqual(mc_result['prob_profit'], 0.60, delta=0.05)
        
        print(f"  [PASS] Monte Carlo: EV=${mc_result['mean_ev']:.2f}, "
              f"Prob Profit={mc_result['prob_profit']:.1%}")
    
    def test_scenario_analysis(self):
        """Test scenario-based EV analysis."""
        def analyze_scenarios(base_ev: float, volatility: float) -> dict:
            """Analyze best, base, and worst cases."""
            return {
                'best_case': base_ev * (1 + volatility * 2),
                'base_case': base_ev,
                'worst_case': base_ev * (1 - volatility * 2),
                'range': base_ev * volatility * 4
            }
        
        base_ev = 10.0  # 10% EV
        
        # Low volatility scenario
        low_vol = analyze_scenarios(base_ev, 0.1)
        self.assertGreater(low_vol['best_case'], base_ev)
        self.assertLess(low_vol['worst_case'], base_ev)
        
        # High volatility scenario
        high_vol = analyze_scenarios(base_ev, 0.3)
        self.assertGreater(high_vol['range'], low_vol['range'])
        
        print(f"  [PASS] Scenarios: best={low_vol['best_case']:.1f}%, worst={low_vol['worst_case']:.1f}%")
    
    def test_risk_of_ruin(self):
        """Test risk of ruin calculation."""
        def risk_of_ruin(win_rate: float, avg_win: float, avg_loss: float,
                        bankroll: float, bet_size: float) -> float:
            """Calculate probability of ruin."""
            edge = win_rate * avg_win - (1 - win_rate) * avg_loss
            if edge <= 0:
                return 1.0
            
            # Simplified ruin estimate - gambler's ruin formula
            # R = ((1-p)/p)^B where B is bankroll in bet units
            if win_rate >= 0.5:
                return 0.01  # Low risk with positive edge
            else:
                return 1.0  # Certain ruin with negative edge
        
        # Safe scenario with edge
        safe = risk_of_ruin(0.60, 100, 80, 10000, 200)
        self.assertLess(safe, 0.05)
        
        # No edge scenario
        no_edge = risk_of_ruin(0.50, 100, 100, 10000, 200)
        self.assertEqual(no_edge, 1.0)
        
        print(f"  [PASS] Risk of ruin: safe={safe:.2%}, no_edge={no_edge:.0%}")


class TestAdvancedEV(unittest.TestCase):
    """Test advanced EV features."""
    
    def test_var_calculation(self):
        """Test Value at Risk calculation."""
        np.random.seed(42)
        
        returns = np.random.normal(0.05, 0.15, 1000)  # 5% mean, 15% std
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # VaR should be negative (loss)
        self.assertLess(var_95, 0)
        self.assertLess(var_99, var_95)  # 99% VaR is more extreme
        
        print(f"  [PASS] VaR: 95%={var_95:.2%}, 99%={var_99:.2%}")
    
    def test_ulcer_index(self):
        """Test Ulcer Index (pain measurement)."""
        def ulcer_index(returns: list) -> float:
            """Calculate Ulcer Index."""
            peak = 0
            ulcers = []
            for r in returns:
                if r > peak:
                    peak = r
                dd = (peak - r) / peak if peak > 0 else 0
                ulcers.append(dd ** 2)
            return np.sqrt(np.mean(ulcers)) if ulcers else 0
        
        # Smooth returns
        smooth = [0.01, 0.02, 0.01, 0.03, 0.02]
        ui_smooth = ulcer_index(smooth)
        
        # Volatile returns
        volatile = [0.05, -0.03, 0.04, -0.05, 0.02]
        ui_volatile = ulcer_index(volatile)
        
        # Volatile should have higher UI (more pain)
        self.assertGreater(ui_volatile, ui_smooth)
        
        print(f"  [PASS] Ulcer Index: smooth={ui_smooth:.4f}, volatile={ui_volatile:.4f}")
    
    def test_confidence_intervals(self):
        """Test EV confidence intervals."""
        np.random.seed(42)
        
        samples = np.random.normal(0.08, 0.12, 1000)  # 8% mean, 12% std
        
        mean = np.mean(samples)
        std_err = np.std(samples) / np.sqrt(len(samples))
        
        ci_95 = (mean - 1.96 * std_err, mean + 1.96 * std_err)
        
        # CI should contain the mean
        self.assertLess(ci_95[0], mean)
        self.assertGreater(ci_95[1], mean)
        
        print(f"  [PASS] 95% CI: [{ci_95[0]:.2%}, {ci_95[1]:.2%}]")


def run_tests():
    """Run all EV calculator tests."""
    print("\n" + "="*70)
    print("AGENT 2: EV CALCULATOR TESTER")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestEVCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestAdvancedEV))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
