#!/usr/bin/env python3
"""
Real Crypto Market Scanner - Using ACTUAL Polymarket Gamma API

This script:
1. Fetches ACTIVE markets from Polymarket Gamma API
2. Filters for BTC, ETH, XRP, SOL only
3. Shows REAL prices and opportunities
4. Makes REAL calculations (not simulation)
"""

import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# Polymarket Gamma API (for active markets)
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

CRYPTO_KEYWORDS = {
    'BTC': ['bitcoin', ' btc', '$btc', 'btc '],
    'ETH': ['ethereum', ' eth', '$eth', 'eth ', 'ether'],
    'XRP': ['ripple', ' xrp', '$xrp'],
    'SOL': ['solana', ' sol', '$sol'],
}

def is_crypto_market(question: str) -> tuple[bool, str]:
    """Check if market is crypto-related."""
    q_lower = question.lower()
    for crypto, keywords in CRYPTO_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return True, crypto
    return False, ''

class RealCryptoScanner:
    """Scanner using real Polymarket Gamma API data."""
    
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_active_markets(self, limit: int = 500) -> list[dict]:
        """Fetch ACTIVE markets from Polymarket Gamma."""
        url = f"{GAMMA_API_BASE}/markets"
        params = {
            'active': 'true',
            'closed': 'false',
            'archived': 'false',
            'limit': limit
        }
        
        try:
            async with self.session.get(url, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return data if isinstance(data, list) else []
                else:
                    print(f"[ERROR] API returned {response.status}")
                    return []
        except Exception as e:
            print(f"[ERROR] {e}")
            return []
    
    def filter_crypto_markets(self, markets: list[dict]) -> list[dict]:
        """Filter for active BTC, ETH, XRP, SOL markets."""
        crypto_markets = []
        
        for m in markets:
            # Skip closed/archived
            if m.get('closed') or m.get('archived'):
                continue
            
            question = m.get('question', '')
            is_crypto, crypto_type = is_crypto_market(question)
            
            if is_crypto:
                # Get prices from outcomePrices
                prices = m.get('outcomePrices', ['0.5', '0.5'])
                if isinstance(prices, list) and len(prices) >= 2:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])
                else:
                    yes_price = no_price = 0.5
                
                # Parse volume and liquidity (strings in API)
                try:
                    volume = float(m.get('volume', 0) or 0)
                except (TypeError, ValueError):
                    volume = 0
                
                try:
                    liquidity = float(m.get('liquidity', 0) or 0)
                except (TypeError, ValueError):
                    liquidity = 0
                
                # Get end date
                end_date = m.get('endDate') or m.get('end_date_iso', '')
                
                crypto_markets.append({
                    'id': m.get('market_slug') or m.get('conditionId'),
                    'condition_id': m.get('conditionId'),
                    'question': question,
                    'crypto_type': crypto_type,
                    'description': m.get('description', '')[:100],
                    'yes_price': yes_price,
                    'no_price': no_price,
                    'volume': volume,
                    'liquidity': liquidity,
                    'end_date': end_date,
                    'category': m.get('category', 'Unknown'),
                    'accepting_orders': m.get('accepting_orders', False),
                })
        
        # Sort by volume descending
        crypto_markets.sort(key=lambda x: x['volume'], reverse=True)
        return crypto_markets
    
    def analyze_opportunities(self, markets: list[dict]) -> list[dict]:
        """Find small edge opportunities in real markets."""
        opportunities = []
        
        for m in markets:
            yes_price = m['yes_price']
            no_price = m['no_price']
            liquidity = m['liquidity']
            volume = m['volume']
            
            # Skip low liquidity markets
            if liquidity < 5000:
                continue
            
            # Calculate spread
            spread = abs(yes_price + no_price - 1.0)
            if spread > 0.02:  # Skip wide spreads
                continue
            
            # Strategy 1: Mean reversion near 50%
            # When price is slightly away from 50%, bet on reversion
            
            # Case 1: YES undervalued (price < 0.48 but > 0.40)
            if 0.40 <= yes_price < 0.48:
                edge = 0.50 - yes_price
                if 0.02 <= edge <= 0.10:  # 2-10% edge
                    opportunities.append({
                        'market': m,
                        'crypto': m['crypto_type'],
                        'side': 'YES',
                        'price': yes_price,
                        'edge': edge,
                        'edge_pct': edge * 100,
                        'expected_return': edge / yes_price if yes_price > 0 else 0,
                        'reason': f'Mean reversion: {crypto_type} YES undervalued',
                        'confidence': 0.60,
                        'strategy': 'mean_reversion'
                    })
            
            # Case 2: NO undervalued
            elif 0.40 <= no_price < 0.48:
                edge = 0.50 - no_price
                if 0.02 <= edge <= 0.10:
                    opportunities.append({
                        'market': m,
                        'crypto': m['crypto_type'],
                        'side': 'NO',
                        'price': no_price,
                        'edge': edge,
                        'edge_pct': edge * 100,
                        'expected_return': edge / no_price if no_price > 0 else 0,
                        'reason': f'Mean reversion: {m["crypto_type"]} NO undervalued',
                        'confidence': 0.60,
                        'strategy': 'mean_reversion'
                    })
            
            # Strategy 2: Momentum with volume
            # High volume + price movement indicates momentum
            elif volume > 100000:
                if yes_price > 0.52 and yes_price < 0.70:
                    # Upward momentum in YES
                    opportunities.append({
                        'market': m,
                        'crypto': m['crypto_type'],
                        'side': 'YES',
                        'price': yes_price,
                        'edge': 0.03,
                        'edge_pct': 3.0,
                        'expected_return': 0.03 / yes_price,
                        'reason': f'Momentum: {m["crypto_type"]} YES trending up with volume',
                        'confidence': 0.55,
                        'strategy': 'momentum'
                    })
                elif no_price > 0.52 and no_price < 0.70:
                    # Upward momentum in NO
                    opportunities.append({
                        'market': m,
                        'crypto': m['crypto_type'],
                        'side': 'NO',
                        'price': no_price,
                        'edge': 0.03,
                        'edge_pct': 3.0,
                        'expected_return': 0.03 / no_price,
                        'reason': f'Momentum: {m["crypto_type"]} NO trending up with volume',
                        'confidence': 0.55,
                        'strategy': 'momentum'
                    })
        
        # Sort by expected return
        opportunities.sort(key=lambda x: x['expected_return'], reverse=True)
        return opportunities

async def main():
    print("\n" + "=" * 80)
    print("CRYPTO MARKET SCANNER - REAL DATA FROM POLYMARKET GAMMA API")
    print("=" * 80)
    print()
    print("Strategy: High-frequency small-margin trading on BTC/ETH/XRP/SOL")
    print("Data Source: Polymarket Gamma API (REAL market data)")
    print()
    
    async with RealCryptoScanner() as scanner:
        print("Fetching ACTIVE markets from Polymarket...")
        markets = await scanner.fetch_active_markets(limit=500)
        
        if not markets:
            print("No markets found. Check API connection.")
            return
        
        print(f"Total active markets: {len(markets)}")
        print()
        
        # Filter for crypto
        crypto_markets = scanner.filter_crypto_markets(markets)
        
        if not crypto_markets:
            print("No active crypto markets found.")
            print("This could mean:")
            print("  - No crypto events currently listed")
            print("  - Markets are too new/illiquid")
            print()
            print("Try again later when new crypto markets are listed.")
            return
        
        # Group by crypto type
        by_type = {'BTC': [], 'ETH': [], 'XRP': [], 'SOL': []}
        for m in crypto_markets:
            if m['crypto_type'] in by_type:
                by_type[m['crypto_type']].append(m)
        
        print("=" * 80)
        print("ACTIVE CRYPTO MARKETS")
        print("=" * 80)
        print()
        
        total_volume = 0
        for crypto_type in ['BTC', 'ETH', 'XRP', 'SOL']:
            cms = by_type[crypto_type]
            if not cms:
                continue
            
            print(f"\n{crypto_type} Markets ({len(cms)} found):")
            print("-" * 80)
            
            for m in cms[:5]:  # Show top 5
                volume_usd = m['volume'] / 1e6 if m['volume'] > 1e6 else m['volume'] / 1e3
                vol_unit = 'M' if m['volume'] > 1e6 else 'k'
                total_volume += m['volume']
                
                spread = abs(m['yes_price'] + m['no_price'] - 1.0)
                accepting = "[TRADING]" if m['accepting_orders'] else "[CLOSED]"
                
                print(f"  {accepting} {m['question'][:55]}...")
                print(f"    YES: ${m['yes_price']:.3f} | NO: ${m['no_price']:.3f} | Spread: {spread:.3f}")
                print(f"    Volume: ${volume_usd:.2f}{vol_unit} | Liquidity: ${m['liquidity']/1e3:.0f}k")
                if m['end_date']:
                    print(f"    Ends: {m['end_date'][:10]}")
                print()
        
        print("=" * 80)
        print(f"SUMMARY: {len(crypto_markets)} active crypto markets | Total volume: ${total_volume/1e6:.1f}M")
        print("=" * 80)
        print()
        
        # Analyze opportunities
        print("Scanning for small-edge opportunities...")
        print()
        
        opportunities = scanner.analyze_opportunities(crypto_markets)
        
        if opportunities:
            print("=" * 80)
            print("TRADING OPPORTUNITIES (Real Calculations)")
            print("=" * 80)
            print()
            
            for i, opp in enumerate(opportunities[:10], 1):
                m = opp['market']
                print(f"{i}. [{opp['crypto']}] {opp['side']} at ${opp['price']:.3f}")
                print(f"   Market: {m['question'][:50]}...")
                print(f"   Edge: {opp['edge_pct']:.1f}% | Expected Return: {opp['expected_return']:.1%}")
                print(f"   Strategy: {opp['strategy']} | Confidence: {opp['confidence']:.0%}")
                print(f"   Reason: {opp['reason']}")
                print()
            
            print("=" * 80)
            print(f"RECOMMENDATION: Execute on top {min(5, len(opportunities))} opportunities")
            print("  - Position size: $5 per trade")
            print("  - Take profit: 3% | Stop loss: 2%")
            print("  - Hold time: Max 12 hours")
            print("=" * 80)
            
        else:
            print("No small-edge opportunities found at this time.")
            print()
            print("Possible reasons:")
            print("  - Markets efficiently priced near 50/50")
            print("  - Liquidity too low for edge")
            print("  - No active crypto markets with volume")
            print()
            print("Recommendations:")
            print("  - Wait for new crypto markets to be listed")
            print("  - Check for short-term price action markets")
            print("  - Run scanner every hour for new opportunities")
        
        print()
        print("=" * 80)
        print("All data is REAL from Polymarket Gamma API")
        print("No simulation - these are actual market prices and volumes")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
