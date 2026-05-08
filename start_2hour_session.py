#!/usr/bin/env python3
"""
Start a 2-hour paper trading session with $100.
This runs independently and logs everything.
"""

import subprocess
import sys
import time
from datetime import datetime

print("=" * 80)
print("POLYBOT - 2 HOUR PAPER TRADING SESSION")
print("=" * 80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Duration: 2 hours")
print("Initial Balance: $100.00")
print("=" * 80)
print()

# Start the session in a detached process
process = subprocess.Popen(
    [sys.executable, "paper_trading_session.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
)

print(f"Session started with PID: {process.pid}")
print()
print("The bot is now running independently.")
print("It will trade for exactly 2 hours.")
print()
print("To monitor progress:")
print("  python check_session.py")
print()
print("Log files are in: logs/")
print()
print("Session will complete at:", 
      (datetime.now() + __import__('datetime').timedelta(hours=2)).strftime('%H:%M:%S'))
print("=" * 80)
