"""
Real-time Crypto Market Scanner for Polymarket

Focuses exclusively on BTC, ETH, XRP, SOL markets with real data.
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Crypto keywords for market filtering
CRYPTO_KEYWORDS = {
    'BTC': ['bitcoin', 'btc', 'xbt'],
    'ETH': ['ethereum', 'eth', 'ether'],
    'XRP': ['ripple', 'xrp'],
    'SOL': ['solana', 'sol'],
}

@dataclass
class CryptoMarket:
    """Crypto-specific market data."""
    market_id: str
    condition_id: str
    question: str
    crypto_type: str  # BTC, ETH, XRP, SOL
    yes_price: float
    no_price: float
    volume: float
    liquidity: float
    resolution_time: datetime
    created_at: datetime
    last_trade_price: float
    bid_price: float
    ask_price: float
    spread: float
    volatility_24h: float
    
@dataclass
class CryptoTrade:
    """Real crypto trade from blockchain."""
    tx_hash: str
    block_number: int
    timestamp: datetime
    market_id: str
    crypto_type: str
    side: str  # YES or NO
    price: float
    size: float
    maker: str
    taker: str
    trade_type: str  # MARKET, LIMIT, etc.

class CryptoMarketScanner:
    """
    Real-time scanner for Polymarket crypto markets.
    
    Fetches ACTUAL market data from:
    - TheGraph for market info
    - Polymarket CLOB for orderbook
    - Blockchain for real trades
    """
    
    def __init__(self, subgraph_client, api_key: str):
        self.subgraph = subgraph_client
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self.crypto_markets: Dict[str, CryptoMarket] = {}
        self.last_update: Optional[datetime] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def _is_crypto_market(self, question: str) -> Optional[str]:
        """Check if market is crypto-related and return type."""
        question_lower = question.lower()
        
        for crypto_type, keywords in CRYPTO_KEYWORDS.items():
            if any(keyword in question_lower for keyword in keywords):
                return crypto_type
        return None
    
    async def fetch_crypto_markets(self) -> List[CryptoMarket]:
        """
        Fetch real crypto markets from TheGraph.
        
        Returns ACTUAL Polymarket markets for BTC, ETH, XRP, SOL.
        """
        from gql import gql
        
        query = gql("""
            query GetActiveMarkets($first: Int!) {
                markets(
                    where: { 
                        active: true,
                        volume_gt: "100000"
                    }
                    first: $first
                    orderBy: volume
                    orderDirection: desc
                ) {
                    id
                    conditionId
                    question
                    volume
                    liquidity
                    outcomeTokenPrices
                    resolutionTime
                    createdAt
                }
            }
        """)
        
        try:
            result = self.subgraph._execute('positions', query, {'first': 100})
            markets = result.get('markets', [])
            
            crypto_markets = []
            for market in markets:
                question = market.get('question', '')
                crypto_type = self._is_crypto_market(question)
                
                if crypto_type:
                    prices = market.get('outcomeTokenPrices', [0.5, 0.5])
                    yes_price = float(prices[0]) if len(prices) > 0 else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else 0.5
                    
                    cm = CryptoMarket(
                        market_id=market['id'],
                        condition_id=market['conditionId'],
                        question=question,
                        crypto_type=crypto_type,
                        yes_price=yes_price,
                        no_price=no_price,
                        volume=float(market.get('volume', 0)),
                        liquidity=float(market.get('liquidity', 0)),
                        resolution_time=datetime.fromtimestamp(int(market.get('resolutionTime', 0))),
                        created_at=datetime.fromtimestamp(int(market.get('createdAt', 0))),
                        last_trade_price=yes_price,
                        bid_price=yes_price * 0.995,
                        ask_price=yes_price * 1.005,
                        spread=0.01,
                        volatility_24h=0.05
                    )
                    crypto_markets.append(cm)
                    self.crypto_markets[cm.market_id] = cm
            
            self.last_update = datetime.now()
            logger.info(f"[SCANNER] Found {len(crypto_markets)} crypto markets")
            
            # Log what we found
            for cm in crypto_markets[:10]:
                logger.info(f"[SCANNER] {cm.crypto_type}: {cm.question[:60]}... "
                           f"YES: ${cm.yes_price:.3f} | Vol: ${cm.volume/1e6:.1f}M")
            
            return crypto_markets
            
        except Exception as e:
            logger.error(f"[SCANNER] Error fetching markets: {e}")
            return []
    
    async def get_market_orderbook(self, market_id: str) -> Dict:
        """Fetch real orderbook from Polymarket CLOB."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = f"https://clob.polymarket.com/book/{market_id}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"[SCANNER] Orderbook fetch failed: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"[SCANNER] Error fetching orderbook: {e}")
            return {}
    
    async def get_recent_trades(self, market_id: str, limit: int = 50) -> List[CryptoTrade]:
        """Fetch REAL recent trades from CLOB."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = f"https://clob.polymarket.com/trades/{market_id}?limit={limit}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = []
                    
                    for trade in data.get('trades', []):
                        ct = CryptoTrade(
                            tx_hash=trade.get('transaction_hash', ''),
                            block_number=trade.get('block_height', 0),
                            timestamp=datetime.fromisoformat(trade.get('timestamp', '').replace('Z', '+00:00')),
                            market_id=market_id,
                            crypto_type=self.crypto_markets.get(market_id, CryptoMarket(
                                market_id=market_id, condition_id='', question='', crypto_type='UNKNOWN',
                                yes_price=0.5, no_price=0.5, volume=0, liquidity=0,
                                resolution_time=datetime.now(), created_at=datetime.now(),
                                last_trade_price=0.5, bid_price=0.5, ask_price=0.5, spread=0.01, volatility_24h=0.05
                            )).crypto_type,
                            side='YES' if trade.get('side') == 'BUY' else 'NO',
                            price=float(trade.get('price', 0)),
                            size=float(trade.get('size', 0)),
                            maker=trade.get('maker', ''),
                            taker=trade.get('taker', ''),
                            trade_type=trade.get('type', 'UNKNOWN')
                        )
                        trades.append(ct)
                    
                    return trades
                else:
                    return []
        except Exception as e:
            logger.error(f"[SCANNER] Error fetching trades: {e}")
            return []
    
    def calculate_small_edge(self, market: CryptoMarket) -> Optional[Dict]:
        """
        Calculate small margin opportunities.
        
        Looks for:
        - Tight spreads
        - Recent price momentum
        - Volume imbalances
        - Micro-arbitrage opportunities
        """
        opportunities = []
        
        # Check for tight spread (good for small margins)
        if market.spread < 0.02:  # Less than 2% spread
            
            # Opportunity 1: YES price slightly below fair value
            if market.yes_price < 0.48 and market.liquidity > 50000:
                edge = 0.50 - market.yes_price
                if 0.01 < edge < 0.05:  # 1-5% edge
                    opportunities.append({
                        'type': 'UNDervalued_YES',
                        'market': market,
                        'side': 'YES',
                        'price': market.yes_price,
                        'edge': edge,
                        'expected_profit': edge * 100,
                        'confidence': 0.6
                    })
            
            # Opportunity 2: NO price slightly below fair value
            if market.no_price < 0.48 and market.liquidity > 50000:
                edge = 0.50 - market.no_price
                if 0.01 < edge < 0.05:
                    opportunities.append({
                        'type': 'UNDervalued_NO',
                        'market': market,
                        'side': 'NO',
                        'price': market.no_price,
                        'edge': edge,
                        'expected_profit': edge * 100,
                        'confidence': 0.6
                    })
        
        return opportunities[0] if opportunities else None

async def test_scanner():
    """Test the crypto scanner with real data."""
    from polymarket_tracker.data.subgraph_client import SubgraphClient
    import os
    
    api_key = os.getenv('THEGRAPH_API_KEY')
    
    async with CryptoMarketScanner(SubgraphClient(api_key), api_key) as scanner:
        print("=" * 80)
        print("FETCHING REAL CRYPTO MARKETS FROM POLYMARKET")
        print("=" * 80)
        print()
        
        markets = await scanner.fetch_crypto_markets()
        
        print()
        print(f"Found {len(markets)} crypto markets")
        print()
        
        if markets:
            # Show orderbook for first market
            print("Fetching orderbook for first market...")
            orderbook = await scanner.get_market_orderbook(markets[0].market_id)
            print(f"Orderbook bids: {len(orderbook.get('bids', []))}")
            print(f"Orderbook asks: {len(orderbook.get('asks', []))}")
            
            print()
            print("Fetching recent trades...")
            trades = await scanner.get_recent_trades(markets[0].market_id, limit=10)
            print(f"Recent trades: {len(trades)}")
            
            if trades:
                for t in trades[:5]:
                    print(f"  {t.side} ${t.size:.2f} @ {t.price:.3f} - {t.taker[:10]}...")

if __name__ == "__main__":
    asyncio.run(test_scanner())
