# BTC 5-Minute Bot - Agent Documentation

## Project Focus

This is a **highly specialized analytical trading intelligence system** focused exclusively on Polymarket's Bitcoin 5-minute prediction markets. 

Unlike general whale trackers, this bot:
- Tracks only BTC 5-minute markets
- Optimizes for 300-second windows
- Uses micro-pattern recognition
- Implements Kelly Criterion sizing
- Focuses on execution quality analysis

## Architecture

```
Data Layer → Analysis Layer → Risk Layer → Execution
    │              │              │            │
    ▼              ▼              ▼            ▼
Scanner      Patterns       Position      Dashboard
Whales       Signals        Manager       Alerts
```

## Key Files

### Core Components
| File | Purpose |
|------|---------|
| `btc_market_scanner.py` | Real-time BTC 5-min market discovery |
| `micro_whale_tracker.py` | Short-term whale tracking |
| `pattern_engine.py` | 6 pattern types detection |
| `signal_generator.py` | Signal synthesis & confidence |
| `position_manager.py` | Kelly sizing & risk management |
| `btc_dashboard.py` | Streamlit UI |

### Entry Points
| File | Use Case |
|------|----------|
| `btc_bot_runner.py` | Complete bot with interactive CLI |
| `btc_dashboard.py` | Real-time monitoring dashboard |

## Development Guidelines

### Adding New Patterns
1. Add detection logic to `PatternEngine`
2. Define `SignalType` enum
3. Set confidence scoring weights
4. Add to dashboard visualization
5. Update tests

### Risk Management
- Never exceed 2% risk per trade (default)
- Always use half-Kelly sizing
- Implement circuit breakers
- Track R-multiples

### Testing
```bash
pytest tests/ -v
```

## Signal Flow

```
Price Tick → Pattern Detect → Whale Confluence → Composite Score
    │              │                  │                │
    ▼              ▼                  ▼                ▼
Buffer      6 Patterns         Top Traders      ≥ 65%?
                                         ↓
                                    Yes → Generate Signal
                                         ↓
                                    Risk Check → Execute
```

## Configuration

Edit `.env`:
```
THEGRAPH_API_KEY=xxx
```

Get key at: https://thegraph.com/studio/

## Performance Targets

| Metric | Target |
|--------|--------|
| Win Rate | > 55% |
| Profit Factor | > 1.5 |
| Expectancy | +0.5R |
| Max Drawdown | < 20% |
| Sharpe Ratio | > 1.0 |

## Safety Rules

1. **Educational Only**: Never use with real money without testing
2. **Paper Trade First**: Minimum 100 trades paper trading
3. **Start Small**: Begin with minimum position sizes
4. **Track Everything**: Log all decisions and outcomes
5. **Review Daily**: Analyze mistakes and refine

## Whale Intelligence

### What Makes a Good 5-Min Whale
- Fast execution (< 1 second from signal)
- Low slippage (< 0.1%)
- Consistent timing
- Win rate > 55% in 5-min markets
- Profit factor > 1.5

### Red Flags (Avoid)
- High slippage
- Slow execution
- Inconsistent sizing
- Chasing entries
- No stop discipline

## Pattern Types

### 1. Momentum Burst
- 2%+ move in 30 seconds
- Volume > 2x average
- Entry on pullback

### 2. Mean Reversion
- Z-score > 2
- Reversal candlestick
- Target: moving average

### 3. Breakout
- Range break + confirmation
- Volume surge
- Target: range projection

### 4. Liquidity Grab
- Large range, small net change
- Stop hunt pattern
- Fade the wick

### 5. Whale Accumulation
- > 60% whale buying
- Aligned with pattern
- Size surge

### 6. Whale Distribution
- > 60% whale selling
- Distribution pattern
- Contrarian signal

## Important Notes

- This is **research/educational software**
- 5-minute trading is **extremely high risk**
- Past performance **does not guarantee future results**
- Always **do your own research**
- Never **risk more than you can afford to lose**
