"""
Polymarket CTF (Conditional Tokens Framework) API Client for Live Trading.

This client provides authenticated access to Polymarket's trading API,
enabling live order placement, position management, and market data retrieval.

Reference: https://docs.polymarket.com/#exchange-api
"""

import time
import hmac
import hashlib
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from enum import Enum

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from ..utils.logger import setup_logging

logger = setup_logging()


# API Endpoints
POLYMARKET_API_BASE = "https://api.polymarket.com"
POLYMARKET_CTF_BASE = "https://ctf.polymarket.com"


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status enumeration."""
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PolymarketAPIError(Exception):
    """Base exception for Polymarket API errors."""
    
    def __init__(self, message: str, status_code: int = None, response: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class PolymarketAuthError(PolymarketAPIError):
    """Authentication error."""
    pass


class PolymarketRateLimitError(PolymarketAPIError):
    """Rate limit exceeded error."""
    pass


class PolymarketValidationError(PolymarketAPIError):
    """Validation error."""
    pass


@dataclass
class Order:
    """Represents a Polymarket order."""
    id: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    size_matched: float
    status: str
    created_at: str
    updated_at: Optional[str] = None
    client_order_id: Optional[str] = None


@dataclass
class Position:
    """Represents a Polymarket position."""
    market_id: str
    token_id: str
    asset_id: str
    outcome: str
    size: float
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float


@dataclass
class Balance:
    """Represents account balance."""
    usdc_balance: float
    usdc_locked: float
    usdc_available: float


class PolymarketClient:
    """
    Client for Polymarket CTF API trading.
    
    Provides methods for:
    - Authentication with API keys
    - Account management (balance, positions, orders)
    - Trading (place/cancel orders)
    - Market data retrieval
    
    Example:
        >>> client = PolymarketClient(
        ...     api_key="your_api_key",
        ...     api_secret="your_api_secret",
        ...     private_key="your_private_key"
        ... )
        >>> balance = client.get_balance()
        >>> print(f"Available: ${balance.usdc_available:.2f}")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        base_url: str = POLYMARKET_API_BASE,
        ctf_url: str = POLYMARKET_CTF_BASE,
    ):
        """
        Initialize Polymarket API client.
        
        Args:
            api_key: Polymarket API key
            api_secret: Polymarket API secret
            private_key: Ethereum private key for transaction signing
            base_url: Base URL for API requests
            ctf_url: Base URL for CTF API requests
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = private_key
        self.base_url = base_url.rstrip('/')
        self.ctf_url = ctf_url.rstrip('/')
        
        # Initialize session with default headers
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        
        # Add authentication headers if credentials provided
        if api_key:
            self.session.headers.update({
                'POLYMARKET_API_KEY': api_key,
            })
        
        logger.info("PolymarketClient initialized")
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """
        Generate HMAC signature for API authentication.
        
        Args:
            timestamp: Unix timestamp string
            method: HTTP method
            path: API path
            body: Request body string
            
        Returns:
            HMAC signature string
        """
        if not self.api_secret:
            raise PolymarketAuthError("API secret required for signed requests")
        
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """
        Get authentication headers for request.
        
        Args:
            method: HTTP method
            path: API path
            body: Request body string
            
        Returns:
            Dictionary of headers
        """
        timestamp = str(int(time.time()))
        headers = {
            'POLYMARKET_TIMESTAMP': timestamp,
        }
        
        if self.api_secret:
            headers['POLYMARKET_SIGNATURE'] = self._generate_signature(
                timestamp, method, path, body
            )
        
        return headers
    
    def _handle_error(self, response: requests.Response) -> None:
        """
        Handle API error responses.
        
        Args:
            response: Response object
            
        Raises:
            PolymarketAPIError: Appropriate exception for error type
        """
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            error_data = {"message": response.text}
        
        message = error_data.get('message', error_data.get('error', 'Unknown error'))
        
        if response.status_code == 401:
            raise PolymarketAuthError(
                f"Authentication failed: {message}",
                status_code=response.status_code,
                response=error_data
            )
        elif response.status_code == 429:
            raise PolymarketRateLimitError(
                f"Rate limit exceeded: {message}",
                status_code=response.status_code,
                response=error_data
            )
        elif response.status_code == 400:
            raise PolymarketValidationError(
                f"Validation error: {message}",
                status_code=response.status_code,
                response=error_data
            )
        else:
            raise PolymarketAPIError(
                f"API error ({response.status_code}): {message}",
                status_code=response.status_code,
                response=error_data
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.RequestException,
            PolymarketRateLimitError,
        )),
        before_sleep=before_sleep_log(logger, logger.level),
        reraise=True
    )
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        authenticated: bool = True
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            authenticated: Whether to include authentication headers
            
        Returns:
            Response data as dictionary
            
        Raises:
            PolymarketAPIError: If request fails
        """
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data) if data else ""
        
        headers = {}
        if authenticated and self.api_key:
            headers.update(self._get_auth_headers(method, endpoint, body))
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data if data else None,
                headers=headers,
                timeout=30
            )
            
            if response.status_code >= 400:
                self._handle_error(response)
            
            return response.json() if response.content else {}
            
        except (PolymarketAuthError, PolymarketValidationError):
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise PolymarketAPIError(f"Request failed: {e}")
    
    # ==================== Account Methods ====================
    
    def get_balance(self) -> Balance:
        """
        Get USDC balance for the authenticated account.
        
        Returns:
            Balance object with total, locked, and available USDC
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketAPIError: If request fails
            
        Example:
            >>> balance = client.get_balance()
            >>> print(f"Total: ${balance.usdc_balance:.2f}")
            >>> print(f"Available: ${balance.usdc_available:.2f}")
        """
        logger.debug("Fetching account balance")
        
        data = self._request("GET", "/balance", authenticated=True)
        
        balance = Balance(
            usdc_balance=float(data.get('balance', 0)),
            usdc_locked=float(data.get('locked', 0)),
            usdc_available=float(data.get('available', 0))
        )
        
        logger.info(
            f"Balance: Total=${balance.usdc_balance:.2f}, "
            f"Available=${balance.usdc_available:.2f}"
        )
        return balance
    
    def get_positions(self, market_id: Optional[str] = None) -> List[Position]:
        """
        Get open positions for the authenticated account.
        
        Args:
            market_id: Optional market ID to filter positions
            
        Returns:
            List of Position objects
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketAPIError: If request fails
            
        Example:
            >>> positions = client.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos.outcome}: {pos.size} @ ${pos.average_price:.3f}")
        """
        logger.debug("Fetching open positions")
        
        params = {}
        if market_id:
            params['marketId'] = market_id
        
        data = self._request("GET", "/positions", params=params, authenticated=True)
        
        positions = []
        for pos_data in data.get('positions', []):
            position = Position(
                market_id=pos_data.get('marketId', ''),
                token_id=pos_data.get('tokenId', ''),
                asset_id=pos_data.get('assetId', ''),
                outcome=pos_data.get('outcome', ''),
                size=float(pos_data.get('size', 0)),
                average_price=float(pos_data.get('avgPrice', 0)),
                current_price=float(pos_data.get('currentPrice', 0)),
                unrealized_pnl=float(pos_data.get('unrealizedPnl', 0)),
                realized_pnl=float(pos_data.get('realizedPnl', 0))
            )
            positions.append(position)
        
        logger.info(f"Found {len(positions)} open positions")
        return positions
    
    def get_orders(
        self,
        market_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Order]:
        """
        Get orders for the authenticated account.
        
        Args:
            market_id: Optional market ID to filter orders
            status: Optional status filter (open, filled, cancelled, etc.)
            limit: Maximum number of orders to return
            
        Returns:
            List of Order objects
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketAPIError: If request fails
            
        Example:
            >>> orders = client.get_orders(status="open")
            >>> for order in orders:
            ...     print(f"{order.side.upper()} {order.size} @ ${order.price:.3f}")
        """
        logger.debug("Fetching orders")
        
        params = {'limit': limit}
        if market_id:
            params['marketId'] = market_id
        if status:
            params['status'] = status
        
        data = self._request("GET", "/orders", params=params, authenticated=True)
        
        orders = []
        for order_data in data.get('orders', []):
            order = Order(
                id=order_data.get('id', ''),
                market_id=order_data.get('marketId', ''),
                token_id=order_data.get('tokenId', ''),
                side=order_data.get('side', ''),
                price=float(order_data.get('price', 0)),
                size=float(order_data.get('size', 0)),
                size_matched=float(order_data.get('sizeMatched', 0)),
                status=order_data.get('status', ''),
                created_at=order_data.get('createdAt', ''),
                updated_at=order_data.get('updatedAt'),
                client_order_id=order_data.get('clientOrderId')
            )
            orders.append(order)
        
        logger.info(f"Found {len(orders)} orders")
        return orders
    
    # ==================== Trading Methods ====================
    
    def place_order(
        self,
        market_id: str,
        side: Union[str, OrderSide],
        size: float,
        price: float,
        token_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Place a limit order on a market.
        
        Args:
            market_id: Market ID (condition ID)
            side: Order side ('buy' or 'sell')
            size: Order size (number of shares)
            price: Limit price (0.001 to 0.999)
            token_id: Optional token ID (auto-fetched if not provided)
            client_order_id: Optional client order ID for tracking
            
        Returns:
            Order object with assigned ID and status
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketValidationError: If order parameters invalid
            PolymarketAPIError: If request fails
            
        Example:
            >>> order = client.place_order(
            ...     market_id="0x123...",
            ...     side="buy",
            ...     size=100,
            ...     price=0.65
            ... )
            >>> print(f"Order placed: {order.id}")
        """
        if isinstance(side, OrderSide):
            side = side.value
        
        side = side.lower()
        if side not in ('buy', 'sell'):
            raise PolymarketValidationError(f"Invalid side: {side}. Use 'buy' or 'sell'")
        
        # Validate price range
        if not 0.001 <= price <= 0.999:
            raise PolymarketValidationError(
                f"Price must be between 0.001 and 0.999, got {price}"
            )
        
        # Validate size
        if size <= 0:
            raise PolymarketValidationError(f"Size must be positive, got {size}")
        
        # Get token ID if not provided
        if not token_id:
            market = self.get_market(market_id)
            outcomes = market.get('outcomes', [])
            if outcomes:
                # Default to first outcome for buys, adjust logic as needed
                token_id = outcomes[0].get('tokenId')
        
        order_data = {
            "marketId": market_id,
            "side": side,
            "size": str(size),
            "price": str(price),
        }
        
        if token_id:
            order_data["tokenId"] = token_id
        if client_order_id:
            order_data["clientOrderId"] = client_order_id
        
        logger.info(
            f"Placing {side.upper()} order: {size} shares @ ${price:.3f} "
            f"(Market: {market_id[:20]}...)"
        )
        
        response = self._request("POST", "/orders", data=order_data, authenticated=True)
        
        order = Order(
            id=response.get('id', ''),
            market_id=market_id,
            token_id=token_id or '',
            side=side,
            price=price,
            size=size,
            size_matched=0,
            status=response.get('status', 'open'),
            created_at=response.get('createdAt', ''),
            client_order_id=client_order_id
        )
        
        logger.info(f"Order placed successfully: {order.id}")
        return order
    
    def place_market_order(
        self,
        market_id: str,
        side: Union[str, OrderSide],
        size: float,
        token_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """
        Place a market order (executes immediately at best available price).
        
        Note: Market orders are executed as limit orders at aggressive prices
        (0.999 for buys, 0.001 for sells) to ensure immediate execution.
        
        Args:
            market_id: Market ID (condition ID)
            side: Order side ('buy' or 'sell')
            size: Order size (number of shares)
            token_id: Optional token ID
            client_order_id: Optional client order ID
            
        Returns:
            Order object with assigned ID and status
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketValidationError: If order parameters invalid
            PolymarketAPIError: If request fails
            
        Example:
            >>> order = client.place_market_order(
            ...     market_id="0x123...",
            ...     side="buy",
            ...     size=100
            ... )
        """
        if isinstance(side, OrderSide):
            side = side.value
        
        side = side.lower()
        
        # Use aggressive limit prices for market execution
        if side == 'buy':
            price = 0.999  # Will match with lowest ask
        else:
            price = 0.001  # Will match with highest bid
        
        logger.info(f"Placing MARKET {side.upper()} order: {size} shares")
        
        return self.place_order(
            market_id=market_id,
            side=side,
            size=size,
            price=price,
            token_id=token_id,
            client_order_id=client_order_id
        )
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancellation was successful
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketAPIError: If request fails
            
        Example:
            >>> success = client.cancel_order("0xabc...")
            >>> print("Order cancelled" if success else "Failed to cancel")
        """
        logger.info(f"Cancelling order: {order_id}")
        
        self._request("DELETE", f"/orders/{order_id}", authenticated=True)
        
        logger.info(f"Order cancelled: {order_id}")
        return True
    
    def cancel_all_orders(self, market_id: Optional[str] = None) -> int:
        """
        Cancel all open orders, optionally filtered by market.
        
        Args:
            market_id: Optional market ID to filter orders
            
        Returns:
            Number of orders cancelled
            
        Raises:
            PolymarketAuthError: If not authenticated
            PolymarketAPIError: If request fails
        """
        logger.info(f"Cancelling all orders" + (f" for market {market_id}" if market_id else ""))
        
        params = {}
        if market_id:
            params['marketId'] = market_id
        
        data = self._request("DELETE", "/orders", params=params, authenticated=True)
        
        count = data.get('cancelled', 0)
        logger.info(f"Cancelled {count} orders")
        return count
    
    def get_market_price(self, market_id: str, side: str = "buy") -> float:
        """
        Get current market price (best bid or ask).
        
        Args:
            market_id: Market ID
            side: 'buy' for ask price, 'sell' for bid price
            
        Returns:
            Current market price
            
        Raises:
            PolymarketAPIError: If request fails
            
        Example:
            >>> best_bid = client.get_market_price("0x123...", side="sell")
            >>> best_ask = client.get_market_price("0x123...", side="buy")
            >>> spread = best_ask - best_bid
        """
        orderbook = self.get_orderbook(market_id)
        
        if side.lower() == 'buy':
            # Return best ask (lowest sell price)
            asks = orderbook.get('asks', [])
            if asks:
                return float(asks[0]['price'])
        else:
            # Return best bid (highest buy price)
            bids = orderbook.get('bids', [])
            if bids:
                return float(bids[0]['price'])
        
        return 0.0
    
    # ==================== Market Data Methods ====================
    
    def get_market(self, market_id: str) -> Dict[str, Any]:
        """
        Get detailed market information.
        
        Args:
            market_id: Market ID (condition ID)
            
        Returns:
            Market data dictionary
            
        Raises:
            PolymarketAPIError: If request fails
            
        Example:
            >>> market = client.get_market("0x123...")
            >>> print(f"Question: {market['question']}")
            >>> print(f"Volume: ${market['volume']:.2f}")
        """
        logger.debug(f"Fetching market: {market_id}")
        
        data = self._request("GET", f"/markets/{market_id}", authenticated=False)
        
        logger.debug(f"Market loaded: {data.get('question', 'Unknown')}")
        return data
    
    def get_orderbook(self, market_id: str, token_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get order book for a market.
        
        Args:
            market_id: Market ID
            token_id: Optional token ID (specific outcome)
            
        Returns:
            Order book data with 'bids' and 'asks' lists
            
        Raises:
            PolymarketAPIError: If request fails
            
        Example:
            >>> book = client.get_orderbook("0x123...")
            >>> best_bid = book['bids'][0] if book['bids'] else None
            >>> best_ask = book['asks'][0] if book['asks'] else None
        """
        logger.debug(f"Fetching orderbook for market: {market_id}")
        
        params = {'marketId': market_id}
        if token_id:
            params['tokenId'] = token_id
        
        data = self._request("GET", "/orderbook", params=params, authenticated=False)
        
        logger.debug(
            f"Orderbook loaded: {len(data.get('bids', []))} bids, "
            f"{len(data.get('asks', []))} asks"
        )
        return data
    
    def get_markets(
        self,
        active: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of markets.
        
        Args:
            active: Only return active markets
            limit: Maximum number of markets
            offset: Pagination offset
            
        Returns:
            List of market data dictionaries
            
        Raises:
            PolymarketAPIError: If request fails
        """
        logger.debug(f"Fetching markets (active={active}, limit={limit})")
        
        params = {
            'active': active,
            'limit': limit,
            'offset': offset,
        }
        
        data = self._request("GET", "/markets", params=params, authenticated=False)
        
        markets = data.get('markets', [])
        logger.info(f"Loaded {len(markets)} markets")
        return markets
    
    def get_trades(
        self,
        market_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades.
        
        Args:
            market_id: Optional market ID to filter
            limit: Maximum number of trades
            
        Returns:
            List of trade data dictionaries
            
        Raises:
            PolymarketAPIError: If request fails
        """
        params = {'limit': limit}
        if market_id:
            params['marketId'] = market_id
        
        data = self._request("GET", "/trades", params=params, authenticated=False)
        return data.get('trades', [])
    
    # ==================== Utility Methods ====================
    
    def estimate_order_cost(self, side: str, size: float, price: float) -> float:
        """
        Estimate the cost of an order including fees.
        
        Polymarket charges a 2% fee on the order size (notional value).
        
        Args:
            side: Order side ('buy' or 'sell')
            size: Number of shares
            price: Price per share
            
        Returns:
            Estimated total cost (including fees)
            
        Example:
            >>> cost = client.estimate_order_cost("buy", 100, 0.65)
            >>> print(f"Estimated cost: ${cost:.2f}")
        """
        notional = size * price
        fee = notional * 0.02  # 2% fee
        
        if side.lower() == 'buy':
            return notional + fee
        else:
            return notional - fee
    
    def calculate_profit(
        self,
        entry_price: float,
        exit_price: float,
        size: float,
        side: str = "buy"
    ) -> Dict[str, float]:
        """
        Calculate potential profit/loss for a trade.
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
            side: Position side ('buy' for long, 'sell' for short)
            
        Returns:
            Dictionary with profit metrics
            
        Example:
            >>> pnl = client.calculate_profit(0.65, 0.75, 100, "buy")
            >>> print(f"Profit: ${pnl['profit']:.2f} ({pnl['return_pct']:.1%})")
        """
        if side.lower() == 'buy':
            price_diff = exit_price - entry_price
        else:
            price_diff = entry_price - exit_price
        
        gross_profit = price_diff * size
        
        # Calculate fees (2% on entry and exit)
        entry_notional = entry_price * size
        exit_notional = exit_price * size
        total_fees = (entry_notional + exit_notional) * 0.02
        
        net_profit = gross_profit - total_fees
        
        # Calculate return percentage
        invested = entry_price * size
        return_pct = net_profit / invested if invested > 0 else 0
        
        return {
            'gross_profit': gross_profit,
            'total_fees': total_fees,
            'net_profit': net_profit,
            'return_pct': return_pct,
            'entry_cost': entry_notional * 1.02,  # Including fee
            'exit_value': exit_notional * 0.98,   # After fee
        }
    
    def is_authenticated(self) -> bool:
        """
        Check if client has valid authentication credentials.
        
        Returns:
            True if authenticated, False otherwise
        """
        return bool(self.api_key and self.api_secret)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session."""
        self.session.close()


# ==================== Convenience Functions ====================

def create_client_from_env() -> PolymarketClient:
    """
    Create a PolymarketClient from environment variables.
    
    Required environment variables:
    - POLYMARKET_API_KEY: Your API key
    - POLYMARKET_API_SECRET: Your API secret
    
    Optional:
    - POLYMARKET_PRIVATE_KEY: For blockchain transactions
    
    Returns:
        Configured PolymarketClient instance
        
    Raises:
        ValueError: If required environment variables are missing
        
    Example:
        >>> from polymarket_tracker.exchange.polymarket_client import create_client_from_env
        >>> client = create_client_from_env()
        >>> print(client.get_balance())
    """
    import os
    
    api_key = os.getenv('POLYMARKET_API_KEY')
    api_secret = os.getenv('POLYMARKET_API_SECRET')
    private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
    
    if not api_key or not api_secret:
        raise ValueError(
            "POLYMARKET_API_KEY and POLYMARKET_API_SECRET environment variables required"
        )
    
    return PolymarketClient(
        api_key=api_key,
        api_secret=api_secret,
        private_key=private_key
    )
