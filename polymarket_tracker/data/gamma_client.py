"""
Gamma API client for Polymarket market metadata.

Gamma API provides market data without authentication.
Reference: https://docs.polymarket.com/#gamma-api
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logger import setup_logging

logger = setup_logging()

GAMMA_API_BASE = "https://gamma-api.polymarket.com"


class GammaClient:
    """Client for Polymarket Gamma API."""
    
    def __init__(self):
        """Initialize Gamma API client."""
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request with retry logic."""
        url = f"{GAMMA_API_BASE}{endpoint}"
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def get_markets(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "volume",
        category: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get markets from Gamma API.
        
        Args:
            active: Include active markets
            closed: Include closed markets
            limit: Number of results
            offset: Pagination offset
            sort_by: Sort field (volume, liquidity, etc.)
            category: Filter by category
            
        Returns:
            DataFrame of markets
        """
        params = {
            'active': active,
            'closed': closed,
            'limit': limit,
            'offset': offset,
            'sort': sort_by,
        }
        
        if category:
            params['category'] = category
        
        data = self._get('/markets', params)
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Clean up data types
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        if 'liquidity' in df.columns:
            df['liquidity'] = pd.to_numeric(df['liquidity'], errors='coerce')
        if 'endDate' in df.columns:
            df['endDate'] = pd.to_datetime(df['endDate'])
        
        logger.info(f"Fetched {len(df)} markets from Gamma API")
        return df
    
    def get_market(self, slug: str) -> Dict:
        """
        Get detailed market information by slug.
        
        Args:
            slug: Market slug (e.g., "will-trump-win-2024")
            
        Returns:
            Market data dictionary
        """
        return self._get(f'/markets/{slug}')
    
    def get_market_by_condition_id(self, condition_id: str) -> Dict:
        """
        Get market by condition ID.
        
        Args:
            condition_id: Market condition ID
            
        Returns:
            Market data dictionary
        """
        params = {'conditionIds': [condition_id]}
        data = self._get('/markets', params)
        return data[0] if data else {}
    
    def get_events(
        self,
        active: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get events from Gamma API.
        
        Args:
            active: Include active events
            limit: Number of results
            offset: Pagination offset
            
        Returns:
            DataFrame of events
        """
        params = {
            'active': active,
            'limit': limit,
            'offset': offset,
        }
        
        data = self._get('/events', params)
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_event(self, slug: str) -> Dict:
        """
        Get detailed event information.
        
        Args:
            slug: Event slug
            
        Returns:
            Event data dictionary
        """
        return self._get(f'/events/{slug}')
    
    def get_order_book(self, token_id: str) -> Dict:
        """
        Get order book for a specific token.
        
        Args:
            token_id: ERC-1155 token ID
            
        Returns:
            Order book data
        """
        return self._get(f'/order-book', {'tokenId': token_id})
    
    def get_price_history(self, market_id: str) -> pd.DataFrame:
        """
        Get historical price data for a market.
        
        Args:
            market_id: Market ID
            
        Returns:
            DataFrame with price history
        """
        data = self._get(f'/markets/{market_id}/prices')
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def get_categories(self) -> List[str]:
        """
        Get available market categories.
        
        Returns:
            List of category names
        """
        markets = self.get_markets(limit=1000, active=True)
        
        if 'category' not in markets.columns:
            return []
        
        return markets['category'].dropna().unique().tolist()
    
    def search_markets(self, query: str, limit: int = 20) -> pd.DataFrame:
        """
        Search markets by query string.
        
        Args:
            query: Search query
            limit: Number of results
            
        Returns:
            DataFrame of matching markets
        """
        # Get all markets and filter
        markets = self.get_markets(limit=500, active=True)
        
        if markets.empty:
            return markets
        
        # Filter by query in question or description
        query_lower = query.lower()
        mask = (
            markets['question'].str.lower().str.contains(query_lower, na=False) |
            markets.get('description', '').str.lower().str.contains(query_lower, na=False)
        )
        
        return markets[mask].head(limit)
