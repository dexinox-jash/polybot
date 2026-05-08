"""
Predictive Whale Entry System - First-Mover Advantage

This system PREDICTS when whales will trade BEFORE they do, giving you first-mover advantage.

Key Capabilities:
- Whale behavior modeling and pattern recognition
- Predictive signals for trade timing, direction, and size
- Pre-positioning strategies with dynamic sizing
- Machine learning-based confidence scoring
- Risk management tailored for prediction-based trading

Prediction Workflow:
1. Monitor whale wallet for pre-trade activity (approvals, funding)
2. Analyze market conditions vs whale's historical preferences
3. Calculate prediction confidence
4. If confidence > threshold: pre-position
5. Monitor for actual whale entry
6. If whale enters: maintain/increase position
7. If whale doesn't enter within timeframe: exit at small loss

Author: PolyBot Intelligence System
"""

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
import hashlib
import random

import numpy as np

from ..utils.logger import setup_logging
from ..utils.config import Config
from ..data.database import TradeDatabase

logger = setup_logging()


class PredictionDirection(Enum):
    """Predicted trade direction."""
    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class PredictionStatus(Enum):
    """Status of a prediction."""
    ACTIVE = "active"
    CONFIRMED = "confirmed"  # Whale traded as predicted
    EXPIRED = "expired"      # Time window passed, no trade
    INVALIDATED = "invalidated"  # Contradictory signals
    EXECUTED = "executed"    # We acted on prediction


class PreTradeSignal(Enum):
    """Signals that may indicate whale is preparing to trade."""
    TOKEN_APPROVAL = "token_approval"          # Approved token spending
    FUNDING_INCREASE = "funding_increase"      # Added funds to wallet
    GAS_ACQUISITION = "gas_acquisition"        # Acquired gas tokens
    PREVIOUS_MARKET_EXIT = "previous_exit"     # Just exited another market
    STAKE_WITHDRAWAL = "stake_withdrawal"      # Withdrew from staking
    BRIDGE_IN = "bridge_in"                    # Bridged funds in
    NFT_SALE = "nft_sale"                      # Sold NFTs for liquidity
    LIMIT_ORDER_CANCEL = "limit_cancel"        # Cancelled existing orders


@dataclass
class PredictionSignal:
    """
    A prediction about a whale's upcoming trade.
    
    Attributes:
        prediction_id: Unique identifier
        whale_address: Target whale address
        market_id: Predicted market
        direction: YES or NO prediction
        confidence: 0-100% confidence score
        timeframe: Expected trade window (minutes)
        expected_size: Predicted position size
        signals: List of signals triggering prediction
        timestamp: When prediction was created
        expiration: When prediction expires
        status: Current prediction status
    """
    prediction_id: str
    whale_address: str
    market_id: str
    direction: PredictionDirection
    confidence: float  # 0-100
    timeframe: int  # minutes
    expected_size: float
    signals: List[PreTradeSignal]
    timestamp: datetime
    expiration: datetime
    status: PredictionStatus = PredictionStatus.ACTIVE
    metadata: Dict = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if prediction has expired."""
        return datetime.now() > self.expiration
    
    def time_remaining_minutes(self) -> float:
        """Get remaining time in minutes."""
        remaining = (self.expiration - datetime.now()).total_seconds() / 60
        return max(0, remaining)
    
    def confidence_decayed(self) -> float:
        """Calculate time-decayed confidence."""
        elapsed = (datetime.now() - self.timestamp).total_seconds() / 60
        decay_factor = max(0.5, 1 - (elapsed / self.timeframe) * 0.5)
        return self.confidence * decay_factor


@dataclass
class PrePosition:
    """
    A pre-position taken based on a prediction.
    
    Attributes:
        position_id: Unique identifier
        prediction_id: Associated prediction
        entry_price: Entry price
        size: Position size
        stop_loss: Stop loss price
        take_profit: Take profit price
        prediction_confidence: Confidence when position opened
        entry_time: When position was opened
        whale_entry_observed: Whether whale actually entered
        exit_time: When position closed
        pnl: Realized profit/loss
    """
    position_id: str
    prediction_id: str
    market_id: str
    side: str  # 'YES' or 'NO'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    prediction_confidence: float
    entry_time: datetime
    whale_entry_observed: bool = False
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    status: str = "open"  # open, closed, stopped
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L."""
        if self.side == "YES":
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size


@dataclass
class PredictionStats:
    """Statistics for prediction performance tracking."""
    whale_address: str
    total_predictions: int = 0
    correct_predictions: int = 0
    false_positives: int = 0
    expired_predictions: int = 0
    
    # Metrics
    accuracy: float = 0.0  # Overall accuracy
    precision: float = 0.0  # TP / (TP + FP)
    recall: float = 0.0     # TP / (TP + FN)
    f1_score: float = 0.0   # Harmonic mean of precision and recall
    
    # Financial performance
    profit_factor: float = 0.0
    avg_return_per_prediction: float = 0.0
    max_consecutive_correct: int = 0
    max_consecutive_wrong: int = 0
    
    # Timing analysis
    avg_prediction_window: float = 0.0
    avg_time_to_confirmation: float = 0.0
    
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_metrics(self):
        """Recalculate all metrics."""
        if self.total_predictions > 0:
            self.accuracy = self.correct_predictions / self.total_predictions
            
            tp = self.correct_predictions
            fp = self.false_positives
            fn = self.expired_predictions
            
            self.precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            self.recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            
            if self.precision + self.recall > 0:
                self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)
        
        self.updated_at = datetime.now()


@dataclass
class WhaleBehaviorFeatures:
    """Feature vector for whale behavior modeling."""
    # Time patterns
    preferred_hours: List[int] = field(default_factory=list)
    day_of_week_bias: Dict[int, float] = field(default_factory=dict)  # 0-6 -> probability
    avg_time_between_trades: float = 0.0  # hours
    
    # Market condition preferences
    preferred_liquidity_range: Tuple[float, float] = (0, float('inf'))
    preferred_volume_range: Tuple[float, float] = (0, float('inf'))
    preferred_price_range: Tuple[float, float] = (0.1, 0.9)
    market_age_preference: str = "any"  # 'new', 'mature', 'any'
    
    # Position patterns
    avg_position_size: float = 0.0
    position_size_std: float = 0.0
    position_scaling_pattern: str = "flat"  # 'increasing', 'decreasing', 'flat'
    
    # Direction bias
    yes_bias: float = 0.5  # 0-1, >0.5 means prefers YES
    momentum_following: float = 0.5  # 0-1, tendency to follow price momentum
    contrarian_tendency: float = 0.5  # 0-1, tendency to bet against consensus
    
    # Pre-trade behavior
    avg_pre_trade_approvals: int = 0
    avg_funding_before_trade: float = 0.0
    typical_preparation_time: int = 0  # minutes between prep and trade
    
    # Success patterns
    best_performing_hours: List[int] = field(default_factory=list)
    best_market_conditions: List[str] = field(default_factory=list)
    worst_conditions: List[str] = field(default_factory=list)


@dataclass
class WhaleBehaviorModel:
    """
    Trained model for a specific whale's behavior.
    
    Attributes:
        whale_address: Target whale
        features: Extracted behavior features
        pattern_weights: ML-like weights for pattern recognition
        performance_metrics: Model performance stats
        last_trained: When model was last updated
        trade_history_sample: Number of trades used for training
    """
    whale_address: str
    features: WhaleBehaviorFeatures
    pattern_weights: Dict[str, float] = field(default_factory=dict)
    performance_metrics: PredictionStats = field(default_factory=lambda: PredictionStats(whale_address=""))
    last_trained: Optional[datetime] = None
    trade_history_sample: int = 0
    
    def __post_init__(self):
        if not self.performance_metrics.whale_address:
            self.performance_metrics.whale_address = self.whale_address


@dataclass
class StagingZone:
    """
    Optimal entry zone for pre-positioning.
    
    Attributes:
        market_id: Target market
        price_range: Entry price range
        confidence: Zone confidence (0-100)
        rationale: Why this zone is optimal
        risk_reward: Expected risk/reward ratio
        timeframe: Valid timeframe for zone
    """
    market_id: str
    price_range: Tuple[float, float]
    confidence: float
    rationale: str
    risk_reward: float
    timeframe: int  # minutes
    created_at: datetime = field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """Check if zone is still valid."""
        elapsed = (datetime.now() - self.created_at).total_seconds() / 60
        return elapsed < self.timeframe


class PredictiveEntryDatabase:
    """
    Database layer for predictive entry system.
    
    Extends the main TradeDatabase with prediction-specific tables.
    """
    
    def __init__(self, db: Optional[TradeDatabase] = None):
        """Initialize with optional existing database."""
        self.db = db or TradeDatabase()
        self._init_prediction_tables()
    
    def _init_prediction_tables(self):
        """Create prediction-specific tables."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            
            # Predictions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    whale_address TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timeframe INTEGER NOT NULL,
                    expected_size REAL NOT NULL,
                    signals TEXT,
                    status TEXT DEFAULT 'active',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expiration TIMESTAMP NOT NULL,
                    metadata TEXT,
                    confirmed_at TIMESTAMP,
                    confirmed_trade_id TEXT
                )
            """)
            
            # Pre-positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pre_positions (
                    position_id TEXT PRIMARY KEY,
                    prediction_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    prediction_confidence REAL NOT NULL,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_time TIMESTAMP,
                    exit_price REAL,
                    pnl REAL,
                    whale_entry_observed BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'open',
                    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
                )
            """)
            
            # Whale behavior models table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_behavior_models (
                    whale_address TEXT PRIMARY KEY,
                    features TEXT NOT NULL,
                    pattern_weights TEXT,
                    performance_metrics TEXT,
                    last_trained TIMESTAMP,
                    trade_history_sample INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Whale trade history for pattern analysis
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    whale_address TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    market_conditions TEXT,
                    pre_trade_signals TEXT,
                    pnl REAL,
                    metadata TEXT
                )
            """)
            
            # Pre-trade activity log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pre_trade_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    whale_address TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details TEXT,
                    followed_by_trade BOOLEAN,
                    time_to_trade_minutes INTEGER
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_whale ON predictions(whale_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_expiration ON predictions(expiration)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pre_positions_prediction ON pre_positions(prediction_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whale_history_address ON whale_trade_history(whale_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pre_trade_whale ON pre_trade_activity(whale_address)
            """)
    
    def save_prediction(self, prediction: PredictionSignal) -> bool:
        """Save a prediction to database."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO predictions (
                        prediction_id, whale_address, market_id, direction, confidence,
                        timeframe, expected_size, signals, status, timestamp, expiration, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prediction.prediction_id,
                    prediction.whale_address,
                    prediction.market_id,
                    prediction.direction.value,
                    prediction.confidence,
                    prediction.timeframe,
                    prediction.expected_size,
                    json.dumps([s.value for s in prediction.signals]),
                    prediction.status.value,
                    prediction.timestamp.isoformat(),
                    prediction.expiration.isoformat(),
                    json.dumps(prediction.metadata)
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to save prediction: {e}")
            return False
    
    def update_prediction_status(
        self,
        prediction_id: str,
        status: PredictionStatus,
        confirmed_trade_id: Optional[str] = None
    ) -> bool:
        """Update prediction status."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE predictions 
                    SET status = ?, confirmed_at = ?, confirmed_trade_id = ?
                    WHERE prediction_id = ?
                """, (
                    status.value,
                    datetime.now().isoformat() if status == PredictionStatus.CONFIRMED else None,
                    confirmed_trade_id,
                    prediction_id
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to update prediction status: {e}")
            return False
    
    def save_pre_position(self, position: PrePosition) -> bool:
        """Save a pre-position to database."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO pre_positions (
                        position_id, prediction_id, market_id, side, entry_price, size,
                        stop_loss, take_profit, prediction_confidence, entry_time,
                        whale_entry_observed, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    position.position_id, position.prediction_id, position.market_id,
                    position.side, position.entry_price, position.size,
                    position.stop_loss, position.take_profit, position.prediction_confidence,
                    position.entry_time.isoformat(),
                    position.whale_entry_observed, position.status
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to save pre-position: {e}")
            return False
    
    def update_pre_position_exit(
        self,
        position_id: str,
        exit_price: float,
        pnl: float,
        status: str = "closed"
    ) -> bool:
        """Update pre-position with exit information."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pre_positions 
                    SET exit_time = ?, exit_price = ?, pnl = ?, status = ?
                    WHERE position_id = ?
                """, (
                    datetime.now().isoformat(), exit_price, pnl, status, position_id
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to update pre-position exit: {e}")
            return False
    
    def get_whale_trade_history(
        self,
        whale_address: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get trade history for a whale."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM whale_trade_history 
                    WHERE whale_address = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (whale_address, limit))
                rows = cursor.fetchall()
                
                trades = []
                for row in rows:
                    trade = dict(row)
                    if trade.get('market_conditions'):
                        trade['market_conditions'] = json.loads(trade['market_conditions'])
                    if trade.get('pre_trade_signals'):
                        trade['pre_trade_signals'] = json.loads(trade['pre_trade_signals'])
                    if trade.get('metadata'):
                        trade['metadata'] = json.loads(trade['metadata'])
                    trades.append(trade)
                return trades
        except Exception as e:
            logger.error(f"Failed to get whale trade history: {e}")
            return []
    
    def save_whale_behavior_model(self, model: WhaleBehaviorModel) -> bool:
        """Save a whale behavior model."""
        try:
            with self.db.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO whale_behavior_models (
                        whale_address, features, pattern_weights, performance_metrics,
                        last_trained, trade_history_sample, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    model.whale_address,
                    json.dumps(asdict(model.features)),
                    json.dumps(model.pattern_weights),
                    json.dumps(asdict(model.performance_metrics)),
                    model.last_trained.isoformat() if model.last_trained else None,
                    model.trade_history_sample,
                    datetime.now().isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Failed to save behavior model: {e}")
            return False
    
    def load_whale_behavior_model(self, whale_address: str) -> Optional[WhaleBehaviorModel]:
        """Load a whale behavior model."""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM whale_behavior_models WHERE whale_address = ?
                """, (whale_address,))
                row = cursor.fetchone()
                
                if row:
                    features = WhaleBehaviorFeatures(**json.loads(row['features']))
                    metrics = PredictionStats(**json.loads(row['performance_metrics']))
                    
                    return WhaleBehaviorModel(
                        whale_address=row['whale_address'],
                        features=features,
                        pattern_weights=json.loads(row['pattern_weights']) if row['pattern_weights'] else {},
                        performance_metrics=metrics,
                        last_trained=datetime.fromisoformat(row['last_trained']) if row['last_trained'] else None,
                        trade_history_sample=row['trade_history_sample']
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to load behavior model: {e}")
            return None
    
    def get_active_predictions(self, whale_address: Optional[str] = None) -> List[PredictionSignal]:
        """Get all active (non-expired) predictions."""
        try:
            query = """
                SELECT * FROM predictions 
                WHERE status = 'active' AND expiration > ?
            """
            params = [datetime.now().isoformat()]
            
            if whale_address:
                query += " AND whale_address = ?"
                params.append(whale_address)
            
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                predictions = []
                for row in rows:
                    pred = PredictionSignal(
                        prediction_id=row['prediction_id'],
                        whale_address=row['whale_address'],
                        market_id=row['market_id'],
                        direction=PredictionDirection(row['direction']),
                        confidence=row['confidence'],
                        timeframe=row['timeframe'],
                        expected_size=row['expected_size'],
                        signals=[PreTradeSignal(s) for s in json.loads(row['signals'])],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        expiration=datetime.fromisoformat(row['expiration']),
                        status=PredictionStatus(row['status']),
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    )
                    predictions.append(pred)
                return predictions
        except Exception as e:
            logger.error(f"Failed to get active predictions: {e}")
            return []


class PredictiveEntrySystem:
    """
    Predictive Whale Entry System - First-Mover Advantage Engine
    
    This system analyzes whale behavior patterns to predict future trades
    before they occur, enabling pre-positioning for maximum alpha capture.
    
    Key Features:
    - ML-inspired pattern recognition on whale history
    - Pre-trade signal detection (approvals, funding, etc.)
    - Confidence-scored predictions with time decay
    - Dynamic position sizing based on prediction quality
    - Comprehensive risk management for prediction-based trading
    
    Usage:
        >>> from polymarket_tracker.realtime import PredictiveEntrySystem
        >>> predictor = PredictiveEntrySystem()
        >>> 
        >>> # Train models on historical data
        >>> await predictor.train_whale_model(whale_address)
        >>> 
        >>> # Get predictions
        >>> prediction = await predictor.predict_next_trade(whale_address)
        >>> 
        >>> # Pre-position based on prediction
        >>> if prediction and prediction.confidence > 70:
        ...     position = await predictor.pre_position(whale_address, market_id, prediction.confidence)
    """
    
    # Configuration defaults
    DEFAULT_CONFIDENCE_THRESHOLD = 65.0
    DEFAULT_MAX_PREDICTION_EXPOSURE = 1000.0  # USD
    DEFAULT_PREDICTION_STOP_LOSS = 0.02  # 2%
    DEFAULT_TIME_DECAY_FACTOR = 0.1  # Confidence decay per minute
    DEFAULT_PREDICTION_WINDOW = 15  # minutes
    
    def __init__(
        self,
        config: Optional[Config] = None,
        database: Optional[PredictiveEntryDatabase] = None
    ):
        """
        Initialize the predictive entry system.
        
        Args:
            config: Configuration object
            database: Database for predictions and models
        """
        self.config = config or Config.from_env()
        self.db = database or PredictiveEntryDatabase()
        
        # Risk parameters
        self.prediction_confidence_threshold = self.DEFAULT_CONFIDENCE_THRESHOLD
        self.max_prediction_exposure = self.DEFAULT_MAX_PREDICTION_EXPOSURE
        self.prediction_stop_loss = self.DEFAULT_PREDICTION_STOP_LOSS
        self.time_decay_factor = self.DEFAULT_TIME_DECAY_FACTOR
        
        # Runtime state
        self.behavior_models: Dict[str, WhaleBehaviorModel] = {}
        self.active_predictions: Dict[str, PredictionSignal] = {}
        self.pre_positions: Dict[str, PrePosition] = {}
        self.wallet_activity_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Monitoring callbacks
        self._prediction_callbacks: List[Callable] = []
        self._pre_position_callbacks: List[Callable] = []
        self._confirmation_callbacks: List[Callable] = []
        
        # Async lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("PredictiveEntrySystem initialized")
    
    # ========================================================================
    # Whale Behavior Modeling
    # ========================================================================
    
    async def train_whale_model(self, whale_address: str) -> Optional[WhaleBehaviorModel]:
        """
        Train a behavior model for a specific whale.
        
        Analyzes historical trades to identify patterns in:
        - Timing preferences
        - Market condition preferences
        - Position sizing patterns
        - Pre-trade behavior
        
        Args:
            whale_address: Whale to model
            
        Returns:
            Trained WhaleBehaviorModel or None if insufficient data
        """
        whale_address = whale_address.lower()
        
        # Load trade history
        trade_history = self.db.get_whale_trade_history(whale_address, limit=200)
        
        if len(trade_history) < 10:
            logger.warning(f"Insufficient data to train model for {whale_address[:10]}")
            return None
        
        logger.info(f"Training behavior model for {whale_address[:10]} with {len(trade_history)} trades")
        
        # Extract features
        features = self._extract_behavior_features(trade_history)
        
        # Calculate pattern weights using simple statistical analysis
        pattern_weights = self._calculate_pattern_weights(trade_history)
        
        # Create or update model
        model = WhaleBehaviorModel(
            whale_address=whale_address,
            features=features,
            pattern_weights=pattern_weights,
            last_trained=datetime.now(),
            trade_history_sample=len(trade_history)
        )
        
        # Load existing performance metrics if available
        existing = self.db.load_whale_behavior_model(whale_address)
        if existing:
            model.performance_metrics = existing.performance_metrics
        
        # Cache and save
        self.behavior_models[whale_address] = model
        self.db.save_whale_behavior_model(model)
        
        logger.info(f"Model trained for {whale_address[:10]}: "
                   f"avg_size=${features.avg_position_size:.0f}, "
                   f"preferred_hours={features.preferred_hours}")
        
        return model
    
    def _extract_behavior_features(self, trades: List[Dict]) -> WhaleBehaviorFeatures:
        """Extract behavior features from trade history."""
        features = WhaleBehaviorFeatures()
        
        if not trades:
            return features
        
        # Time patterns
        hours = []
        days_of_week = []
        timestamps = []
        
        for trade in trades:
            ts = trade.get('timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts:
                hours.append(ts.hour)
                days_of_week.append(ts.weekday())
                timestamps.append(ts)
        
        if hours:
            # Find preferred hours (top 3)
            from collections import Counter
            hour_counts = Counter(hours)
            features.preferred_hours = [h for h, _ in hour_counts.most_common(3)]
            
            # Day of week bias
            day_counts = Counter(days_of_week)
            for day in range(7):
                features.day_of_week_bias[day] = day_counts.get(day, 0) / len(days_of_week)
        
        # Time between trades
        if len(timestamps) > 1:
            timestamps.sort()
            intervals = [(timestamps[i] - timestamps[i-1]).total_seconds() / 3600 
                        for i in range(1, len(timestamps))]
            features.avg_time_between_trades = np.mean(intervals)
        
        # Position sizing
        sizes = [t.get('size', 0) for t in trades]
        if sizes:
            features.avg_position_size = np.mean(sizes)
            features.position_size_std = np.std(sizes) if len(sizes) > 1 else 0
            
            # Detect scaling pattern
            if len(sizes) >= 5:
                first_half = np.mean(sizes[:len(sizes)//2])
                second_half = np.mean(sizes[len(sizes)//2:])
                if second_half > first_half * 1.2:
                    features.position_scaling_pattern = "increasing"
                elif second_half < first_half * 0.8:
                    features.position_scaling_pattern = "decreasing"
        
        # Direction bias
        yes_trades = sum(1 for t in trades if t.get('side', '').upper() == 'YES')
        if trades:
            features.yes_bias = yes_trades / len(trades)
        
        # Market condition preferences
        liquidities = []
        volumes = []
        prices = []
        
        for trade in trades:
            conditions = trade.get('market_conditions', {})
            if conditions:
                if 'liquidity' in conditions:
                    liquidities.append(conditions['liquidity'])
                if 'volume' in conditions:
                    volumes.append(conditions['volume'])
            prices.append(trade.get('price', 0.5))
        
        if liquidities:
            features.preferred_liquidity_range = (
                np.percentile(liquidities, 25),
                np.percentile(liquidities, 75)
            )
        if volumes:
            features.preferred_volume_range = (
                np.percentile(volumes, 25),
                np.percentile(volumes, 75)
            )
        if prices:
            features.preferred_price_range = (
                max(0.1, np.percentile(prices, 25)),
                min(0.9, np.percentile(prices, 75))
            )
        
        # Analyze pre-trade signals
        pre_trade_signals = []
        for trade in trades:
            signals = trade.get('pre_trade_signals', [])
            if signals:
                pre_trade_signals.extend(signals)
        
        if pre_trade_signals:
            features.avg_pre_trade_approvals = len(pre_trade_signals) / len(trades)
        
        return features
    
    def _calculate_pattern_weights(self, trades: List[Dict]) -> Dict[str, float]:
        """Calculate ML-inspired pattern weights from trade history."""
        weights = {}
        
        if len(trades) < 10:
            return weights
        
        # Weight: Time of day correlation with success
        hour_success = defaultdict(lambda: {'wins': 0, 'total': 0})
        for trade in trades:
            ts = trade.get('timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts:
                hour = ts.hour
                hour_success[hour]['total'] += 1
                pnl = trade.get('pnl', 0)
                if pnl and pnl > 0:
                    hour_success[hour]['wins'] += 1
        
        # Find best hours
        best_hours = []
        for hour, stats in hour_success.items():
            if stats['total'] >= 3 and stats['wins'] / stats['total'] > 0.6:
                best_hours.append(hour)
        
        if best_hours:
            weights['time_of_day'] = 0.15
        
        # Weight: Position size correlation with success
        size_pnl_pairs = [(t.get('size', 0), t.get('pnl', 0)) for t in trades if t.get('pnl')]
        if size_pnl_pairs:
            sizes, pnls = zip(*size_pnl_pairs)
            if len(sizes) > 5:
                # Calculate correlation
                correlation = np.corrcoef(sizes, pnls)[0, 1] if np.std(sizes) > 0 else 0
                if abs(correlation) > 0.3:
                    weights['position_size'] = abs(correlation) * 0.1
        
        # Weight: Streak persistence
        streaks = []
        current_streak = 0
        for trade in sorted(trades, key=lambda x: x.get('timestamp', '')):
            pnl = trade.get('pnl', 0)
            if pnl:
                if pnl > 0:
                    if current_streak > 0:
                        current_streak += 1
                    else:
                        current_streak = 1
                else:
                    if current_streak < 0:
                        current_streak -= 1
                    else:
                        current_streak = -1
                streaks.append(current_streak)
        
        if streaks:
            avg_streak_length = np.mean([abs(s) for s in streaks])
            if avg_streak_length > 1.5:
                weights['momentum_persistence'] = 0.1
        
        # Default weights for known patterns
        weights.setdefault('pre_trade_signals', 0.2)
        weights.setdefault('market_conditions', 0.15)
        weights.setdefault('recent_activity', 0.1)
        
        return weights
    
    async def refresh_model(self, whale_address: str) -> Optional[WhaleBehaviorModel]:
        """Refresh a whale's behavior model with latest data."""
        return await self.train_whale_model(whale_address)
    
    # ========================================================================
    # Predictive Signals
    # ========================================================================
    
    async def predict_next_trade(
        self,
        whale_address: str,
        market_context: Optional[Dict] = None
    ) -> Optional[PredictionSignal]:
        """
        Predict if and when a whale will trade next.
        
        Analyzes:
        - Recent wallet activity
        - Historical timing patterns
        - Market conditions vs preferences
        - Current market opportunities
        
        Args:
            whale_address: Target whale
            market_context: Current market conditions
            
        Returns:
            PredictionSignal if prediction made, None otherwise
        """
        whale_address = whale_address.lower()
        
        # Load or train model
        model = self.behavior_models.get(whale_address)
        if not model:
            model = await self.train_whale_model(whale_address)
            if not model:
                return None
        
        # Check if model is stale
        if model.last_trained and (datetime.now() - model.last_trained).days > 7:
            model = await self.refresh_model(whale_address)
        
        # Analyze pre-trade signals
        pre_trade_signals = self._detect_pre_trade_signals(whale_address)
        
        # Calculate base confidence
        confidence = 0.0
        signals_used = []
        
        # Signal 1: Recent wallet activity
        if pre_trade_signals:
            activity_score = min(len(pre_trade_signals) * 15, 40)
            confidence += activity_score
            signals_used.extend(pre_trade_signals)
        
        # Signal 2: Time alignment with preferences
        current_hour = datetime.now().hour
        if current_hour in model.features.preferred_hours:
            confidence += 20
            signals_used.append(PreTradeSignal.PREVIOUS_MARKET_EXIT)
        
        # Signal 3: Time since last trade
        last_trade_time = await self._get_last_trade_time(whale_address)
        if last_trade_time and model.features.avg_time_between_trades > 0:
            hours_since = (datetime.now() - last_trade_time).total_seconds() / 3600
            expected_interval = model.features.avg_time_between_trades
            
            # Higher confidence if we're near expected interval
            if 0.8 <= hours_since / expected_interval <= 1.5:
                confidence += 15
        
        # Signal 4: Market opportunity match
        if market_context:
            match_score = self._calculate_market_match(model, market_context)
            confidence += match_score * 20
        
        # Apply pattern weights
        for signal, weight in model.pattern_weights.items():
            confidence += weight * 10
        
        # Normalize confidence
        confidence = min(95, max(0, confidence))
        
        # Generate prediction only if confidence exceeds threshold
        if confidence < self.prediction_confidence_threshold:
            logger.debug(f"Prediction confidence {confidence:.1f} below threshold for {whale_address[:10]}")
            return None
        
        # Determine expected timeframe
        timeframe = self._estimate_timeframe(model, signals_used)
        
        # Determine expected size
        expected_size = model.features.avg_position_size
        
        # Determine direction (requires market context)
        direction = PredictionDirection.UNKNOWN
        if market_context:
            direction = self._predict_direction(model, market_context)
        
        # Create prediction
        prediction = PredictionSignal(
            prediction_id=str(uuid.uuid4()),
            whale_address=whale_address,
            market_id=market_context.get('market_id', 'unknown') if market_context else 'unknown',
            direction=direction,
            confidence=confidence,
            timeframe=timeframe,
            expected_size=expected_size,
            signals=signals_used,
            timestamp=datetime.now(),
            expiration=datetime.now() + timedelta(minutes=timeframe),
            metadata={
                'model_version': model.last_trained.isoformat() if model.last_trained else None,
                'pattern_weights_used': list(model.pattern_weights.keys()),
                'pre_trade_activity_count': len(pre_trade_signals)
            }
        )
        
        # Store prediction
        async with self._lock:
            self.active_predictions[prediction.prediction_id] = prediction
        
        self.db.save_prediction(prediction)
        
        # Notify callbacks
        for callback in self._prediction_callbacks:
            try:
                await callback(prediction)
            except Exception as e:
                logger.error(f"Prediction callback error: {e}")
        
        logger.info(f"Prediction generated for {whale_address[:10]}: "
                   f"{direction.value} with {confidence:.1f}% confidence, "
                   f"window: {timeframe}min")
        
        return prediction
    
    async def predict_market_direction(
        self,
        whale_address: str,
        market_id: str,
        market_data: Optional[Dict] = None
    ) -> PredictionDirection:
        """
        Predict whether whale will bet YES or NO on a specific market.
        
        Args:
            whale_address: Target whale
            market_id: Market to analyze
            market_data: Current market data
            
        Returns:
            Predicted direction
        """
        whale_address = whale_address.lower()
        
        model = self.behavior_models.get(whale_address)
        if not model:
            return PredictionDirection.UNKNOWN
        
        # Base bias from history
        yes_probability = model.features.yes_bias
        
        # Adjust based on market conditions
        if market_data:
            current_price = market_data.get('yes_price', 0.5)
            
            # Contrarian tendency
            if current_price > 0.7:
                yes_probability -= model.features.contrarian_tendency * 0.2
            elif current_price < 0.3:
                yes_probability += model.features.contrarian_tendency * 0.2
            
            # Momentum following
            price_change = market_data.get('price_change_24h', 0)
            if price_change > 0:
                yes_probability += model.features.momentum_following * 0.1
            else:
                yes_probability -= model.features.momentum_following * 0.1
        
        # Normalize
        yes_probability = max(0.1, min(0.9, yes_probability))
        
        if yes_probability > 0.55:
            return PredictionDirection.YES
        elif yes_probability < 0.45:
            return PredictionDirection.NO
        else:
            return PredictionDirection.UNKNOWN
    
    async def predict_entry_timing(
        self,
        whale_address: str,
        market_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Predict the window of likely entry.
        
        Returns:
            Dictionary with timing predictions
        """
        whale_address = whale_address.lower()
        
        model = self.behavior_models.get(whale_address)
        if not model:
            return {'confidence': 'low', 'estimated_window': 'unknown'}
        
        now = datetime.now()
        
        # Check if we're in preferred hours
        in_preferred = now.hour in model.features.preferred_hours
        
        # Estimate next preferred window
        next_preferred = None
        if not in_preferred:
            for hour in sorted(model.features.preferred_hours):
                if hour > now.hour:
                    next_preferred = hour
                    break
            if next_preferred is None and model.features.preferred_hours:
                next_preferred = min(model.features.preferred_hours) + 24
        
        # Calculate expected time based on avg interval
        last_trade = await self._get_last_trade_time(whale_address)
        expected_trade_time = None
        if last_trade and model.features.avg_time_between_trades > 0:
            expected_trade_time = last_trade + timedelta(
                hours=model.features.avg_time_between_trades
            )
        
        return {
            'confidence': 'high' if in_preferred else 'medium',
            'current_hour_preferred': in_preferred,
            'next_preferred_window': next_preferred,
            'estimated_trade_time': expected_trade_time.isoformat() if expected_trade_time else None,
            'avg_interval_hours': model.features.avg_time_between_trades,
            'typical_preparation_minutes': model.features.typical_preparation_time
        }
    
    async def predict_position_size(
        self,
        whale_address: str,
        market_conditions: Dict
    ) -> float:
        """
        Predict expected position size based on market conditions.
        
        Args:
            whale_address: Target whale
            market_conditions: Current market conditions
            
        Returns:
            Predicted position size in USD
        """
        whale_address = whale_address.lower()
        
        model = self.behavior_models.get(whale_address)
        if not model:
            return 0.0
        
        base_size = model.features.avg_position_size
        
        # Adjust for market conditions
        liquidity = market_conditions.get('liquidity', 100000)
        volume = market_conditions.get('volume', 10000)
        
        # Scale down if liquidity is low
        if liquidity < 50000:
            base_size *= 0.7
        elif liquidity > 500000:
            base_size *= 1.2
        
        # Scale based on volume trend
        volume_24h = market_conditions.get('volume_24h', volume)
        if volume_24h > volume * 2:
            base_size *= 1.1  # High activity = more confidence
        
        # Apply position scaling pattern
        if model.features.position_scaling_pattern == "increasing":
            base_size *= 1.1
        elif model.features.position_scaling_pattern == "decreasing":
            base_size *= 0.9
        
        return base_size
    
    # ========================================================================
    # Pre-Positioning Strategies
    # ========================================================================
    
    async def pre_position(
        self,
        whale_address: str,
        market_id: str,
        confidence: float,
        market_data: Optional[Dict] = None
    ) -> Optional[PrePosition]:
        """
        Enter a position before the whale trades.
        
        Args:
            whale_address: Whale being predicted
            market_id: Market to trade
            confidence: Prediction confidence (0-100)
            market_data: Current market data
            
        Returns:
            PrePosition if entered, None otherwise
        """
        # Validate confidence
        if confidence < self.prediction_confidence_threshold:
            logger.debug(f"Confidence {confidence} below threshold, skipping pre-position")
            return None
        
        # Determine direction
        direction = await self.predict_market_direction(whale_address, market_id, market_data)
        if direction == PredictionDirection.UNKNOWN:
            logger.debug("Cannot determine direction, skipping pre-position")
            return None
        
        # Calculate position size
        size = self.dynamic_sizing(confidence, self.max_prediction_exposure)
        
        # Get current price
        if market_data:
            if direction == PredictionDirection.YES:
                entry_price = market_data.get('yes_price', 0.5)
            else:
                entry_price = market_data.get('no_price', 0.5)
        else:
            entry_price = 0.5
        
        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_exit_levels(entry_price, direction)
        
        # Create position
        position = PrePosition(
            position_id=str(uuid.uuid4()),
            prediction_id="manual",  # Will be updated if linked to prediction
            market_id=market_id,
            side=direction.value,
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            prediction_confidence=confidence,
            entry_time=datetime.now()
        )
        
        # Store position
        async with self._lock:
            self.pre_positions[position.position_id] = position
        
        self.db.save_pre_position(position)
        
        # Notify callbacks
        for callback in self._pre_position_callbacks:
            try:
                await callback(position)
            except Exception as e:
                logger.error(f"Pre-position callback error: {e}")
        
        logger.info(f"Pre-position opened: {direction.value} {size:.0f} @ {entry_price:.3f} "
                   f"(confidence: {confidence:.1f}%)")
        
        return position
    
    def dynamic_sizing(self, confidence: float, max_risk: float) -> float:
        """
        Calculate position size based on prediction confidence.
        
        Uses a confidence-adjusted sizing formula that scales
        exposure based on prediction quality.
        
        Args:
            confidence: Prediction confidence (0-100)
            max_risk: Maximum risk exposure
            
        Returns:
            Position size in USD
        """
        # Normalize confidence to 0-1
        conf_norm = confidence / 100.0
        
        # Apply non-linear scaling (more aggressive at high confidence)
        size_multiplier = conf_norm ** 1.5
        
        # Scale to max risk
        position_size = max_risk * size_multiplier
        
        # Minimum position size
        min_size = max_risk * 0.1
        
        return max(min_size, position_size)
    
    async def staging_zones(self, market_id: str, market_data: Dict) -> List[StagingZone]:
        """
        Identify optimal entry zones for pre-positioning.
        
        Analyzes order book, recent trades, and price action
        to find high-probability entry zones.
        
        Args:
            market_id: Market to analyze
            market_data: Current market data
            
        Returns:
            List of staging zones sorted by confidence
        """
        zones = []
        
        current_price = market_data.get('yes_price', 0.5)
        spread = market_data.get('spread', 0.01)
        
        # Zone 1: Pullback zone (small discount)
        if current_price > 0.15:
            pullback_price = current_price - spread * 2
            zones.append(StagingZone(
                market_id=market_id,
                price_range=(pullback_price - 0.005, pullback_price + 0.005),
                confidence=75.0,
                rationale="Pullback entry for better risk/reward",
                risk_reward=2.0,
                timeframe=10
            ))
        
        # Zone 2: Breakout confirmation
        breakout_price = current_price + spread * 3
        zones.append(StagingZone(
            market_id=market_id,
            price_range=(breakout_price - 0.003, breakout_price + 0.003),
            confidence=65.0,
            rationale="Momentum breakout entry",
            risk_reward=1.5,
            timeframe=5
        ))
        
        # Zone 3: Support bounce (if we have level data)
        support = market_data.get('support_level')
        if support:
            zones.append(StagingZone(
                market_id=market_id,
                price_range=(support - 0.005, support + 0.005),
                confidence=70.0,
                rationale="Support level bounce",
                risk_reward=2.5,
                timeframe=15
            ))
        
        # Sort by confidence
        zones.sort(key=lambda z: z.confidence, reverse=True)
        
        return zones
    
    async def exit_prediction(
        self,
        whale_address: str,
        position_entry_price: float,
        position_side: str
    ) -> Dict[str, Any]:
        """
        Predict when whale will exit their position.
        
        Used to time our own exits.
        
        Args:
            whale_address: Target whale
            position_entry_price: Our entry price
            position_side: Our position side (YES/NO)
            
        Returns:
            Exit prediction details
        """
        whale_address = whale_address.lower()
        
        model = self.behavior_models.get(whale_address)
        if not model:
            return {'confidence': 'low', 'estimated_hold_time': 'unknown'}
        
        # Analyze historical hold times
        trades = self.db.get_whale_trade_history(whale_address, limit=50)
        hold_times = []
        
        for trade in trades:
            entry = trade.get('timestamp')
            exit_time = trade.get('exit_timestamp')
            if isinstance(entry, str):
                entry = datetime.fromisoformat(entry)
            if isinstance(exit_time, str):
                exit_time = datetime.fromisoformat(exit_time)
            if entry and exit_time:
                hold_times.append((exit_time - entry).total_seconds() / 60)
        
        avg_hold = np.mean(hold_times) if hold_times else 30
        
        # Estimate profit-taking levels
        if position_side == "YES":
            profit_target = position_entry_price * 1.1
            stop_level = position_entry_price * 0.95
        else:
            profit_target = position_entry_price * 0.9
            stop_level = position_entry_price * 1.05
        
        return {
            'confidence': 'medium' if len(hold_times) > 10 else 'low',
            'estimated_hold_time_minutes': avg_hold,
            'profit_target': profit_target,
            'stop_level': stop_level,
            'exit_signals_to_watch': ['position_reduction', 'market_exit', 'size_decrease']
        }
    
    # ========================================================================
    # Signal Detection
    # ========================================================================
    
    def on_wallet_activity(
        self,
        whale_address: str,
        activity_type: str,
        details: Optional[Dict] = None
    ):
        """
        Record wallet activity for pre-trade signal detection.
        
        Call this method when monitoring detects wallet activity.
        
        Args:
            whale_address: Wallet address
            activity_type: Type of activity
            details: Additional details
        """
        whale_address = whale_address.lower()
        
        activity = {
            'type': activity_type,
            'timestamp': datetime.now(),
            'details': details or {}
        }
        
        self.wallet_activity_buffer[whale_address].append(activity)
        
        logger.debug(f"Wallet activity recorded for {whale_address[:10]}: {activity_type}")
    
    def _detect_pre_trade_signals(self, whale_address: str) -> List[PreTradeSignal]:
        """Detect pre-trade signals from wallet activity."""
        signals = []
        activities = list(self.wallet_activity_buffer[whale_address])
        
        if not activities:
            return signals
        
        # Check recent activity (last 30 minutes)
        cutoff = datetime.now() - timedelta(minutes=30)
        recent = [a for a in activities if a['timestamp'] > cutoff]
        
        for activity in recent:
            activity_type = activity['type'].lower()
            
            if 'approve' in activity_type or 'approval' in activity_type:
                signals.append(PreTradeSignal.TOKEN_APPROVAL)
            elif 'fund' in activity_type or 'deposit' in activity_type:
                signals.append(PreTradeSignal.FUNDING_INCREASE)
            elif 'gas' in activity_type:
                signals.append(PreTradeSignal.GAS_ACQUISITION)
            elif 'bridge' in activity_type:
                signals.append(PreTradeSignal.BRIDGE_IN)
            elif 'withdraw' in activity_type or 'unstake' in activity_type:
                signals.append(PreTradeSignal.STAKE_WITHDRAWAL)
            elif 'cancel' in activity_type:
                signals.append(PreTradeSignal.LIMIT_ORDER_CANCEL)
        
        return list(set(signals))  # Remove duplicates
    
    async def _get_last_trade_time(self, whale_address: str) -> Optional[datetime]:
        """Get timestamp of whale's last trade."""
        trades = self.db.get_whale_trade_history(whale_address, limit=1)
        if trades:
            ts = trades[0].get('timestamp')
            if isinstance(ts, str):
                return datetime.fromisoformat(ts)
            return ts
        return None
    
    def _calculate_market_match(self, model: WhaleBehaviorModel, market_context: Dict) -> float:
        """Calculate how well current market matches whale's preferences."""
        score = 0.0
        checks = 0
        
        features = model.features
        
        # Liquidity match
        if 'liquidity' in market_context:
            liq = market_context['liquidity']
            if features.preferred_liquidity_range[0] <= liq <= features.preferred_liquidity_range[1]:
                score += 1.0
            checks += 1
        
        # Volume match
        if 'volume' in market_context:
            vol = market_context['volume']
            if features.preferred_volume_range[0] <= vol <= features.preferred_volume_range[1]:
                score += 1.0
            checks += 1
        
        # Price match
        if 'yes_price' in market_context:
            price = market_context['yes_price']
            if features.preferred_price_range[0] <= price <= features.preferred_price_range[1]:
                score += 1.0
            checks += 1
        
        return score / checks if checks > 0 else 0.5
    
    def _estimate_timeframe(self, model: WhaleBehaviorModel, signals: List[PreTradeSignal]) -> int:
        """Estimate prediction timeframe based on signals."""
        # Base timeframe
        base = self.DEFAULT_PREDICTION_WINDOW
        
        # Adjust based on preparation signals
        if PreTradeSignal.TOKEN_APPROVAL in signals:
            base = min(base, 10)  # Usually trades soon after approval
        
        if PreTradeSignal.BRIDGE_IN in signals:
            base = max(base, 20)  # May take time to settle and trade
        
        return base
    
    def _predict_direction(
        self,
        model: WhaleBehaviorModel,
        market_context: Dict
    ) -> PredictionDirection:
        """Predict trade direction based on model and context."""
        yes_prob = model.features.yes_bias
        
        # Adjust for current price
        if 'yes_price' in market_context:
            price = market_context['yes_price']
            
            # Contrarian adjustment
            if price > 0.7:
                yes_prob -= 0.15
            elif price < 0.3:
                yes_prob += 0.15
            
            # Momentum adjustment
            if 'price_change_24h' in market_context:
                change = market_context['price_change_24h']
                if change > 0:
                    yes_prob += model.features.momentum_following * 0.1
                else:
                    yes_prob -= model.features.momentum_following * 0.1
        
        yes_prob = max(0.1, min(0.9, yes_prob))
        
        if yes_prob > 0.55:
            return PredictionDirection.YES
        elif yes_prob < 0.45:
            return PredictionDirection.NO
        return PredictionDirection.UNKNOWN
    
    def _calculate_exit_levels(
        self,
        entry_price: float,
        direction: PredictionDirection
    ) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels."""
        if direction == PredictionDirection.YES:
            stop_loss = entry_price * (1 - self.prediction_stop_loss)
            take_profit = entry_price * (1 + self.prediction_stop_loss * 2)
        else:
            stop_loss = entry_price * (1 + self.prediction_stop_loss)
            take_profit = entry_price * (1 - self.prediction_stop_loss * 2)
        
        return round(stop_loss, 3), round(take_profit, 3)
    
    # ========================================================================
    # Prediction Monitoring & Confirmation
    # ========================================================================
    
    async def monitor_predictions(self):
        """
        Background task to monitor active predictions.
        
        Checks for:
        - Expired predictions
        - Whale entry confirmation
        - Position updates
        """
        while True:
            try:
                await self._check_prediction_status()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Prediction monitoring error: {e}")
                await asyncio.sleep(10)
    
    async def _check_prediction_status(self):
        """Check and update status of active predictions."""
        async with self._lock:
            current_time = datetime.now()
            
            for pred_id, prediction in list(self.active_predictions.items()):
                # Check expiration
                if prediction.is_expired():
                    prediction.status = PredictionStatus.EXPIRED
                    self.db.update_prediction_status(pred_id, PredictionStatus.EXPIRED)
                    
                    # Update stats
                    model = self.behavior_models.get(prediction.whale_address)
                    if model:
                        model.performance_metrics.expired_predictions += 1
                        model.performance_metrics.total_predictions += 1
                        model.performance_metrics.update_metrics()
                    
                    del self.active_predictions[pred_id]
                    logger.info(f"Prediction {pred_id[:8]} expired")
    
    async def on_whale_trade_detected(
        self,
        whale_address: str,
        market_id: str,
        side: str,
        size: float,
        trade_id: Optional[str] = None
    ):
        """
        Call when a whale trade is detected to check against predictions.
        
        Args:
            whale_address: Whale that traded
            market_id: Market traded
            side: Trade side (YES/NO)
            size: Trade size
            trade_id: Optional trade identifier
        """
        whale_address = whale_address.lower()
        
        async with self._lock:
            # Find matching prediction
            for pred_id, prediction in self.active_predictions.items():
                if (prediction.whale_address == whale_address and 
                    prediction.market_id == market_id):
                    
                    # Check direction match
                    predicted_dir = prediction.direction
                    actual_dir = PredictionDirection.YES if side.upper() == "YES" else PredictionDirection.NO
                    
                    is_correct = predicted_dir == actual_dir or predicted_dir == PredictionDirection.UNKNOWN
                    
                    if is_correct:
                        prediction.status = PredictionStatus.CONFIRMED
                        self.db.update_prediction_status(
                            pred_id, PredictionStatus.CONFIRMED, trade_id
                        )
                        
                        # Update model stats
                        model = self.behavior_models.get(whale_address)
                        if model:
                            model.performance_metrics.correct_predictions += 1
                            model.performance_metrics.total_predictions += 1
                            model.performance_metrics.update_metrics()
                        
                        logger.info(f"Prediction {pred_id[:8]} CONFIRMED for {whale_address[:10]}")
                        
                        # Update any pre-positions
                        for pos_id, position in self.pre_positions.items():
                            if position.prediction_id == pred_id:
                                position.whale_entry_observed = True
                                self.db.save_pre_position(position)
                        
                        # Notify callbacks
                        for callback in self._confirmation_callbacks:
                            try:
                                await callback(prediction, True)
                            except Exception as e:
                                logger.error(f"Confirmation callback error: {e}")
                    else:
                        prediction.status = PredictionStatus.INVALIDATED
                        self.db.update_prediction_status(pred_id, PredictionStatus.INVALIDATED)
                        
                        # Update model stats
                        model = self.behavior_models.get(whale_address)
                        if model:
                            model.performance_metrics.false_positives += 1
                            model.performance_metrics.total_predictions += 1
                            model.performance_metrics.update_metrics()
                        
                        logger.warning(f"Prediction {pred_id[:8]} INVALIDATED for {whale_address[:10]}")
                    
                    del self.active_predictions[pred_id]
                    return
    
    # ========================================================================
    # Risk Management
    # ========================================================================
    
    async def update_position_risk(self, position_id: str, current_price: float) -> Optional[str]:
        """
        Check position risk and return action if needed.
        
        Args:
            position_id: Position to check
            current_price: Current market price
            
        Returns:
            Action: 'hold', 'stop', 'profit', or 'time_exit'
        """
        position = self.pre_positions.get(position_id)
        if not position or position.status != "open":
            return None
        
        # Check stop loss
        if position.side == "YES":
            if current_price <= position.stop_loss:
                return "stop"
            if current_price >= position.take_profit:
                return "profit"
        else:  # NO
            if current_price >= position.stop_loss:
                return "stop"
            if current_price <= position.take_profit:
                return "profit"
        
        # Check time-based exit (if whale didn't enter)
        if not position.whale_entry_observed:
            time_in_position = (datetime.now() - position.entry_time).total_seconds() / 60
            
            # If prediction window passed and no whale entry, consider exit
            if time_in_position > self.DEFAULT_PREDICTION_WINDOW:
                pnl = position.calculate_pnl(current_price)
                
                # Exit at small loss or small profit if whale doesn't show
                if pnl < -position.size * 0.01:  # >1% loss
                    return "time_exit"
        
        return "hold"
    
    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "manual"
    ) -> bool:
        """
        Close a pre-position.
        
        Args:
            position_id: Position to close
            exit_price: Exit price
            reason: Exit reason
            
        Returns:
            True if successful
        """
        position = self.pre_positions.get(position_id)
        if not position:
            return False
        
        # Calculate P&L
        pnl = position.calculate_pnl(exit_price)
        
        position.exit_price = exit_price
        position.pnl = pnl
        position.exit_time = datetime.now()
        position.status = "closed"
        
        self.db.update_pre_position_exit(position_id, exit_price, pnl, reason)
        
        logger.info(f"Pre-position {position_id[:8]} closed: {reason}, P&L: ${pnl:.2f}")
        
        return True
    
    # ========================================================================
    # Callback Registration
    # ========================================================================
    
    def on_prediction(self, callback: Callable):
        """Register callback for new predictions."""
        self._prediction_callbacks.append(callback)
    
    def on_pre_position(self, callback: Callable):
        """Register callback for new pre-positions."""
        self._pre_position_callbacks.append(callback)
    
    def on_confirmation(self, callback: Callable):
        """Register callback for prediction confirmations."""
        self._confirmation_callbacks.append(callback)
    
    # ========================================================================
    # Statistics & Reporting
    # ========================================================================
    
    def get_prediction_stats(self, whale_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get prediction statistics.
        
        Args:
            whale_address: Optional whale to filter by
            
        Returns:
            Statistics dictionary
        """
        if whale_address:
            model = self.behavior_models.get(whale_address.lower())
            if model:
                return asdict(model.performance_metrics)
            return {}
        
        # Aggregate stats across all whales
        all_stats = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'false_positives': 0,
            'expired_predictions': 0,
            'overall_accuracy': 0.0,
            'avg_confidence': 0.0,
            'active_predictions': len(self.active_predictions),
            'open_pre_positions': len([p for p in self.pre_positions.values() if p.status == "open"])
        }
        
        confidences = []
        for model in self.behavior_models.values():
            stats = model.performance_metrics
            all_stats['total_predictions'] += stats.total_predictions
            all_stats['correct_predictions'] += stats.correct_predictions
            all_stats['false_positives'] += stats.false_positives
            all_stats['expired_predictions'] += stats.expired_predictions
        
        for pred in self.active_predictions.values():
            confidences.append(pred.confidence)
        
        if all_stats['total_predictions'] > 0:
            all_stats['overall_accuracy'] = (
                all_stats['correct_predictions'] / all_stats['total_predictions']
            )
        
        if confidences:
            all_stats['avg_confidence'] = np.mean(confidences)
        
        return all_stats
    
    def get_active_predictions_report(self) -> str:
        """Generate a formatted report of active predictions."""
        lines = [
            "=" * 60,
            "ACTIVE PREDICTIONS REPORT",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Active Predictions: {len(self.active_predictions)}",
            f"Open Pre-Positions: {len([p for p in self.pre_positions.values() if p.status == 'open'])}",
            "-" * 60
        ]
        
        for pred in sorted(self.active_predictions.values(), 
                          key=lambda p: p.confidence, reverse=True):
            time_left = pred.time_remaining_minutes()
            decayed_conf = pred.confidence_decayed()
            
            lines.append(f"\nPrediction: {pred.prediction_id[:8]}")
            lines.append(f"  Whale: {pred.whale_address[:12]}...")
            lines.append(f"  Market: {pred.market_id[:20]}...")
            lines.append(f"  Direction: {pred.direction.value}")
            lines.append(f"  Confidence: {pred.confidence:.1f}% (decayed: {decayed_conf:.1f}%)")
            lines.append(f"  Time Remaining: {time_left:.1f} min")
            lines.append(f"  Expected Size: ${pred.expected_size:,.0f}")
            lines.append(f"  Signals: {', '.join(s.value for s in pred.signals)}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    # ========================================================================
    # Model Persistence
    # ========================================================================
    
    async def load_all_models(self):
        """Load all saved behavior models from database."""
        # This would query the database for all whale models
        # For now, models are loaded on-demand
        logger.info("Models will be loaded on-demand")
    
    async def save_all_models(self):
        """Save all behavior models to database."""
        for model in self.behavior_models.values():
            self.db.save_whale_behavior_model(model)
        logger.info(f"Saved {len(self.behavior_models)} behavior models")


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_prediction_system(
    config: Optional[Config] = None,
    database: Optional[TradeDatabase] = None
) -> PredictiveEntrySystem:
    """
    Create and initialize a PredictiveEntrySystem.
    
    Args:
        config: Optional configuration
        database: Optional database instance
        
    Returns:
        Initialized PredictiveEntrySystem
    """
    db = PredictiveEntryDatabase(database)
    system = PredictiveEntrySystem(config, db)
    await system.load_all_models()
    return system


async def quick_predict(
    whale_address: str,
    market_context: Optional[Dict] = None
) -> Optional[PredictionSignal]:
    """
    Quick prediction without managing full system state.
    
    Args:
        whale_address: Whale to predict
        market_context: Optional market context
        
    Returns:
        Prediction if made
    """
    system = await create_prediction_system()
    return await system.predict_next_trade(whale_address, market_context)


async def train_whale_models(whale_addresses: List[str]) -> Dict[str, bool]:
    """
    Train behavior models for multiple whales.
    
    Args:
        whale_addresses: List of whale addresses
        
    Returns:
        Dictionary mapping addresses to success status
    """
    system = await create_prediction_system()
    results = {}
    
    for address in whale_addresses:
        model = await system.train_whale_model(address)
        results[address] = model is not None
    
    return results
