#!/usr/bin/env python3
"""
Check the status of the paper trading session.
"""

import json
from datetime import datetime
from pathlib import Path

def get_latest_log():
    log_dir = Path("logs")
    logs = sorted(log_dir.glob("paper_trading_session_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return logs[0] if logs else None

def get_latest_stats():
    log_dir = Path("logs")
    stats = sorted(log_dir.glob("stats_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if stats:
        with open(stats[0], 'r') as f:
            return json.load(f)
    return None

def main():
    print("=" * 80)
    print("POLYBOT SESSION STATUS")
    print("=" * 80)
    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get latest log
    latest_log = get_latest_log()
    if not latest_log:
        print("No session log found.")
        return
    
    print(f"Latest Log: {latest_log.name}")
    print()
    
    # Read last 100 lines
    with open(latest_log, 'r') as f:
        lines = f.readlines()
    
    # Extract current status
    balance = 100.0
    trades = 0
    elapsed = "0m 0s"
    remaining = "120m 0s"
    
    for line in lines[-100:]:
        if "[HEARTBEAT]" in line:
            # Parse heartbeat
            if "Balance:" in line:
                try:
                    balance = float(line.split("Balance: $")[-1].split("|")[0].strip())
                except:
                    pass
            if "Trades:" in line:
                try:
                    trades = int(line.split("Trades:")[-1].split("|")[0].strip())
                except:
                    pass
            if "Elapsed:" in line:
                try:
                    parts = line.split("|")
                    for part in parts:
                        if "Elapsed:" in part:
                            elapsed = part.split(":")[-1].strip()
                        if "Remaining:" in part:
                            remaining = part.split(":")[-1].strip()
                except:
                    pass
    
    pnl = balance - 100.0
    pnl_pct = pnl / 100.0 * 100
    
    print("CURRENT STATUS:")
    print("-" * 80)
    print(f"  Elapsed Time:     {elapsed}")
    print(f"  Remaining Time:   {remaining}")
    print()
    print(f"  Initial Balance:  $100.00")
    print(f"  Current Balance:  ${balance:.2f}")
    print(f"  P&L:              ${pnl:+.2f} ({pnl_pct:+.2f}%)")
    print()
    print(f"  Total Trades:     {trades}")
    print("-" * 80)
    
    # Recent activity
    print()
    print("RECENT ACTIVITY (last 5 events):")
    print("-" * 80)
    
    recent_events = []
    for line in lines[-50:]:
        if "[WHALE]" in line or "[COPY]" in line or "[RESULT]" in line:
            timestamp = line.split("|")[0].split(",")[0].strip()
            message = line.split("|")[-1].strip()
            recent_events.append(f"{timestamp} | {message}")
    
    for event in recent_events[-5:]:
        print(f"  {event}")
    
    print("-" * 80)
    
    # Check if complete
    if "FINAL SESSION REPORT" in ''.join(lines[-20:]):
        print()
        print("[DONE] SESSION COMPLETE!")
        print(f"Check final report: logs/final_report_*.json")
    else:
        print()
        print("[ACTIVE] Session in progress...")
        print("Run 'python check_session.py' again to update.")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
