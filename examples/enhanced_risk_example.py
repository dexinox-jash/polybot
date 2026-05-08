"""
Enhanced Risk Manager - Example Usage

This example demonstrates how to integrate the EnhancedRiskManager
with the paper trading system for comprehensive risk management.

Features demonstrated:
1. Per-trade risk controls
2. Portfolio risk management
3. Circuit breakers
4. Tiered take-profit exits
5. Volatility-adjusted sizing
6. Risk status monitoring
"""

import sys
import random
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, 'c:\\Users\\Dexinox\\Documents\\kimi code\\Polybot')

from polymarket_tracker.risk import (
    EnhancedRiskManager,
    RiskManagedPaperTradingSession,
    CircuitBreakerType,
    ExitReason,
    RiskStatus,
)


def example_basic_usage():
    """Basic usage example of EnhancedRiskManager."""
    print("=" * 70)
    print("EXAMPLE 1: Basic EnhancedRiskManager Usage")
    print("=" * 70)
    
    # Initialize risk manager
    risk_manager = EnhancedRiskManager(
        initial_balance=10000.0,
        max_trade_loss_pct=0.02,      # 2% max loss per trade
        max_portfolio_heat_pct=0.50,  # 50% max portfolio heat
        max_daily_drawdown_pct=0.10,  # 10% daily drawdown limit
        max_total_drawdown_pct=0.20,  # 20% total drawdown stop
        max_positions=5
    )
    
    print(f"\nInitial balance: $10,000")
    print(f"Max trade loss: 2%")
    print(f"Max portfolio heat: 50%")
    print(f"Max daily drawdown: 10%")
    print(f"Max concurrent positions: 5")
    
    # Check if we can open a position
    can_trade, reason = risk_manager.can_open_position(
        size=1000,
        current_balance=10000.0,
        open_positions=[]
    )
    print(f"\nCan trade $1,000 position? {can_trade} ({reason})")
    
    # Register a position
    risk_profile = risk_manager.register_position(
        entry_price=0.50,
        direction='YES',
        size_usd=1000
    )
    print(f"\nPosition registered: {risk_profile.position_id}")
    print(f"  Entry: ${risk_profile.entry_price}")
    print(f"  Size: ${risk_profile.size_usd}")
    print(f"  Stop Loss: ${risk_profile.stop_loss_price:.4f}")
    print(f"  Time Exit: {risk_profile.time_exit_at}")
    
    # Check exit conditions at various prices
    test_prices = [0.48, 0.52, 0.55, 0.60]
    print("\n--- Exit Condition Tests ---")
    for price in test_prices:
        should_exit, reason, details = risk_manager.check_exit_conditions(
            risk_profile.position_id, price
        )
        status = "EXIT" if should_exit else "HOLD"
        reason_str = reason.value if reason else "none"
        print(f"Price ${price:.2f}: {status} ({reason_str})")
    
    # Get status
    status = risk_manager.get_status()
    print("\n--- Risk Status ---")
    print(f"Risk Status: {status['risk_status']}")
    print(f"Open Positions: {status['positions']['open_count']}")
    print(f"Portfolio Heat: ${status['positions']['heat']:.0f} ({status['positions']['heat_pct']:.1%})")


def example_circuit_breakers():
    """Demonstrate circuit breaker functionality."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Circuit Breakers")
    print("=" * 70)
    
    risk_manager = EnhancedRiskManager(initial_balance=10000.0)
    
    # Simulate consecutive losses
    print("\nSimulating 3 consecutive losing trades...")
    for i in range(3):
        # Register and close a losing position
        profile = risk_manager.register_position(
            entry_price=0.50,
            direction='YES',
            size_usd=1000
        )
        # Close with loss
        risk_manager.close_position(
            profile.position_id,
            exit_price=0.475,  # 5% loss
            pnl=-25.0,
            exit_reason=ExitReason.STOP_LOSS
        )
        print(f"  Trade {i+1}: Loss -$25.00")
    
    # Try to open another position
    can_trade, reason = risk_manager.can_open_position(
        size=1000,
        current_balance=9925.0,
        open_positions=[]
    )
    print(f"\nCan trade after 3 losses? {can_trade}")
    print(f"Reason: {reason}")
    
    # Show status
    status = risk_manager.get_status()
    print(f"\nCircuit Breaker Active: {status['circuit_breaker']['active']}")
    print(f"Circuit Breaker Type: {status['circuit_breaker']['type']}")
    print(f"Consecutive Losses: {status['daily_stats']['consecutive_losses']}")


def example_tiered_exits():
    """Demonstrate tiered take-profit exits."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Tiered Take-Profit Exits")
    print("=" * 70)
    
    risk_manager = EnhancedRiskManager(initial_balance=10000.0)
    
    # Open a position
    profile = risk_manager.register_position(
        entry_price=0.50,
        direction='YES',
        size_usd=1000
    )
    
    print(f"\nPosition opened at $0.50")
    print(f"Tier 1 (+10%): $0.55 (close 50%)")
    print(f"Tier 2 (+20%): $0.60 (close remaining)")
    print(f"Trailing stop activates at +15% ($0.575)")
    
    # Test various price levels
    price_scenarios = [
        (0.52, "Small profit"),
        (0.55, "Tier 1 target hit"),
        (0.57, "Above tier 1, trailing stop active"),
        (0.60, "Tier 2 target hit"),
    ]
    
    for price, description in price_scenarios:
        should_exit, reason, details = risk_manager.check_exit_conditions(
            profile.position_id, price
        )
        
        print(f"\nPrice ${price:.2f} - {description}")
        print(f"  Should exit: {should_exit}")
        print(f"  Reason: {reason.value if reason else 'none'}")
        
        if details:
            for key, value in details.items():
                print(f"  {key}: {value}")


def example_volatility_adjustment():
    """Demonstrate volatility-adjusted position sizing."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Volatility-Adjusted Position Sizing")
    print("=" * 70)
    
    risk_manager = EnhancedRiskManager(initial_balance=10000.0)
    
    # Simulate different volatility regimes
    volatility_scenarios = [
        ([0.5, 0.3, 0.4, 0.2, 0.3], "Low volatility"),
        ([1.5, 2.0, 1.8, 2.2, 1.9], "Normal volatility"),
        ([4.0, 5.5, 4.5, 6.0, 5.0], "High volatility"),
        ([8.0, 10.0, 12.0, 9.0, 11.0], "Extreme volatility"),
    ]
    
    for changes, description in volatility_scenarios:
        # Create fresh risk manager for each scenario
        rm = EnhancedRiskManager(initial_balance=10000.0)
        
        # Add price changes
        for change in changes:
            rm.record_volatility(change)
        
        status = rm.get_status()
        
        print(f"\n{description}:")
        print(f"  Volatility: {rm.volatility_metrics.current_volatility:.2f}")
        print(f"  Regime: {rm.volatility_metrics.volatility_regime}")
        print(f"  Position size multiplier: {status['volatility']['position_size_multiplier']:.1f}")
        
        # Calculate recommended size for $1,000 base
        recommended = rm.get_recommended_position_size(
            signal_confidence=0.8,
            base_size=1000,
            current_balance=10000.0
        )
        print(f"  Recommended size (base $1,000): ${recommended:.0f}")


def example_risk_managed_session():
    """Demonstrate RiskManagedPaperTradingSession."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Risk-Managed Paper Trading Session")
    print("=" * 70)
    
    # Create session
    session = RiskManagedPaperTradingSession(
        initial_balance=10000.0,
        max_trade_loss_pct=0.02,
        max_portfolio_heat_pct=0.50,
        max_positions=5
    )
    
    print(f"\nStarting balance: $10,000")
    
    # Simulate opening some positions
    class MockSignal:
        def __init__(self, direction, price, confidence, size):
            self.direction = direction
            self.price = price
            self.pattern_confidence = confidence
            self.suggested_size = size
            self.market_id = "mock-market-1"
            self.whale_address = "0x1234"
    
    # Open first position
    signal1 = MockSignal('YES', 0.50, 0.75, 1000)
    pos1 = session.open_position(
        signal=signal1,
        market_data={'current_price': 0.50},
        delay_seconds=5.0
    )
    
    if pos1:
        print(f"\nOpened position 1:")
        print(f"  ID: {pos1['position_id']}")
        print(f"  Direction: {pos1['direction']}")
        print(f"  Size: ${pos1['size_usd']:.0f}")
        print(f"  Entry: ${pos1['entry_price']:.4f}")
    
    # Try to open more positions
    for i in range(6):
        signal = MockSignal('YES', 0.50 + i*0.01, 0.7, 1000)
        pos = session.open_position(
            signal=signal,
            market_data={'current_price': signal.price},
            delay_seconds=3.0
        )
        
        if pos:
            print(f"Opened position {i+2}: ${pos['size_usd']:.0f} at ${pos['entry_price']:.4f}")
        else:
            can_trade, reason = session.can_trade(1000)
            print(f"Position {i+2} rejected: {reason}")
            break
    
    # Show current status
    status = session.get_risk_status()
    print(f"\n--- Session Status ---")
    print(f"Open positions: {status['session']['open_positions']}")
    print(f"Total trades: {status['session']['total_trades']}")
    print(f"Portfolio heat: ${status['positions']['heat']:.0f} ({status['positions']['heat_pct']:.1%})")
    print(f"Risk status: {status['risk_status']}")
    
    # Simulate price updates
    print("\n--- Simulating Price Updates ---")
    market_prices = {
        pos['market_id']: 0.55  # 10% gain
        for pos in session.positions.values()
    }
    
    # Update one market with a price that should trigger tier 1
    if session.positions:
        first_pos_id = list(session.positions.keys())[0]
        session.positions[first_pos_id]['current_price'] = 0.55
        market_prices[session.positions[first_pos_id]['market_id']] = 0.55
    
    session.update_positions(market_prices)
    
    print(f"Positions remaining: {len(session.positions)}")
    print(f"Current balance: ${session.balance:.2f}")


def example_api_error_handling():
    """Demonstrate API error tracking and circuit breakers."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: API Error Handling")
    print("=" * 70)
    
    risk_manager = EnhancedRiskManager(initial_balance=10000.0)
    
    print("\nSimulating API errors...")
    
    # Simulate some errors
    for i in range(5):
        risk_manager.record_api_error(f"error_type_{i}")
        print(f"  Recorded error {i+1}")
    
    status = risk_manager.get_status()
    print(f"\nErrors in window: {status['api_health']['errors_in_window']}")
    print(f"Consecutive errors: {status['api_health']['consecutive_errors']}")
    
    # Try to trade
    can_trade, reason = risk_manager.can_open_position(
        size=1000,
        current_balance=10000.0,
        open_positions=[]
    )
    print(f"\nCan trade? {can_trade}")
    print(f"Reason: {reason}")
    
    # Record some successes to reset
    print("\nRecording successful API calls...")
    for _ in range(3):
        risk_manager.record_api_success()
    
    status = risk_manager.get_status()
    print(f"Consecutive errors after successes: {status['api_health']['consecutive_errors']}")


def example_drawdown_protection():
    """Demonstrate drawdown protection and daily limits."""
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Drawdown Protection")
    print("=" * 70)
    
    risk_manager = EnhancedRiskManager(
        initial_balance=10000.0,
        max_daily_drawdown_pct=0.10,
        max_total_drawdown_pct=0.20
    )
    
    print(f"\nInitial balance: $10,000")
    print(f"Daily drawdown limit: 10%")
    print(f"Total drawdown limit: 20%")
    
    # Simulate losses
    loss_scenarios = [
        (-500, "-$500 loss"),
        (-400, "-$400 loss (total -$900)"),
        (-200, "-$200 loss (total -$1,100)"),
    ]
    
    current_balance = 10000.0
    
    for loss, description in loss_scenarios:
        current_balance += loss
        risk_manager.current_balance = current_balance
        risk_manager.update_daily_stats(loss)
        
        status = risk_manager.get_status()
        
        print(f"\n{description}")
        print(f"  Current balance: ${current_balance:.2f}")
        print(f"  Daily drawdown: {status['drawdown']['daily']:.1%}")
        print(f"  Total drawdown: {status['drawdown']['total']:.1%}")
        
        # Check if can trade
        can_trade, reason = risk_manager.can_open_position(
            size=1000,
            current_balance=current_balance,
            open_positions=[]
        )
        print(f"  Can trade: {can_trade} ({reason})")


def run_all_examples():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("ENHANCED RISK MANAGER - COMPREHENSIVE EXAMPLES")
    print("=" * 70)
    print("\nThis demo shows all features of the Enhanced Risk Manager")
    print("=" * 70)
    
    example_basic_usage()
    example_circuit_breakers()
    example_tiered_exits()
    example_volatility_adjustment()
    example_risk_managed_session()
    example_api_error_handling()
    example_drawdown_protection()
    
    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    run_all_examples()
