"""
Example script: Scan for arbitrage opportunities.

This script finds markets where YES + NO < $1.00,
indicating a potential arbitrage opportunity.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polymarket_tracker import WhaleTracker
from polymarket_tracker.utils.config import Config


def main():
    """Run arbitrage scanner."""
    print("=" * 60)
    print("💰 Arbitrage Opportunity Scanner")
    print("=" * 60)
    print("\nLooking for markets where YES + NO < $1.00\n")
    
    # Initialize
    config = Config.from_env()
    tracker = WhaleTracker(config)
    
    try:
        opportunities = tracker.detect_arbitrage_opportunities()
        
        if not opportunities:
            print("No arbitrage opportunities found at this time.")
            print("\nThis is normal - arbitrage opportunities are:")
            print("  - Rare in efficient markets")
            print("  - Quickly filled by bots")
            print("  - Most common during high volatility")
            return
        
        print(f"Found {len(opportunities)} opportunity(s):\n")
        
        for i, opp in enumerate(opportunities, 1):
            print(f"{i}. {opp['question'][:60]}...")
            print(f"   Sum of prices: ${opp['sum_prices']:.4f}")
            print(f"   Potential profit: {opp['potential_profit']*100:.2f}%")
            print(f"   YES: ${opp['prices'][0]:.4f}, NO: ${opp['prices'][1]:.4f}")
            print()
        
        print("=" * 60)
        print("⚠️  IMPORTANT NOTES")
        print("=" * 60)
        print("1. These are gross opportunities - fees not included")
        print("2. Check gas costs on Polygon before executing")
        print("3. Opportunities can disappear quickly")
        print("4. Verify market liquidity before trading")
        
    except Exception as e:
        print(f"Error scanning for arbitrage: {e}")


if __name__ == "__main__":
    main()
