#!/usr/bin/env python3
"""Quick CLI Bot Demo"""

print("""
================================================================================
               POLYMARKET TOP 5 WINNERS - CLI BOT DEMO

     Efficient. Focused. Command-line only.
     Target: 1 quality bet per day.
================================================================================

This demo shows how the CLI bot works.

KEY FEATURES:
  [OK] Command-line only (no dashboard, no alerts)
  [OK] Silent background operation
  [OK] Focus on TOP 5 winners (saves API credits)
  [OK] Target: 1 high-quality bet per day
  [OK] You decide when to execute (not automatic)

==============================================================================
COMMAND: python cli_bot.py status
==============================================================================

BOT STATUS
============================================================

[API Keys]
  thegraph    : [OK]
  openai      : [OK]
  polymarket  : [OK]

[Top 5 Winners]
  Tracked: 0
  Not scanned yet - run 'scan'

[Daily Target]
  Bets today: 0/1
  Status: Ready for new opportunities

[Portfolio]
  Bankroll: $10,000.00
  Total P&L: $+0.00
  Active positions: 0

[Monitoring]
  Status: Stopped
============================================================

==============================================================================
COMMAND: python cli_bot.py scan
==============================================================================

[SCAN] Finding top 5 winners...
  This uses API credits - scanning efficiently...
  -> Querying trader performance data...

  [OK] Found 5 verified winners

[TOP 5 WINNERS]
#    Name                 Win Rate     P&L             Score     
----------------------------------------------------------------
1    alphawin.eth         62.0%       $    45,600    87.5      
2    gammaedge.eth        65.0%       $    52,300    91.3      
3    deltaflow.eth        59.0%       $    32,100    82.1      
4    omegawin.eth         61.0%       $    44,500    88.9      
5    betaprofit.eth       58.0%       $    28,900    78.2      

  Next: Run 'watch' to start monitoring these winners

==============================================================================
COMMAND: python cli_bot.py watch
==============================================================================

[WATCH] Starting background monitoring...
  Monitoring: 5 top winners
  Target: 1 bet(s) per day
  Mode: Silent (run 'status' to check)

  [OK] Monitoring started (PID: 12345)
  Run 'analyze' to find today's best bet

[The bot now runs silently in background]
[It will NOT trade automatically - you decide when to 'copy']

==============================================================================
COMMAND: python cli_bot.py analyze
==============================================================================

[ANALYZE] Deep analysis for best opportunity...
  -> Analyzing recent bets from top 5 winners...
  -> Calculating EV for each opportunity...
  -> Comparing risk/reward ratios...

  [OK] Analysis complete

[TODAY'S BEST BET]
  Winner: gammaedge.eth (65% WR)
  Market: Will BTC close above $95K today?
  Direction: YES
  Entry Price: $0.54
  Expected Value: +8.5%
  Confidence: 82%
  Time Left: 4 hours

[REASONING]
  * Winner has 65% true win rate (excellent)
  * EV of 8.5% after all costs
  * Winner's best category (crypto)
  * Strong momentum in winner's direction

  Suggested Size: $200 (2% of bankroll)

  Run 'copy' to execute this trade

==============================================================================
COMMAND: python cli_bot.py copy --yes
==============================================================================

[COPY] Execute replication trade

  Market: Will BTC close above $95K today?
  Direction: YES
  Size: $200
  Expected Value: +8.5%

  -> Executing trade...
  [OK] Trade executed!
  Trade ID: trade_1709823456
  Daily progress: 1/1

  [OK] Daily target met! Bot will continue monitoring but won't trade.

==============================================================================
COMMAND: python cli_bot.py portfolio
==============================================================================

============================================================
PORTFOLIO
============================================================

[Summary]
  Bankroll: $10,000.00
  Total P&L: $+278.00
  Active Positions: 1

[Active Positions]
Market                         Dir    Size       Entry    EV %    
----------------------------------------------------------------
BTC close above $95K           YES    $200       $0.54    +8.5%

[Recent History]
  [OK] BTC close above $95K: $+230.00
  [OK] ETH outperform BTC: $+93.00
  [X] Trump 2024: $-66.00
  [OK] Fed Rate: $+21.00
============================================================

==============================================================================
TYPICAL DAILY WORKFLOW
==============================================================================

8:00 AM - Start your day
$ python cli_bot.py status
  Check: Bot running? Daily target met? Portfolio?

9:00 AM - Find today's opportunity
$ python cli_bot.py analyze
  Bot analyzes all top 5 winner activity
  Finds the 1 best bet with highest EV

9:15 AM - Execute if good
$ python cli_bot.py copy --yes
  If EV > 5% and confidence > 75%
  Execute the copy trade

12:00 PM - Check progress
$ python cli_bot.py portfolio
  See active positions and P&L

5:00 PM - End of day
$ python cli_bot.py status
  Confirm daily target met
  Review performance

--- NEXT DAY ---

Repeat. Simple. Efficient. 1 bet per day.

Estimated time: 15 minutes per day
API usage: ~10-20 calls per day (very efficient)
Target: $50-200 profit per day (depends on bankroll)

==============================================================================
                         DEMO COMPLETED
==============================================================================

USAGE:
  $ python cli_bot.py [command]

COMMANDS:
  status     - Check current status
  scan       - Find top 5 winners (uses API credits)
  watch      - Start background monitoring
  analyze    - Find best bet today
  copy       - Execute trade (use --yes)
  portfolio  - Show portfolio & P&L

WORKFLOW:
  1. scan -> 2. watch -> 3. analyze -> 4. copy

EFFICIENT API USAGE:
  * Scan once per week (or when needed)
  * Analyze 1-2 times per day
  * Copy only when you approve
  * ~10-20 API calls per day

TARGET: 1 bet per day with 5-10% expected edge

==============================================================================
""")
