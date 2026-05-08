"""
Example script: Track whale consensus for a specific market.

This script demonstrates how to:
1. Get whale positions for a specific market
2. Calculate consensus and confidence
3. Detect whale disagreements
4. Generate trading signals
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from polymarket_tracker import WhaleTracker
from polymarket_tracker.analysis.consensus_engine import ConsensusEngine, ConsensusResult
from polymarket_tracker.utils.config import Config
from polymarket_tracker.utils.logger import setup_logging

logger = setup_logging()


def main():
    """Run market tracking example."""
    print("=" * 60)
    print("📈 Market Whale Tracker")
    print("=" * 60)
    
    # Initialize
    config = Config.from_env()
    tracker = WhaleTracker(config)
    
    # Example market (replace with real condition ID)
    example_market_id = "0x..."  # Replace with real market condition ID
    
    if example_market_id == "0x...":
        print("\n📋 To use this script:")
        print("1. Find a market on Polymarket")
        print("2. Get the condition ID from the URL")
        print("3. Replace example_market_id in this script")
        print("\nExample condition ID format:")
        print("  0x1234567890abcdef...")
        return
    
    print(f"\n🔍 Analyzing market: {example_market_id}\n")
    
    # Get whale consensus
    try:
        consensus = tracker.get_market_whale_consensus(example_market_id)
        
        print("📊 WHALE CONSENSUS")
        print("-" * 40)
        print(f"Consensus: {consensus.get('consensus', 'No Consensus')}")
        print(f"Confidence: {consensus.get('confidence', 0) * 100:.1f}%")
        print(f"Whale Volume: ${consensus.get('total_whale_volume', 0):,.0f}")
        print(f"Number of Whales: {consensus.get('num_whales', 0)}")
        
        # Whale-implied probability vs market
        whale_prob = consensus.get('whale_probability', 0.5)
        market_prob = consensus.get('market_probability', 0.5)
        divergence = whale_prob - market_prob
        
        print(f"\n📈 PROBABILITY ANALYSIS")
        print("-" * 40)
        print(f"Whale-Implied: {whale_prob * 100:.1f}%")
        print(f"Market Price: {market_prob * 100:.1f}%")
        print(f"Divergence: {divergence * 100:+.1f}%")
        
        if abs(divergence) > 0.1:
            if divergence > 0:
                print("\n✅ SIGNAL: Whales are MORE BULLISH than market")
            else:
                print("\n⚠️  SIGNAL: Whales are MORE BEARISH than market")
        else:
            print("\n⚪ Whales and market are aligned")
        
        # Calculate Kelly Criterion
        result = ConsensusResult(
            market_id=example_market_id,
            consensus=consensus.get('consensus'),
            confidence=consensus.get('confidence', 0),
            whale_probability=whale_prob,
            market_probability=market_prob,
            divergence=divergence,
            total_whale_volume=consensus.get('total_whale_volume', 0),
            num_whales=consensus.get('num_whales', 0),
            whale_positions=consensus.get('positions', [])
        )
        
        engine = ConsensusEngine()
        kelly = engine._calculate_kelly(result)
        
        print(f"\n💰 POSITION SIZING (Kelly Criterion)")
        print("-" * 40)
        print(f"Kelly Fraction: {kelly * 100:.2f}% of bankroll")
        
        if kelly > 0:
            print(f"Half-Kelly (recommended): {kelly * 50:.2f}% of bankroll")
        
    except Exception as e:
        print(f"Error analyzing market: {e}")
        logger.exception("Market analysis failed")


if __name__ == "__main__":
    main()
