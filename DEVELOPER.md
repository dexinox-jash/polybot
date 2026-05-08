# PolyBot - Developer Guide

For developers who want to extend, modify, or integrate with PolyBot.

---

## Development Setup

### 1. Clone and Setup

```powershell
git clone <repo-url> Polybot
cd Polybot

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dev dependencies
pip install -r requirements.txt
pip install pytest black flake8 mypy
```

### 2. Project Structure

```
Polybot/
├── cli_bot.py                    # Main entry point
├── requirements.txt              # Dependencies
├── .env                          # API keys (not in git)
├── bot_state.json               # Runtime state
├── polymarket_tracker/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── subgraph_client.py   # GraphQL client
│   │   ├── gamma_client.py      # Gamma API
│   │   └── whale_tracker.py     # Whale monitoring
│   ├── winners/
│   │   ├── __init__.py
│   │   ├── winner_discovery.py  # Find winners
│   │   ├── ev_calculator.py     # EV calculations
│   │   ├── copy_engine.py       # Decision engine
│   │   └── bet_tracker.py       # Position tracking
│   ├── deep_analysis/
│   │   ├── __init__.py
│   │   ├── winner_intelligence.py
│   │   ├── advanced_ev.py
│   │   ├── multi_factor_model.py
│   │   └── research_engine.py
│   ├── risk/
│   │   ├── __init__.py
│   │   └── position_manager.py
│   ├── analysis/
│   │   ├── archetype_classifier.py
│   │   ├── consensus_engine.py
│   │   ├── pattern_engine.py
│   │   └── signal_generator.py
│   └── utils/
│       ├── config.py
│       └── logger.py
└── tests/
    ├── test_winner_discovery.py
    ├── test_ev_calculator.py
    ├── test_copy_engine.py
    ├── test_multi_factor.py
    ├── test_cli_workflow.py
    └── run_all_tests.py
```

---

## Adding a New Module

### Example: Custom Scoring Module

Create `polymarket_tracker/custom/my_scorer.py`:

```python
"""Custom scoring algorithm."""

from typing import Dict
from dataclasses import dataclass


@dataclass
class CustomScore:
    """Custom scoring result."""
    score: float
    confidence: float
    reasoning: str


class MyScorer:
    """Custom winner scoring algorithm."""
    
    def __init__(self, weight: float = 1.0):
        self.weight = weight
    
    def calculate(self, winner) -> CustomScore:
        """Calculate custom score for a winner."""
        # Your logic here
        score = winner.true_win_rate * 0.5 + winner.profit_factor * 0.3
        
        return CustomScore(
            score=score,
            confidence=0.8,
            reasoning="Weighted combination of WR and PF"
        )
```

Integrate into CLI:

```python
# cli_bot.py
from polymarket_tracker.custom.my_scorer import MyScorer

class CLIBot:
    def __init__(self):
        # ... existing init ...
        self.my_scorer = MyScorer(weight=0.5)
    
    async def analyze(self):
        # ... existing analysis ...
        custom_score = self.my_scorer.calculate(winner)
        print(f"Custom Score: {custom_score.score}")
```

---

## Extending the Copy Engine

### Add New Decision Type

```python
# polymarket_tracker/winners/copy_engine.py

class CopyDecisionType(Enum):
    # ... existing types ...
    SCALE_IN = "scale_in"  # Add new type

class CopyEngine:
    def evaluate_opportunity(self, winner, bet, portfolio):
        # ... existing logic ...
        
        # Add new condition
        if ev_percent > 15 and portfolio.heat < 0.3:
            return CopyDecision(
                decision=CopyDecisionType.SCALE_IN,
                confidence=0.9,
                target_size=position_size * 1.5,  # 1.5x size
                # ... other params ...
            )
```

---

## Custom Risk Parameters

### Create Custom Risk Profile

```python
# polymarket_tracker/risk/aggressive_params.py

from .position_manager import RiskParameters

AGGRESSIVE_PARAMS = RiskParameters(
    max_risk_per_trade=0.05,      # 5% per trade
    max_position_size=10000,       # $10k max
    max_total_exposure=0.70,       # 70% heat
    max_open_positions=10,         # 10 positions
    max_daily_drawdown=0.15,       # 15% drawdown
)

CONSERVATIVE_PARAMS = RiskParameters(
    max_risk_per_trade=0.01,      # 1% per trade
    max_position_size=200,         # $200 max
    max_total_exposure=0.30,       # 30% heat
    max_open_positions=3,          # 3 positions
    max_daily_drawdown=0.05,       # 5% drawdown
)
```

Use in CLI:

```python
# cli_bot.py
from polymarket_tracker.risk.aggressive_params import AGGRESSIVE_PARAMS

self.position_manager = PositionManager(
    initial_bankroll=10000,
    risk_params=AGGRESSIVE_PARAMS  # Use aggressive profile
)
```

---

## Adding a New CLI Command

### Step 1: Add Command Parser

```python
# cli_bot.py

parser.add_argument(
    'command',
    choices=['status', 'scan', 'analyze', 'copy', 'portfolio', 'stop', 'backtest'],
    help='Command to execute'
)
```

### Step 2: Implement Handler

```python
# cli_bot.py

class CLIBot:
    def backtest(self, days: int = 30):
        """Run backtest on historical data."""
        print(f"Running backtest for {days} days...")
        
        # Load historical data
        # Run strategy
        # Calculate metrics
        
        results = {
            'total_return': 0.15,
            'sharpe_ratio': 1.2,
            'max_drawdown': 0.08
        }
        
        print(f"Backtest Results:")
        print(f"  Return: {results['total_return']:.1%}")
        print(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        print(f"  Max DD: {results['max_drawdown']:.1%}")
```

### Step 3: Add to Main

```python
# cli_bot.py

elif args.command == 'backtest':
    bot.backtest(days=args.days)
```

---

## Integrating Live Trading

### Step 1: Create Exchange Client

```python
# polymarket_tracker/exchange/polymarket_client.py

import requests
from typing import Dict, Optional


class PolymarketClient:
    """Client for Polymarket API."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.polymarket.com"
    
    def get_balance(self) -> float:
        """Get USDC balance."""
        response = requests.get(
            f"{self.base_url}/balance",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()['balance']
    
    def place_order(
        self,
        market_id: str,
        side: str,
        size: float,
        price: float
    ) -> Dict:
        """Place an order."""
        order = {
            "marketId": market_id,
            "side": side,
            "size": size,
            "price": price
        }
        
        response = requests.post(
            f"{self.base_url}/orders",
            json=order,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        
        return response.json()
    
    def get_positions(self) -> list:
        """Get open positions."""
        response = requests.get(
            f"{self.base_url}/positions",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()
```

### Step 2: Integrate with Copy Engine

```python
# polymarket_tracker/winners/copy_engine.py

from ..exchange.polymarket_client import PolymarketClient

class CopyEngine:
    def __init__(self, ev_calculator, position_manager, live_mode=False):
        # ... existing init ...
        self.live_mode = live_mode
        self.exchange = None
        
        if live_mode:
            api_key = os.getenv("POLYMARKET_API_KEY")
            api_secret = os.getenv("POLYMARKET_API_SECRET")
            self.exchange = PolymarketClient(api_key, api_secret)
    
    async def execute_decision(self, decision: CopyDecision):
        """Execute the copy decision."""
        if not self.live_mode:
            print("[MOCK] Trade executed")
            return {"status": "mock_success"}
        
        # Live execution
        order = self.exchange.place_order(
            market_id=decision.market_id,
            side="buy" if decision.direction == "YES" else "sell",
            size=decision.target_size,
            price=decision.entry_price_target
        )
        
        return order
```

### Step 3: Add Live Mode Flag

```python
# cli_bot.py

parser.add_argument(
    '--live',
    action='store_true',
    help='Enable live trading (requires API keys)'
)

# In main:
if args.live:
    print("LIVE TRADING MODE ENABLED")
    print("Real money will be used!")
    confirm = input("Type 'YES' to confirm: ")
    if confirm != 'YES':
        print("Aborted")
        return
```

---

## Testing Your Changes

### Unit Tests

```python
# tests/test_my_feature.py

import unittest
from polymarket_tracker.custom.my_scorer import MyScorer


class TestMyScorer(unittest.TestCase):
    def test_calculate(self):
        scorer = MyScorer(weight=1.0)
        
        # Mock winner
        winner = MockTrader(
            address="0x123",
            true_win_rate=0.60,
            profit_factor=1.5
        )
        
        result = scorer.calculate(winner)
        
        self.assertGreater(result.score, 0)
        self.assertLessEqual(result.score, 1.0)
```

### Integration Tests

```python
# tests/test_integration.py

async def test_full_workflow():
    bot = CLIBot()
    
    # Test scan
    await bot.scan()
    assert len(bot.winners) > 0
    
    # Test analyze
    await bot.analyze()
    assert bot.state['recommended_trade'] is not None
    
    # Test copy (mock)
    bot.copy_trade(auto_confirm=True)
    assert bot.state['daily_bet_count'] == 1
```

---

## Database Integration

### SQLite for Trade History

```python
# polymarket_tracker/data/database.py

import sqlite3
from datetime import datetime
from typing import List, Dict


class TradeDatabase:
    def __init__(self, db_path: str = "trades.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                market_id TEXT,
                winner_address TEXT,
                direction TEXT,
                size REAL,
                entry_price REAL,
                exit_price REAL,
                pnl REAL,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                status TEXT
            )
        """)
        self.conn.commit()
    
    def record_trade(self, trade: Dict):
        self.conn.execute("""
            INSERT INTO trades 
            (market_id, winner_address, direction, size, entry_price, entry_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            trade['market_id'],
            trade['winner_address'],
            trade['direction'],
            trade['size'],
            trade['entry_price'],
            datetime.now(),
            'open'
        ))
        self.conn.commit()
    
    def get_trade_history(self) -> List[Dict]:
        cursor = self.conn.execute("SELECT * FROM trades ORDER BY entry_time DESC")
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

---

## Performance Optimization

### Caching Strategy

```python
# polymarket_tracker/utils/cache.py

import functools
import pickle
from pathlib import Path

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def disk_cache(ttl_seconds: int = 3600):
    """Decorator to cache function results to disk."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            key = f"{func.__name__}_{hash(str(args))}_{hash(str(kwargs))}"
            cache_file = CACHE_DIR / f"{key}.pkl"
            
            # Check if cache exists and is fresh
            if cache_file.exists():
                age = time.time() - cache_file.stat().st_mtime
                if age < ttl_seconds:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
            
            # Compute and cache
            result = func(*args, **kwargs)
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
            
            return result
        return wrapper
    return decorator


# Usage
@disk_cache(ttl_seconds=3600)  # Cache for 1 hour
async def fetch_market_data(market_id: str):
    # Expensive API call
    return await subgraph_client.get_market(market_id)
```

---

## Debugging Tips

### Enable Verbose Logging

```python
# cli_bot.py
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
```

### Interactive Debugging

```powershell
# Start Python with bot loaded
python -i cli_bot.py

# In interactive mode:
>>> bot = CLIBot()
>>> await bot._init_clients()
>>> bot.winner_discovery.discover_winners(limit=5)
```

### Profiling Performance

```python
import cProfile
import pstats

# Profile the scan operation
profiler = cProfile.Profile()
profiler.enable()

await bot.scan()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

---

## Contributing Guidelines

### Code Style

```powershell
# Format code
black polymarket_tracker/ tests/

# Check style
flake8 polymarket_tracker/ tests/

# Type checking
mypy polymarket_tracker/
```

### Commit Messages

```
feat: Add live trading integration
fix: Correct EV calculation for edge cases
docs: Update README with new commands
test: Add tests for copy engine
refactor: Simplify winner discovery logic
```

### Pull Request Checklist

- [ ] Tests pass: `python tests/run_all_tests.py`
- [ ] Code formatted: `black .`
- [ ] No linting errors: `flake8`
- [ ] Documentation updated
- [ ] Type hints added
- [ ] CHANGELOG.md updated

---

## API Documentation

### Auto-generate Docs

```powershell
# Installpdoc
pip install pdoc

# Generate HTML docs
pdoc polymarket_tracker -o docs/

# Serve docs locally
pdoc polymarket_tracker --http localhost:8080
```

---

## Resources

- **Polymarket CTF Docs**: https://docs.polymarket.com/
- **TheGraph Docs**: https://thegraph.com/docs/
- **Python Async**: https://docs.python.org/3/library/asyncio.html
- **GQL Library**: https://gql.readthedocs.io/

---

**Questions?** Open an issue or check the main [README.md](README.md).
