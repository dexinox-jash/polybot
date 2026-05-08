# PolyBot - Polymarket Copy-Trading Bot

> **Maximum Research Depth. Zero Compromises on Calculation Quality.**  
> **1 Exceptional Bet Per Day. API-Efficient. Risk-First.**

---

## Table of Contents

- [Overview](#overview)
- [Philosophy](#philosophy)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [Module Documentation](#module-documentation)
- [Risk Management](#risk-management)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

---

## Overview

PolyBot is an institutional-grade copy-trading system for Polymarket prediction markets. Unlike typical trading bots that chase every signal, PolyBot focuses on **maximum analysis depth** for a single, high-conviction trade per day.

### Key Features

- **Winner Discovery Engine**: Identifies statistically proven betters (>50 bets, >55% win rate, >1.3 profit factor, p<0.05)
- **Advanced EV Calculator**: Monte Carlo simulation, scenario analysis, Kelly Criterion sizing
- **Multi-Factor Model**: 20+ factors across 6 categories for comprehensive scoring
- **Risk-First Architecture**: Portfolio heat limits, circuit breakers, position sizing
- **CLI-Only Interface**: No web dashboard, command-line efficiency
- **API Efficient**: Fetch once, analyze deeply locally (~10-20 API calls/day)

### Daily Workflow (15 Minutes)

```
1. status   → Check daily targets, portfolio heat
2. scan     → Find top 5 statistically proven winners
3. analyze  → Deep analysis to find best daily bet
4. copy     → Execute with --yes flag
5. portfolio→ Verify position added
```

---

## Philosophy

### Quality Over Quantity

Traditional trading bots suffer from over-trading. PolyBot enforces a **hard limit of 1 bet per day**, ensuring every trade receives maximum analytical attention.

### Deep Analysis, Not Deep API Usage

"Deep analysis" doesn't mean more API calls—it means more computation on fetched data. We cache everything and perform extensive local calculations:
- Monte Carlo simulations (10,000 runs)
- Multi-factor scoring (20+ factors)
- Scenario analysis (best/base/worst cases)

### Risk-First Design

Every decision prioritizes capital preservation:
- Portfolio heat < 50%
- Kelly Criterion sizing (Half-Kelly)
- 10% daily drawdown circuit breaker
- Max 5 concurrent positions

### Copy Winners, Not Predict Markets

We don't predict markets—we copy proven winners. The bot finds betters with measurable edge and determines if copying their positions is +EV.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI INTERFACE                                │
│  Commands: status, scan, analyze, copy, portfolio, stop             │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌─────────────────────┐  ┌─────────────────────┐
        │   WINNER MODULES    │  │  DEEP ANALYSIS      │
        ├─────────────────────┤  ├─────────────────────┤
        │ winner_discovery    │  │ winner_intelligence │
        │ ev_calculator       │  │ advanced_ev         │
        │ copy_engine         │  │ multi_factor_model  │
        │ bet_tracker         │  │ research_engine     │
        └─────────────────────┘  └─────────────────────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
                    ┌─────────────────────┐
                    │    DATA LAYER       │
                    ├─────────────────────┤
                    │ subgraph_client     │
                    │ gamma_client        │
                    │ whale_tracker       │
                    └─────────────────────┘
```

### Module Dependencies

```
CLI Bot
├── Winner Discovery (finds winners)
│   └── Subgraph Client
├── EV Calculator (calculates EV)
│   └── Subgraph Client
├── Copy Engine (makes decisions)
│   ├── EV Calculator
│   └── Position Manager
├── Deep Analysis (comprehensive research)
│   ├── Winner Intelligence
│   ├── Advanced EV
│   ├── Multi-Factor Model
│   └── Research Engine
└── State Management (JSON file)
```

---

## Installation

### Prerequisites

- Python 3.10+
- Windows PowerShell or Command Prompt
- API keys for TheGraph (Polymarket subgraph)

### Step 1: Clone Repository

```powershell
cd "C:\Users\Dexinox\Documents\kimi code"
git clone <repository-url> Polybot
cd Polybot
```

### Step 2: Install Dependencies

```powershell
pip install -r requirements.txt
```

Required packages:
- pandas >= 2.0.0
- numpy >= 1.24.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0
- gql >= 4.0.0
- aiohttp >= 3.8.0
- tenacity >= 8.0.0
- loguru >= 0.7.0
- requests-toolbelt >= 1.0.0

### Step 3: Configure Environment

Create `.env` file:

```powershell
# Create .env file
@'
THEGRAPH_API_KEY=your_api_key_here
OPENAI_API_KEY=your_api_key_here
POLYMARKET_API_KEY=your_api_key_here
'@ | Out-File -FilePath ".env" -Encoding utf8
```

Get your API keys:
- **TheGraph**: https://thegraph.com/studio/apikeys/
- **OpenAI**: https://platform.openai.com/api-keys (optional)
- **Polymarket**: https://polymarket.com/settings/api (for live trading)

### Step 4: Verify Installation

```powershell
python cli_bot.py status
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `THEGRAPH_API_KEY` | Yes | Access Polymarket subgraph data |
| `OPENAI_API_KEY` | No | Future LLM features |
| `POLYMARKET_API_KEY` | No | Live trade execution |

### Bot State File

The bot maintains state in `bot_state.json`:

```json
{
  "daily_bet_count": 0,
  "last_bet_date": "2026-03-05",
  "portfolio_value": 10000,
  "current_positions": [],
  "daily_pnl": 0,
  "total_pnl": 0,
  "winners_cached": [],
  "recommended_trade": null
}
```

### Risk Parameters

Configure in `cli_bot.py`:

```python
risk_params = RiskParameters(
    max_risk_per_trade=0.02,      # 2% of bankroll per trade
    max_total_exposure=0.50,       # 50% portfolio heat limit
    max_open_positions=5,          # Max concurrent positions
    max_daily_drawdown=0.10,       # 10% daily drawdown stop
    max_position_size=500,         # $500 max per position
    min_position_size=50           # $50 min per position
)
```

---

## Usage Guide

### Daily Workflow Commands

#### 1. Check Status

```powershell
python cli_bot.py status
```

Output shows:
- Daily bet count (0/1)
- Portfolio value and heat
- Cached winners
- Last scan time

#### 2. Scan for Winners

```powershell
python cli_bot.py scan
```

Finds top 5 statistically proven winners based on:
- >50 bets (statistical significance)
- >55% true win rate
- >1.3 profit factor
- p<0.05 significance
- Low vanity gap (<15%)

Results are cached for the day.

#### 3. Deep Analysis

```powershell
python cli_bot.py analyze
```

Performs comprehensive analysis:
- Analyzes each winner's recent activity
- Calculates EV for each opportunity
- Runs multi-factor scoring
- Selects highest EV bet
- Generates recommendation

Only works if:
- Daily limit not reached
- Winners cached from scan

#### 4. Execute Trade

Dry run (shows what it would do):
```powershell
python cli_bot.py copy
```

Actually execute:
```powershell
python cli_bot.py copy --yes
```

Requirements:
- `--yes` flag required
- Daily limit not reached
- Recommendation exists

#### 5. View Portfolio

```powershell
python cli_bot.py portfolio
```

Shows:
- Total value and P&L
- Open positions with entry times
- Portfolio heat calculation
- Risk metrics

#### 6. Stop Bot

```powershell
python cli_bot.py stop
```

Closes all positions (simulated) and stops operations.

### Command Reference

| Command | Description | Options |
|---------|-------------|---------|
| `status` | Show current status | None |
| `scan` | Find top winners | None |
| `analyze` | Deep analysis | None |
| `copy` | Execute trade | `--yes` to confirm |
| `portfolio` | View portfolio | None |
| `stop` | Stop operations | None |

---

## Module Documentation

### 1. Winner Discovery (`polymarket_tracker/winners/winner_discovery.py`)

**Purpose**: Find statistically proven winners worth copying.

**Key Classes**:

```python
class TraderPerformance:
    address: str
    total_bets: int
    true_win_rate: float
    profit_factor: float
    copy_score: float
    is_statistically_significant: bool
    vanity_gap: float

class WinnerDiscovery:
    async def discover_winners(limit: int = 100) -> List[TraderPerformance]
    def scan_for_winners(wallets, trade_history) -> List[TraderPerformance]
    def get_top_winners(n: int = 10) -> List[TraderPerformance]
```

**Criteria for "Copyable" Winner**:
```python
is_profitably_copyable = (
    true_win_rate > 0.55 and
    net_pnl > 0 and
    profit_factor > 1.3 and
    total_bets >= 50 and
    is_statistically_significant and
    vanity_gap < 0.15
)
```

**Copy Score Calculation**:
- Win rate component (35%)
- Profit factor component (25%)
- Sample size component (20%)
- Consistency component (10%)
- Sharpe ratio component (10%)

---

### 2. EV Calculator (`polymarket_tracker/winners/ev_calculator.py`)

**Purpose**: Calculate Expected Value of copying specific bets.

**Key Classes**:

```python
class CopyEV:
    expected_value_percent: float
    win_probability: float
    potential_win: float
    potential_loss: float
    slippage_estimate: float
    timing_penalty: float
    kelly_fraction: float
    confidence: str

class EVCalculator:
    def calculate_copy_ev(winner, bet, market) -> CopyEV
    def estimate_slippage(position_size, liquidity) -> float
    def calculate_kelly(win_rate, odds) -> float
```

**EV Formula**:
```
EV = (Winner's Win Rate × Potential Win) - 
     (Loser's Rate × Potential Loss) - 
     Costs (slippage + fees + timing)
```

**Timing Penalties**:
- >24 hours to close: 0%
- 6-24 hours: 5%
- 1-6 hours: 15%
- <1 hour: 30%

---

### 3. Copy Engine (`polymarket_tracker/winners/copy_engine.py`)

**Purpose**: Make intelligent copy decisions with risk management.

**Key Classes**:

```python
class CopyDecisionType(Enum):
    IMMEDIATE_COPY = "immediate_copy"
    STAGED_COPY = "staged_copy"
    WAIT_FOR_DIP = "wait_for_dip"
    SKIP = "skip"
    REDUCE_SIZE = "reduce_size"

class CopyDecision:
    decision: CopyDecisionType
    confidence: float
    target_size: float
    execution_strategy: str
    stop_loss: float
    take_profit: float

class CopyEngine:
    def evaluate_opportunity(winner, bet, portfolio) -> CopyDecision
    def check_constraints(portfolio) -> bool
```

**Decision Tree**:
```
Daily limit reached? → SKIP_DAILY_LIMIT
Circuit breaker triggered? → SKIP_CIRCUIT_BREAKER
Portfolio heat > 50%? → SKIP_HEAT_LIMIT
EV < 2%? → SKIP_LOW_EV
Liquidity < $10k? → WAIT_LIQUIDITY
Timing score < 0.5? → WAIT_TIMING
EV > 8%? → COPY_STRONG
Otherwise → COPY_MODERATE
```

---

### 4. Winner Intelligence (`polymarket_tracker/deep_analysis/winner_intelligence.py`)

**Purpose**: Deep behavioral and performance analysis.

**Key Classes**:

```python
class DeepWinnerProfile:
    # Identity
    address: str
    ens_name: str
    labels: List[str]
    
    # Performance
    overall_win_rate: float
    win_rate_by_category: Dict[str, float]
    profit_factor: float
    sharpe_ratio: float
    
    # Behavioral
    behavioral_patterns: Dict
    psychological_profile: str
    optimal_copy_window: timedelta
    
    # Risk
    max_drawdown: float
    risk_of_ruin: float
    bet_size_volatility: float

class WinnerIntelligence:
    def analyze_winner(address, trade_history) -> DeepWinnerProfile
    def detect_behavioral_patterns(trades) -> Dict
    def calculate_edge_decomposition(trades) -> Dict
```

---

### 5. Advanced EV (`polymarket_tracker/deep_analysis/advanced_ev.py`)

**Purpose**: Institutional-grade EV with Monte Carlo simulation.

**Key Classes**:

```python
class ScenarioType(Enum):
    BEST_CASE = "best_case"
    BASE_CASE = "base_case"
    WORST_CASE = "worst_case"

class AdvancedEV:
    base_ev_percent: float
    monte_carlo_ev: float
    probability_of_profit: float
    risk_of_ruin: float
    optimal_kelly: float
    monte_carlo_var_95: float
    ulcer_index: float
    scenarios: Dict[ScenarioType, ScenarioAnalysis]

class AdvancedEVCalculator:
    def calculate_advanced_ev(...) -> AdvancedEV
    def run_monte_carlo(winner, market, n=10000) -> Dict
    def calculate_var(returns, confidence=0.95) -> float
```

**Monte Carlo Simulation**:
- 10,000 independent simulations
- Accounts for winner's historical variance
- Generates probability distribution
- Calculates VaR and expected drawdown

---

### 6. Multi-Factor Model (`polymarket_tracker/deep_analysis/multi_factor_model.py`)

**Purpose**: Score opportunities across 6 categories with 20+ factors.

**Key Classes**:

```python
class FactorCategory(Enum):
    WINNER_QUALITY = "winner_quality"       # 25%
    MARKET_CONDITIONS = "market_conditions" # 20%
    TIMING = "timing"                       # 15%
    RISK = "risk"                           # 20%
    BEHAVIORAL = "behavioral"               # 10%
    FUNDAMENTAL = "fundamental"             # 10%

class MultiFactorScore:
    composite_score: float      # 0-1
    grade: str                  # A+ to D
    confidence: float
    factors: List[FactorScore]
    strengths: List[str]
    weaknesses: List[str]
    recommended_action: str
    position_size_adjustment: float

class MultiFactorModel:
    def calculate_score(winner, market, timing, portfolio) -> MultiFactorScore
    def generate_swot(factors) -> Tuple[List, List, List, List]
```

**Grade Scale**:
- A+: >85%
- A: 80-85%
- A-: 75-80%
- B+: 70-75%
- B: 65-70%
- B-: 60-65%
- C+: 55-60%
- C: 50-55%
- D: <50%

---

### 7. Research Engine (`polymarket_tracker/deep_analysis/research_engine.py`)

**Purpose**: Produce institutional-grade research reports.

**Key Classes**:

```python
class ResearchReport:
    report_id: str
    generated_at: datetime
    recommendation: str
    confidence_level: str
    grade: str
    expected_return: float
    risk_rating: str
    winner_intelligence: Dict
    advanced_ev: Dict
    multi_factor_score: Dict
    scenario_analysis: Dict
    risk_assessment: Dict
    entry_strategy: str
    position_size: float
    stop_loss: float
    take_profit: float

class ResearchEngine:
    def generate_research_report(...) -> ResearchReport
    def generate_executive_summary(report) -> str
    def export_report_json(report) -> str
```

---

### 8. Position Manager (`polymarket_tracker/risk/position_manager.py`)

**Purpose**: Portfolio-level risk management.

**Key Classes**:

```python
class RiskParameters:
    max_risk_per_trade: float = 0.02
    max_position_size: float = 5000
    min_position_size: float = 100
    max_total_exposure: float = 0.50
    max_open_positions: int = 5
    max_daily_drawdown: float = 0.10

class Position:
    position_id: str
    market_id: str
    direction: str
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float

class PortfolioState:
    bankroll: float
    available_balance: float
    total_exposure: float
    open_positions: Dict[str, Position]
    daily_pnl: float
    current_drawdown: float

class PositionManager:
    def can_open_position(market, size) -> Tuple[bool, str]
    def open_position(signal, size) -> Position
    def close_position(position_id, reason) -> float
    def update_pnl() -> float
    def check_circuit_breakers() -> bool
```

---

### 9. CLI Bot (`cli_bot.py`)

**Purpose**: Main user interface.

**Key Methods**:

```python
class CLIBot:
    def status() -> None
    async def scan() -> None
    async def analyze() -> None
    def copy_trade(auto_confirm=False) -> None
    def portfolio() -> None
    def stop() -> None
```

**State Management**:
- Loads from `bot_state.json`
- Auto-resets daily counters
- Saves after each operation

---

## Risk Management

### Portfolio-Level Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| Max Heat | 50% | Total exposure / Bankroll |
| Max Positions | 5 | Concurrent open positions |
| Daily Drawdown | 10% | Stop trading if reached |
| Total Drawdown | 20% | Emergency stop |

### Position-Level Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| Base Size | 2% | Of bankroll |
| Max Size | $500 | Hard cap |
| Min Size | $50 | Minimum trade |
| Kelly Fraction | 0.5 | Half-Kelly for safety |

### Stop Loss Rules

- **Hard Stop**: 5% below entry
- **Take Profit**: 10% above entry
- **Time Exit**: Market close or 24 hours

### Circuit Breakers

```python
def is_circuit_breaker_triggered(portfolio):
    if portfolio.daily_drawdown >= 0.10:
        return True  # Stop for the day
    if portfolio.current_drawdown >= 0.20:
        return True  # Emergency stop
    return False
```

---

## Testing

### Run All Tests

```powershell
python tests/run_all_tests.py
```

### Test Agents

The test suite uses 5 specialized AI agents:

| Agent | Tests | Coverage |
|-------|-------|----------|
| Agent 1: Winner Discovery | 9 | Statistical filtering, copy scoring |
| Agent 2: EV Calculator | 11 | EV formula, Kelly, Monte Carlo |
| Agent 3: Copy Engine | 10 | Risk management, decisions |
| Agent 4: Multi-Factor | 12 | Factor scoring, SWOT |
| Agent 5: CLI Workflow | 17 | Commands, state management |

### Individual Test Files

```powershell
python tests/test_winner_discovery.py
python tests/test_ev_calculator.py
python tests/test_copy_engine.py
python tests/test_multi_factor.py
python tests/test_cli_workflow.py
```

### Test Coverage

- **59 total tests**
- All core logic validated
- Edge cases covered
- Error handling verified

---

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors

```powershell
pip install -r requirements.txt
```

#### 2. "THEGRAPH_API_KEY not set"

```powershell
# Check .env file exists
Get-Content .env

# Or set temporarily
$env:THEGRAPH_API_KEY="your_api_key"
```

#### 3. "No winners cached. Run 'scan' first"

You must run `python cli_bot.py scan` before `analyze`.

#### 4. "Daily bet target already reached"

Only 1 bet per day allowed. Wait for next day or edit `bot_state.json`:

```json
{
  "daily_bet_count": 0,
  "last_bet_date": "2026-03-04"
}
```

#### 5. Tests failing

```powershell
# Re-run tests
python tests/run_all_tests.py

# Check specific agent
python tests/test_winner_discovery.py -v
```

### Debug Mode

Enable verbose logging by setting environment variable:

```powershell
$env:LOG_LEVEL="DEBUG"
python cli_bot.py status
```

---

## API Reference

### Subgraph Queries

The bot uses TheGraph to query Polymarket data:

```python
# Get active markets
query {
  markets(where: {active: true}) {
    id
    question
    outcomes
    liquidity
    volume
  }
}

# Get trader history
query {
  orderFills(where: {maker: $address}) {
    market {
      id
    }
    outcome
    amount
    price
    timestamp
  }
}
```

### State File Schema

```json
{
  "daily_bet_count": int,
  "last_bet_date": string (YYYY-MM-DD),
  "portfolio_value": float,
  "current_positions": [
    {
      "market": string,
      "size": float,
      "entry_time": string (ISO8601)
    }
  ],
  "daily_pnl": float,
  "total_pnl": float,
  "winners_cached": [
    {
      "address": string,
      "ens": string,
      "win_rate": float,
      "profit_factor": float,
      "copy_score": float
    }
  ],
  "recommended_trade": {
    "winner": object,
    "market": string,
    "size": float,
    "ev": float
  }
}
```

---

## Deployment

### Paper Trading (Recommended First Step)

1. Run bot with mock execution (current behavior)
2. Track paper P&L for 30 days
3. Compare to live market prices
4. Verify edge exists

### Live Trading Integration

To enable real trades:

1. Get Polymarket API credentials
2. Implement `execute_trade()` in `copy_engine.py`:

```python
async def execute_live_trade(market_id, direction, size):
    # Call Polymarket CTF contract
    # Use conditional tokens framework
    # Verify transaction receipt
    pass
```

3. Add to CLI:

```python
if auto_confirm:
    result = await self.copy_engine.execute_live_trade(...)
```

### Server Deployment

For 24/7 operation:

```bash
# Using systemd
cat > /etc/systemd/system/polybot.service << 'EOF'
[Unit]
Description=PolyBot Copy Trading
After=network.target

[Service]
Type=simple
User=polybot
WorkingDirectory=/home/polybot/Polybot
ExecStart=/usr/bin/python cli_bot.py scan
Environment=THEGRAPH_API_KEY=your_key
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl enable polybot
systemctl start polybot
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "cli_bot.py", "status"]
```

---

## Future Roadmap

### Phase 1: Foundation (Complete)
- Winner discovery engine
- EV calculations
- Risk management
- CLI interface

### Phase 2: Live Trading (In Progress)
- Polymarket API integration
- Real order execution
- Transaction monitoring

### Phase 3: Intelligence (Planned)
- LLM-powered market analysis
- News sentiment integration
- On-chain flow analysis

### Phase 4: Automation (Planned)
- Fully autonomous mode
- Discord/Telegram notifications
- Advanced reporting dashboard

---

## License

MIT License - Use at your own risk. This is educational software. Trading carries risk of loss.

---

## Support

For issues or questions:
1. Check this documentation
2. Review test output: `python tests/run_all_tests.py`
3. Check logs in `logs/` directory
4. Open an issue on GitHub

---

## Credits

Built with:
- Python 3.14
- TheGraph
- Polymarket CTF Protocol
- NumPy, Pandas, GQL

---

*Last Updated: 2026-03-05*  
*Version: 1.0.0*
