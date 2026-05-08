#!/usr/bin/env python3
"""
Hyperliquid API Client Template

Use this as starting point for your trading bot.
Hyperliquid offers:
- 0.01% fees (vs 2% on Polymarket)
- 24/7 crypto markets
- $1B+ daily volume
- Full trading API

Website: https://hyperliquid.xyz
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Optional

HYPERLIQUID_API = "https://api.hyperliquid.xyz"


class HyperliquidClient:
    """
    Client for Hyperliquid API.
    
    This is a template - you'll need to:
    1. Add authentication (wallet signing)
    2. Implement order placement
    3. Add your strategies
    """
    
    def __init__(self, wallet_address: str = None):
        self.wallet_address = wallet_address
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get_markets(self) -> List[Dict]:
        """Get available markets."""
        url = f"{HYPERLIQUID_API}/info"
        
        payload = {
            "type": "meta"
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('universe', [])
                return []
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []
    
    async def get_orderbook(self, coin: str = "BTC") -> Dict:
        """Get orderbook for a coin."""
        url = f"{HYPERLIQUID_API}/info"
        
        payload = {
            "type": "l2Book",
            "coin": coin
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return {}
    
    async def get_recent_trades(self, coin: str = "BTC", limit: int = 100) -> List[Dict]:
        """Get recent trades."""
        url = f"{HYPERLIQUID_API}/info"
        
        payload = {
            "type": "recentTrades",
            "coin": coin
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[:limit]
                return []
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []
    
    async def get_user_state(self) -> Dict:
        """Get user account state."""
        if not self.wallet_address:
            return {}
        
        url = f"{HYPERLIQUID_API}/info"
        
        payload = {
            "type": "clearinghouseState",
            "user": self.wallet_address
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception as e:
            print(f"Error fetching user state: {e}")
            return {}
    
    def analyze_orderbook(self, orderbook: Dict) -> Dict:
        """
        Analyze orderbook for trading signals.
        
        Returns:
            Dict with spread, imbalance, signals
        """
        if not orderbook:
            return {}
        
        levels = orderbook.get('levels', [[], []])
        bids = levels[0]  # Buy orders
        asks = levels[1]  # Sell orders
        
        if not bids or not asks:
            return {}
        
        best_bid = float(bids[0]['px'])
        best_ask = float(asks[0]['px'])
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid) * 100
        
        # Calculate depth
        bid_depth = sum(float(b['sz']) for b in bids[:5])
        ask_depth = sum(float(a['sz']) for a in asks[:5])
        
        # Imbalance
        imbalance = bid_depth / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0.5
        
        # Signal generation
        signal = None
        if spread_pct < 0.05:  # Very tight spread
            if imbalance > 0.7:
                signal = "BUY"  # More buyers
            elif imbalance < 0.3:
                signal = "SELL"  # More sellers
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'spread': spread,
            'spread_pct': spread_pct,
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'imbalance': imbalance,
            'signal': signal
        }


async def test_hyperliquid():
    """Test Hyperliquid API connection."""
    print("=" * 80)
    print("HYPERLIQUID API TEST")
    print("=" * 80)
    print()
    
    async with HyperliquidClient() as client:
        # Test 1: Get markets
        print("1. Fetching available markets...")
        markets = await client.get_markets()
        print(f"   Found {len(markets)} markets")
        
        if markets:
            print("   Top 5 markets:")
            for m in markets[:5]:
                print(f"     - {m.get('name')} (Max leverage: {m.get('maxLeverage')}x)")
        print()
        
        # Test 2: Get orderbook
        print("2. Fetching BTC orderbook...")
        ob = await client.get_orderbook("BTC")
        
        if ob:
            analysis = client.analyze_orderbook(ob)
            if analysis:
                print(f"   Best Bid: ${analysis['best_bid']:,.2f}")
                print(f"   Best Ask: ${analysis['best_ask']:,.2f}")
                print(f"   Spread: {analysis['spread_pct']:.4f}%")
                print(f"   Bid Depth: {analysis['bid_depth']:.4f} BTC")
                print(f"   Ask Depth: {analysis['ask_depth']:.4f} BTC")
                print(f"   Signal: {analysis['signal']}")
        print()
        
        # Test 3: Get recent trades
        print("3. Fetching recent trades...")
        trades = await client.get_recent_trades("BTC", limit=5)
        
        if trades:
            print("   Recent trades:")
            for t in trades:
                side = "BUY" if t.get('side') == 'B' else "SELL"
                price = float(t.get('px', 0))
                size = float(t.get('sz', 0))
                print(f"     {side} {size:.4f} BTC @ ${price:,.2f}")
        print()
        
        print("=" * 80)
        print("CONNECTION SUCCESSFUL")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Create Hyperliquid account: https://hyperliquid.xyz")
        print("2. Connect your wallet")
        print("3. Deposit USDC")
        print("4. Add wallet address to this script")
        print("5. Start building your trading bot")


async def demo_strategy():
    """
    Demo scalping strategy.
    
    This is a template - adapt for your own strategy.
    """
    print("=" * 80)
    print("DEMO: Orderbook Imbalance Strategy")
    print("=" * 80)
    print()
    
    async with HyperliquidClient() as client:
        # Configuration
        COIN = "BTC"
        THRESHOLD = 0.7  # 70% imbalance
        
        print(f"Monitoring {COIN} for orderbook imbalances...")
        print(f"Threshold: {THRESHOLD * 100:.0f}%")
        print()
        
        for i in range(5):  # Check 5 times
            ob = await client.get_orderbook(COIN)
            analysis = client.analyze_orderbook(ob)
            
            if analysis:
                print(f"Check {i+1}:")
                print(f"  Spread: {analysis['spread_pct']:.4f}%")
                print(f"  Imbalance: {analysis['imbalance']:.2%}")
                
                if analysis['signal'] == "BUY":
                    print(f"  >>> BUY SIGNAL (more buyers)")
                elif analysis['signal'] == "SELL":
                    print(f"  >>> SELL SIGNAL (more sellers)")
                else:
                    print(f"  No signal")
            
            await asyncio.sleep(2)  # Wait 2 seconds
            print()
        
        print("Demo complete.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_strategy())
    else:
        asyncio.run(test_hyperliquid())
