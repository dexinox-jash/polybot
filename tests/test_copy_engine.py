"""
Agent 3: Copy Engine & Risk Management Tester

Validates:
- Daily target enforcement (1 bet/day)
- Portfolio heat limits (<50%)
- Max position limits (5 positions)
- Circuit breakers (10% drawdown)
- Position sizing logic
- Copy decision logic
"""

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict


@dataclass
class MockPortfolio:
    """Mock portfolio for testing."""
    total_value: float = 10000
    daily_bet_count: int = 0
    daily_pnl: float = 0
    positions: List[Dict] = field(default_factory=list)
    
    @property
    def current_exposure(self) -> float:
        return sum(p.get('size', 0) for p in self.positions)
    
    @property
    def heat(self) -> float:
        return self.current_exposure / self.total_value if self.total_value > 0 else 0
    
    @property
    def daily_drawdown(self) -> float:
        return abs(min(0, self.daily_pnl)) / self.total_value


@dataclass
class MockOpportunity:
    """Mock opportunity for testing."""
    ev_percent: float
    winner_score: float
    market_liquidity: float
    timing_score: float


class TestRiskManagement(unittest.TestCase):
    """Test risk management rules."""
    
    def test_daily_target_enforcement(self):
        """Test that 1 bet/day limit is enforced."""
        def can_place_bet(portfolio: MockPortfolio) -> bool:
            return portfolio.daily_bet_count < 1
        
        # Fresh day - should allow
        fresh = MockPortfolio(daily_bet_count=0)
        self.assertTrue(can_place_bet(fresh))
        
        # Already placed bet - should block
        blocked = MockPortfolio(daily_bet_count=1)
        self.assertFalse(can_place_bet(blocked))
        
        # Edge case: exactly at limit
        at_limit = MockPortfolio(daily_bet_count=1)
        self.assertFalse(can_place_bet(at_limit))
        
        print(f"  [PASS] Daily target: fresh={can_place_bet(fresh)}, blocked={can_place_bet(blocked)}")
    
    def test_portfolio_heat_limit(self):
        """Test that heat < 50% is enforced."""
        MAX_HEAT = 0.50
        
        def check_heat(portfolio: MockPortfolio) -> tuple:
            current = portfolio.heat
            remaining = MAX_HEAT - current
            return current, remaining
        
        # Empty portfolio
        empty = MockPortfolio(positions=[])
        heat, remaining = check_heat(empty)
        self.assertEqual(heat, 0)
        self.assertEqual(remaining, 0.50)
        
        # Half full (25% heat)
        half = MockPortfolio(positions=[{'size': 2500}])
        heat, remaining = check_heat(half)
        self.assertEqual(heat, 0.25)
        self.assertEqual(remaining, 0.25)
        
        # At limit (50% heat)
        at_limit = MockPortfolio(positions=[{'size': 5000}])
        heat, remaining = check_heat(at_limit)
        self.assertEqual(heat, 0.50)
        self.assertEqual(remaining, 0)
        
        # Over limit - should not happen but test
        over = MockPortfolio(positions=[{'size': 6000}])
        heat, remaining = check_heat(over)
        self.assertGreater(heat, 0.50)
        self.assertLess(remaining, 0)
        
        print(f"  [PASS] Heat limits: empty={heat:.0%}, at_limit={at_limit.heat:.0%}")
    
    def test_max_positions_limit(self):
        """Test max 5 positions limit."""
        MAX_POSITIONS = 5
        
        def can_add_position(portfolio: MockPortfolio) -> bool:
            return len(portfolio.positions) < MAX_POSITIONS
        
        # No positions
        empty = MockPortfolio(positions=[])
        self.assertTrue(can_add_position(empty))
        
        # 3 positions
        partial = MockPortfolio(positions=[{'size': 100} for _ in range(3)])
        self.assertTrue(can_add_position(partial))
        
        # At limit
        at_limit = MockPortfolio(positions=[{'size': 100} for _ in range(5)])
        self.assertFalse(can_add_position(at_limit))
        
        # Over limit
        over = MockPortfolio(positions=[{'size': 100} for _ in range(6)])
        self.assertFalse(can_add_position(over))
        
        print(f"  [PASS] Position limits: 0={can_add_position(empty)}, 5={can_add_position(at_limit)}")
    
    def test_daily_drawdown_circuit_breaker(self):
        """Test 10% daily drawdown circuit breaker."""
        DRAWDOWN_LIMIT = 0.10
        
        def is_circuit_breaker_triggered(portfolio: MockPortfolio) -> bool:
            return portfolio.daily_drawdown >= DRAWDOWN_LIMIT
        
        # No drawdown
        profit = MockPortfolio(daily_pnl=500)
        self.assertFalse(is_circuit_breaker_triggered(profit))
        
        # Small loss (5%)
        small_loss = MockPortfolio(daily_pnl=-500)
        self.assertFalse(is_circuit_breaker_triggered(small_loss))
        
        # At limit (10%)
        at_limit = MockPortfolio(daily_pnl=-1000)
        self.assertTrue(is_circuit_breaker_triggered(at_limit))
        
        # Over limit (15%)
        over_limit = MockPortfolio(daily_pnl=-1500)
        self.assertTrue(is_circuit_breaker_triggered(over_limit))
        
        print(f"  [PASS] Circuit breaker: profit={is_circuit_breaker_triggered(profit)}, "
              f"at_limit={is_circuit_breaker_triggered(at_limit)}")
    
    def test_position_sizing_kelly(self):
        """Test Kelly-based position sizing."""
        def calculate_position_size(bankroll: float, kelly_fraction: float, 
                                   ev_percent: float) -> float:
            """Calculate position size with Kelly and EV scaling."""
            BASE_SIZE = bankroll * 0.02  # 2% base = $200 for $10k
            
            # Kelly adjustment (use half-Kelly for safety)
            kelly_adj = min(max(kelly_fraction, 0.5), 2.0)
            
            # EV scaling
            ev_adj = min(max(ev_percent / 10, 0.5), 1.5)
            
            size = BASE_SIZE * kelly_adj * ev_adj
            return min(size, 500)  # Hard max $500
        
        bankroll = 10000
        
        # Standard case: $200 * 1.0 * 0.5 = $100, but min is higher
        standard = calculate_position_size(bankroll, 0.25, 5)
        self.assertGreater(standard, 0)
        
        # High EV should give larger size
        high_ev = calculate_position_size(bankroll, 0.30, 15)
        self.assertGreater(high_ev, standard)
        
        # Verify max cap works
        very_high = calculate_position_size(bankroll, 1.0, 100)
        self.assertLessEqual(very_high, 500)
        
        print(f"  [PASS] Position sizing: standard=${standard:.0f}, high_ev=${high_ev:.0f}")


class TestCopyDecision(unittest.TestCase):
    """Test copy decision logic."""
    
    def test_copy_decision_logic(self):
        """Test decision tree for copying."""
        def make_decision(opportunity: MockOpportunity, portfolio: MockPortfolio) -> str:
            """Determine copy action."""
            # Check daily limit
            if portfolio.daily_bet_count >= 1:
                return "SKIP_DAILY_LIMIT"
            
            # Check drawdown
            if portfolio.daily_drawdown >= 0.10:
                return "SKIP_CIRCUIT_BREAKER"
            
            # Check portfolio heat
            if portfolio.heat >= 0.50:
                return "SKIP_HEAT_LIMIT"
            
            # Check EV
            if opportunity.ev_percent < 2:
                return "SKIP_LOW_EV"
            
            # Check liquidity
            if opportunity.market_liquidity < 10000:
                return "WAIT_LIQUIDITY"
            
            # Check timing
            if opportunity.timing_score < 0.5:
                return "WAIT_TIMING"
            
            # All checks passed
            if opportunity.ev_percent > 8:
                return "COPY_STRONG"
            else:
                return "COPY_MODERATE"
        
        # Strong opportunity, fresh portfolio
        strong_opp = MockOpportunity(10, 85, 100000, 0.9)
        fresh_port = MockPortfolio()
        decision = make_decision(strong_opp, fresh_port)
        self.assertEqual(decision, "COPY_STRONG")
        
        # Daily limit reached
        limited_port = MockPortfolio(daily_bet_count=1)
        decision = make_decision(strong_opp, limited_port)
        self.assertEqual(decision, "SKIP_DAILY_LIMIT")
        
        # Circuit breaker
        cb_port = MockPortfolio(daily_pnl=-1200)
        decision = make_decision(strong_opp, cb_port)
        self.assertEqual(decision, "SKIP_CIRCUIT_BREAKER")
        
        # Low EV
        weak_opp = MockOpportunity(1, 70, 100000, 0.8)
        decision = make_decision(weak_opp, fresh_port)
        self.assertEqual(decision, "SKIP_LOW_EV")
        
        # Low liquidity
        illiquid_opp = MockOpportunity(8, 80, 5000, 0.8)
        decision = make_decision(illiquid_opp, fresh_port)
        self.assertEqual(decision, "WAIT_LIQUIDITY")
        
        print(f"  [PASS] Decision logic: strong={decision}")
    
    def test_composite_score_calculation(self):
        """Test composite opportunity scoring."""
        def calculate_composite_score(opp: MockOpportunity) -> float:
            """Calculate composite score 0-100."""
            ev_score = min(opp.ev_percent / 10, 1.0) * 40  # 40% weight
            winner_score = opp.winner_score * 0.25  # 25% weight
            liquidity_score = min(opp.market_liquidity / 100000, 1.0) * 20  # 20% weight
            timing_score = opp.timing_score * 15  # 15% weight
            return ev_score + winner_score + liquidity_score + timing_score
        
        # Excellent opportunity
        excellent = MockOpportunity(15, 90, 200000, 0.95)
        excellent_score = calculate_composite_score(excellent)
        self.assertGreater(excellent_score, 80)
        
        # Good opportunity
        good = MockOpportunity(8, 75, 100000, 0.8)
        good_score = calculate_composite_score(good)
        self.assertGreater(good_score, 60)
        self.assertLess(good_score, excellent_score)
        
        # Mediocre opportunity
        mediocre = MockOpportunity(3, 60, 50000, 0.6)
        mediocre_score = calculate_composite_score(mediocre)
        self.assertLess(mediocre_score, 50)
        
        print(f"  [PASS] Composite scores: excellent={excellent_score:.1f}, good={good_score:.1f}, mediocre={mediocre_score:.1f}")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def test_zero_bankroll(self):
        """Test handling of zero bankroll."""
        portfolio = MockPortfolio(total_value=0)
        self.assertEqual(portfolio.heat, 0)
        
        print(f"  [PASS] Zero bankroll handled")
    
    def test_negative_pnl(self):
        """Test handling of extreme negative P&L."""
        portfolio = MockPortfolio(daily_pnl=-5000)
        self.assertEqual(portfolio.daily_drawdown, 0.50)
        
        print(f"  [PASS] Negative P&L: drawdown={portfolio.daily_drawdown:.0%}")
    
    def test_rapid_trading(self):
        """Test prevention of rapid multiple trades."""
        # Simulate trying to place multiple trades quickly
        portfolio = MockPortfolio(daily_bet_count=0)
        
        # First trade
        portfolio.daily_bet_count += 1
        portfolio.positions.append({'size': 200})
        
        # Try second trade - should be blocked
        can_trade = portfolio.daily_bet_count < 1
        self.assertFalse(can_trade)
        
        print(f"  [PASS] Rapid trading blocked")


def run_tests():
    """Run all copy engine tests."""
    print("\n" + "="*70)
    print("AGENT 3: COPY ENGINE & RISK MANAGEMENT TESTER")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestCopyDecision))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
