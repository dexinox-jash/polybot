# Polymarket Copy-Trading Bot - Architecture

A sophisticated, API-efficient copy-trading system focused on quality over quantity.

## Core Philosophy

**1 bet per day, maximum research depth, zero compromises on calculation quality.**

- **API Efficiency**: Fetch raw data once, perform extensive local calculations
- **Quality Focus**: Hard limit of 1 exceptional bet per day
- **Risk-First**: Portfolio heat < 50%, Kelly Criterion sizing, circuit breakers
- **Deep Analysis**: Multi-factor scoring, Monte Carlo EV, comprehensive research reports

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

## Module Breakdown

### 1. Winner Discovery (`winners/winner_discovery.py`)

**Purpose**: Find statistically proven winners worth copying.

**Key Features**:
- Filters: >50 bets, >55% true win rate, >1.3 profit factor, p<0.05
- Vanity gap detection (stat manipulation check)
- Win rate by category, time, market type
- Composite copy score ranking

**Output**: Top 5 winners with detailed performance metrics

### 2. EV Calculator (`winners/ev_calculator.py`)

**Purpose**: Calculate Expected Value of copying specific bets.

**Key Features**:
- Winner's historical edge in market category
- Slippage estimation based on position size
- Timing penalty for late entry
- Monte Carlo simulation (10,000 runs)
- Kelly Criterion optimal sizing

**Output**: EV percentage, probability of profit, risk metrics

### 3. Copy Engine (`winners/copy_engine.py`)

**Purpose**: Make intelligent copy decisions with risk management.

**Key Features**:
- Daily target enforcement (1 bet/day)
- Portfolio constraints (heat < 50%, max 5 positions)
- Liquidity verification
- Circuit breakers (10% daily drawdown)

**Output**: COPY/SKIP/WAIT/REDUCE decision with size and confidence

### 4. Winner Intelligence (`deep_analysis/winner_intelligence.py`)

**Purpose**: Deep behavioral and performance analysis of winners.

**Key Features**:
- Complete trade history analysis
- Behavioral pattern recognition
- Edge decomposition by category
- Risk profile analysis
- Temporal patterns (time of day, day of week)
- Psychological profiling

**Output**: `DeepWinnerProfile` with 50+ metrics

### 5. Advanced EV (`deep_analysis/advanced_ev.py`)

**Purpose**: Institutional-grade EV calculations with scenario analysis.

**Key Features**:
- Scenario analysis (best/base/worst cases)
- Monte Carlo simulation
- Risk of ruin calculation
- Expected maximum drawdown
- Ulcer Index (pain measurement)
- Confidence intervals

**Output**: `AdvancedEV` with comprehensive risk metrics

### 6. Multi-Factor Model (`deep_analysis/multi_factor_model.py`)

**Purpose**: Score opportunities across 6 categories with 20+ factors.

**Categories**:
- Winner Quality (25%): Win rate, profit factor, Sharpe ratio, consistency
- Market Conditions (20%): Liquidity, spread, volatility, price efficiency
- Timing (15%): Time to close, preferred hours, entry speed
- Risk (20%): Portfolio heat, correlation, downside protection
- Behavioral (10%): Streak analysis, bet sizing consistency
- Fundamental (10%): Market sentiment, volume trend

**Output**: Composite score (0-1), letter grade (A+ to D), SWOT analysis

### 7. Research Engine (`deep_analysis/research_engine.py`)

**Purpose**: Produce institutional-grade research reports.

**Key Features**:
- Combines all analysis modules
- Executive summary generation
- Comparative analysis (vs historical, consensus, portfolio)
- Risk factors and mitigation strategies
- Execution recommendations

**Output**: `ResearchReport` with complete analysis and action plan

### 8. CLI Bot (`cli_bot.py`)

**Purpose**: User interface for the entire system.

**Commands**:
- `status`: Show daily targets, portfolio, winners cached
- `scan`: Find top 5 statistically proven winners
- `analyze`: Deep analysis to find best daily bet
- `copy --yes`: Execute recommended trade (requires confirmation)
- `portfolio`: Detailed portfolio view
- `stop`: Close all positions and stop

## Workflow

### Daily Workflow (15 minutes)

```
1. python cli_bot.py status
   └─ Check daily targets, portfolio heat, current positions

2. python cli_bot.py scan
   └─ Fetch top 5 winners (if not cached)
   └─ Cache results for deep analysis

3. python cli_bot.py analyze
   └─ Deep analysis of each winner's recent activity
   └─ Calculate EV for each opportunity
   └─ Run multi-factor scoring
   └─ Select highest EV bet
   └─ Generate research report
   └─ Save recommendation to state

4. python cli_bot.py copy --yes
   └─ Execute the recommended trade
   └─ Update daily target tracking
   └─ Add to portfolio
```

### Analysis Pipeline

```
Winner Discovery
      │
      ▼
Deep Profile Analysis (Winner Intelligence)
      │
      ▼
Advanced EV Calculation (with Monte Carlo)
      │
      ▼
Multi-Factor Scoring (6 categories, 20+ factors)
      │
      ▼
Research Report Generation
      │
      ▼
Copy Decision (with risk management)
```

## Risk Management

### Portfolio Level
- **Max Heat**: 50% of portfolio in open positions
- **Max Positions**: 5 concurrent positions
- **Daily Drawdown Circuit**: 10% daily loss = stop trading

### Position Level
- **Base Size**: 2% of bankroll
- **Kelly Adjustment**: Half-Kelly sizing
- **Max Single Position**: $200 (default)
- **Stop Loss**: 5% below entry
- **Take Profit**: 10% above entry

### Winner Quality Filters
- **Min Bets**: 50 (statistical significance)
- **Min Win Rate**: 55% (true win rate, not displayed)
- **Min Profit Factor**: 1.3
- **Max Vanity Gap**: 10% (stat manipulation check)
- **Confidence**: p < 0.05

## API Efficiency Strategy

**Design Principle**: Deep analysis != More API calls

- **Fetch Once**: Cache all raw data locally
- **Calculate Deeply**: Perform extensive local computations
- **Cache Everything**: Winners, market data, calculations
- **API Call Budget**: ~10-20 calls/day (mostly for execution)

## Configuration

Environment variables (in `.env`):
```
THEGRAPH_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key  # For future LLM features
POLYMARKET_API_KEY=your_api_key
```

## State Management

Bot state stored in `bot_state.json`:
```json
{
  "daily_bet_count": 0,
  "last_bet_date": "2026-03-05",
  "portfolio_value": 10000,
  "current_positions": [],
  "winners_cached": [],
  "recommended_trade": null
}
```

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python cli_bot.py status
```

## Future Enhancements

1. **Live Execution**: Integrate Polymarket CTF contracts
2. **Notification System**: Alerts for high-EV opportunities
3. **Performance Tracking**: Detailed P&L analytics
4. **ML Prediction**: Predict winner's next moves
5. **Market Making**: Provide liquidity to earn fees

## License

MIT License - Use at your own risk. This is educational software.
