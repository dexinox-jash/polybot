"""
GraphQL client for Polymarket The Graph subgraphs.

Subgraphs available:
- Positions: Wallet balances and positions
- Activity: Splits, merges, redemptions
- PnL: Profit/loss tracking
- Orderbook: Market microstructure
"""

from typing import Dict, List, Optional, Any
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from tenacity import retry, stop_after_attempt, wait_exponential
import pandas as pd
from datetime import datetime, timedelta

from ..utils.logger import setup_logging

logger = setup_logging()


class SubgraphClient:
    """Client for querying Polymarket subgraphs."""
    
    # GraphQL Queries
    POSITIONS_QUERY = gql("""
        query GetPositions($wallet: String!, $first: Int!, $skip: Int!) {
            positions(
                where: { user: $wallet }
                first: $first
                skip: $skip
                orderBy: createdAt
                orderDirection: desc
            ) {
                id
                market {
                    id
                    question
                    conditionId
                    outcomeTokenPrices
                    outcomes
                    resolutionTime
                    status
                }
                outcomeIndex
                amount
                createdAt
                updatedAt
            }
        }
    """)
    
    ORDERS_QUERY = gql("""
        query GetOrders($wallet: String!, $first: Int!, $skip: Int!) {
            orders(
                where: { maker: $wallet }
                first: $first
                skip: $skip
                orderBy: createdAt
                orderDirection: desc
            ) {
                id
                market {
                    id
                    question
                    conditionId
                }
                side
                price
                size
                filledSize
                status
                createdAt
                updatedAt
            }
        }
    """)
    
    TRADES_QUERY = gql("""
        query GetTrades($wallet: String!, $first: Int!, $skip: Int!) {
            trades(
                where: { user: $wallet }
                first: $first
                skip: $skip
                orderBy: timestamp
                orderDirection: desc
            ) {
                id
                market {
                    id
                    question
                    conditionId
                    outcomes
                }
                outcomeIndex
                side
                price
                size
                fee
                pnl
                timestamp
                transactionHash
            }
        }
    """)
    
    PNL_QUERY = gql("""
        query GetPnL($wallet: String!) {
            user(id: $wallet) {
                id
                totalVolume
                totalPnL
                realizedPnL
                unrealizedPnL
                totalTrades
                winningTrades
                losingTrades
                markets {
                    market {
                        id
                        question
                    }
                    volume
                    pnl
                    trades
                }
            }
        }
    """)
    
    MARKET_QUERY = gql("""
        query GetMarket($marketId: String!) {
            market(id: $marketId) {
                id
                question
                description
                conditionId
                outcomes
                outcomeTokenPrices
                volume
                liquidity
                resolutionTime
                status
                createdAt
                category
                subcategory
            }
        }
    """)
    
    MARKETS_QUERY = gql("""
        query GetMarkets($first: Int!, $skip: Int!, $status: String) {
            markets(
                first: $first
                skip: $skip
                where: { status: $status }
                orderBy: volume
                orderDirection: desc
            ) {
                id
                question
                conditionId
                outcomes
                outcomeTokenPrices
                volume
                liquidity
                resolutionTime
                status
                category
            }
        }
    """)
    
    def __init__(self, api_key: str):
        """
        Initialize the subgraph client.
        
        Args:
            api_key: The Graph API key
        """
        self.api_key = api_key
        self.base_url = f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/"
        
        # Subgraph IDs
        self.subgraphs = {
            'positions': 'Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp',
            'activity': '9AAsF5GbijppB9oC8z37LyBgC7R5fbHRGz5VjG4V4WQp',
            'pnl': '7W1hT7fWz2G5e2R1sY3t8u4i6o9p2q5r7s9t1u3v5w7y9z1',
            'orderbook': 'DrPj32ibxFq8b6JRBC1z81G7b8yN4jBv7d4e4z4yP8j',
        }
        
        self.clients = {}
        self._init_clients()
    
    def _init_clients(self):
        """Initialize GraphQL clients for each subgraph."""
        for name, subgraph_id in self.subgraphs.items():
            try:
                transport = RequestsHTTPTransport(
                    url=f"{self.base_url}{subgraph_id}",
                    verify=True,
                    retries=3,
                )
                self.clients[name] = Client(transport=transport, fetch_schema_from_transport=True)
                logger.debug(f"Initialized {name} subgraph client")
            except Exception as e:
                logger.warning(f"Failed to initialize {name} client: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _execute(self, client_name: str, query, variables: Dict[str, Any]) -> Dict:
        """Execute a GraphQL query with retry logic."""
        if client_name not in self.clients:
            raise ValueError(f"Unknown client: {client_name}")
        
        try:
            result = self.clients[client_name].execute(query, variable_values=variables)
            return result
        except Exception as e:
            logger.error(f"Query failed for {client_name}: {e}")
            raise
    
    def get_positions(self, wallet: str, first: int = 100, skip: int = 0) -> List[Dict]:
        """
        Get all positions for a wallet.
        
        Args:
            wallet: Ethereum address
            first: Number of results to return
            skip: Number of results to skip
            
        Returns:
            List of position data
        """
        wallet = wallet.lower()
        result = self._execute('positions', self.POSITIONS_QUERY, {
            'wallet': wallet,
            'first': first,
            'skip': skip
        })
        return result.get('positions', [])
    
    def get_all_positions(self, wallet: str) -> pd.DataFrame:
        """
        Get all positions for a wallet (paginated).
        
        Args:
            wallet: Ethereum address
            
        Returns:
            DataFrame with all positions
        """
        all_positions = []
        skip = 0
        first = 100
        
        while True:
            positions = self.get_positions(wallet, first, skip)
            if not positions:
                break
            
            all_positions.extend(positions)
            skip += first
            
            if len(positions) < first:
                break
        
        df = pd.DataFrame(all_positions)
        
        if not df.empty:
            # Convert timestamps
            df['createdAt'] = pd.to_datetime(df['createdAt'], unit='s')
            df['updatedAt'] = pd.to_datetime(df['updatedAt'], unit='s')
        
        logger.info(f"Fetched {len(df)} positions for {wallet}")
        return df
    
    def get_trades(self, wallet: str, first: int = 100, skip: int = 0) -> List[Dict]:
        """
        Get all trades for a wallet.
        
        Args:
            wallet: Ethereum address
            first: Number of results
            skip: Number to skip
            
        Returns:
            List of trade data
        """
        wallet = wallet.lower()
        result = self._execute('positions', self.TRADES_QUERY, {
            'wallet': wallet,
            'first': first,
            'skip': skip
        })
        return result.get('trades', [])
    
    def get_all_trades(self, wallet: str) -> pd.DataFrame:
        """
        Get all trades for a wallet (paginated).
        
        Args:
            wallet: Ethereum address
            
        Returns:
            DataFrame with all trades
        """
        all_trades = []
        skip = 0
        first = 100
        
        while True:
            trades = self.get_trades(wallet, first, skip)
            if not trades:
                break
            
            all_trades.extend(trades)
            skip += first
            
            if len(trades) < first:
                break
        
        df = pd.DataFrame(all_trades)
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['price'] = df['price'].astype(float)
            df['size'] = df['size'].astype(float)
        
        logger.info(f"Fetched {len(df)} trades for {wallet}")
        return df
    
    def get_pnl(self, wallet: str) -> Dict:
        """
        Get profit/loss summary for a wallet.
        
        Args:
            wallet: Ethereum address
            
        Returns:
            PnL data dictionary
        """
        wallet = wallet.lower()
        result = self._execute('pnl', self.PNL_QUERY, {'wallet': wallet})
        return result.get('user', {})
    
    def get_market(self, market_id: str) -> Dict:
        """
        Get market details.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Market data dictionary
        """
        result = self._execute('positions', self.MARKET_QUERY, {'marketId': market_id})
        return result.get('market', {})
    
    def get_active_markets(self, first: int = 100, skip: int = 0) -> pd.DataFrame:
        """
        Get active markets sorted by volume.
        
        Args:
            first: Number of results
            skip: Number to skip
            
        Returns:
            DataFrame of active markets
        """
        result = self._execute('positions', self.MARKETS_QUERY, {
            'first': first,
            'skip': skip,
            'status': 'open'
        })
        
        markets = result.get('markets', [])
        df = pd.DataFrame(markets)
        
        if not df.empty:
            df['outcomeTokenPrices'] = df['outcomeTokenPrices'].apply(
                lambda x: [float(p) for p in x] if x else []
            )
        
        return df
    
    def get_market_whale_positions(self, market_id: str, min_size: float = 1000) -> pd.DataFrame:
        """
        Get whale positions for a specific market.
        
        Args:
            market_id: Market condition ID
            min_size: Minimum position size to qualify as whale
            
        Returns:
            DataFrame of whale positions
        """
        query = gql("""
            query GetMarketPositions($marketId: String!, $minSize: BigDecimal!) {
                positions(
                    where: { 
                        market: $marketId,
                        amount_gt: $minSize
                    }
                    first: 1000
                    orderBy: amount
                    orderDirection: desc
                ) {
                    id
                    user {
                        id
                    }
                    outcomeIndex
                    amount
                    createdAt
                }
            }
        """)
        
        result = self._execute('positions', query, {
            'marketId': market_id,
            'minSize': str(min_size)
        })
        
        positions = result.get('positions', [])
        
        # Flatten user data
        for pos in positions:
            pos['wallet'] = pos.get('user', {}).get('id', '')
            del pos['user']
        
        df = pd.DataFrame(positions)
        
        if not df.empty:
            df['createdAt'] = pd.to_datetime(df['createdAt'], unit='s')
            df['amount'] = df['amount'].astype(float)
        
        return df
