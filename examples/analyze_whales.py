"""
Example script: Analyze Polymarket whales.

This script demonstrates how to use the WhaleTracker to:
1. Track multiple whale wallets
2. Calculate true win rates
3. Classify strategy archetypes
4. Generate a leaderboard
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from polymarket_tracker import WhaleTracker, ArchetypeClassifier
from polymarket_tracker.utils.config import Config
from polymarket_tracker.utils.logger import setup_logging

logger = setup_logging(debug=True)


def main():
    """Run whale analysis example."""
    print("=" * 60)
    print("🐋 Polymarket Whale Analyzer")
    print("=" * 60)
    
    # Initialize
    config = Config.from_env()
    
    if not config.thegraph_api_key:
        print("\n⚠️  Warning: THEGRAPH_API_KEY not set in .env")
        print("Some features will be limited. Get a key at:")
        print("https://thegraph.com/studio/")
        print()
    
    tracker = WhaleTracker(config)
    classifier = ArchetypeClassifier()
    
    # Add example wallets (replace with real addresses)
    example_wallets = [
        # Add real whale wallet addresses here
        # "0x1234567890123456789012345678901234567890",
    ]
    
    if not example_wallets:
        print("\n📋 To use this script, add wallet addresses to the example_wallets list")
        print("\nExample wallets you might want to track:")
        print("  - Known whale addresses from Polymarket leaderboards")
        print("  - ENS names like 'seriouslysirius.eth'")
        print("  - Your own wallets for analysis")
        return
    
    for wallet in example_wallets:
        tracker.add_wallet(wallet)
    
    print(f"\n🔍 Analyzing {len(example_wallets)} wallet(s)...\n")
    
    # Analyze all wallets
    results = []
    
    for address in tracker.profiles:
        try:
            print(f"Analyzing {address}...")
            
            # Get profile
            profile = tracker.analyze_wallet(address)
            
            # Classify archetype
            data = tracker.fetch_wallet_data(address)
            archetype_result = classifier.analyze_wallet(
                data['trades'],
                data['positions'],
                {
                    'trades_per_day': profile.trades_per_day,
                    'hedge_ratio': profile.hedge_ratio,
                    'true_win_rate': profile.true_win_rate,
                }
            )
            
            results.append({
                'Address': address,
                'True Win Rate': f"{profile.true_win_rate:.1f}%",
                'Displayed WR': f"{profile.displayed_win_rate:.1f}%",
                'Vanity Gap': f"{profile.vanity_gap:.1f}%",
                'Total Trades': profile.total_trades,
                'Zombie Orders': profile.zombie_orders,
                'Total PnL': f"${profile.total_pnl:,.0f}",
                'Archetype': archetype_result['archetype'],
                'Confidence': f"{archetype_result['confidence']:.1%}",
            })
            
            print(f"  ✓ Archetype: {archetype_result['archetype']}")
            print(f"  ✓ True WR: {profile.true_win_rate:.1f}%")
            print()
            
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
    
    # Display results
    if results:
        print("\n" + "=" * 60)
        print("📊 ANALYSIS RESULTS")
        print("=" * 60)
        
        df = pd.DataFrame(results)
        print(df.to_string(index=False))
        
        # Summary statistics
        print("\n" + "=" * 60)
        print("📈 SUMMARY STATISTICS")
        print("=" * 60)
        
        print(f"Wallets analyzed: {len(results)}")
        print(f"Archetypes found: {df['Archetype'].nunique()}")
        print(f"Total zombie orders: {df['Zombie Orders'].astype(int).sum()}")
    else:
        print("\n❌ No results to display")


if __name__ == "__main__":
    main()
