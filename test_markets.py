import aiohttp
import asyncio

async def test():
    url = 'https://gamma-api.polymarket.com/markets'
    params = {'active': 'true', 'limit': 500}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=30) as resp:
            data = await resp.json()
            
            # Find crypto category markets
            crypto_markets = [m for m in data if m.get('category') == 'Crypto']
            
            print(f'Crypto category markets: {len(crypto_markets)}')
            print()
            
            # Sort by volume
            crypto_markets.sort(key=lambda x: float(x.get('volume') or 0), reverse=True)
            
            # Show top 10
            for m in crypto_markets[:10]:
                print(f"Q: {m.get('question')}")
                print(f"  Accepting: {m.get('accepting_orders')}")
                print(f"  Active: {m.get('active')}")
                print(f"  Closed: {m.get('closed')}")
                print(f"  Prices: {m.get('outcomePrices')}")
                print(f"  Volume: {m.get('volume')}")
                print(f"  Enable OB: {m.get('enable_order_book')}")
                print()

asyncio.run(test())
