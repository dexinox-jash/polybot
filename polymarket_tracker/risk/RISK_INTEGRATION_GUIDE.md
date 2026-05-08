# Enhanced Risk Manager - Integration Guide

This guide explains how to integrate the `EnhancedRiskManager` with the existing PolyBot paper trading system.

## Overview

The `EnhancedRiskManager` provides comprehensive risk management including:
- Per-trade risk controls (max loss, stop loss, take profit targets)
- Portfolio risk management (heat, concurrent positions, drawdown)
- Circuit breakers (daily loss, consecutive losses, volatility, API errors)
- Tiered take-profit exits
- Volatility-adjusted position sizing

## Quick Start

### Option 1: Use RiskManagedPaperTradingSession (Recommended)

This wraps the risk manager with a session-based interface:

```python
from polymarket_tracker.risk import RiskManagedPaperTradingSession, ExitReason

# Initialize session
session = RiskManagedPaperTradingSession(
    initial_balance=10000.0,
    max_trade_loss_pct=0.02,      # 2% max loss per trade
    max_portfolio_heat_pct=0.50,  # 50% max portfolio heat
    max_daily_drawdown_pct=0.10,  # 10% daily drawdown limit
    max_positions=5
)

# Check if trading is allowed
can_trade, reason = session.can_trade(proposed_size=1000)
if can_trade:
    # Open position using signal
    position = session.open_position(
        signal=signal,
        market_data={'current_price': 0.50}
    )

# Update positions periodically (checks exits)
market_prices = {'market-1': 0.55, 'market-2': 0.48}
session.update_positions(market_prices)

# Get comprehensive risk status
status = session.get_risk_status()
print(f"Risk Status: {status['risk_status']}")
print(f"Portfolio Heat: {status['positions']['heat_pct']:.1%}")
print(f"Daily P&L: ${status['daily_stats']['realized_pnl']:+.2f}")
```

### Option 2: Direct EnhancedRiskManager Usage

For more control, use the risk manager directly:

```python
from polymarket_tracker.risk import EnhancedRiskManager, ExitReason

# Initialize risk manager
risk_manager = EnhancedRiskManager(initial_balance=10000.0)

# Before opening position
can_trade, reason = risk_manager.can_open_position(
    size=1000,
    current_balance=10000.0,
    open_positions=current_positions
)

if can_trade:
    # Register the position
    risk_profile = risk_manager.register_position(
        entry_price=0.50,
        direction='YES',
        size_usd=1000
    )
    
    # Store position_id for later
    position_id = risk_profile.position_id

# Periodically check exit conditions
should_exit, reason, details = risk_manager.check_exit_conditions(
    position_id=position_id,
    current_price=0.55
)

if should_exit:
    # Close position
    result = risk_manager.close_position(
        position_id=position_id,
        exit_price=0.55,
        pnl=50.0,
        exit_reason=reason
    )
```

## Integration with Existing PaperTradingEngine

To integrate with the existing `PaperTradingEngine`:

```python
from polymarket_tracker.paper_trading.paper_trading_engine import PaperTradingEngine
from polymarket_tracker.risk import EnhancedRiskManager, ExitReason

class RiskManagedTradingEngine:
    """Paper trading engine with enhanced risk management."""
    
    def __init__(self, initial_balance=10000.0):
        self.engine = PaperTradingEngine(initial_balance)
        self.risk_manager = EnhancedRiskManager(initial_balance)
        
    def execute_trade(self, signal, market_data):
        """Execute trade with risk checks."""
        # Check risk limits
        can_trade, reason = self.risk_manager.can_open_position(
            size=getattr(signal, 'suggested_size', 1000),
            current_balance=self.engine.balance,
            open_positions=list(self.engine.positions.values())
        )
        
        if not can_trade:
            logger.warning(f"Trade rejected: {reason}")
            return None
        
        # Execute via original engine
        position = self.engine.execute_paper_trade(signal, 0, market_data)
        
        # Register with risk manager
        if position:
            risk_profile = self.risk_manager.register_position(
                entry_price=position.entry_price,
                direction=position.direction,
                size_usd=position.size_usd,
                custom_stop_loss=position.stop_loss_price
            )
            # Link risk profile to position
            position.risk_profile = risk_profile
        
        return position
    
    def update_positions(self, market_prices):
        """Update positions with risk checks."""
        # First, update via original engine
        self.engine.update_positions(market_prices)
        
        # Check additional risk exits
        for position_id, position in list(self.engine.positions.items()):
            if hasattr(position, 'risk_profile'):
                should_exit, reason, details = self.risk_manager.check_exit_conditions(
                    position.risk_profile.position_id,
                    market_prices.get(position.market_id, position.entry_price)
                )
                
                if should_exit and reason != ExitReason.STOP_LOSS:
                    # Close for reasons other than stop loss (already handled)
                    self.engine.close_position(position_id, details['exit_price'], reason.value)
                    
                    # Update risk manager
                    self.risk_manager.close_position(
                        position.risk_profile.position_id,
                        details['exit_price'],
                        details.get('pnl', 0),
                        reason
                    )
```

## Risk Parameters

### Per-Trade Risk Controls

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_trade_loss_pct` | 2% | Maximum loss per trade as % of balance |
| `STOP_LOSS_PCT` | 5% | Stop loss from entry price |
| `take_profit.tier1_pct` | 10% | First take profit target |
| `take_profit.tier1_size` | 50% | % of position to close at tier 1 |
| `take_profit.tier2_pct` | 20% | Second take profit target |
| `take_profit.tier2_size` | 100% | % of remaining position to close at tier 2 |
| `max_hold_hours` | 24 | Maximum time to hold a position |

### Portfolio Risk Controls

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_portfolio_heat_pct` | 50% | Max % of balance in open positions |
| `max_positions` | 5 | Maximum concurrent positions |
| `max_daily_drawdown_pct` | 10% | Daily loss limit before circuit breaker |
| `max_total_drawdown_pct` | 20% | Total drawdown before circuit breaker |

### Circuit Breaker Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `CONSECUTIVE_LOSSES_THRESHOLD` | 3 | Trades before pausing |
| `CONSECUTIVE_LOSSES_PAUSE_MINUTES` | 60 | Pause duration after consecutive losses |
| `HIGH_VOLATILITY_PAUSE_MINUTES` | 30 | Pause duration for high volatility |
| `API_ERROR_PAUSE_MINUTES` | 15 | Pause duration after API errors |

## Circuit Breakers

The system includes multiple circuit breakers:

### 1. Daily Loss Limit
```python
# Triggered when daily loss exceeds 10%
status = risk_manager.get_status()
if status['circuit_breaker']['active']:
    print(f"Trading paused due to: {status['circuit_breaker']['type']}")
```

### 2. Consecutive Losses
```python
# Automatically triggered after 3 consecutive losses
# Resets after 60 minutes or when a winning trade occurs
```

### 3. High Volatility
```python
# Record volatility data
risk_manager.record_volatility(price_change_pct=5.0)

# Check current regime
status = risk_manager.get_status()
print(f"Volatility: {status['volatility']['regime']}")
```

### 4. API Errors
```python
# Record API errors
risk_manager.record_api_error("timeout")
risk_manager.record_api_error("rate_limit")

# Record successes to reset
risk_manager.record_api_success()
```

## Tiered Take-Profit System

The system supports automatic tiered exits:

```python
from polymarket_tracker.risk import TakeProfitLevels

# Custom take profit levels
risk_profile = risk_manager.register_position(
    entry_price=0.50,
    direction='YES',
    size_usd=1000,
    custom_take_profit=TakeProfitLevels(
        tier1_pct=0.08,      # 8% for tier 1
        tier1_size=0.30,     # Close 30% at tier 1
        tier2_pct=0.15,      # 15% for tier 2
        tier2_size=1.0,      # Close remaining at tier 2
        trailing_stop_activation=0.12,
        trailing_stop_distance=0.03
    )
)

# Check for tier 1 exit
should_exit, reason, details = risk_manager.check_exit_conditions(
    position_id, current_price=0.54  # 8% gain
)
# Returns: True, ExitReason.TAKE_PROFIT_TIER1, {...}

# After tier 1, position size is reduced
# Check for tier 2 or trailing stop
should_exit, reason, details = risk_manager.check_exit_conditions(
    position_id, current_price=0.575  # 15% gain
)
# Returns: True, ExitReason.TAKE_PROFIT_TIER2 or ExitReason.TRAILING_STOP
```

## Volatility-Adjusted Sizing

Position sizes are automatically adjusted based on market volatility:

```python
# Record price changes to calculate volatility
for change in price_changes:
    risk_manager.record_volatility(change)

# Get recommended size
recommended_size = risk_manager.get_recommended_position_size(
    signal_confidence=0.8,
    base_size=1000,
    current_balance=10000.0
)

# Multipliers by regime:
# - Low volatility: 1.2x (increase size)
# - Normal: 1.0x (base size)
# - High: 0.6x (reduce size)
# - Extreme: 0.3x (significantly reduce)
```

## Risk Status Monitoring

Get comprehensive risk status:

```python
status = risk_manager.get_status()

# Overall risk status
print(f"Status: {status['risk_status']}")  # normal, caution, restricted, halted

# Circuit breaker state
if status['circuit_breaker']['active']:
    print(f"Circuit breaker: {status['circuit_breaker']['type']}")
    print(f"Resumes at: {status['circuit_breaker']['until']}")

# Balance and drawdown
print(f"Balance: ${status['balance']['current']:.2f}")
print(f"Daily drawdown: {status['drawdown']['daily']:.1%}")
print(f"Total drawdown: {status['drawdown']['total']:.1%}")

# Position information
print(f"Open positions: {status['positions']['open_count']}")
print(f"Portfolio heat: {status['positions']['heat_pct']:.1%}")

# Daily statistics
print(f"Today's trades: {status['daily_stats']['total_trades']}")
print(f"Win rate: {status['daily_stats']['win_rate']:.1%}")
print(f"Consecutive losses: {status['daily_stats']['consecutive_losses']}")

# Volatility
print(f"Volatility regime: {status['volatility']['regime']}")
print(f"Size multiplier: {status['volatility']['position_size_multiplier']}")

# API health
print(f"API errors (5min): {status['api_health']['errors_in_window']}")
```

## Daily Reset

Reset statistics at the start of each trading day:

```python
# At start of new trading day
risk_manager.reset_daily_stats(new_starting_balance=current_balance)

# Or with RiskManagedPaperTradingSession
session.reset_daily()
```

## Best Practices

1. **Always check `can_trade()` before opening positions**
   ```python
   can_trade, reason = risk_manager.can_open_position(...)
   if not can_trade:
       logger.warning(f"Trade blocked: {reason}")
       return
   ```

2. **Regularly update positions**
   ```python
   # In your main loop
   while running:
       market_prices = fetch_prices()
       session.update_positions(market_prices)
       time.sleep(1)
   ```

3. **Monitor circuit breakers**
   ```python
   status = risk_manager.get_status()
   if status['risk_status'] == 'halted':
       logger.critical("Trading halted - manual intervention required")
   ```

4. **Track API health**
   ```python
   try:
       data = api.fetch_data()
       risk_manager.record_api_success()
   except APIError as e:
       risk_manager.record_api_error(str(e))
   ```

5. **Record volatility data**
   ```python
   price_change = ((new_price - old_price) / old_price) * 100
   risk_manager.record_volatility(price_change)
   ```

## Error Handling

The risk manager handles various edge cases:

```python
# Unknown position
result = risk_manager.check_exit_conditions("unknown_id", 0.50)
# Returns: (False, None, None)

# Position already closed
result = risk_manager.close_position(closed_id, 0.55, 50.0)
# Returns: {}

# Circuit breaker active
can_trade, reason = risk_manager.can_open_position(...)
# Returns: (False, "Circuit breaker active (daily_loss_limit), 23h remaining")
```

## Testing

Run the comprehensive test suite:

```bash
cd c:\Users\Dexinox\Documents\kimi code\Polybot
python tests/test_enhanced_risk_manager.py
```

Run the example script:

```bash
python examples/enhanced_risk_example.py
```

## Migration from PositionManager

If you're currently using `PositionManager`:

```python
# Old way
from polymarket_tracker.risk import PositionManager
pm = PositionManager(initial_bankroll=10000.0)

# New way - EnhancedRiskManager
from polymarket_tracker.risk import EnhancedRiskManager
rm = EnhancedRiskManager(initial_balance=10000.0)

# Or use the wrapper session
from polymarket_tracker.risk import RiskManagedPaperTradingSession
session = RiskManagedPaperTradingSession(initial_balance=10000.0)
```

The `EnhancedRiskManager` provides all features of `PositionManager` plus:
- Circuit breakers
- Tiered take profits
- Volatility adjustment
- API error tracking
- More comprehensive status reporting
