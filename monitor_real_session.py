#!/usr/bin/env python3
"""
Monitor the real-time trading session.
"""

import os
import time
import sys
from datetime import datetime
from pathlib import Path

def find_latest_log():
    """Find the most recent real trading session log."""
    log_dir = Path("logs")
    logs = sorted(log_dir.glob("real_trading_session_*.log"), 
                  key=lambda x: x.stat().st_mtime, reverse=True)
    return logs[0] if logs else None

def display_status():
    """Display current trading status."""
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 80)
    print("POLYBOT REAL-TIME TRADING MONITOR")
    print("=" * 80)
    print(f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    log_file = find_latest_log()
    if not log_file:
        print("[WAITING] No active session found...")
        return True
    
    print(f"Session Log: {log_file.name}")
    print()
    
    # Read log
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except:
        print("[ERROR] Cannot read log file")
        return True
    
    # Parse status
    balance = 100.0
    trades = 0
    blocks = 0
    whales = 0
    elapsed = "0h 0m"
    
    for line in lines[-50:]:
        if "[HEARTBEAT]" in line:
            if "Balance:" in line:
                try:
                    balance = float(line.split("Balance: $")[-1].split("|")[0].strip())
                except:
                    pass
            if "Trades:" in line:
                try:
                    trades = int(line.split("Trades:")[-1].strip())
                except:
                    pass
            if "Elapsed:" in line:
                try:
                    elapsed = line.split("Elapsed:")[-1].split("|")[0].strip()
                except:
                    pass
        if "[BLOCK]" in line and "Blocks seen:" in line:
            try:
                parts = line.split("Blocks seen:")
                if len(parts) > 1:
                    blocks = int(parts[1].split("|")[0].strip())
            except:
                pass
        if "[WHALE]" in line and "Whale transaction detected" in line:
            whales += 1
    
    # Display
    pnl = balance - 100.0
    pnl_pct = pnl
    
    print("SESSION STATUS:")
    print("-" * 80)
    print(f"  Elapsed Time:     {elapsed}")
    print(f"  Current Balance:  ${balance:.2f}")
    print(f"  P&L:              ${pnl:+.2f} ({pnl_pct:+.2f}%)")
    print()
    print(f"  Blocks Monitored: {blocks}")
    print(f"  Whale TX Seen:    {whales}")
    print(f"  Trades Executed:  {trades}")
    print("-" * 80)
    
    # Recent activity
    print()
    print("RECENT ACTIVITY:")
    print("-" * 80)
    
    recent = []
    for line in lines[-20:]:
        if any(tag in line for tag in ["[WHALE]", "[COPY]", "[RESULT]", "[BLOCK]"]):
            ts = line.split("|")[0].split(" ")[-1] if "|" in line else ""
            msg = line.split("|")[-1].strip() if "|" in line else line.strip()
            recent.append(f"  {ts} | {msg[:70]}")
    
    for event in recent[-8:]:
        print(event)
    
    if not recent:
        print("  [Waiting for activity...]")
    
    print("-" * 80)
    
    # Check if complete
    if "FINAL SESSION REPORT" in ''.join(lines[-10:]):
        print()
        print("[DONE] Session complete!")
        return False
    
    print()
    print("Refreshing every 10 seconds... (Press Ctrl+C to exit)")
    return True

if __name__ == "__main__":
    print("\n" * 3)
    
    try:
        while True:
            running = display_status()
            if not running:
                break
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\nMonitor stopped.")
        print(f"Log file: logs/real_trading_session_*.log")
