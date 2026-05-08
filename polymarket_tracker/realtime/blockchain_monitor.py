"""
Blockchain Event Monitor for Polygon
Monitors Polymarket transactions on the blockchain BEFORE they confirm.

This module provides real-time monitoring of:
- Pending transactions in the mempool
- OrderFilled events from Polymarket Exchange
- PositionSplit/Merge/Redemption events from CTF
- Whale address activity detection

Usage:
    monitor = BlockchainMonitor()
    await monitor.start()
    
    # Subscribe to events
    monitor.on_blockchain_event = handle_event
    monitor.on_pending_tx = handle_pending
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import urlparse
import warnings

# Third-party imports
try:
    from web3 import Web3, AsyncWeb3
    from web3.datastructures import AttributeDict
    from web3.exceptions import TransactionNotFound, Web3Exception
    from web3.types import TxData, TxReceipt, Wei
    from eth_abi import decode
    from eth_utils import decode_hex, encode_hex, event_signature_to_log_topic, to_checksum_address
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    warnings.warn("web3.py not installed. Blockchain monitoring unavailable.")

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS - Polymarket Contract Addresses
# ============================================================================

class PolymarketContracts:
    """Polymarket contract addresses on Polygon Mainnet."""
    
    # Polymarket Exchange (OrderFilled events)
    EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
    
    # Conditional Tokens Framework
    CTF = "0x4D97DCd97eC939f037Cb11d2054073fD5bdE3C72"
    
    # Neg Risk Exchange (for binary markets)
    NEG_RISK_EXCHANGE = "0xd91E80cF2E7be2e162C6513ceD06f1dD0dA35296"
    
    # USDC on Polygon
    USDC = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    # Wrapped Matic
    WMATIC = "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"


# ============================================================================
# DATA CLASSES
# ============================================================================

class EventType(Enum):
    """Types of blockchain events to monitor."""
    ORDER_FILLED = "order_filled"
    POSITION_SPLIT = "position_split"
    POSITION_MERGE = "position_merge"
    REDEMPTION = "redemption"
    PENDING_TRANSACTION = "pending_transaction"
    BLOCK_MINED = "block_mined"
    WHALE_DETECTED = "whale_detected"
    ARBITRAGE_OPPORTUNITY = "arbitrage_opportunity"


@dataclass
class BlockchainEvent:
    """
    Represents a blockchain event.
    
    Attributes:
        tx_hash: Transaction hash
        block_number: Block number (None for pending)
        event_type: Type of event
        data: Event-specific data dictionary
        timestamp: Detection timestamp
        confirmations: Number of confirmations (0 for pending)
        gas_price: Gas price in gwei
        gas_used: Gas used (None until confirmed)
    """
    tx_hash: str
    block_number: Optional[int]
    event_type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confirmations: int = 0
    gas_price: Optional[float] = None
    gas_used: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "confirmations": self.confirmations,
            "gas_price": self.gas_price,
            "gas_used": self.gas_used
        }


@dataclass
class PendingTransaction:
    """
    Represents a transaction in the mempool (pre-confirmation).
    
    Attributes:
        tx_hash: Transaction hash
        from_address: Sender address
        to_address: Contract/interaction address
        input_data: Transaction input data
        gas_price: Gas price in wei
        gas_limit: Gas limit
        value: ETH/MATIC value transferred
        detected_at: Detection timestamp
        nonce: Transaction nonce
    """
    tx_hash: str
    from_address: str
    to_address: Optional[str]
    input_data: str
    gas_price: int
    gas_limit: int
    value: int
    detected_at: datetime = field(default_factory=datetime.utcnow)
    nonce: Optional[int] = None
    
    @property
    def gas_price_gwei(self) -> float:
        """Gas price in gwei."""
        return self.gas_price / 1e9
    
    @property
    def age_seconds(self) -> float:
        """Age in seconds since detection."""
        return (datetime.utcnow() - self.detected_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tx_hash": self.tx_hash,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "input_data": self.input_data[:100] + "..." if len(self.input_data) > 100 else self.input_data,
            "gas_price_wei": self.gas_price,
            "gas_price_gwei": self.gas_price_gwei,
            "gas_limit": self.gas_limit,
            "value": self.value,
            "nonce": self.nonce,
            "detected_at": self.detected_at.isoformat(),
            "age_seconds": self.age_seconds
        }


@dataclass
class MempoolStats:
    """
    Statistics about the current mempool state.
    
    Attributes:
        pending_count: Number of pending transactions
        avg_gas_price: Average gas price in gwei
        median_gas_price: Median gas price in gwei
        congestion_level: Low, Medium, High, or Extreme
        timestamp: Stats collection time
    """
    pending_count: int
    avg_gas_price: float
    median_gas_price: float
    congestion_level: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_pending_txs(cls, txs: List[PendingTransaction]) -> "MempoolStats":
        """Calculate stats from pending transactions."""
        if not txs:
            return cls(0, 0, 0, "unknown")
        
        gas_prices = [tx.gas_price_gwei for tx in txs]
        avg_gas = sum(gas_prices) / len(gas_prices)
        median_gas = sorted(gas_prices)[len(gas_prices) // 2]
        
        # Determine congestion level
        if avg_gas < 50:
            level = "low"
        elif avg_gas < 100:
            level = "medium"
        elif avg_gas < 200:
            level = "high"
        else:
            level = "extreme"
        
        return cls(
            pending_count=len(txs),
            avg_gas_price=round(avg_gas, 2),
            median_gas_price=round(median_gas, 2),
            congestion_level=level
        )


@dataclass
class OrderFilledData:
    """Data from an OrderFilled event."""
    maker: str
    taker: str
    order_hash: str
    market_id: str
    outcome_index: int
    side: str  # "buy" or "sell"
    amount: Decimal
    price: Decimal
    filled_amount: Decimal
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "maker": self.maker,
            "taker": self.taker,
            "order_hash": self.order_hash,
            "market_id": self.market_id,
            "outcome_index": self.outcome_index,
            "side": self.side,
            "amount": str(self.amount),
            "price": str(self.price),
            "filled_amount": str(self.filled_amount),
            "timestamp": self.timestamp.isoformat()
        }


# ============================================================================
# CONTRACT ABIs
# ============================================================================

# Minimal ABI for Polymarket Exchange (OrderFilled event)
POLYMARKET_EXCHANGE_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": True, "name": "taker", "type": "address"},
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": False, "name": "market", "type": "address"},
            {"indexed": False, "name": "outcomeIndex", "type": "uint256"},
            {"indexed": False, "name": "side", "type": "uint8"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "price", "type": "uint256"},
            {"indexed": False, "name": "filledAmount", "type": "uint256"}
        ],
        "name": "OrderFilled",
        "type": "event"
    }
]

# Conditional Tokens Framework ABI
CTF_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "stakeholder", "type": "address"},
            {"indexed": True, "name": "collateralToken", "type": "address"},
            {"indexed": True, "name": "parentCollectionId", "type": "bytes32"},
            {"indexed": False, "name": "conditionId", "type": "bytes32"},
            {"indexed": False, "name": "partition", "type": "uint256[]"},
            {"indexed": False, "name": "amount", "type": "uint256"}
        ],
        "name": "PositionSplit",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "stakeholder", "type": "address"},
            {"indexed": True, "name": "collateralToken", "type": "address"},
            {"indexed": True, "name": "parentCollectionId", "type": "bytes32"},
            {"indexed": False, "name": "conditionId", "type": "bytes32"},
            {"indexed": False, "name": "partition", "type": "uint256[]"},
            {"indexed": False, "name": "amount", "type": "uint256"}
        ],
        "name": "PositionMerge",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "redeemer", "type": "address"},
            {"indexed": True, "name": "collateralToken", "type": "address"},
            {"indexed": True, "name": "parentCollectionId", "type": "bytes32"},
            {"indexed": False, "name": "conditionId", "type": "bytes32"},
            {"indexed": False, "name": "indexSets", "type": "uint256[]"},
            {"indexed": False, "name": "payout", "type": "uint256"}
        ],
        "name": "Redemption",
        "type": "event"
    }
]

# ERC20 ABI for token transfers
ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]

# Event signatures for log topic filtering
try:
    ORDER_FILLED_TOPIC = event_signature_to_log_topic("OrderFilled(address,address,bytes32,address,uint256,uint8,uint256,uint256,uint256)")
    POSITION_SPLIT_TOPIC = event_signature_to_log_topic("PositionSplit(address,address,bytes32,bytes32,uint256[],uint256)")
    POSITION_MERGE_TOPIC = event_signature_to_log_topic("PositionMerge(address,address,bytes32,bytes32,uint256[],uint256)")
    REDEMPTION_TOPIC = event_signature_to_log_topic("Redemption(address,address,bytes32,bytes32,uint256[],uint256)")
except NameError:
    # web3 not available, topics will be None
    ORDER_FILLED_TOPIC = None
    POSITION_SPLIT_TOPIC = None
    POSITION_MERGE_TOPIC = None
    REDEMPTION_TOPIC = None


# ============================================================================
# MAIN MONITOR CLASS
# ============================================================================

class BlockchainMonitor:
    """
    Real-time blockchain monitor for Polymarket transactions.
    
    Monitors the Polygon blockchain for:
    - Pending transactions in mempool (pre-confirmation)
    - OrderFilled events from Polymarket Exchange
    - Position management events from CTF
    - Whale address activity
    
    Example:
        monitor = BlockchainMonitor(
            providers=["wss://polygon-mainnet.g.alchemy.com/v2/KEY"],
            whale_addresses=["0x..."],
            min_whale_usd=10000
        )
        
        # Set up event handlers
        monitor.on_blockchain_event = lambda e: print(f"Event: {e}")
        monitor.on_pending_tx = lambda tx: print(f"Pending: {tx.tx_hash}")
        
        # Start monitoring
        await monitor.start()
    """
    
    def __init__(
        self,
        providers: Optional[List[str]] = None,
        whale_addresses: Optional[Set[str]] = None,
        min_whale_usd: float = 5000.0,
        mempool_enabled: bool = True,
        poll_interval: float = 0.5,
        max_pending_cache: int = 10000,
        health_check_interval: float = 30.0
    ):
        """
        Initialize the blockchain monitor.
        
        Args:
            providers: List of WebSocket/HTTP provider URLs
            whale_addresses: Set of addresses to track as whales
            min_whale_usd: Minimum USD value to consider a whale transaction
            mempool_enabled: Whether to monitor pending transactions
            poll_interval: Seconds between mempool polls
            max_pending_cache: Maximum pending transactions to cache
            health_check_interval: Seconds between connection health checks
        """
        if not WEB3_AVAILABLE:
            raise RuntimeError("web3.py is required. Install with: pip install web3")
        
        # Provider configuration
        self.providers = providers or self._get_default_providers()
        self.current_provider_index = 0
        self.w3: Optional[Web3] = None
        self.async_w3: Optional[AsyncWeb3] = None
        
        # Whale tracking
        self.whale_addresses = set(whale_addresses or [])
        self.min_whale_usd = min_whale_usd
        self.known_whale_patterns: Dict[str, Dict] = {}
        
        # Mempool monitoring
        self.mempool_enabled = mempool_enabled
        self.poll_interval = poll_interval
        self.max_pending_cache = max_pending_cache
        self.pending_transactions: Dict[str, PendingTransaction] = {}
        self.mempool_stats: MempoolStats = MempoolStats(0, 0, 0, "unknown")
        
        # Connection health
        self.health_check_interval = health_check_interval
        self.last_block_time: Optional[datetime] = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        
        # Event handlers (callbacks)
        self.on_blockchain_event: Optional[Callable[[BlockchainEvent], None]] = None
        self.on_pending_tx: Optional[Callable[[PendingTransaction], None]] = None
        self.on_mempool_stats: Optional[Callable[[MempoolStats], None]] = None
        self.on_connection_error: Optional[Callable[[Exception], None]] = None
        
        # Internal state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        self._event_filters: List = []
        
        # Contract instances (initialized on connect)
        self.exchange_contract = None
        self.ctf_contract = None
        
        logger.info(f"BlockchainMonitor initialized with {len(self.providers)} providers")
    
    def _get_default_providers(self) -> List[str]:
        """Get default providers from environment or use public endpoints."""
        import os
        
        providers = []
        
        # Check for Alchemy
        alchemy_key = os.getenv("ALCHEMY_API_KEY") or os.getenv("POLYGON_ALCHEMY_KEY")
        if alchemy_key:
            providers.append(f"wss://polygon-mainnet.g.alchemy.com/v2/{alchemy_key}")
        
        # Check for Infura
        infura_key = os.getenv("INFURA_API_KEY") or os.getenv("INFURA_PROJECT_ID")
        if infura_key:
            providers.append(f"wss://polygon-mainnet.infura.io/ws/v3/{infura_key}")
        
        # Check for QuickNode
        quicknode_url = os.getenv("QUICKNODE_POLYGON_URL")
        if quicknode_url:
            providers.append(quicknode_url)
        
        # Fallback to public RPC (less reliable)
        if not providers:
            providers.append("https://polygon-rpc.com")
            logger.warning("No API keys found. Using public RPC (limited functionality).")
        
        return providers
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    async def connect(self) -> bool:
        """
        Establish connection to Polygon network.
        
        Returns:
            True if connected successfully
        """
        for i, provider_url in enumerate(self.providers):
            try:
                logger.info(f"Connecting to provider {i+1}/{len(self.providers)}: {self._mask_url(provider_url)}")
                
                if provider_url.startswith("wss://"):
                    # WebSocket connection
                    self.async_w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(provider_url))
                    # Note: For true WebSocket, use AsyncWeb3 with WebSocketProvider
                    # For now, we use HTTP polling as fallback
                else:
                    # HTTP connection
                    self.async_w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(provider_url))
                
                # Test connection
                connected = await self.async_w3.is_connected()
                if connected:
                    # Get sync Web3 for event filtering
                    self.w3 = Web3(Web3.HTTPProvider(provider_url.replace("wss://", "https://").replace("ws://", "http://")))
                    
                    block_number = await self.async_w3.eth.block_number
                    logger.info(f"Connected to Polygon at block {block_number}")
                    
                    self.is_connected = True
                    self.current_provider_index = i
                    self.reconnect_attempts = 0
                    self.last_block_time = datetime.utcnow()
                    
                    # Initialize contracts
                    await self._initialize_contracts()
                    
                    return True
                else:
                    logger.warning(f"Provider {i+1} connected but not responding")
                    
            except Exception as e:
                logger.error(f"Failed to connect to provider {i+1}: {e}")
                continue
        
        logger.error("All providers failed")
        return False
    
    async def _initialize_contracts(self):
        """Initialize contract instances."""
        if not self.w3:
            return
        
        try:
            self.exchange_contract = self.w3.eth.contract(
                address=to_checksum_address(PolymarketContracts.EXCHANGE),
                abi=POLYMARKET_EXCHANGE_ABI
            )
            
            self.ctf_contract = self.w3.eth.contract(
                address=to_checksum_address(PolymarketContracts.CTF),
                abi=CTF_ABI
            )
            
            logger.info("Contract instances initialized")
        except Exception as e:
            logger.error(f"Failed to initialize contracts: {e}")
    
    async def disconnect(self):
        """Disconnect from the network."""
        self.is_connected = False
        
        # Cancel all running tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks = []
        logger.info("Disconnected from network")
    
    async def _health_check_loop(self):
        """Periodic health check and reconnection."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                if not self.is_connected or not self.async_w3:
                    logger.warning("Connection lost, attempting reconnection...")
                    await self._reconnect()
                    continue
                
                # Test connection
                try:
                    block_number = await asyncio.wait_for(
                        self.async_w3.eth.block_number,
                        timeout=10.0
                    )
                    self.last_block_time = datetime.utcnow()
                    logger.debug(f"Health check passed, block: {block_number}")
                except asyncio.TimeoutError:
                    logger.warning("Health check timeout")
                    await self._reconnect()
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                if self.on_connection_error:
                    self.on_connection_error(e)
    
    async def _reconnect(self):
        """Attempt to reconnect to a provider."""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            await self.stop()
            return
        
        # Try next provider
        self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
        
        # Exponential backoff
        delay = min(2 ** self.reconnect_attempts, 60)
        logger.info(f"Reconnection attempt {self.reconnect_attempts}, waiting {delay}s...")
        await asyncio.sleep(delay)
        
        connected = await self.connect()
        if connected:
            logger.info("Reconnection successful")
        else:
            logger.error("Reconnection failed")
    
    def _mask_url(self, url: str) -> str:
        """Mask API key in URL for logging."""
        try:
            parsed = urlparse(url)
            if parsed.path and len(parsed.path) > 20:
                # Mask the API key portion
                path_parts = parsed.path.split("/")
                if len(path_parts) > 2:
                    key = path_parts[-1]
                    if len(key) > 8:
                        masked_key = key[:4] + "..." + key[-4:]
                        path_parts[-1] = masked_key
                        masked_path = "/".join(path_parts)
                        return f"{parsed.scheme}://{parsed.netloc}{masked_path}"
            return url[:30] + "..."
        except:
            return "***masked***"
    
    # ========================================================================
    # MAIN MONITORING LOOPS
    # ========================================================================
    
    async def start(self):
        """Start all monitoring tasks."""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        
        # Connect first
        if not await self.connect():
            raise RuntimeError("Failed to connect to any provider")
        
        # Start monitoring tasks
        tasks = [
            self._health_check_loop(),
            self._block_listener(),
            self._event_listener(),
        ]
        
        if self.mempool_enabled:
            tasks.append(self._mempool_monitor())
            tasks.append(self._pending_cleanup_loop())
        
        # Run all tasks concurrently
        self._tasks = [asyncio.create_task(t) for t in tasks]
        
        logger.info("Blockchain monitor started")
    
    async def stop(self):
        """Stop all monitoring."""
        self._running = False
        await self.disconnect()
        logger.info("Blockchain monitor stopped")
    
    async def _block_listener(self):
        """Listen for new blocks."""
        last_block = 0
        
        while self._running:
            try:
                if not self.async_w3:
                    await asyncio.sleep(1)
                    continue
                
                current_block = await self.async_w3.eth.block_number
                
                if current_block > last_block:
                    logger.debug(f"New block: {current_block}")
                    last_block = current_block
                    
                    # Emit block event
                    event = BlockchainEvent(
                        tx_hash="",
                        block_number=current_block,
                        event_type=EventType.BLOCK_MINED,
                        data={"block_number": current_block}
                    )
                    await self._emit_event(event)
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Block listener error: {e}")
                await asyncio.sleep(1)
    
    async def _event_listener(self):
        """Listen for contract events."""
        # Get current block to start from
        start_block = await self.async_w3.eth.block_number if self.async_w3 else 0
        
        while self._running:
            try:
                if not self.w3 or not self.exchange_contract:
                    await asyncio.sleep(1)
                    continue
                
                current_block = self.w3.eth.block_number
                
                if current_block > start_block:
                    # Check for OrderFilled events
                    await self._check_order_filled_events(start_block, current_block)
                    
                    # Check for CTF events
                    await self._check_ctf_events(start_block, current_block)
                    
                    start_block = current_block + 1
                
                await asyncio.sleep(self.poll_interval * 2)
                
            except Exception as e:
                logger.error(f"Event listener error: {e}")
                await asyncio.sleep(1)
    
    async def _check_order_filled_events(self, from_block: int, to_block: int):
        """Check for OrderFilled events in block range."""
        try:
            # Create event filter for OrderFilled
            event_filter = self.exchange_contract.events.OrderFilled().create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            entries = event_filter.get_all_entries()
            
            for entry in entries:
                await self._process_order_filled(entry)
                
        except Exception as e:
            logger.error(f"Error checking OrderFilled events: {e}")
    
    async def _check_ctf_events(self, from_block: int, to_block: int):
        """Check for CTF events in block range."""
        try:
            # PositionSplit events
            split_filter = self.ctf_contract.events.PositionSplit().create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for entry in split_filter.get_all_entries():
                await self._process_position_split(entry)
            
            # PositionMerge events
            merge_filter = self.ctf_contract.events.PositionMerge().create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for entry in merge_filter.get_all_entries():
                await self._process_position_merge(entry)
            
            # Redemption events
            redemption_filter = self.ctf_contract.events.Redemption().create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            
            for entry in redemption_filter.get_all_entries():
                await self._process_redemption(entry)
                
        except Exception as e:
            logger.error(f"Error checking CTF events: {e}")
    
    # ========================================================================
    # MEMPOOL MONITORING
    # ========================================================================
    
    async def _mempool_monitor(self):
        """Monitor pending transactions in mempool."""
        logger.info("Starting mempool monitor")
        
        # Track seen transactions to avoid duplicates
        seen_txs: Set[str] = set()
        
        while self._running:
            try:
                if not self.async_w3:
                    await asyncio.sleep(1)
                    continue
                
                # Get pending transactions (this is provider-dependent)
                # Note: Not all providers support pending transaction filters
                pending_filter = await self.async_w3.eth.filter("pending")
                pending_hashes = await pending_filter.get_new_entries()
                
                for tx_hash in pending_hashes:
                    tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, 'hex') else str(tx_hash)
                    
                    if tx_hash_hex in seen_txs:
                        continue
                    
                    seen_txs.add(tx_hash_hex)
                    
                    # Limit seen cache
                    if len(seen_txs) > self.max_pending_cache:
                        seen_txs = set(list(seen_txs)[-self.max_pending_cache//2:])
                    
                    # Get transaction details
                    try:
                        tx = await self.async_w3.eth.get_transaction(tx_hash)
                        await self._process_pending_transaction(tx)
                    except TransactionNotFound:
                        # Transaction may have been dropped or already mined
                        pass
                    except Exception as e:
                        logger.debug(f"Error fetching pending tx {tx_hash_hex}: {e}")
                
                # Update mempool stats periodically
                await self._update_mempool_stats()
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Mempool monitor error: {e}")
                await asyncio.sleep(1)
    
    async def _process_pending_transaction(self, tx: TxData):
        """Process a pending transaction."""
        try:
            tx_hash = tx.get('hash', b'').hex() if hasattr(tx.get('hash'), 'hex') else str(tx.get('hash'))
            to_address = tx.get('to')
            from_address = tx.get('from')
            
            if not to_address or not from_address:
                return
            
            to_address = to_address.lower()
            from_address = from_address.lower()
            
            # Check if transaction is to Polymarket contracts
            is_polymarket_tx = to_address in [
                PolymarketContracts.EXCHANGE.lower(),
                PolymarketContracts.CTF.lower(),
                PolymarketContracts.NEG_RISK_EXCHANGE.lower()
            ]
            
            # Check if from whale address
            is_whale_tx = from_address in {a.lower() for a in self.whale_addresses}
            
            if not is_polymarket_tx and not is_whale_tx:
                return
            
            # Create pending transaction object
            pending_tx = PendingTransaction(
                tx_hash=tx_hash,
                from_address=from_address,
                to_address=to_address,
                input_data=tx.get('input', '0x'),
                gas_price=tx.get('gasPrice', 0),
                gas_limit=tx.get('gas', 0),
                value=tx.get('value', 0),
                nonce=tx.get('nonce')
            )
            
            # Store in cache
            async with self._lock:
                self.pending_transactions[tx_hash] = pending_tx
            
            # Call handler
            if self.on_pending_tx:
                try:
                    self.on_pending_tx(pending_tx)
                except Exception as e:
                    logger.error(f"Pending tx handler error: {e}")
            
            # Decode and analyze if Polymarket transaction
            if is_polymarket_tx:
                await self._analyze_polymarket_pending(pending_tx)
            
            # Check for whale pattern
            if is_whale_tx or self.detect_whale_pattern(from_address, pending_tx.input_data):
                await self._handle_whale_pending(pending_tx)
                
        except Exception as e:
            logger.error(f"Error processing pending tx: {e}")
    
    async def _analyze_polymarket_pending(self, pending_tx: PendingTransaction):
        """Analyze a pending Polymarket transaction."""
        try:
            # Decode transaction input
            decoded = self._decode_transaction_input(
                pending_tx.to_address,
                pending_tx.input_data
            )
            
            if decoded:
                logger.info(f"Decoded Polymarket tx {pending_tx.tx_hash}: {decoded.get('function')}")
                
                # Check for large orders
                value_usd = self._estimate_tx_value_usd(decoded)
                
                if value_usd >= self.min_whale_usd:
                    event = BlockchainEvent(
                        tx_hash=pending_tx.tx_hash,
                        block_number=None,
                        event_type=EventType.PENDING_TRANSACTION,
                        data={
                            "pending_tx": pending_tx.to_dict(),
                            "decoded": decoded,
                            "estimated_value_usd": value_usd,
                            "is_whale": True
                        },
                        gas_price=pending_tx.gas_price_gwei
                    )
                    await self._emit_event(event)
                    
        except Exception as e:
            logger.debug(f"Error analyzing pending tx: {e}")
    
    async def _handle_whale_pending(self, pending_tx: PendingTransaction):
        """Handle a pending transaction from a known whale."""
        event = BlockchainEvent(
            tx_hash=pending_tx.tx_hash,
            block_number=None,
            event_type=EventType.WHALE_DETECTED,
            data={
                "pending_tx": pending_tx.to_dict(),
                "whale_address": pending_tx.from_address,
                "detection_type": "mempool"
            },
            gas_price=pending_tx.gas_price_gwei
        )
        await self._emit_event(event)
        logger.info(f"Whale transaction detected: {pending_tx.tx_hash[:20]}...")
    
    async def _update_mempool_stats(self):
        """Update and emit mempool statistics."""
        async with self._lock:
            pending_list = list(self.pending_transactions.values())
        
        if pending_list:
            stats = MempoolStats.from_pending_txs(pending_list)
            self.mempool_stats = stats
            
            if self.on_mempool_stats:
                try:
                    self.on_mempool_stats(stats)
                except Exception as e:
                    logger.error(f"Mempool stats handler error: {e}")
    
    async def _pending_cleanup_loop(self):
        """Clean up old pending transactions."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                async with self._lock:
                    current_time = datetime.utcnow()
                    # Remove transactions older than 10 minutes
                    to_remove = [
                        tx_hash for tx_hash, tx in self.pending_transactions.items()
                        if (current_time - tx.detected_at).total_seconds() > 600
                    ]
                    for tx_hash in to_remove:
                        del self.pending_transactions[tx_hash]
                    
                    if to_remove:
                        logger.debug(f"Cleaned up {len(to_remove)} old pending transactions")
                        
            except Exception as e:
                logger.error(f"Pending cleanup error: {e}")
    
    # ========================================================================
    # EVENT PROCESSING
    # ========================================================================
    
    async def _process_order_filled(self, event: AttributeDict):
        """Process an OrderFilled event."""
        try:
            args = event.args
            
            order_data = OrderFilledData(
                maker=args.maker.lower(),
                taker=args.taker.lower(),
                order_hash=args.orderHash.hex() if hasattr(args.orderHash, 'hex') else str(args.orderHash),
                market_id=args.market.lower(),
                outcome_index=args.outcomeIndex,
                side="buy" if args.side == 0 else "sell",
                amount=Decimal(args.amount) / Decimal(1e6),  # USDC has 6 decimals
                price=Decimal(args.price) / Decimal(1e6),
                filled_amount=Decimal(args.filledAmount) / Decimal(1e6),
                timestamp=datetime.utcnow()
            )
            
            # Check for whale involvement
            is_whale = (
                order_data.maker in self.whale_addresses or
                order_data.taker in self.whale_addresses
            )
            
            # Calculate USD value
            value_usd = float(order_data.amount * order_data.price)
            
            blockchain_event = BlockchainEvent(
                tx_hash=event.transactionHash.hex() if hasattr(event.transactionHash, 'hex') else str(event.transactionHash),
                block_number=event.blockNumber,
                event_type=EventType.ORDER_FILLED,
                data={
                    "order": order_data.to_dict(),
                    "is_whale": is_whale,
                    "value_usd": value_usd,
                    "log_index": event.logIndex
                },
                gas_price=None
            )
            
            await self._emit_event(blockchain_event)
            
            # Remove from pending if it was there
            tx_hash = blockchain_event.tx_hash
            async with self._lock:
                if tx_hash in self.pending_transactions:
                    del self.pending_transactions[tx_hash]
                    
        except Exception as e:
            logger.error(f"Error processing OrderFilled: {e}")
    
    async def _process_position_split(self, event: AttributeDict):
        """Process a PositionSplit event."""
        await self._emit_ctf_event(event, EventType.POSITION_SPLIT)
    
    async def _process_position_merge(self, event: AttributeDict):
        """Process a PositionMerge event."""
        await self._emit_ctf_event(event, EventType.POSITION_MERGE)
    
    async def _process_redemption(self, event: AttributeDict):
        """Process a Redemption event."""
        await self._emit_ctf_event(event, EventType.REDEMPTION)
    
    async def _emit_ctf_event(self, event: AttributeDict, event_type: EventType):
        """Emit a CTF event."""
        try:
            args = event.args
            
            blockchain_event = BlockchainEvent(
                tx_hash=event.transactionHash.hex() if hasattr(event.transactionHash, 'hex') else str(event.transactionHash),
                block_number=event.blockNumber,
                event_type=event_type,
                data={
                    "stakeholder": args.stakeholder.lower(),
                    "collateral_token": args.collateralToken.lower(),
                    "condition_id": args.conditionId.hex() if hasattr(args.conditionId, 'hex') else str(args.conditionId),
                    "amount": str(Decimal(args.amount) / Decimal(1e6)),
                    "log_index": event.logIndex
                }
            )
            
            await self._emit_event(blockchain_event)
            
        except Exception as e:
            logger.error(f"Error processing {event_type.value}: {e}")
    
    async def _emit_event(self, event: BlockchainEvent):
        """Emit a blockchain event to the handler."""
        if self.on_blockchain_event:
            try:
                # Support both sync and async handlers
                if asyncio.iscoroutinefunction(self.on_blockchain_event):
                    await self.on_blockchain_event(event)
                else:
                    self.on_blockchain_event(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    # ========================================================================
    # SMART DETECTION METHODS
    # ========================================================================
    
    def detect_whale_pattern(self, address: str, tx_data: str) -> bool:
        """
        Detect if an address exhibits whale trading patterns.
        
        Args:
            address: Ethereum address
            tx_data: Transaction input data
            
        Returns:
            True if whale pattern detected
        """
        address = address.lower()
        
        # Check if known whale
        if address in {a.lower() for a in self.whale_addresses}:
            return True
        
        # Analyze transaction data for large value indicators
        try:
            if len(tx_data) < 10:
                return False
            
            # Decode function selector
            selector = tx_data[:10]
            
            # Common Polymarket function selectors for large trades
            whale_selectors = {
                "0x7e9e",       # fillOrder
                "0xbc6139a0",   # fillOrders
                "0x",           # transfer (could be large)
            }
            
            # Check for large value in data (simplified heuristic)
            if selector in whale_selectors:
                # Additional heuristics could be added here
                # For example, analyzing the calldata for large amounts
                return len(tx_data) > 500  # Complex transactions are often large orders
                
        except Exception as e:
            logger.debug(f"Error detecting whale pattern: {e}")
        
        return False
    
    def predict_price_impact(
        self,
        amount: Decimal,
        side: str,
        orderbook: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Predict price impact of a trade.
        
        Args:
            amount: Trade amount in USDC
            side: "buy" or "sell"
            orderbook: Optional orderbook data
            
        Returns:
            Dictionary with impact analysis
        """
        if not orderbook:
            # Return estimate based on amount alone
            if amount < Decimal("1000"):
                impact = 0.001  # 0.1%
            elif amount < Decimal("5000"):
                impact = 0.005  # 0.5%
            elif amount < Decimal("20000"):
                impact = 0.015  # 1.5%
            else:
                impact = 0.05   # 5%
            
            return {
                "estimated_impact": impact,
                "slippage_bps": int(impact * 10000),
                "confidence": "low",
                "note": "Estimate without orderbook data"
            }
        
        # With orderbook, calculate more precisely
        # This would integrate with actual orderbook depth
        
        return {
            "estimated_impact": 0.01,  # Placeholder
            "slippage_bps": 100,
            "confidence": "medium",
            "note": "Orderbook-based calculation not yet implemented"
        }
    
    def calculate_front_run_opportunity(
        self,
        pending_tx: PendingTransaction,
        current_price: Optional[Decimal] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate optimal execution strategy (legal MEV optimization).
        
        This analyzes pending transactions to determine:
        - Expected price after the transaction executes
        - Optimal gas price for inclusion
        - Time-to-confirmation estimate
        
        Args:
            pending_tx: Pending transaction to analyze
            current_price: Current market price
            
        Returns:
            Opportunity analysis or None if no opportunity
        """
        try:
            # Decode transaction to understand its impact
            decoded = self._decode_transaction_input(
                pending_tx.to_address,
                pending_tx.input_data
            )
            
            if not decoded:
                return None
            
            # Calculate time to confirmation based on gas price
            mempool_position = self._estimate_mempool_position(pending_tx)
            
            # Estimate execution price
            estimated_execution_price = self._estimate_execution_price(decoded)
            
            return {
                "opportunity_type": "execution_optimization",
                "target_tx": pending_tx.tx_hash,
                "mempool_position": mempool_position,
                "estimated_confirmation_seconds": mempool_position * 12,  # ~12s per block
                "suggested_gas_price_gwei": self._suggest_gas_price(pending_tx),
                "estimated_price_impact": estimated_execution_price,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"Error calculating front-run opportunity: {e}")
            return None
    
    def _decode_transaction_input(self, to_address: str, input_data: str) -> Optional[Dict]:
        """Decode transaction input data."""
        if not input_data or input_data == "0x":
            return None
        
        try:
            selector = input_data[:10]
            params = input_data[10:]
            
            # Known function selectors for Polymarket
            selectors = {
                "0x7e9e": "fillOrder",
                "0xbc6139a0": "fillOrders",
                "0xa694fc3a": "stake",
                "0x2e1a7d4d": "withdraw",
                "0xa9059cbb": "transfer",
                "0x23b872dd": "transferFrom",
            }
            
            function_name = selectors.get(selector, "unknown")
            
            return {
                "function": function_name,
                "selector": selector,
                "params": params,
                "to": to_address
            }
            
        except Exception as e:
            logger.debug(f"Error decoding input: {e}")
            return None
    
    def _estimate_tx_value_usd(self, decoded: Dict) -> float:
        """Estimate transaction value in USD."""
        # Simplified estimation based on function type
        func = decoded.get("function", "")
        
        if func in ["fillOrder", "fillOrders"]:
            # These typically involve larger amounts
            return 10000.0  # Conservative estimate
        elif func in ["transfer", "transferFrom"]:
            return 5000.0
        
        return 0.0
    
    def _estimate_mempool_position(self, pending_tx: PendingTransaction) -> int:
        """Estimate position in mempool based on gas price."""
        if not self.mempool_stats.avg_gas_price:
            return 5  # Default estimate
        
        # Higher gas price = better position
        gas_ratio = pending_tx.gas_price_gwei / max(self.mempool_stats.avg_gas_price, 1)
        
        if gas_ratio > 2:
            return 1  # Next block
        elif gas_ratio > 1.5:
            return 2
        elif gas_ratio > 1.0:
            return 3
        else:
            return 5  # Lower priority
    
    def _suggest_gas_price(self, target_tx: PendingTransaction) -> float:
        """Suggest optimal gas price for transaction."""
        # Suggest slightly higher than target for faster inclusion
        return round(target_tx.gas_price_gwei * 1.1 + 1, 2)
    
    def _estimate_execution_price(self, decoded: Dict) -> Optional[float]:
        """Estimate the execution price of a transaction."""
        # This would require full ABI decoding of parameters
        # Placeholder for future implementation
        return None
    
    # ========================================================================
    # PUBLIC API
    # ========================================================================
    
    def add_whale_address(self, address: str):
        """Add an address to whale tracking."""
        self.whale_addresses.add(address.lower())
        logger.info(f"Added whale address: {address}")
    
    def remove_whale_address(self, address: str):
        """Remove an address from whale tracking."""
        self.whale_addresses.discard(address.lower())
        logger.info(f"Removed whale address: {address}")
    
    def get_mempool_stats(self) -> MempoolStats:
        """Get current mempool statistics."""
        return self.mempool_stats
    
    def get_pending_transactions(self) -> List[PendingTransaction]:
        """Get list of currently pending transactions."""
        return list(self.pending_transactions.values())
    
    async def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: float = 60.0,
        confirmations: int = 1
    ) -> Optional[BlockchainEvent]:
        """
        Wait for a transaction to be confirmed.
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum seconds to wait
            confirmations: Required confirmations
            
        Returns:
            BlockchainEvent if confirmed, None if timeout
        """
        start_time = time.time()
        tx_hash = tx_hash.lower()
        
        while time.time() - start_time < timeout:
            try:
                if not self.async_w3:
                    await asyncio.sleep(1)
                    continue
                
                receipt = await self.async_w3.eth.get_transaction_receipt(tx_hash)
                
                if receipt and receipt.blockNumber:
                    current_block = await self.async_w3.eth.block_number
                    confs = current_block - receipt.blockNumber + 1
                    
                    if confs >= confirmations:
                        return BlockchainEvent(
                            tx_hash=tx_hash,
                            block_number=receipt.blockNumber,
                            event_type=EventType.BLOCK_MINED,
                            data={"confirmations": confs, "status": receipt.status},
                            confirmations=confs,
                            gas_used=receipt.gasUsed
                        )
                
                await asyncio.sleep(1)
                
            except TransactionNotFound:
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error waiting for confirmation: {e}")
                await asyncio.sleep(1)
        
        logger.warning(f"Timeout waiting for confirmation of {tx_hash}")
        return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_monitor_from_env(**kwargs) -> BlockchainMonitor:
    """
    Create a BlockchainMonitor using environment variables.
    
    Environment variables:
        ALCHEMY_API_KEY: Alchemy API key
        INFURA_API_KEY: Infura project ID
        QUICKNODE_POLYGON_URL: QuickNode WebSocket URL
        WHALE_ADDRESSES: Comma-separated list of whale addresses
        MIN_WHALE_USD: Minimum USD for whale detection
    
    Returns:
        Configured BlockchainMonitor instance
    """
    import os
    
    # Parse whale addresses
    whale_env = os.getenv("WHALE_ADDRESSES", "")
    whale_addresses = set(a.strip() for a in whale_env.split(",") if a.strip())
    
    min_whale = float(os.getenv("MIN_WHALE_USD", "5000"))
    
    return BlockchainMonitor(
        whale_addresses=whale_addresses,
        min_whale_usd=min_whale,
        **kwargs
    )


async def run_monitor_demo():
    """Demo function to show monitor functionality."""
    logging.basicConfig(level=logging.INFO)
    
    # Create monitor
    monitor = create_monitor_from_env()
    
    # Set up event handlers
    def on_event(event: BlockchainEvent):
        print(f"\n[EVENT] {event.event_type.value}")
        print(f"  TX: {event.tx_hash[:30]}...")
        print(f"  Block: {event.block_number or 'pending'}")
        print(f"  Data: {json.dumps(event.data, indent=2, default=str)[:200]}")
    
    def on_pending(tx: PendingTransaction):
        print(f"\n[PENDING] {tx.tx_hash[:30]}... from {tx.from_address[:20]}...")
    
    monitor.on_blockchain_event = on_event
    monitor.on_pending_tx = on_pending
    
    try:
        await monitor.start()
        print("Monitor running. Press Ctrl+C to stop.")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        await monitor.stop()


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_monitor_demo())
