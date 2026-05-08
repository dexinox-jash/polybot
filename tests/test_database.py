"""
Unit tests for PolyBot Database Integration
"""

import sys
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import to avoid dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "database", 
    str(Path(__file__).parent.parent / "polymarket_tracker" / "data" / "database.py")
)
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

TradeDatabase = database_module.TradeDatabase
TradeData = database_module.TradeData
TradeStatus = database_module.TradeStatus
TradeSide = database_module.TradeSide
TradeType = database_module.TradeType
PatternType = database_module.PatternType
EventType = database_module.EventType
WhaleProfile = database_module.WhaleProfile
MarketCache = database_module.MarketCache


class TestTradeDatabase(unittest.TestCase):
    """Test cases for TradeDatabase class."""
    
    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.mktemp(suffix=".db")
        self.db = TradeDatabase(self.temp_db)
    
    def tearDown(self):
        """Clean up test database."""
        self.db.close()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)
    
    def test_record_trade(self):
        """Test recording a trade."""
        trade = TradeData(
            trade_id="test_trade_001",
            market_id="market_123",
            market_question="Test market",
            side="YES",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0,
        )
        
        result = self.db.record_trade(trade)
        self.assertTrue(result)
        
        # Verify trade was recorded
        trades = self.db.get_trade_history()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['trade_id'], "test_trade_001")
    
    def test_update_trade_result(self):
        """Test updating a trade with exit information."""
        # First record a trade
        trade = TradeData(
            trade_id="test_trade_002",
            market_id="market_123",
            market_question="Test market",
            side="YES",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0,
        )
        self.db.record_trade(trade)
        
        # Update with exit
        result = self.db.update_trade_result(
            trade_id="test_trade_002",
            exit_price=0.65,
            pnl=30.0,
            exit_reason="take_profit"
        )
        self.assertTrue(result)
        
        # Verify update
        trades = self.db.get_trade_history(filters={'status': 'closed'})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]['pnl'], 30.0)
        self.assertEqual(trades[0]['exit_price'], 0.65)
    
    def test_get_open_positions(self):
        """Test getting open positions."""
        # Create open trade
        open_trade = TradeData(
            trade_id="open_001",
            market_id="market_123",
            market_question="Test",
            side="YES",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0,
            status="open"
        )
        self.db.record_trade(open_trade)
        
        # Create closed trade
        closed_trade = TradeData(
            trade_id="closed_001",
            market_id="market_124",
            market_question="Test 2",
            side="NO",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0,
            status="closed",
            exit_price=0.60,
            pnl=20.0
        )
        self.db.record_trade(closed_trade)
        
        open_positions = self.db.get_open_positions()
        self.assertEqual(len(open_positions), 1)
        self.assertEqual(open_positions[0]['trade_id'], "open_001")
    
    def test_save_and_get_whale_profile(self):
        """Test saving and retrieving whale profiles."""
        whale = WhaleProfile(
            address="0xtest123",
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            total_pnl=1000.0,
            win_rate=60.0,
            reliability_tier="gold"
        )
        
        result = self.db.save_whale_profile(whale)
        self.assertTrue(result)
        
        # Retrieve
        profile = self.db.get_whale_profile("0xtest123")
        self.assertIsNotNone(profile)
        self.assertEqual(profile['address'], "0xtest123")
        self.assertEqual(profile['win_rate'], 60.0)
        self.assertEqual(profile['reliability_tier'], "gold")
    
    def test_get_top_whales(self):
        """Test getting top performing whales."""
        # Create multiple whales
        for i in range(5):
            whale = WhaleProfile(
                address=f"0xwhale{i}",
                total_trades=20 + i * 10,
                winning_trades=15 + i * 5,
                losing_trades=5 + i * 5,
                total_pnl=500.0 + i * 100,
                win_rate=50.0 + i * 5,
                reliability_tier="silver" if i < 3 else "bronze"
            )
            self.db.save_whale_profile(whale)
        
        top_whales = self.db.get_top_whales(limit=3, min_trades=10)
        self.assertEqual(len(top_whales), 3)
        # Should be ordered by win rate descending
        self.assertEqual(top_whales[0]['address'], "0xwhale4")
    
    def test_cache_market_data(self):
        """Test caching and retrieving market data."""
        market = MarketCache(
            market_id="market_test",
            question="Test question?",
            category="Crypto",
            yes_price=0.55,
            no_price=0.45,
            volume=100000.0
        )
        
        result = self.db.cache_market_data("market_test", market)
        self.assertTrue(result)
        
        # Retrieve
        cached = self.db.get_cached_market("market_test")
        self.assertIsNotNone(cached)
        self.assertEqual(cached['question'], "Test question?")
        self.assertEqual(cached['category'], "Crypto")
    
    def test_get_markets_by_category(self):
        """Test filtering markets by category."""
        # Add markets in different categories
        for i in range(3):
            market = MarketCache(
                market_id=f"crypto_{i}",
                question=f"Crypto question {i}?",
                category="Crypto"
            )
            self.db.cache_market_data(f"crypto_{i}", market)
        
        for i in range(2):
            market = MarketCache(
                market_id=f"sports_{i}",
                question=f"Sports question {i}?",
                category="Sports"
            )
            self.db.cache_market_data(f"sports_{i}", market)
        
        crypto_markets = self.db.get_markets_by_category("Crypto")
        self.assertEqual(len(crypto_markets), 3)
    
    def test_log_event(self):
        """Test logging system events."""
        result = self.db.log_event(
            EventType.INFO,
            "Test message",
            {"key": "value"}
        )
        self.assertTrue(result)
        
        # Verify
        events = self.db.get_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['message'], "Test message")
        self.assertEqual(events[0]['data']['key'], "value")
    
    def test_get_events_filtering(self):
        """Test event filtering by type."""
        # Log different event types
        self.db.log_event(EventType.INFO, "Info message")
        self.db.log_event(EventType.WARNING, "Warning message")
        self.db.log_event(EventType.ERROR, "Error message")
        self.db.log_event(EventType.INFO, "Another info")
        
        # Filter by type
        info_events = self.db.get_events(event_type=EventType.INFO)
        self.assertEqual(len(info_events), 2)
        
        warning_events = self.db.get_events(event_type=EventType.WARNING)
        self.assertEqual(len(warning_events), 1)
    
    def test_performance_summary(self):
        """Test performance summary calculation."""
        # Add some trades
        for i in range(5):
            trade = TradeData(
                trade_id=f"trade_{i}",
                market_id=f"market_{i}",
                market_question="Test",
                side="YES",
                trade_type="paper",
                entry_price=0.50,
                size_usd=100.0,
                status="closed",
                exit_price=0.60 if i < 3 else 0.40,  # 3 winners, 2 losers
                pnl=20.0 if i < 3 else -20.0
            )
            self.db.record_trade(trade)
        
        summary = self.db.get_performance_summary(days=30)
        self.assertEqual(summary['total_trades'], 5)
        self.assertEqual(summary['winning_trades'], 3)
        self.assertEqual(summary['losing_trades'], 2)
        self.assertEqual(summary['win_rate'], 60.0)
    
    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        # Add winning trades
        for i in range(3):
            trade = TradeData(
                trade_id=f"win_{i}",
                market_id="m1",
                market_question="Test",
                side="YES",
                trade_type="paper",
                entry_price=0.50,
                size_usd=100.0,
                status="closed",
                exit_price=0.60,
                pnl=20.0
            )
            self.db.record_trade(trade)
        
        # Add losing trades
        for i in range(2):
            trade = TradeData(
                trade_id=f"loss_{i}",
                market_id="m2",
                market_question="Test",
                side="NO",
                trade_type="paper",
                entry_price=0.50,
                size_usd=100.0,
                status="closed",
                exit_price=0.40,
                pnl=-20.0
            )
            self.db.record_trade(trade)
        
        win_rate = self.db.get_win_rate(days=30)
        self.assertEqual(win_rate, 60.0)
    
    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        # Add trades with specific P&L
        trades_data = [
            ("t1", 100.0),   # Win
            ("t2", 150.0),   # Win
            ("t3", -50.0),   # Loss
            ("t4", -25.0),   # Loss
        ]
        
        for trade_id, pnl in trades_data:
            trade = TradeData(
                trade_id=trade_id,
                market_id="m1",
                market_question="Test",
                side="YES",
                trade_type="paper",
                entry_price=0.50,
                size_usd=100.0,
                status="closed",
                exit_price=0.60,
                pnl=pnl
            )
            self.db.record_trade(trade)
        
        pf = self.db.get_profit_factor(days=30)
        # Gross profit: 250, Gross loss: 75, PF = 250/75 = 3.33
        self.assertAlmostEqual(pf, 3.33, places=1)
    
    def test_pattern_performance(self):
        """Test pattern performance analysis."""
        # Add trades with different patterns
        patterns = [
            ("momentum_burst", 20.0),
            ("momentum_burst", 15.0),
            ("momentum_burst", -10.0),
            ("breakout", 25.0),
            ("breakout", -5.0),
        ]
        
        for i, (pattern, pnl) in enumerate(patterns):
            trade = TradeData(
                trade_id=f"p{i}",
                market_id="m1",
                market_question="Test",
                side="YES",
                trade_type="paper",
                entry_price=0.50,
                size_usd=100.0,
                status="closed",
                pattern_type=pattern,
                exit_price=0.60,
                pnl=pnl
            )
            self.db.record_trade(trade)
        
        patterns_perf = self.db.get_pattern_performance()
        self.assertEqual(len(patterns_perf), 2)
        
        # Find momentum burst stats
        momentum = next(p for p in patterns_perf if p['pattern_type'] == 'momentum_burst')
        self.assertEqual(momentum['total_signals'], 3)
        self.assertAlmostEqual(momentum['win_rate'], 66.7, places=1)
    
    def test_database_stats(self):
        """Test database statistics."""
        # Add some data
        self.db.record_trade(TradeData(
            trade_id="t1",
            market_id="m1",
            market_question="Test",
            side="YES",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0
        ))
        
        self.db.save_whale_profile(WhaleProfile(address="0xw1"))
        self.db.cache_market_data("m1", MarketCache(market_id="m1", question="Test"))
        self.db.log_event(EventType.INFO, "Test")
        
        stats = self.db.get_database_stats()
        self.assertEqual(stats['trades'], 1)
        self.assertEqual(stats['whale_profiles'], 1)
        self.assertEqual(stats['market_cache'], 1)
        self.assertEqual(stats['system_events'], 1)
        self.assertIn('database_size_bytes', stats)
    
    def test_trade_history_filtering(self):
        """Test trade history with filters."""
        # Add trades with different attributes
        self.db.record_trade(TradeData(
            trade_id="t1",
            market_id="m1",
            market_question="Test",
            side="YES",
            trade_type="paper",
            entry_price=0.50,
            size_usd=100.0,
            status="open"
        ))
        
        self.db.record_trade(TradeData(
            trade_id="t2",
            market_id="m2",
            market_question="Test",
            side="NO",
            trade_type="live",
            entry_price=0.50,
            size_usd=100.0,
            status="closed",
            exit_price=0.60,
            pnl=20.0
        ))
        
        # Filter by status
        open_trades = self.db.get_trade_history(filters={'status': 'open'})
        self.assertEqual(len(open_trades), 1)
        
        # Filter by trade type
        live_trades = self.db.get_trade_history(filters={'trade_type': 'live'})
        self.assertEqual(len(live_trades), 1)
    
    def test_whale_profile_update(self):
        """Test updating an existing whale profile."""
        # Create initial profile
        whale = WhaleProfile(
            address="0xupdate",
            total_trades=10,
            win_rate=50.0,
            reliability_tier="bronze"
        )
        self.db.save_whale_profile(whale)
        
        # Update
        updated = WhaleProfile(
            address="0xupdate",
            total_trades=20,
            win_rate=60.0,
            reliability_tier="silver"
        )
        self.db.save_whale_profile(updated)
        
        # Verify
        profile = self.db.get_whale_profile("0xupdate")
        self.assertEqual(profile['total_trades'], 20)
        self.assertEqual(profile['win_rate'], 60.0)
        self.assertEqual(profile['reliability_tier'], "silver")


if __name__ == '__main__':
    unittest.main(verbosity=2)
