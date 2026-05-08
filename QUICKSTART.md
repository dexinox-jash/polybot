# PolyBot - Quick Start Guide

Get up and running with PolyBot in 5 minutes.

---

## Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] PowerShell or Command Prompt
- [ ] TheGraph API key
- [ ] 15 minutes per day for trading

---

## 3-Step Setup

### Step 1: Install

```powershell
cd "C:\Users\Dexinox\Documents\kimi code\Polybot"
pip install -r requirements.txt
```

### Step 2: Configure

Create `.env` file:

```powershell
@'
THEGRAPH_API_KEY=your_api_key_here
'@ | Out-File -FilePath ".env" -Encoding utf8
```

Get API key: https://thegraph.com/studio/apikeys/

### Step 3: Verify

```powershell
python cli_bot.py status
```

Should show:
```
Bets placed today: 0 / 1
Portfolio Value: $10,000
Portfolio Heat: 0%
```

---

## Daily 15-Minute Routine

```powershell
# 1. Check status (30 seconds)
python cli_bot.py status

# 2. Scan for winners (2 minutes)
python cli_bot.py scan

# 3. Deep analysis (10 minutes)
python cli_bot.py analyze

# 4. Execute trade (2 minutes)
python cli_bot.py copy --yes

# 5. Verify position (30 seconds)
python cli_bot.py portfolio
```

---

## Command Cheat Sheet

| Command | When to Use | Time |
|---------|-------------|------|
| `status` | Start of day | 30s |
| `scan` | Find winners | 2min |
| `analyze` | Find best bet | 10min |
| `copy` | Dry run | 10s |
| `copy --yes` | Execute | 2min |
| `portfolio` | Check positions | 30s |
| `stop` | Emergency exit | 10s |

---

## Typical Output Examples

### Status
```
[DAILY TARGETS]
  Bets placed today: 0 / 1
  Remaining: 1

[PORTFOLIO]
  Total Value: $10,000
  Daily P&L: $+0.00
  Total P&L: $+0.00
  Portfolio Heat: 0%

[WINNERS]
  No winners cached. Run 'scan' first.
```

### Scan
```
Found 5 qualifying winners

Top 5 Winners:
  #   Address/ENS          Win%     PF     Score 
  --------------------------------------------------
  1   Winner0              60.0%   1.50  75   
  2   Winner1              61.0%   1.60  70   
  3   Winner2              62.0%   1.70  65   

Top 5 winners cached for analysis.
```

### Analyze
```
BEST OPPORTUNITY FOUND

  Winner: Winner0
  Market: Market_1
  Expected Value: +13.0%
  Recommended Size: $200

  To execute: python cli_bot.py copy --yes
```

### Copy
```
Executing trade...
[MOCK] Trade executed successfully!

Daily target: 1/1 complete.
```

### Portfolio
```
[POSITIONS]
  Market               Size       Entry               
  --------------------------------------------------
  Market_1             $200       2026-03-05T23:07

  Total Exposure: $200
  Portfolio Heat: 2.0%
```

---

## Risk Limits

The bot enforces these limits automatically:

| Limit | Value | What Happens |
|-------|-------|--------------|
| Daily bets | 1 | Blocks more trades |
| Portfolio heat | 50% | Blocks new positions |
| Max positions | 5 | Blocks new positions |
| Daily drawdown | 10% | Stops trading |
| Position size | $500 | Caps individual trades |

---

## First Week Plan

### Day 1-3: Paper Trading
- Run all commands
- Observe recommendations
- Do NOT use `--yes` flag
- Track hypothetical P&L

### Day 4-7: Validation
- Compare bot's picks to actual outcomes
- Verify edge exists
- Check slippage estimates

### Week 2+: Live Trading
- Add `--yes` flag
- Start with small size ($50-100)
- Monitor daily

---

## Troubleshooting

### "No winners cached"
```powershell
python cli_bot.py scan  # Must run first
```

### "Daily limit reached"
Wait for next day, or reset state:
```powershell
# Edit bot_state.json
{
  "daily_bet_count": 0,
  "last_bet_date": "2026-03-04"
}
```

### "THEGRAPH_API_KEY not set"
```powershell
$env:THEGRAPH_API_KEY="your_key"
```

---

## Next Steps

1. Read full documentation: [README.md](README.md)
2. Run tests: `python tests/run_all_tests.py`
3. Review architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
4. Customize risk params in `cli_bot.py`

---

**Ready to start? Run: `python cli_bot.py status`**
