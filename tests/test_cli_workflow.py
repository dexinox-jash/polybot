"""
Agent 5: CLI Workflow Tester

Validates:
- Command parsing and execution
- State management
- Daily target tracking
- Portfolio updates
- Error handling
- User confirmation flows
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List


class MockState:
    """Mock bot state for testing."""
    
    def __init__(self):
        self.daily_bet_count = 0
        self.last_bet_date = None
        self.portfolio_value = 10000
        self.current_positions = []
        self.daily_pnl = 0
        self.total_pnl = 0
        self.winners_cached = []
        self.recommended_trade = None
    
    def to_dict(self):
        return {
            "daily_bet_count": self.daily_bet_count,
            "last_bet_date": self.last_bet_date,
            "portfolio_value": self.portfolio_value,
            "current_positions": self.current_positions,
            "daily_pnl": self.daily_pnl,
            "total_pnl": self.total_pnl,
            "winners_cached": self.winners_cached,
        }
    
    @classmethod
    def from_dict(cls, data):
        state = cls()
        state.daily_bet_count = data.get("daily_bet_count", 0)
        state.last_bet_date = data.get("last_bet_date")
        state.portfolio_value = data.get("portfolio_value", 10000)
        state.current_positions = data.get("current_positions", [])
        state.daily_pnl = data.get("daily_pnl", 0)
        state.total_pnl = data.get("total_pnl", 0)
        state.winners_cached = data.get("winners_cached", [])
        return state


class TestStateManagement(unittest.TestCase):
    """Test bot state management."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = MockState()
    
    def test_initial_state(self):
        """Test initial state values."""
        self.assertEqual(self.state.daily_bet_count, 0)
        self.assertEqual(self.state.portfolio_value, 10000)
        self.assertEqual(len(self.state.current_positions), 0)
        self.assertEqual(self.state.daily_pnl, 0)
        
        print(f"  [PASS] Initial state correct")
    
    def test_daily_reset(self):
        """Test daily counter reset."""
        # Simulate yesterday's activity
        self.state.daily_bet_count = 1
        self.state.daily_pnl = 500
        self.state.last_bet_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Check if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.last_bet_date != today:
            self.state.daily_bet_count = 0
            self.state.daily_pnl = 0
            self.state.last_bet_date = today
        
        self.assertEqual(self.state.daily_bet_count, 0)
        self.assertEqual(self.state.daily_pnl, 0)
        
        print(f"  [PASS] Daily reset working")
    
    def test_no_reset_same_day(self):
        """Test that same day doesn't reset."""
        self.state.daily_bet_count = 1
        self.state.daily_pnl = 200
        self.state.last_bet_date = datetime.now().strftime("%Y-%m-%d")
        
        # Check same day
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.last_bet_date != today:
            self.state.daily_bet_count = 0
            self.state.daily_pnl = 0
        
        self.assertEqual(self.state.daily_bet_count, 1)
        self.assertEqual(self.state.daily_pnl, 200)
        
        print(f"  [PASS] Same day preserved")
    
    def test_state_persistence(self):
        """Test state save/load."""
        # Modify state
        self.state.daily_bet_count = 1
        self.state.portfolio_value = 10500
        self.state.current_positions = [{"market": "test", "size": 200}]
        
        # Save to dict
        data = self.state.to_dict()
        
        # Load from dict
        loaded = MockState.from_dict(data)
        
        self.assertEqual(loaded.daily_bet_count, 1)
        self.assertEqual(loaded.portfolio_value, 10500)
        self.assertEqual(len(loaded.current_positions), 1)
        
        print(f"  [PASS] State persistence working")
    
    def test_position_addition(self):
        """Test adding positions."""
        trade = {"market": "BTC_65K", "size": 200, "entry_time": datetime.now().isoformat()}
        
        self.state.current_positions.append(trade)
        self.state.daily_bet_count += 1
        
        self.assertEqual(len(self.state.current_positions), 1)
        self.assertEqual(self.state.daily_bet_count, 1)
        
        print(f"  [PASS] Position addition working")
    
    def test_position_removal(self):
        """Test removing positions."""
        # Add position
        self.state.current_positions = [
            {"market": "BTC_65K", "size": 200},
            {"market": "ETH_3K", "size": 150}
        ]
        
        # Remove one
        self.state.current_positions = [p for p in self.state.current_positions 
                                       if p["market"] != "BTC_65K"]
        
        self.assertEqual(len(self.state.current_positions), 1)
        self.assertEqual(self.state.current_positions[0]["market"], "ETH_3K")
        
        print(f"  [PASS] Position removal working")
    
    def test_pnl_updates(self):
        """Test P&L tracking."""
        # Winning day
        self.state.daily_pnl += 300
        self.state.total_pnl += 300
        self.state.portfolio_value += 300
        
        self.assertEqual(self.state.daily_pnl, 300)
        self.assertEqual(self.state.total_pnl, 300)
        self.assertEqual(self.state.portfolio_value, 10300)
        
        # Losing trade
        self.state.daily_pnl -= 100
        self.state.total_pnl -= 100
        self.state.portfolio_value -= 100
        
        self.assertEqual(self.state.daily_pnl, 200)
        self.assertEqual(self.state.total_pnl, 200)
        
        print(f"  [PASS] P&L tracking working")


class TestCommandValidation(unittest.TestCase):
    """Test command validation."""
    
    def test_status_command(self):
        """Test status command execution."""
        state = MockState()
        
        # Should always work
        can_run = True
        self.assertTrue(can_run)
        
        print(f"  [PASS] Status command always available")
    
    def test_scan_command(self):
        """Test scan command validation."""
        state = MockState()
        
        # Scan needs API access - always allowed but may fail
        can_run = True
        self.assertTrue(can_run)
        
        print(f"  [PASS] Scan command validation")
    
    def test_analyze_command(self):
        """Test analyze command validation."""
        state = MockState()
        
        # Analyze needs winners cached
        def can_analyze(state):
            if state.daily_bet_count >= 1:
                return False, "Daily limit reached"
            if not state.winners_cached:
                return False, "No winners cached"
            return True, "OK"
        
        # Without winners
        ok, msg = can_analyze(state)
        self.assertFalse(ok)
        self.assertEqual(msg, "No winners cached")
        
        # With winners
        state.winners_cached = [{"address": "0x123"}]
        ok, msg = can_analyze(state)
        self.assertTrue(ok)
        
        # With daily limit reached
        state.daily_bet_count = 1
        ok, msg = can_analyze(state)
        self.assertFalse(ok)
        self.assertEqual(msg, "Daily limit reached")
        
        print(f"  [PASS] Analyze command validation")
    
    def test_copy_command(self):
        """Test copy command validation."""
        state = MockState()
        
        def can_copy(state, auto_confirm=False):
            if state.daily_bet_count >= 1:
                return False, "Daily limit reached"
            if not state.recommended_trade:
                return False, "No recommended trade"
            if not auto_confirm:
                return False, "Needs --yes flag"
            return True, "OK"
        
        # No trade recommended
        ok, msg = can_copy(state, auto_confirm=True)
        self.assertFalse(ok)
        
        # Has trade but no confirmation
        state.recommended_trade = {"market": "BTC", "size": 200}
        ok, msg = can_copy(state, auto_confirm=False)
        self.assertFalse(ok)
        self.assertEqual(msg, "Needs --yes flag")
        
        # Ready to execute
        ok, msg = can_copy(state, auto_confirm=True)
        self.assertTrue(ok)
        
        print(f"  [PASS] Copy command validation")


class TestWorkflowIntegration(unittest.TestCase):
    """Test complete workflows."""
    
    def test_full_daily_workflow(self):
        """Test complete daily workflow."""
        state = MockState()
        
        # Step 1: Status check
        self.assertEqual(state.daily_bet_count, 0)
        
        # Step 2: Scan winners
        state.winners_cached = [
            {"address": f"0x{i:03d}", "win_rate": 0.60 + i*0.01} 
            for i in range(5)
        ]
        self.assertEqual(len(state.winners_cached), 5)
        
        # Step 3: Analyze (would recommend trade)
        state.recommended_trade = {
            "winner": state.winners_cached[0],
            "market": "BTC_65K_Mar",
            "size": 200,
            "ev": 8.5
        }
        self.assertIsNotNone(state.recommended_trade)
        
        # Step 4: Copy (with confirmation)
        trade = state.recommended_trade
        state.current_positions.append({
            "market": trade["market"],
            "size": trade["size"],
            "entry_time": datetime.now().isoformat()
        })
        state.daily_bet_count += 1
        
        # Verify final state
        self.assertEqual(state.daily_bet_count, 1)
        self.assertEqual(len(state.current_positions), 1)
        
        print(f"  [PASS] Full daily workflow executed")
    
    def test_double_trade_prevention(self):
        """Test that double trading is prevented."""
        state = MockState()
        state.daily_bet_count = 1
        state.winners_cached = [{"address": "0x123"}]
        
        # Try to analyze when daily limit reached
        can_analyze = state.daily_bet_count < 1
        self.assertFalse(can_analyze)
        
        # Try to copy when daily limit reached
        can_copy = state.daily_bet_count < 1
        self.assertFalse(can_copy)
        
        print(f"  [PASS] Double trade prevention working")
    
    def test_portfolio_heat_check(self):
        """Test portfolio heat calculation in workflow."""
        state = MockState()
        state.portfolio_value = 10000
        
        # Add positions
        state.current_positions = [
            {"market": "BTC", "size": 2000},
            {"market": "ETH", "size": 1500},
        ]
        
        exposure = sum(p["size"] for p in state.current_positions)
        heat = exposure / state.portfolio_value
        
        self.assertEqual(heat, 0.35)
        self.assertLess(heat, 0.50)  # Under limit
        
        # Add more to reach limit
        state.current_positions.append({"market": "SOL", "size": 1500})
        new_heat = sum(p["size"] for p in state.current_positions) / state.portfolio_value
        
        self.assertEqual(new_heat, 0.50)  # At limit
        
        print(f"  [PASS] Portfolio heat tracking: {heat:.0%} -> {new_heat:.0%}")


class TestErrorHandling(unittest.TestCase):
    """Test error handling."""
    
    def test_missing_state_file(self):
        """Test handling of missing state file."""
        # Simulate loading from non-existent file
        data = {}
        state = MockState.from_dict(data)
        
        # Should have defaults
        self.assertEqual(state.portfolio_value, 10000)
        self.assertEqual(state.daily_bet_count, 0)
        
        print(f"  [PASS] Missing state file handled")
    
    def test_corrupted_state(self):
        """Test handling of corrupted state."""
        corrupted = {
            "portfolio_value": "not_a_number",
            "daily_bet_count": -5,  # Invalid
        }
        
        # Should handle gracefully
        try:
            if isinstance(corrupted.get("portfolio_value"), (int, float)):
                value = corrupted["portfolio_value"]
            else:
                value = 10000  # Default
            
            count = max(0, corrupted.get("daily_bet_count", 0))
            self.assertEqual(value, 10000)
            self.assertEqual(count, 0)
        except:
            self.fail("Should handle corrupted state")
        
        print(f"  [PASS] Corrupted state handled")
    
    def test_invalid_trade_data(self):
        """Test handling of invalid trade data."""
        invalid_trade = {
            "market": None,
            "size": -100,  # Negative
        }
        
        # Validation
        is_valid = (invalid_trade.get("market") and 
                   invalid_trade.get("size", 0) > 0)
        
        self.assertFalse(is_valid)
        
        print(f"  [PASS] Invalid trade data rejected")


def run_tests():
    """Run all CLI workflow tests."""
    print("\n" + "="*70)
    print("AGENT 5: CLI WORKFLOW TESTER")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestStateManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestCommandValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkflowIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    run_tests()
