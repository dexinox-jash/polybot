#!/usr/bin/env python3
"""
Crypto Market Watcher for Polymarket

Simple script to check for new crypto markets and alert when found.
Run this hourly or daily to monitor for new listings.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from pathlib import Path

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

CRYPTO_KEYWORDS = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'xrp', 'ripple', 'crypto']

# File to store previously seen markets
STATE_FILE = Path("crypto_markets_state.json")


async def fetch_all_markets(session: aiohttp.ClientSession) -> list:
    """Fetch all markets from Polymarket."""
    markets = []
    
    # Gamma API
    try:
        async with session.get(f"{GAMMA_API}/markets", params={'limit': 500}, timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list):
                    markets.extend(data)
    except:
        pass
    
    # CLOB API
    try:
        async with session.get(f"{CLOB_API}/markets", timeout=30) as resp:
            if resp.status == 200:
                data = await resp.json()
                markets.extend(data.get('data', []))
    except:
        pass
    
    return markets


def filter_crypto_markets(markets: list) -> list:
    """Filter for crypto markets accepting orders."""
    crypto_markets = []
    
    for m in markets:
        question = m.get('question', '').lower()
        
        # Check if crypto-related
        is_crypto = any(kw in question for kw in CRYPTO_KEYWORDS)
        
        if is_crypto and m.get('accepting_orders'):
            crypto_markets.append({
                'condition_id': m.get('conditionId') or m.get('condition_id'),
                'question': m.get('question'),
                'slug': m.get('market_slug') or m.get('slug'),
                'prices': m.get('outcomePrices'),
                'volume': m.get('volume'),
                'liquidity': m.get('liquidity'),
                'end_date': m.get('endDate') or m.get('end_date_iso'),
            })
    
    return crypto_markets


def load_previous_state() -> list:
    """Load previously seen market IDs."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('market_ids', [])
        except:
            pass
    return []


def save_state(market_ids: list):
    """Save current market IDs."""
    with open(STATE_FILE, 'w') as f:
        json.dump({
            'market_ids': market_ids,
            'last_check': datetime.now().isoformat()
        }, f, indent=2)


async def main():
    print("=" * 80)
    print("POLYMARKET CRYPTO MARKET WATCHER")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    async with aiohttp.ClientSession() as session:
        # Fetch markets
        print("Fetching markets from Polymarket...")
        markets = await fetch_all_markets(session)
        print(f"Total markets: {len(markets)}")
        
        # Find crypto markets
        crypto_markets = filter_crypto_markets(markets)
        print(f"Active crypto markets: {len(crypto_markets)}")
        print()
        
        # Load previous state
        previous_ids = load_previous_state()
        current_ids = [m['condition_id'] for m in crypto_markets if m['condition_id']]
        
        # Find new markets
        new_markets = [m for m in crypto_markets if m['condition_id'] not in previous_ids]
        
        if new_markets:
            print("=" * 80)
            print("🎉 NEW CRYPTO MARKETS FOUND!")
            print("=" * 80)
            print()
            
            for i, m in enumerate(new_markets, 1):
                print(f"{i}. {m['question']}")
                print(f"   Slug: {m['slug']}")
                print(f"   Prices: {m['prices']}")
                print(f"   Volume: {m['volume']}")
                print(f"   Liquidity: {m['liquidity']}")
                print(f"   End: {m['end_date']}")
                print()
            
            print("=" * 80)
            print("ACTION: Run your bot now!")
            print("  python polymarket_5m_crypto_bot.py")
            print("=" * 80)
            
        elif crypto_markets:
            print("=" * 80)
            print("Active crypto markets (already known):")
            print("=" * 80)
            print()
            
            for m in crypto_markets[:5]:
                print(f"- {m['question'][:60]}...")
                print(f"  Prices: {m['prices']}")
            
            print()
            print(f"Total: {len(crypto_markets)} markets (no new ones)")
            
        else:
            print("=" * 80)
            print("No active crypto markets found.")
            print("Keep monitoring - markets may appear during:")
            print("  - High volatility periods")
            print("  - Major crypto events")
            print("  - ETF approvals")
            print("=" * 80)
        
        # Save state
        save_state(current_ids)
        
        print()
        print(f"State saved. Will check for new markets on next run.")
        print()


if __name__ == "__main__":
    asyncio.run(main())
