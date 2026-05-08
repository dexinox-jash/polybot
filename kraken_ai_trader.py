#!/usr/bin/env python3
"""
Kraken AI Trading Bot - For Canadian Users

Since Hyperliquid is not available in Canada, this uses Kraken:
- Available in ALL Canadian provinces
- Low fees: 0-0.4%
- Excellent API
- High liquidity
- CAD deposits via Interac

Website: https://kraken.com
"""

import asyncio
import aiohttp
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Dict, Optional, List
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Kraken API endpoints
KRAKEN_API_PUBLIC = "https://api.kraken.com/0/public"
KRAKEN_API_PRIVATE = "https://api.kraken.com/0/private"


class KrakenClient:
    """
    Kraken API Client for Canadians.
    
    Features:
    - Market data (orderbook, trades)
    - Account balance (when authenticated)
    - Order placement (when authenticated)
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, urlpath: str, data: dict) -> str:
        """Generate Kraken API signature."""
        if not self.api_secret:
            return None
        
        postdata = '&'.join(f'{key}={value}' for key, value in data.items())
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()
    
    async def public_query(self, method: str, params: dict = None) -> dict:
        """Public API query (no authentication)."""
        url = f"{KRAKEN_API_PUBLIC}/{method}"
        
        try:
            async with self.session.get(url, params=params or {}, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('error'):
                        logger.error(f"Kraken error: {data['error']}")
                        return {}
                    return data.get('result', {})
                else:
                    logger.error(f"HTTP {resp.status}")
                    return {}
        except Exception as e:
            logger.error(f"Request error: {e}")
            return {}
    
    async def get_orderbook(self, pair: str = "XXBTZUSD", count: int = 10) -> Optional[dict]:
        """
        Get orderbook depth.
        
        Args:
            pair: Trading pair (XBTUSD=BTC/USD, ETHUSD=ETH/USD)
            count: Number of levels to fetch
        """
        params = {
            'pair': pair,
            'count': count
        }
        
        result = await self.public_query('Depth', params)
        
        # Kraken returns different pair format
        kraken_pair = pair
        if pair == "XBTUSD":
            kraken_pair = "XXBTZUSD"
        elif pair == "ETHUSD":
            kraken_pair = "XETHZUSD"
        
        if result and kraken_pair in result:
            data = result[kraken_pair]
            # Kraken returns: [price, volume, timestamp]
            bids = [[float(p), float(v)] for p, v, _ in data.get('bids', [])]
            asks = [[float(p), float(v)] for p, v, _ in data.get('asks', [])]
            
            if bids and asks:
                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = (best_ask - best_bid) / best_bid * 100
                
                # Calculate depth
                bid_depth = sum(b[1] for b in bids[:5])
                ask_depth = sum(a[1] for a in asks[:5])
                
                return {
                    'pair': pair,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'spread_pct': spread,
                    'bid_depth': bid_depth,
                    'ask_depth': ask_depth,
                    'bids': bids,
                    'asks': asks
                }
        
        return None
    
    async def get_recent_trades(self, pair: str = "XBTUSD") -> List[dict]:
        """Get recent trades."""
        params = {'pair': pair}
        result = await self.public_query('Trades', params)
        
        # Kraken returns different pair format
        kraken_pair = pair
        if pair == "XBTUSD":
            kraken_pair = "XXBTZUSD"
        elif pair == "ETHUSD":
            kraken_pair = "XETHZUSD"
        
        if result and kraken_pair in result:
            trades = result[kraken_pair]
            # Format: [price, volume, time, side, type, misc]
            return [
                {
                    'price': float(t[0]),
                    'volume': float(t[1]),
                    'time': t[2],
                    'side': 'buy' if t[3] == 'b' else 'sell'
                }
                for t in trades[:20]
            ]
        
        return []
    
    async def get_ticker(self, pair: str = "XBTUSD") -> Optional[dict]:
        """Get ticker data."""
        params = {'pair': pair}
        result = await self.public_query('Ticker', params)
        
        # Kraken returns different pair format
        kraken_pair = pair
        if pair == "XBTUSD":
            kraken_pair = "XXBTZUSD"
        elif pair == "ETHUSD":
            kraken_pair = "XETHZUSD"
        
        if result and kraken_pair in result:
            data = result[kraken_pair]
            return {
                'ask': float(data['a'][0]),
                'bid': float(data['b'][0]),
                'last': float(data['c'][0]),
                'volume': float(data['v'][1]),
                'high': float(data['h'][1]),
                'low': float(data['l'][1])
            }
        
        return None


class KrakenAIStrategy:
    """
    AI Trading Strategy for Kraken.
    
    Implements:
    1. Orderbook imbalance
    2. Spread scalping
    3. Momentum following
    """
    
    def __init__(self):
        self.price_history = []
        
    def analyze_orderbook(self, ob: dict) -> dict:
        """Analyze orderbook for trading signals."""
        if not ob:
            return {'signal': None}
        
        total_depth = ob['bid_depth'] + ob['ask_depth']
        if total_depth == 0:
            return {'signal': None}
        
        imbalance = ob['bid_depth'] / total_depth
        spread = ob['spread_pct']
        
        analysis = {
            'pair': ob['pair'],
            'price': (ob['best_bid'] + ob['best_ask']) / 2,
            'spread': spread,
            'imbalance': imbalance,
            'signal': None,
            'confidence': 0
        }
        
        # Strategy 1: Orderbook Imbalance
        if spread < 0.15:  # Tight spread only
            if imbalance > 0.7:
                analysis['signal'] = 'buy'
                analysis['confidence'] = imbalance
                analysis['reason'] = f'Strong bid imbalance ({imbalance:.1%})'
            elif imbalance < 0.3:
                analysis['signal'] = 'sell'
                analysis['confidence'] = 1 - imbalance
                analysis['reason'] = f'Strong ask imbalance ({1-imbalance:.1%})'
        
        return analysis
    
    def analyze_momentum(self, trades: List[dict]) -> dict:
        """Analyze recent trade momentum."""
        if len(trades) < 5:
            return {'signal': None}
        
        recent = trades[:5]
        buys = sum(1 for t in recent if t['side'] == 'buy')
        sells = 5 - buys
        
        if buys >= 4:
            return {
                'signal': 'buy',
                'confidence': buys / 5,
                'reason': f'Buying momentum ({buys}/5)'
            }
        elif sells >= 4:
            return {
                'signal': 'sell',
                'confidence': sells / 5,
                'reason': f'Selling momentum ({sells}/5)'
            }
        
        return {'signal': None}


class KrakenAITrader:
    """
    Complete AI Trading Bot for Kraken (Canada).
    
    Features:
    - Real-time market analysis
    - Signal generation
    - Paper trading mode (default)
    - Ready for live trading
    """
    
    def __init__(self, pairs: List[str] = None):
        self.pairs = pairs or ["XBTUSD", "ETHUSD"]
        self.client: Optional[KrakenClient] = None
        self.strategy = KrakenAIStrategy()
        self.running = False
        self.stats = {
            'signals': 0,
            'trades': 0,
            'skipped': 0
        }
        self.positions = {}
    
    async def __aenter__(self):
        self.client = await KrakenClient().__aenter__()
        return self
    
    async def __aexit__(self, *args):
        if self.client:
            await self.client.__aexit__(*args)
    
    async def scan_pair(self, pair: str):
        """Scan a single trading pair."""
        # Get orderbook
        ob = await self.client.get_orderbook(pair)
        if not ob:
            return None
        
        # Get recent trades
        trades = await self.client.get_recent_trades(pair)
        
        # Analyze
        ob_analysis = self.strategy.analyze_orderbook(ob)
        mom_analysis = self.strategy.analyze_momentum(trades)
        
        # Combine signals
        signal = None
        if ob_analysis.get('signal'):
            signal = ob_analysis
        elif mom_analysis.get('signal'):
            signal = mom_analysis
        
        return {
            'pair': pair,
            'price': ob['best_ask'] if ob else 0,
            'spread': ob['spread_pct'] if ob else 0,
            'signal': signal
        }
    
    def execute_signal(self, pair: str, signal: dict):
        """Execute or log a trading signal."""
        if not signal:
            return
        
        # Risk checks
        if pair in self.positions:
            logger.info(f"[SKIP] {pair}: Already in position")
            self.stats['skipped'] += 1
            return
        
        if signal['confidence'] < 0.6:
            logger.info(f"[SKIP] {pair}: Low confidence {signal['confidence']:.1%}")
            self.stats['skipped'] += 1
            return
        
        # Log the trade (paper mode)
        logger.info("=" * 80)
        logger.info(f"[TRADE] {pair}: {signal['signal'].upper()}")
        logger.info(f"[TRADE] Confidence: {signal['confidence']:.1%}")
        logger.info(f"[TRADE] Reason: {signal['reason']}")
        logger.info("=" * 80)
        
        # Track position
        self.positions[pair] = {
            'side': signal['signal'],
            'entry_time': datetime.now()
        }
        
        self.stats['trades'] += 1
    
    async def trading_loop(self):
        """Main trading loop."""
        logger.info("=" * 80)
        logger.info("KRAKEN AI TRADER - CANADA")
        logger.info("=" * 80)
        logger.info("Available in ALL Canadian provinces")
        logger.info("Low fees: 0-0.4% | High liquidity | CAD deposits")
        logger.info("")
        logger.info(f"Monitoring: {', '.join(self.pairs)}")
        logger.info("Mode: PAPER TRADING (logging only)")
        logger.info("")
        
        while self.running:
            try:
                for pair in self.pairs:
                    if not self.running:
                        break
                    
                    # Scan for opportunities
                    result = await self.scan_pair(pair)
                    
                    if result:
                        logger.info(f"\n{datetime.now().strftime('%H:%M:%S')} | {pair}")
                        logger.info(f"  Price: ${result['price']:,.2f}")
                        logger.info(f"  Spread: {result['spread']:.4f}%")
                        
                        if result['signal']:
                            self.stats['signals'] += 1
                            self.execute_signal(pair, result['signal'])
                        else:
                            logger.info("  No signal")
                    
                    await asyncio.sleep(2)  # Delay between pairs
                
                await asyncio.sleep(5)  # Delay between cycles
                
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(10)
    
    async def status_report(self):
        """Periodic status report."""
        while self.running:
            await asyncio.sleep(60)
            
            logger.info("-" * 80)
            logger.info("[STATUS] Kraken Trading Report")
            logger.info(f"[STATUS] Signals: {self.stats['signals']}")
            logger.info(f"[STATUS] Trades: {self.stats['trades']}")
            logger.info(f"[STATUS] Skipped: {self.stats['skipped']}")
            logger.info(f"[STATUS] Positions: {len(self.positions)}")
            logger.info("-" * 80)
    
    async def run(self, duration_minutes: int = 10):
        """Run the bot."""
        self.running = True
        
        await asyncio.gather(
            self.trading_loop(),
            self.status_report(),
            self._timer(duration_minutes)
        )
        
        self._final_report()
    
    async def _timer(self, minutes: int):
        """Session timer."""
        await asyncio.sleep(minutes * 60)
        self.running = False
    
    def _final_report(self):
        """Final report."""
        print("\n" + "=" * 80)
        print("KRAKEN AI TRADER - FINAL REPORT")
        print("=" * 80)
        print(f"Signals Generated: {self.stats['signals']}")
        print(f"Trades Executed: {self.stats['trades']}")
        print(f"Trades Skipped: {self.stats['skipped']}")
        print()
        print("Next Steps:")
        print("1. Create Kraken account: https://kraken.com")
        print("2. Get API keys")
        print("3. Add authentication to this bot")
        print("4. Trade with real money")
        print("=" * 80)


async def test_kraken_connection():
    """Test Kraken API connection."""
    print("=" * 80)
    print("TESTING KRAKEN API CONNECTION")
    print("=" * 80)
    print()
    
    async with KrakenClient() as client:
        # Test orderbook
        print("1. Fetching BTC orderbook...")
        ob = await client.get_orderbook("XBTUSD")
        
        if ob:
            print(f"   [OK] Best Bid: ${ob['best_bid']:,.2f}")
            print(f"   [OK] Best Ask: ${ob['best_ask']:,.2f}")
            print(f"   [OK] Spread: {ob['spread']:.4f}%")
            print(f"   [OK] Bid Depth: {ob['bid_depth']:.4f} BTC")
            print(f"   [OK] Ask Depth: {ob['ask_depth']:.4f} BTC")
        else:
            print("   [ERROR] Failed to fetch orderbook")
        
        print()
        
        # Test ticker
        print("2. Fetching BTC ticker...")
        ticker = await client.get_ticker("XBTUSD")
        
        if ticker:
            print(f"   [OK] Last Price: ${ticker['last']:,.2f}")
            print(f"   [OK] 24h High: ${ticker['high']:,.2f}")
            print(f"   [OK] 24h Low: ${ticker['low']:,.2f}")
            print(f"   [OK] 24h Volume: {ticker['volume']:.2f} BTC")
        else:
            print("   [ERROR] Failed to fetch ticker")
        
        print()
        
        # Test trades
        print("3. Fetching recent trades...")
        trades = await client.get_recent_trades("XBTUSD")
        
        if trades:
            print(f"   [OK] Found {len(trades)} recent trades")
            print("   Recent trades:")
            for t in trades[:5]:
                side = "BUY" if t['side'] == 'buy' else "SELL"
                print(f"     {side} {t['volume']:.4f} BTC @ ${t['price']:,.2f}")
        else:
            print("   [ERROR] Failed to fetch trades")
    
    print()
    print("=" * 80)
    print("CONNECTION TEST COMPLETE")
    print("=" * 80)


async def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Just test connection
        await test_kraken_connection()
    else:
        # Run trading bot
        async with KrakenAITrader(pairs=["XBTUSD", "ETHUSD"]) as trader:
            await trader.run(duration_minutes=5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
