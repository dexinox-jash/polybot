#!/usr/bin/env python3
"""
Monitor the paper trading session and display live updates.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

def find_latest_session():
    """Find the most recent session log."""
    log_dir = Path("logs")
    if not log_dir.exists():
        return None
    
    log_files = sorted(log_dir.glob("paper_trading_session_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files[0] if log_files else None

def display_live_status():
    """Display live trading status."""
    print("=" * 80)
    print("POLYBOT PAPER TRADING - LIVE MONITOR")
    print("=" * 80)
    print(f"Monitoring Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    # Find latest log
    log_file = find_latest_session()
    if not log_file:
        print("No active session found. Waiting for session to start...")
        return False
    
    print(f"Session Log: {log_file.name}")
    print("")
    
    # Read log file
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading log: {e}")
        return True
    
    # Parse recent activity
    recent_trades = []
    balance = 100.0
    trades_count = 0
    elapsed = "0m 0s"
    remaining = "120m 0s"
    
    for line in lines[-50:]:  # Last 50 lines
        if "[COPY] Executed" in line:
            recent_trades.append(line.strip())
        if "Current Balance:" in line:
            try:
                balance_str = line.split("$")[-1].split()[0]
                balance = float(balance_str.replace(",", ""))
            except:
                pass
        if "Trades:" in line and "[HEARTBEAT]" in line:
            try:
                trades_count = int(line.split("Trades:")[-1].split("|")[0].strip())
            except:
                pass
        if "[HEARTBEAT]" in line:
            try:
                parts = line.split("|")
                for part in parts:
                    if "Elapsed:" in part:
                        elapsed = part.split(":")[-1].strip()
                    if "Remaining:" in part:
                        remaining = part.split(":")[-1].strip()
            except:
                pass
    
    # Display status
    print(f"[TIME] Elapsed: {elapsed}")
    print(f"[TIME] Remaining: {remaining}")
    print("")
    print(f"[BALANCE] Current: ${balance:.2f}")
    print(f"[TRADES] Total: {trades_count}")
    pnl = balance - 100.0
    print(f"[P&L] ${pnl:+.2f} ({pnl/100*100:+.2f}%)")
    print("")
    
    if recent_trades:
        print("[WHALE] RECENT ACTIVITY:")
        print("-" * 80)
        for trade in recent_trades[-5:]:
            # Parse trade line
            timestamp = trade.split("|")[0].strip()
            print(f"  {timestamp}")
        print("-" * 80)
    else:
        print("[INFO] No recent trades. Monitoring for whale activity...")
    
    print("")
    
    # Check if session is complete
    if "SESSION COMPLETE" in lines[-1] or "FINAL SESSION REPORT" in ''.join(lines[-10:]):
        print("[DONE] SESSION COMPLETE!")
        return False
    
    return True

if __name__ == "__main__":
    import sys
    
    print("\n" * 3)
    running = True
    check_count = 0
    
    while running and check_count < 240:  # Max 2 hours of checks (every 30 seconds)
        # Clear screen (Windows)
        os.system('cls' if os.name == 'nt' else 'clear')
        
        running = display_live_status()
        
        if running:
            print(f"\n[INFO] Refreshing in 30 seconds... (Press Ctrl+C to stop monitoring)")
            print(f"       Log file: logs/paper_trading_session_*.log")
            time.sleep(30)
            check_count += 1
        else:
            break
    
    print("\n" + "=" * 80)
    print("Monitoring stopped.")
    print(f"Full logs available in: logs/")
    print("=" * 80)
