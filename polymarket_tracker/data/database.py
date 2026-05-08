"""
PolyBot Database Integration - SQLite Local Storage

Comprehensive database layer for tracking:
- Trade history with P&L
- Whale profiles and performance
- Market data caching
- Performance metrics
- System logs and events

Features:
- Connection pooling with context managers
- Automatic table creation and indexing
- Data validation and error handling
- Analytics and aggregation queries
"""

import sqlite3
import json
import threading
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TradeSide(Enum):
    """Trade direction."""
    YES = "YES"
    NO = "NO"


class TradeType(Enum):
    """Type of trade execution."""
    PAPER = "paper"
    LIVE = "live"


class PatternType(Enum):
    """Pattern types for trade classification."""
    MOMENTUM_BURST = "momentum_burst"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    LIQUIDITY_GRAB = "liquidity_grab"
    WHALE_ACCUMULATION = "whale_accumulation"
    WHALE_DISTRIBUTION = "whale_distribution"
    UNKNOWN = "unknown"


class EventType(Enum):
    """System event types."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    TRADE = "trade"
    SIGNAL = "signal"
    WHALE = "whale"
    SYSTEM = "system"


@dataclass
class TradeData:
    """Trade data structure."""
    trade_id: str
    market_id: str
    market_question: str
    side: str  # 'YES' or 'NO'
    trade_type: str  # 'paper' or 'live'
    entry_price: float
    size_usd: float
    status: str = "open"
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    signal_id: Optional[str] = None
    pattern_type: Optional[str] = None
    whale_address: Optional[str] = None
    whale_confidence: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    fees: float = 0.0
    metadata: Optional[Dict] = None
    created_at: Optional[str] = None
    closed_at: Optional[str] = None


@dataclass
class WhaleProfile:
    """Whale profile data structure."""
    address: str
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_size: float = 0.0
    avg_hold_time_minutes: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    confluence_score: float = 0.0
    reliability_tier: str = "unverified"
    market_specialization: Optional[str] = None
    metadata: Optional[Dict] = None


@dataclass
class MarketCache:
    """Cached market data structure."""
    market_id: str
    question: str
    category: Optional[str] = None
    description: Optional[str] = None
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    volume: Optional[float] = None
    liquidity: Optional[float] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict] = None
    cached_at: Optional[str] = None


@dataclass
class SystemEvent:
    """System event log structure."""
    event_id: Optional[int] = None
    event_type: str = "info"
    message: str = ""
    data: Optional[Dict] = None
    created_at: Optional[str] = None


class TradeDatabase:
    """
    Comprehensive SQLite database for PolyBot data management.
    
    Features:
    - Thread-safe connection pooling
    - Automatic schema creation and migration
    - Indexed queries for performance
    - Comprehensive analytics
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file. Defaults to data/polybot.db
        """
        if db_path is None:
            # Store in project data directory
            base_dir = Path(__file__).parent.parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "polybot.db"
        
        self.db_path = str(db_path)
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Initialize tables
        self._init_database()
        
        logger.info(f"TradeDatabase initialized at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        with self._lock:
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Transaction failed: {e}")
                raise
    
    def _init_database(self):
        """Initialize database tables and indexes."""
        with self.transaction() as conn:
            cursor = conn.cursor()
            
            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    market_question TEXT,
                    side TEXT NOT NULL CHECK(side IN ('YES', 'NO')),
                    trade_type TEXT NOT NULL DEFAULT 'paper' CHECK(trade_type IN ('paper', 'live')),
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    size_usd REAL NOT NULL,
                    pnl REAL,
                    pnl_percent REAL,
                    fees REAL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('pending', 'open', 'closed', 'cancelled', 'expired')),
                    signal_id TEXT,
                    pattern_type TEXT,
                    whale_address TEXT,
                    whale_confidence REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                )
            """)
            
            # Whale profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_profiles (
                    address TEXT PRIMARY KEY,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0.0,
                    win_rate REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    avg_trade_size REAL DEFAULT 0.0,
                    avg_hold_time_minutes REAL DEFAULT 0.0,
                    largest_win REAL DEFAULT 0.0,
                    largest_loss REAL DEFAULT 0.0,
                    confluence_score REAL DEFAULT 0.0,
                    reliability_tier TEXT DEFAULT 'unverified' CHECK(reliability_tier IN ('unverified', 'bronze', 'silver', 'gold', 'platinum')),
                    market_specialization TEXT,
                    metadata TEXT
                )
            """)
            
            # Market cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_cache (
                    market_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    category TEXT,
                    description TEXT,
                    yes_price REAL,
                    no_price REAL,
                    volume REAL,
                    liquidity REAL,
                    end_date TIMESTAMP,
                    status TEXT,
                    metadata TEXT,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # System events/log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL CHECK(event_type IN ('info', 'warning', 'error', 'trade', 'signal', 'whale', 'system')),
                    message TEXT NOT NULL,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Performance metrics table (daily snapshots)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    sharpe_ratio REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    avg_trade_pnl REAL DEFAULT 0.0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Pattern performance table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_performance (
                    pattern_type TEXT PRIMARY KEY,
                    total_signals INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    avg_pnl REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    avg_confidence REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_market_id ON trades(market_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_whale_address ON trades(whale_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_pattern_type ON trades(pattern_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_cache_category ON market_cache(category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_cache_cached_at ON market_cache(cached_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_events_type ON system_events(event_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_system_events_created_at ON system_events(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whale_profiles_win_rate ON whale_profiles(win_rate)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whale_profiles_tier ON whale_profiles(reliability_tier)
            """)
            
            logger.info("Database tables and indexes created successfully")
    
    # =========================================================================
    # Trade Management
    # =========================================================================
    
    def record_trade(self, trade_data: Union[TradeData, Dict]) -> bool:
        """
        Record a new trade in the database.
        
        Args:
            trade_data: TradeData object or dictionary with trade details
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(trade_data, dict):
                trade = TradeData(**trade_data)
            else:
                trade = trade_data
            
            # Set timestamp if not provided
            if trade.created_at is None:
                trade.created_at = datetime.now().isoformat()
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trades (
                        trade_id, market_id, market_question, side, trade_type,
                        entry_price, exit_price, size_usd, pnl, pnl_percent,
                        fees, status, signal_id, pattern_type, whale_address,
                        whale_confidence, stop_loss, take_profit, metadata, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id, trade.market_id, trade.market_question,
                    trade.side, trade.trade_type, trade.entry_price,
                    trade.exit_price, trade.size_usd, trade.pnl, trade.pnl_percent,
                    trade.fees, trade.status, trade.signal_id, trade.pattern_type,
                    trade.whale_address, trade.whale_confidence, trade.stop_loss,
                    trade.take_profit,
                    json.dumps(trade.metadata) if trade.metadata else None,
                    trade.created_at
                ))
            
            logger.info(f"Trade recorded: {trade.trade_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            return False
    
    def update_trade_result(
        self,
        trade_id: str,
        exit_price: float,
        pnl: float,
        status: str = "closed",
        exit_reason: Optional[str] = None
    ) -> bool:
        """
        Update a trade with exit information.
        
        Args:
            trade_id: Unique trade identifier
            exit_price: Exit price
            pnl: Realized P&L
            status: New status (default: closed)
            exit_reason: Reason for closing
            
        Returns:
            True if successful, False otherwise
        """
        try:
            closed_at = datetime.now().isoformat()
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                # Get entry price to calculate P&L percent
                cursor.execute(
                    "SELECT entry_price, size_usd FROM trades WHERE trade_id = ?",
                    (trade_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"Trade not found: {trade_id}")
                    return False
                
                entry_price = row['entry_price']
                size_usd = row['size_usd']
                
                # Calculate P&L percent
                pnl_percent = (pnl / size_usd * 100) if size_usd > 0 else 0.0
                
                # Update metadata with exit reason
                cursor.execute("SELECT metadata FROM trades WHERE trade_id = ?", (trade_id,))
                metadata_row = cursor.fetchone()
                metadata = json.loads(metadata_row['metadata']) if metadata_row['metadata'] else {}
                if exit_reason:
                    metadata['exit_reason'] = exit_reason
                
                cursor.execute("""
                    UPDATE trades 
                    SET exit_price = ?, pnl = ?, pnl_percent = ?, status = ?, 
                        closed_at = ?, metadata = ?
                    WHERE trade_id = ?
                """, (
                    exit_price, pnl, pnl_percent, status, closed_at,
                    json.dumps(metadata), trade_id
                ))
                
                # Update whale performance if applicable
                cursor.execute(
                    "SELECT whale_address FROM trades WHERE trade_id = ?",
                    (trade_id,)
                )
                whale_row = cursor.fetchone()
                if whale_row and whale_row['whale_address']:
                    self._update_whale_stats(conn, whale_row['whale_address'], pnl)
            
            logger.info(f"Trade updated: {trade_id}, P&L: ${pnl:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update trade: {e}")
            return False
    
    def get_trade_history(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get trade history with optional filters.
        
        Args:
            filters: Dictionary of filters (status, market_id, whale_address, 
                     pattern_type, start_date, end_date, trade_type)
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of trade dictionaries
        """
        try:
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if filters:
                if 'status' in filters:
                    query += " AND status = ?"
                    params.append(filters['status'])
                if 'market_id' in filters:
                    query += " AND market_id = ?"
                    params.append(filters['market_id'])
                if 'whale_address' in filters:
                    query += " AND whale_address = ?"
                    params.append(filters['whale_address'])
                if 'pattern_type' in filters:
                    query += " AND pattern_type = ?"
                    params.append(filters['pattern_type'])
                if 'trade_type' in filters:
                    query += " AND trade_type = ?"
                    params.append(filters['trade_type'])
                if 'start_date' in filters:
                    query += " AND created_at >= ?"
                    params.append(filters['start_date'])
                if 'end_date' in filters:
                    query += " AND created_at <= ?"
                    params.append(filters['end_date'])
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                trades = []
                for row in rows:
                    trade = dict(row)
                    if trade.get('metadata'):
                        trade['metadata'] = json.loads(trade['metadata'])
                    trades.append(trade)
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
    
    def get_open_positions(self) -> List[Dict]:
        """
        Get all currently open positions.
        
        Returns:
            List of open trade dictionaries
        """
        return self.get_trade_history(filters={'status': 'open'}, limit=1000)
    
    def get_performance_summary(self, days: int = 30) -> Dict:
        """
        Get P&L summary for a specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(CASE WHEN pnl = 0 THEN 1 ELSE 0 END) as break_even_trades,
                        SUM(pnl) as total_pnl,
                        AVG(pnl) as avg_pnl,
                        AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                        AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                        MAX(pnl) as largest_win,
                        MIN(pnl) as largest_loss,
                        SUM(fees) as total_fees
                    FROM trades 
                    WHERE status = 'closed' AND created_at >= ?
                """, (start_date,))
                
                row = cursor.fetchone()
                
                total_trades = row['total_trades'] or 0
                winning_trades = row['winning_trades'] or 0
                losing_trades = row['losing_trades'] or 0
                
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
                
                # Profit factor
                gross_profit = abs(row['avg_win'] or 0) * winning_trades
                gross_loss = abs(row['avg_loss'] or 0) * losing_trades
                profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                return {
                    'period_days': days,
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'break_even_trades': row['break_even_trades'] or 0,
                    'win_rate': win_rate,
                    'profit_factor': profit_factor,
                    'total_pnl': row['total_pnl'] or 0.0,
                    'total_fees': row['total_fees'] or 0.0,
                    'net_pnl': (row['total_pnl'] or 0.0) - (row['total_fees'] or 0.0),
                    'avg_pnl': row['avg_pnl'] or 0.0,
                    'avg_win': row['avg_win'] or 0.0,
                    'avg_loss': row['avg_loss'] or 0.0,
                    'largest_win': row['largest_win'] or 0.0,
                    'largest_loss': row['largest_loss'] or 0.0
                }
                
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {}
    
    # =========================================================================
    # Whale Profiles
    # =========================================================================
    
    def save_whale_profile(self, whale_data: Union[WhaleProfile, Dict]) -> bool:
        """
        Save or update a whale profile.
        
        Args:
            whale_data: WhaleProfile object or dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(whale_data, dict):
                whale = WhaleProfile(**whale_data)
            else:
                whale = whale_data
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                
                # Check if whale exists
                cursor.execute(
                    "SELECT address FROM whale_profiles WHERE address = ?",
                    (whale.address,)
                )
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update
                    cursor.execute("""
                        UPDATE whale_profiles SET
                            last_seen = CURRENT_TIMESTAMP,
                            total_trades = ?,
                            winning_trades = ?,
                            losing_trades = ?,
                            total_pnl = ?,
                            win_rate = ?,
                            profit_factor = ?,
                            avg_trade_size = ?,
                            avg_hold_time_minutes = ?,
                            largest_win = ?,
                            largest_loss = ?,
                            confluence_score = ?,
                            reliability_tier = ?,
                            market_specialization = ?,
                            metadata = ?
                        WHERE address = ?
                    """, (
                        whale.total_trades, whale.winning_trades, whale.losing_trades,
                        whale.total_pnl, whale.win_rate, whale.profit_factor,
                        whale.avg_trade_size, whale.avg_hold_time_minutes,
                        whale.largest_win, whale.largest_loss, whale.confluence_score,
                        whale.reliability_tier, whale.market_specialization,
                        json.dumps(whale.metadata) if whale.metadata else None,
                        whale.address
                    ))
                else:
                    # Insert
                    cursor.execute("""
                        INSERT INTO whale_profiles (
                            address, first_seen, last_seen, total_trades, winning_trades,
                            losing_trades, total_pnl, win_rate, profit_factor,
                            avg_trade_size, avg_hold_time_minutes, largest_win,
                            largest_loss, confluence_score, reliability_tier,
                            market_specialization, metadata
                        ) VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        whale.address, whale.total_trades, whale.winning_trades,
                        whale.losing_trades, whale.total_pnl, whale.win_rate,
                        whale.profit_factor, whale.avg_trade_size,
                        whale.avg_hold_time_minutes, whale.largest_win,
                        whale.largest_loss, whale.confluence_score,
                        whale.reliability_tier, whale.market_specialization,
                        json.dumps(whale.metadata) if whale.metadata else None
                    ))
            
            logger.info(f"Whale profile saved: {whale.address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save whale profile: {e}")
            return False
    
    def get_whale_profile(self, address: str) -> Optional[Dict]:
        """
        Get whale profile by address.
        
        Args:
            address: Whale wallet address
            
        Returns:
            Whale profile dictionary or None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM whale_profiles WHERE address = ?",
                    (address,)
                )
                row = cursor.fetchone()
                
                if row:
                    profile = dict(row)
                    if profile.get('metadata'):
                        profile['metadata'] = json.loads(profile['metadata'])
                    return profile
                return None
                
        except Exception as e:
            logger.error(f"Failed to get whale profile: {e}")
            return None
    
    def get_top_whales(
        self,
        limit: int = 10,
        min_trades: int = 5,
        tier: Optional[str] = None
    ) -> List[Dict]:
        """
        Get top performing whales.
        
        Args:
            limit: Maximum number of results
            min_trades: Minimum number of trades to qualify
            tier: Filter by reliability tier (optional)
            
        Returns:
            List of whale profile dictionaries
        """
        try:
            query = """
                SELECT * FROM whale_profiles 
                WHERE total_trades >= ?
            """
            params = [min_trades]
            
            if tier:
                query += " AND reliability_tier = ?"
                params.append(tier)
            
            query += " ORDER BY win_rate DESC, profit_factor DESC LIMIT ?"
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                whales = []
                for row in rows:
                    whale = dict(row)
                    if whale.get('metadata'):
                        whale['metadata'] = json.loads(whale['metadata'])
                    whales.append(whale)
                
                return whales
                
        except Exception as e:
            logger.error(f"Failed to get top whales: {e}")
            return []
    
    def update_whale_performance(
        self,
        address: str,
        trade_result: Dict
    ) -> bool:
        """
        Update whale statistics with a new trade result.
        
        Args:
            address: Whale wallet address
            trade_result: Dictionary with trade outcome (pnl, size, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.transaction() as conn:
                self._update_whale_stats(conn, address, trade_result.get('pnl', 0))
            return True
        except Exception as e:
            logger.error(f"Failed to update whale performance: {e}")
            return False
    
    def _update_whale_stats(self, conn: sqlite3.Connection, address: str, pnl: float):
        """Internal method to update whale statistics."""
        cursor = conn.cursor()
        
        # Get current stats
        cursor.execute(
            "SELECT * FROM whale_profiles WHERE address = ?",
            (address,)
        )
        row = cursor.fetchone()
        
        if not row:
            # Create new profile
            cursor.execute("""
                INSERT INTO whale_profiles (address, total_trades, winning_trades, 
                    losing_trades, total_pnl, win_rate, largest_win, largest_loss)
                VALUES (?, 1, ?, ?, ?, ?, ?, ?)
            """, (
                address,
                1 if pnl > 0 else 0,
                1 if pnl < 0 else 0,
                pnl,
                100.0 if pnl > 0 else 0.0,
                pnl if pnl > 0 else 0.0,
                pnl if pnl < 0 else 0.0
            ))
        else:
            # Update existing
            total_trades = row['total_trades'] + 1
            winning_trades = row['winning_trades'] + (1 if pnl > 0 else 0)
            losing_trades = row['losing_trades'] + (1 if pnl < 0 else 0)
            total_pnl = row['total_pnl'] + pnl
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            largest_win = max(row['largest_win'], pnl) if pnl > 0 else row['largest_win']
            largest_loss = min(row['largest_loss'], pnl) if pnl < 0 else row['largest_loss']
            
            # Update tier based on performance
            tier = row['reliability_tier']
            if total_trades >= 50 and win_rate >= 60 and total_pnl > 0:
                tier = 'platinum'
            elif total_trades >= 30 and win_rate >= 55 and total_pnl > 0:
                tier = 'gold'
            elif total_trades >= 15 and win_rate >= 52 and total_pnl > 0:
                tier = 'silver'
            elif total_trades >= 5 and win_rate >= 50 and total_pnl > 0:
                tier = 'bronze'
            
            cursor.execute("""
                UPDATE whale_profiles SET
                    last_seen = CURRENT_TIMESTAMP,
                    total_trades = ?,
                    winning_trades = ?,
                    losing_trades = ?,
                    total_pnl = ?,
                    win_rate = ?,
                    largest_win = ?,
                    largest_loss = ?,
                    reliability_tier = ?
                WHERE address = ?
            """, (
                total_trades, winning_trades, losing_trades, total_pnl,
                win_rate, largest_win, largest_loss, tier, address
            ))
    
    # =========================================================================
    # Market Data
    # =========================================================================
    
    def cache_market_data(self, market_id: str, data: Union[MarketCache, Dict]) -> bool:
        """
        Cache market information.
        
        Args:
            market_id: Market identifier
            data: MarketCache object or dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(data, dict):
                market = MarketCache(market_id=market_id, **data)
            else:
                market = data
            
            market.cached_at = datetime.now().isoformat()
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO market_cache (
                        market_id, question, category, description, yes_price,
                        no_price, volume, liquidity, end_date, status, metadata, cached_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    market.market_id, market.question, market.category,
                    market.description, market.yes_price, market.no_price,
                    market.volume, market.liquidity, market.end_date,
                    market.status,
                    json.dumps(market.metadata) if market.metadata else None,
                    market.cached_at
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache market data: {e}")
            return False
    
    def get_cached_market(self, market_id: str) -> Optional[Dict]:
        """
        Get cached market information.
        
        Args:
            market_id: Market identifier
            
        Returns:
            Market data dictionary or None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM market_cache WHERE market_id = ?",
                    (market_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    market = dict(row)
                    if market.get('metadata'):
                        market['metadata'] = json.loads(market['metadata'])
                    return market
                return None
                
        except Exception as e:
            logger.error(f"Failed to get cached market: {e}")
            return None
    
    def get_markets_by_category(
        self,
        category: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get markets by category.
        
        Args:
            category: Market category
            limit: Maximum number of results
            
        Returns:
            List of market dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM market_cache 
                    WHERE category = ? 
                    ORDER BY cached_at DESC 
                    LIMIT ?
                """, (category, limit))
                rows = cursor.fetchall()
                
                markets = []
                for row in rows:
                    market = dict(row)
                    if market.get('metadata'):
                        market['metadata'] = json.loads(market['metadata'])
                    markets.append(market)
                
                return markets
                
        except Exception as e:
            logger.error(f"Failed to get markets by category: {e}")
            return []
    
    def cleanup_old_cache(self, max_age_hours: int = 24) -> int:
        """
        Remove stale market cache entries.
        
        Args:
            max_age_hours: Maximum age of cache entries
            
        Returns:
            Number of entries removed
        """
        try:
            cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM market_cache WHERE cached_at < ?",
                    (cutoff,)
                )
                deleted = cursor.rowcount
            
            logger.info(f"Cleaned up {deleted} old cache entries")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup cache: {e}")
            return 0
    
    # =========================================================================
    # Analytics
    # =========================================================================
    
    def get_win_rate(self, days: int = 30, pattern_type: Optional[str] = None) -> float:
        """
        Calculate win rate for a period.
        
        Args:
            days: Number of days to analyze
            pattern_type: Optional pattern type filter
            
        Returns:
            Win rate as percentage
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins
                    FROM trades 
                    WHERE status = 'closed' AND created_at >= ?
                """
                params = [start_date]
                
                if pattern_type:
                    query += " AND pattern_type = ?"
                    params.append(pattern_type)
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                total = row['total'] or 0
                wins = row['wins'] or 0
                
                return (wins / total * 100) if total > 0 else 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate win rate: {e}")
            return 0.0
    
    def get_profit_factor(self, days: int = 30) -> float:
        """
        Calculate profit factor (gross profit / gross loss).
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Profit factor ratio
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
                        ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)) as gross_loss
                    FROM trades 
                    WHERE status = 'closed' AND created_at >= ?
                """, (start_date,))
                
                row = cursor.fetchone()
                gross_profit = row['gross_profit'] or 0
                gross_loss = row['gross_loss'] or 0
                
                return gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
        except Exception as e:
            logger.error(f"Failed to calculate profit factor: {e}")
            return 0.0
    
    def get_sharpe_ratio(
        self,
        days: int = 30,
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sharpe ratio for the period.
        
        Args:
            days: Number of days to analyze
            risk_free_rate: Annual risk-free rate (default 0)
            
        Returns:
            Sharpe ratio
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT pnl, created_at 
                    FROM trades 
                    WHERE status = 'closed' AND created_at >= ?
                    ORDER BY created_at
                """, (start_date,))
                
                rows = cursor.fetchall()
                
                if len(rows) < 2:
                    return 0.0
                
                returns = [row['pnl'] for row in rows]
                avg_return = sum(returns) / len(returns)
                
                # Calculate standard deviation
                variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
                std_dev = variance ** 0.5
                
                if std_dev == 0:
                    return 0.0
                
                # Annualized Sharpe ratio
                sharpe = (avg_return - risk_free_rate) / std_dev
                return sharpe
                
        except Exception as e:
            logger.error(f"Failed to calculate Sharpe ratio: {e}")
            return 0.0
    
    def get_pattern_performance(self, pattern_type: Optional[str] = None) -> List[Dict]:
        """
        Get performance statistics by pattern type.
        
        Args:
            pattern_type: Specific pattern to analyze (None for all)
            
        Returns:
            List of pattern performance statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                if pattern_type:
                    cursor.execute("""
                        SELECT 
                            pattern_type,
                            COUNT(*) as total_signals,
                            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                            AVG(pnl) as avg_pnl,
                            SUM(pnl) as total_pnl,
                            AVG(whale_confidence) as avg_confidence
                        FROM trades 
                        WHERE status = 'closed' AND pattern_type = ?
                        GROUP BY pattern_type
                    """, (pattern_type,))
                else:
                    cursor.execute("""
                        SELECT 
                            COALESCE(pattern_type, 'unknown') as pattern_type,
                            COUNT(*) as total_signals,
                            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                            AVG(pnl) as avg_pnl,
                            SUM(pnl) as total_pnl,
                            AVG(whale_confidence) as avg_confidence
                        FROM trades 
                        WHERE status = 'closed'
                        GROUP BY pattern_type
                    """)
                
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    stats = dict(row)
                    total = stats['total_signals'] or 0
                    wins = stats['wins'] or 0
                    stats['win_rate'] = (wins / total * 100) if total > 0 else 0.0
                    results.append(stats)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get pattern performance: {e}")
            return []
    
    def get_daily_pnl(self, days: int = 30) -> List[Dict]:
        """
        Get daily P&L breakdown.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of daily P&L records
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as trades,
                        SUM(pnl) as pnl,
                        SUM(fees) as fees,
                        SUM(pnl - fees) as net_pnl
                    FROM trades 
                    WHERE status = 'closed' AND created_at >= ?
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """, (start_date,))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to get daily P&L: {e}")
            return []
    
    # =========================================================================
    # System Logging
    # =========================================================================
    
    def log_event(
        self,
        event_type: Union[EventType, str],
        message: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Log a system event.
        
        Args:
            event_type: Type of event
            message: Event message
            data: Optional structured data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if isinstance(event_type, EventType):
                event_type = event_type.value
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_events (event_type, message, data)
                    VALUES (?, ?, ?)
                """, (
                    event_type,
                    message,
                    json.dumps(data) if data else None
                ))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False
    
    def get_events(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        limit: int = 100,
        start_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Get system events.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of results
            start_date: Filter by start date
            
        Returns:
            List of event dictionaries
        """
        try:
            if isinstance(event_type, EventType):
                event_type = event_type.value
            
            query = "SELECT * FROM system_events WHERE 1=1"
            params = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            if start_date:
                query += " AND created_at >= ?"
                params.append(start_date)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                events = []
                for row in rows:
                    event = dict(row)
                    if event.get('data'):
                        event['data'] = json.loads(event['data'])
                    events.append(event)
                
                return events
                
        except Exception as e:
            logger.error(f"Failed to get events: {e}")
            return []
    
    def cleanup_old_events(self, max_age_days: int = 30) -> int:
        """
        Remove old system events.
        
        Args:
            max_age_days: Maximum age of events to keep
            
        Returns:
            Number of events removed
        """
        try:
            cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
            
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM system_events WHERE created_at < ?",
                    (cutoff,)
                )
                deleted = cursor.rowcount
            
            logger.info(f"Cleaned up {deleted} old events")
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup events: {e}")
            return 0
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_database_stats(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with table counts and sizes
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                tables = ['trades', 'whale_profiles', 'market_cache', 'system_events']
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                    stats[table] = cursor.fetchone()['count']
                
                # Get file size
                db_size = Path(self.db_path).stat().st_size
                stats['database_size_bytes'] = db_size
                stats['database_size_mb'] = round(db_size / (1024 * 1024), 2)
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
    
    def export_to_json(self, table: str, filepath: str) -> bool:
        """
        Export table data to JSON file.
        
        Args:
            table: Table name to export
            filepath: Output file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                
                data = []
                for row in rows:
                    record = dict(row)
                    # Parse JSON fields
                    for key, value in record.items():
                        if isinstance(value, str) and value.startswith('{'):
                            try:
                                record[key] = json.loads(value)
                            except:
                                pass
                    data.append(record)
                
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                
                logger.info(f"Exported {len(data)} records from {table} to {filepath}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
