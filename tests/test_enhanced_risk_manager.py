"""
Comprehensive Tests for Enhanced Risk Manager

Tests all features including:
- Per-trade risk controls
- Portfolio risk management
- Circuit breakers
- Tiered exits
- Volatility adjustment
- Drawdown protection
"""

import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, 'c:\\Users\\Dexinox\\Documents\\kimi code\\Polybot')

from polymarket_tracker.risk import (
    EnhancedRiskManager,
    RiskManagedPaperTradingSession,
    CircuitBreakerType,
    ExitReason,
    RiskStatus,
    TakeProfitLevels,
    PositionRiskProfile,
    DailyStats,
    VolatilityMetrics,
    APIErrorTracker,
)


class TestEnhancedRiskManager(unittest.TestCase):
    """Test EnhancedRiskManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.risk_manager = EnhancedRiskManager(initial_balance=10000.0)
    
    def test_initialization(self):
        """Test risk manager initialization."""
        self.assertEqual(self.risk_manager.initial_balance, 10000.0)
        self.assertEqual(self.risk_manager.current_balance, 10000.0)
        self.assertFalse(self.risk_manager.circuit_breaker_active)
        self.assertEqual(self.risk_manager.risk_status, RiskStatus.NORMAL)
    
    def test_can_open_position_basic(self):
        """Test basic position opening permission."""
        can_trade, reason = self.risk_manager.can_open_position(
            size=1000,
            current_balance=10000.0,
            open_positions=[]
        )
        self.assertTrue(can_trade)
        self.assertEqual(reason, "OK")
    
    def test_max_positions_limit(self):
        """Test max concurrent positions limit."""
        # Open max positions
        for i in range(5):
            self.risk_manager.register_position(
                entry_price=0.50,
                direction='YES',
                size_usd=500
            )
        
        # Try to open one more
        can_trade, reason = self.risk_manager.can_open_position(
            size=500,
            current_balance=10000.0,
            open_positions=[]
        )
        self.assertFalse(can_trade)
        self.assertIn("Max positions reached", reason)
    
    def test_portfolio_heat_limit(self):
        """Test portfolio heat limit."""
        # Open positions that use most heat
        for i in range(3):
            self.risk_manager.register_position(
                entry_price=0.50,
                direction='YES',
                size_usd=1500  # 45% total
            )
        
        # Try to open another large position
        can_trade, reason = self.risk_manager.can_open_position(
            size=1000,  # Would exceed 50%
            current_balance=10000.0,
            open_positions=[]
        )
        self.assertFalse(can_trade)
        self.assertIn("Portfolio heat limit", reason)
    
    def test_stop_loss_check(self):
        """Test stop loss detection."""
        profile = self.risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000
        )
        
        # Price above stop
        should_exit = self.risk_manager.check_stop_loss(
            profile.position_id, 0.49
        )
        self.assertFalse(should_exit)
        
        # Price at stop (5% below entry = 0.475)
        should_exit = self.risk_manager.check_stop_loss(
            profile.position_id, 0.47
        )
        self.assertTrue(should_exit)
    
    def test_take_profit_tier1(self):
        """Test tier 1 take profit detection."""
        profile = self.risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000
        )
        
        # Below tier 1
        should_exit, tier = self.risk_manager.check_take_profit(
            profile.position_id, 0.54
        )
        self.assertFalse(should_exit)
        
        # At tier 1 (10% above entry = 0.55)
        should_exit, tier = self.risk_manager.check_take_profit(
            profile.position_id, 0.55
        )
        self.assertTrue(should_exit)
        self.assertEqual(tier, "tier1")
    
    def test_consecutive_losses_circuit_breaker(self):
        """Test consecutive losses circuit breaker."""
        # Simulate 3 losses
        for i in range(3):
            profile = self.risk_manager.register_position(
                entry_price=0.50,
                direction='YES',
                size_usd=1000
            )
            self.risk_manager.close_position(
                profile.position_id,
                exit_price=0.475,
                pnl=-25.0,
                exit_reason=ExitReason.STOP_LOSS
            )
        
        # Check circuit breaker
        self.assertTrue(self.risk_manager.circuit_breaker_active)
        self.assertEqual(
            self.risk_manager.circuit_breaker_type,
            CircuitBreakerType.CONSECUTIVE_LOSSES
        )
        
        # Try to trade
        can_trade, reason = self.risk_manager.can_open_position(
            size=1000,
            current_balance=9925.0,
            open_positions=[]
        )
        self.assertFalse(can_trade)
        # Circuit breaker is already active, so reason mentions it's active
        self.assertIn("Circuit breaker active", reason)
    
    def test_daily_drawdown_circuit_breaker(self):
        """Test daily drawdown circuit breaker."""
        # Simulate large daily loss (over 10%)
        self.risk_manager.current_balance = 8900  # 11% loss
        self.risk_manager.daily_stats.current_balance = 8900
        self.risk_manager.daily_stats.starting_balance = 10000
        
        can_trade, reason = self.risk_manager.can_open_position(
            size=1000,
            current_balance=8900.0,
            open_positions=[]
        )
        self.assertFalse(can_trade)
        self.assertIn("drawdown limit hit", reason)
    
    def test_volatility_adjustment(self):
        """Test volatility-adjusted position sizing."""
        # Low volatility - use values with small variation
        for i in range(10):
            self.risk_manager.record_volatility(0.1 + i * 0.01)
        
        status = self.risk_manager.get_status()
        # With low variation, regime should be low
        self.assertEqual(status['volatility']['regime'], 'low')
        
        # Create new risk manager for high volatility test - use very spread out values
        rm2 = EnhancedRiskManager(initial_balance=10000.0)
        # Create values from 1.0 to 8.0 to ensure high standard deviation
        for i in range(20):
            rm2.record_volatility(1.0 + i * 0.4)
        
        status2 = rm2.get_status()
        self.assertEqual(status2['volatility']['regime'], 'high')
    
    def test_api_error_circuit_breaker(self):
        """Test API error circuit breaker."""
        # Simulate many errors
        for _ in range(10):
            self.risk_manager.record_api_error("timeout")
        
        can_trade, reason = self.risk_manager.can_open_position(
            size=1000,
            current_balance=10000.0,
            open_positions=[]
        )
        self.assertFalse(can_trade)
        self.assertIn("API errors", reason)
    
    def test_time_based_exit(self):
        """Test time-based position exit."""
        # Set time exit to already be expired by using negative max_hold_hours
        # Actually, let's set the time_exit_at directly after creation
        profile = self.risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000,
            max_hold_hours=24.0
        )
        
        # Should not exit immediately
        should_exit, reason, _ = self.risk_manager.check_exit_conditions(
            profile.position_id, 0.50
        )
        self.assertFalse(should_exit)
        
        # Manually set time exit to be in the past for testing
        profile.time_exit_at = datetime.now() - timedelta(seconds=1)
        
        # Should exit now
        should_exit, reason, _ = self.risk_manager.check_exit_conditions(
            profile.position_id, 0.50
        )
        self.assertTrue(should_exit)
        self.assertEqual(reason, ExitReason.TIME_EXIT)
    
    def test_get_status(self):
        """Test risk status reporting."""
        status = self.risk_manager.get_status()
        
        self.assertIn('risk_status', status)
        self.assertIn('circuit_breaker', status)
        self.assertIn('balance', status)
        self.assertIn('drawdown', status)
        self.assertIn('positions', status)
        self.assertIn('daily_stats', status)
        self.assertIn('volatility', status)
        self.assertIn('api_health', status)
    
    def test_recommended_position_size(self):
        """Test recommended position size calculation."""
        size = self.risk_manager.get_recommended_position_size(
            signal_confidence=0.8,
            base_size=1000,
            current_balance=10000.0
        )
        
        # Should be adjusted by confidence and volatility
        self.assertGreater(size, 0)
        self.assertLessEqual(size, 1000)


class TestRiskManagedPaperTradingSession(unittest.TestCase):
    """Test RiskManagedPaperTradingSession class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.session = RiskManagedPaperTradingSession(initial_balance=10000.0)
    
    def test_session_initialization(self):
        """Test session initialization."""
        self.assertEqual(self.session.initial_balance, 10000.0)
        self.assertEqual(self.session.balance, 10000.0)
        self.assertIsNotNone(self.session.risk_manager)
    
    def test_can_trade(self):
        """Test can_trade method."""
        can_trade, reason = self.session.can_trade(1000)
        self.assertTrue(can_trade)
        self.assertEqual(reason, "OK")
    
    def test_open_position(self):
        """Test opening a position."""
        class MockSignal:
            def __init__(self):
                self.pattern_confidence = 0.75
                self.suggested_size = 1000
                self.market_id = "test-market"
        
        signal = MockSignal()
        signal.trade = MagicMock()
        signal.trade.outcome = 'YES'
        signal.trade.price = 0.50
        signal.trade.market_id = "test-market"
        signal.trade.market_question = "Test Market"
        signal.trade.tx_hash = "0x1234"
        signal.trade.whale_address = "0xabcd"
        signal.whale_pattern_profile = "momentum"
        
        position = self.session.open_position(
            signal=signal,
            market_data={'current_price': 0.50}
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position['direction'], 'YES')
        self.assertEqual(position['entry_price'], 0.50)
        self.assertEqual(len(self.session.positions), 1)
    
    def test_update_positions_stop_loss(self):
        """Test position update triggering stop loss."""
        # Open position
        profile = self.session.risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000
        )
        
        self.session.positions[profile.position_id] = {
            'position_id': profile.position_id,
            'market_id': 'test-market',
            'direction': 'YES',
            'entry_price': 0.50,
            'size_usd': 1000,
            'risk_profile': profile,
            'current_price': 0.50,
            'realized_pnl': 0.0  # Initialize required field
        }
        
        # Update with price below stop
        market_prices = {'test-market': 0.46}  # Below 0.475 stop
        self.session.update_positions(market_prices)
        
        # Position should be closed
        self.assertEqual(len(self.session.positions), 0)
        self.assertEqual(len(self.session.closed_positions), 1)
    
    def test_close_position(self):
        """Test closing a position."""
        # Open and close position
        profile = self.session.risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000
        )
        
        self.session.positions[profile.position_id] = {
            'position_id': profile.position_id,
            'market_id': 'test-market',
            'direction': 'YES',
            'entry_price': 0.50,
            'size_usd': 1000,
            'risk_profile': profile,
            'realized_pnl': 0.0  # Initialize required field
        }
        
        result = self.session.close_position(
            profile.position_id,
            exit_price=0.55,
            exit_reason=ExitReason.TAKE_PROFIT_TIER1
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['exit_price'], 0.55)
        self.assertEqual(result['status'], 'closed')
        self.assertEqual(self.session.balance, 10050.0)  # $50 profit
    
    def test_get_risk_status(self):
        """Test getting comprehensive risk status."""
        status = self.session.get_risk_status()
        
        self.assertIn('risk_status', status)
        self.assertIn('session', status)
        self.assertIn('balance', status)
        self.assertIn('positions', status)


class TestTakeProfitLevels(unittest.TestCase):
    """Test TakeProfitLevels dataclass."""
    
    def test_default_values(self):
        """Test default take profit levels."""
        tpl = TakeProfitLevels()
        self.assertEqual(tpl.tier1_pct, 0.10)
        self.assertEqual(tpl.tier1_size, 0.50)
        self.assertEqual(tpl.tier2_pct, 0.20)
        self.assertEqual(tpl.tier2_size, 1.0)
    
    def test_custom_values(self):
        """Test custom take profit levels."""
        tpl = TakeProfitLevels(
            tier1_pct=0.15,
            tier1_size=0.33,
            tier2_pct=0.30,
            tier2_size=1.0
        )
        self.assertEqual(tpl.tier1_pct, 0.15)
        self.assertEqual(tpl.tier1_size, 0.33)


class TestVolatilityMetrics(unittest.TestCase):
    """Test VolatilityMetrics class."""
    
    def test_add_price_changes(self):
        """Test adding price changes."""
        vm = VolatilityMetrics()
        
        # Need at least 2 data points for std dev
        for i in range(10):
            vm.add_price_change(2.0 + i * 0.1)  # Varying values
        
        self.assertEqual(len(vm.price_changes), 10)
        self.assertGreaterEqual(vm.current_volatility, 0)
    
    def test_volatility_regime(self):
        """Test volatility regime detection."""
        vm = VolatilityMetrics()
        
        # Low volatility - use very similar values for low std dev
        for i in range(10):
            vm.add_price_change(0.3 + i * 0.01)  # Very small variation
        
        # Should be in low regime with low variation
        self.assertEqual(vm.volatility_regime, 'low')
        
        # High volatility - use very different values
        vm2 = VolatilityMetrics()
        for i in range(10):
            vm2.add_price_change(1.0 + i * 0.8)  # Large variation
        self.assertEqual(vm2.volatility_regime, 'high')
    
    def test_position_size_multiplier(self):
        """Test position size multipliers."""
        vm = VolatilityMetrics()
        
        # First add some data so we don't return default
        for i in range(5):
            vm.add_price_change(1.0 + i * 0.1)
        
        vm.volatility_regime = 'low'
        self.assertEqual(vm.get_position_size_multiplier(), 1.2)
        
        vm.volatility_regime = 'normal'
        self.assertEqual(vm.get_position_size_multiplier(), 1.0)
        
        vm.volatility_regime = 'high'
        self.assertEqual(vm.get_position_size_multiplier(), 0.6)
        
        vm.volatility_regime = 'extreme'
        self.assertEqual(vm.get_position_size_multiplier(), 0.3)


class TestAPIErrorTracker(unittest.TestCase):
    """Test APIErrorTracker class."""
    
    def test_record_error(self):
        """Test recording errors."""
        tracker = APIErrorTracker()
        tracker.record_error("timeout")
        
        self.assertEqual(tracker.get_error_count(), 1)
        self.assertEqual(tracker.consecutive_errors, 1)
    
    def test_record_success(self):
        """Test recording successes."""
        tracker = APIErrorTracker()
        tracker.record_error("timeout")
        tracker.record_error("timeout")
        self.assertEqual(tracker.consecutive_errors, 2)
        
        tracker.record_success()
        self.assertEqual(tracker.consecutive_errors, 0)
    
    def test_circuit_breaker_threshold(self):
        """Test circuit breaker threshold."""
        tracker = APIErrorTracker()
        
        # Not enough errors - threshold is 5
        for _ in range(4):
            tracker.record_error("timeout")
        self.assertFalse(tracker.should_circuit_break())
        
        # One more error triggers circuit breaker
        tracker.record_error("timeout")
        self.assertTrue(tracker.should_circuit_break())
    
    def test_consecutive_error_circuit_breaker(self):
        """Test consecutive error circuit breaker."""
        tracker = APIErrorTracker()
        
        for _ in range(5):
            tracker.record_error("timeout")
        
        self.assertTrue(tracker.should_circuit_break())


class TestDailyStats(unittest.TestCase):
    """Test DailyStats dataclass."""
    
    def test_update_drawdown(self):
        """Test drawdown calculation."""
        stats = DailyStats(
            starting_balance=10000.0,
            current_balance=10000.0,
            peak_balance=10000.0
        )
        
        # No drawdown
        stats.update_drawdown()
        self.assertEqual(stats.current_drawdown, 0.0)
        
        # With drawdown
        stats.current_balance = 9000.0
        stats.update_drawdown()
        self.assertEqual(stats.current_drawdown, 0.10)
        
        # New peak
        stats.current_balance = 11000.0
        stats.update_drawdown()
        self.assertEqual(stats.current_drawdown, 0.0)
        self.assertEqual(stats.peak_balance, 11000.0)


class TestPositionRiskProfile(unittest.TestCase):
    """Test PositionRiskProfile dataclass."""
    
    def test_initialization(self):
        """Test profile initialization."""
        profile = PositionRiskProfile(
            position_id="test123",
            entry_price=0.50,
            direction='YES',
            size_usd=1000,
            entry_time=datetime.now(),
            stop_loss_price=0.475
        )
        
        self.assertEqual(profile.position_id, "test123")
        self.assertEqual(profile.entry_price, 0.50)
        self.assertEqual(profile.original_size, 1000)
        self.assertFalse(profile.tier1_exited)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete risk system."""
    
    def test_full_trade_lifecycle(self):
        """Test a complete trade lifecycle with risk management."""
        rm = EnhancedRiskManager(initial_balance=10000.0)
        
        # 1. Check can trade
        can_trade, _ = rm.can_open_position(1000, 10000.0, [])
        self.assertTrue(can_trade)
        
        # 2. Open position
        profile = rm.register_position(0.50, 'YES', 1000)
        self.assertIn(profile.position_id, rm.position_risk_profiles)
        
        # 3. Check no exit at start price
        should_exit, _, _ = rm.check_exit_conditions(profile.position_id, 0.50)
        self.assertFalse(should_exit)
        
        # 4. Check stop loss
        should_exit, reason, _ = rm.check_exit_conditions(profile.position_id, 0.47)
        self.assertTrue(should_exit)
        self.assertEqual(reason, ExitReason.STOP_LOSS)
        
        # 5. Check take profit
        should_exit, reason, details = rm.check_exit_conditions(profile.position_id, 0.55)
        self.assertTrue(should_exit)
        self.assertEqual(reason, ExitReason.TAKE_PROFIT_TIER1)
        
        # 6. Close position with STOP_LOSS to force full close (not partial tier1)
        result = rm.close_position(profile.position_id, 0.55, 50.0, ExitReason.STOP_LOSS)
        # The result dict contains 'pnl' field
        self.assertIn('pnl', result)
        self.assertEqual(result['pnl'], 50.0)
        self.assertNotIn(profile.position_id, rm.position_risk_profiles)
    
    def test_multiple_positions_with_heat(self):
        """Test multiple positions with portfolio heat tracking."""
        rm = EnhancedRiskManager(initial_balance=10000.0)
        
        # Open positions
        for i in range(4):
            can_trade, _ = rm.can_open_position(1000, 10000.0, [])
            if can_trade:
                rm.register_position(0.50, 'YES', 1000)
        
        # Check heat
        status = rm.get_status()
        self.assertEqual(status['positions']['open_count'], 4)
        self.assertEqual(status['positions']['heat'], 4000)
        self.assertEqual(status['positions']['heat_pct'], 0.40)
        
        # Should be able to open one more (max 5)
        can_trade, _ = rm.can_open_position(500, 10000.0, [])
        self.assertTrue(can_trade)
        
        # Should not be able to open more
        rm.register_position(0.50, 'YES', 500)  # Now 5 positions
        can_trade, reason = rm.can_open_position(100, 10000.0, [])
        self.assertFalse(can_trade)
        self.assertIn("Max positions", reason)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedRiskManager))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskManagedPaperTradingSession))
    suite.addTests(loader.loadTestsFromTestCase(TestTakeProfitLevels))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatilityMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIErrorTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyStats))
    suite.addTests(loader.loadTestsFromTestCase(TestPositionRiskProfile))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
