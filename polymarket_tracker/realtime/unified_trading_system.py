"""
Unified Real-Time Trading System for Polymarket

Orchestrates ALL real-time components into one high-performance trading engine.

Signal Flow:
-----------
WebSocket Trade → Blockchain Confirm → Detection (10-100ms)
     ↓
Pattern Analysis → Prediction Check → Signal Generation (1-5ms)
     ↓
Risk Check → Route Selection → Order Preparation (1-2ms)
     ↓
Order Submission → Fill Confirmation (50-500ms)
     ↓
Notification → Database Logging → Analytics Update

Architecture:
------------
┌─────────────────────────────────────────────────────────────────────┐
│                    UNIFIED TRADING SYSTEM                           │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   WebSocket  │  │  Blockchain  │  │   Predictive Entry       │  │
│  │    Client    │  │   Monitor    │  │       System             │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘  │
│         │                 │                      │                 │
│         └─────────────────┼──────────────────────┘                 │
│                           ▼                                        │
│              ┌────────────────────────┐                            │
│              │   PRIORITY SIGNAL      │                            │
│              │       QUEUE            │                            │
│              │  (whale > arb > pred)  │                            │
│              └───────────┬────────────┘                            │
│                          ▼                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              SIGNAL PROCESSING PIPELINE                     │   │
│  │  ┌─────────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐   │   │
│  │  │   Pattern   │→│ Prediction│→│  Risk  │→│  Route   │   │   │
│  │  │   Analysis  │  │  Check   │  │ Check  │  │ Selection│   │   │
│  │  └─────────────┘  └──────────┘  └────────┘  └────┬─────┘   │   │
│  │                                                  │         │   │
│  │  ┌───────────────────────────────────────────────┘         │   │
│  │  │                                                          │   │
│  │  ▼                                                          │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │          ULTRA-LOW LATENCY EXECUTOR                     │ │   │
│  │  │     ┌─────────────┐  ┌────────────┐  ┌──────────┐      │ │   │
│  │  │     │  Sniper     │  │   Smart    │  │ Arbitrage│      │ │   │
│  │  │     │   Entry     │  │   Router   │  │ Detector │      │ │   │
│  │  │     └─────────────┘  └────────────┘  └──────────┘      │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                           │                                        │
│                           ▼                                        │
│              ┌────────────────────────┐                            │
│              │   NOTIFICATION MGR     │                            │
│              │   + DATABASE LOGGING   │                            │
│              └────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘

Usage:
    >>> from polymarket_tracker.realtime import UnifiedRealTimeTradingSystem
    >>> 
    >>> # Initialize system
    >>> system = UnifiedRealTimeTradingSystem(
    ...     mode=TradingMode.PAPER,
    ...     speed=SpeedMode.BALANCED,
    ...     risk=RiskProfile.MODERATE
    ... )
    >>> 
    >>> # Start all components
    >>> await system.start()
    >>> 
    >>> # Monitor status
    >>> status = await system.get_status()
    >>> print(f"System health: {status.health}")
    >>> 
    >>> # Emergency stop if needed
    >>> await system.emergency_stop()

Author: Claude
"""

import asyncio
import logging
import time
import threading
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple, Union
from collections import deque
from queue import PriorityQueue
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime, timedelta
import heapq

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class TradingMode(Enum):
    """Trading operation modes."""
    PAPER = "paper"           # Simulated trading, no real money
    LIVE = "live"             # Real money trading
    BACKTEST = "backtest"     # Historical simulation
    SIMULATION = "simulation" # Real-time simulation with paper feeds


class SpeedMode(Enum):
    """Execution speed optimization modes."""
    ULTRA = "ultra"       # Minimum latency, max gas, direct routes
    BALANCED = "balanced" # Optimal speed/cost ratio
    ECONOMY = "economy"   # Minimum cost, patient execution


class RiskProfile(Enum):
    """Risk management profiles."""
    CONSERVATIVE = "conservative"  # Low risk, smaller positions
    MODERATE = "moderate"          # Balanced risk/reward
    AGGRESSIVE = "aggressive"      # Higher risk, larger positions


class SignalPriority(Enum):
    """Signal processing priorities (lower = higher priority)."""
    WHALE_URGENT = 1      # Large whale move, immediate action
    WHALE_NORMAL = 2      # Standard whale signal
    ARBITRAGE = 3         # Arbitrage opportunity
    PREDICTION = 4        # Predictive entry signal
    BLOCKCHAIN = 5        # Blockchain event
    WEBSOCKET = 6         # Standard WebSocket update


class SystemState(Enum):
    """Overall system state."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ComponentState(Enum):
    """Individual component states."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"
    DEGRADED = "degraded"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Signal:
    """Trading signal with priority."""
    priority: SignalPriority
    timestamp: float
    signal_type: str
    data: Dict[str, Any]
    source: str
    market_id: Optional[str] = None
    confidence: float = 0.0
    expected_profit: float = 0.0
    max_latency_ms: float = 100.0
    
    # For priority queue comparison
    def __lt__(self, other: 'Signal') -> bool:
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.timestamp < other.timestamp


@dataclass  
class SystemStatus:
    """Complete system status."""
    state: SystemState
    component_states: Dict[str, ComponentState]
    health: str  # "healthy", "degraded", "critical"
    uptime_seconds: float
    active_signals: int
    processed_signals: int
    errors_last_minute: int
    timestamp: float


@dataclass
class LatencyStats:
    """Latency statistics."""
    detection_ms: float = 0.0
    analysis_ms: float = 0.0
    risk_check_ms: float = 0.0
    routing_ms: float = 0.0
    execution_ms: float = 0.0
    total_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "detection_ms": self.detection_ms,
            "analysis_ms": self.analysis_ms,
            "risk_check_ms": self.risk_check_ms,
            "routing_ms": self.routing_ms,
            "execution_ms": self.execution_ms,
            "total_ms": self.total_ms
        }


@dataclass
class ThroughputStats:
    """Throughput statistics."""
    signals_per_second: float = 0.0
    trades_per_second: float = 0.0
    messages_per_second: float = 0.0
    peak_signals_ps: float = 0.0
    peak_trades_ps: float = 0.0


@dataclass
class PerformanceMetrics:
    """Complete performance metrics."""
    latency_stats: LatencyStats = field(default_factory=LatencyStats)
    throughput_stats: ThroughputStats = field(default_factory=ThroughputStats)
    error_rates: Dict[str, float] = field(default_factory=dict)
    component_latencies: Dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class TradingConfig:
    """Trading system configuration."""
    mode: TradingMode = TradingMode.PAPER
    speed: SpeedMode = SpeedMode.BALANCED
    risk: RiskProfile = RiskProfile.MODERATE
    
    # Feature toggles
    enable_websocket: bool = True
    enable_blockchain: bool = True
    enable_prediction: bool = True
    enable_arbitrage: bool = True
    enable_notifications: bool = True
    enable_auto_trading: bool = False
    
    # Performance settings
    max_signal_queue_size: int = 10000
    max_execution_queue_size: int = 1000
    signal_processing_threads: int = 4
    execution_threads: int = 2
    
    # Risk settings
    max_position_size: float = 10000.0
    max_daily_loss: float = 1000.0
    max_concurrent_trades: int = 10
    
    # Latency targets (ms)
    target_detection_ms: float = 50.0
    target_analysis_ms: float = 5.0
    target_routing_ms: float = 2.0
    target_execution_ms: float = 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "speed": self.speed.value,
            "risk": self.risk.value,
            "features": {
                "websocket": self.enable_websocket,
                "blockchain": self.enable_blockchain,
                "prediction": self.enable_prediction,
                "arbitrage": self.enable_arbitrage,
                "notifications": self.enable_notifications,
                "auto_trading": self.enable_auto_trading,
            },
            "limits": {
                "max_position": self.max_position_size,
                "max_daily_loss": self.max_daily_loss,
                "max_concurrent": self.max_concurrent_trades,
            }
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    state: ComponentState
    latency_ms: float
    error_rate: float
    last_heartbeat: float
    message: str = ""
    
    @property
    def is_healthy(self) -> bool:
        return self.state == ComponentState.RUNNING and self.error_rate < 0.01


# =============================================================================
# COMPONENT INTERFACES (Abstract base classes for type hints)
# =============================================================================

class ComponentInterface:
    """Base interface for all system components."""
    
    async def start(self) -> bool:
        raise NotImplementedError
    
    async def stop(self) -> bool:
        raise NotImplementedError
    
    async def get_health(self) -> ComponentHealth:
        raise NotImplementedError
    
    async def pause(self) -> bool:
        raise NotImplementedError
    
    async def resume(self) -> bool:
        raise NotImplementedError


# =============================================================================
# PLACEHOLDER CLASSES (Will be replaced with actual imports)
# =============================================================================

class WebSocketClientWrapper:
    """Wrapper for PolymarketWebSocketClient."""
    
    def __init__(self):
        self.state = ComponentState.STOPPED
        self._client = None
        self._message_handler: Optional[Callable] = None
        
    async def start(self, message_handler: Callable) -> bool:
        """Start WebSocket client."""
        try:
            from .websocket_client import PolymarketWebSocketClient
            self._message_handler = message_handler
            self._client = PolymarketWebSocketClient()
            # Set up callbacks
            self._client.on_trade = self._on_trade
            self._client.on_orderbook = self._on_orderbook
            await self._client.connect()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start WebSocket client: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        if self._client:
            await self._client.disconnect()
        self.state = ComponentState.STOPPED
        return True
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="websocket_client",
            state=self.state,
            latency_ms=10.0,  # Approximate
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Running" if self.state == ComponentState.RUNNING else "Stopped"
        )
    
    def _on_trade(self, trade_data: Dict):
        if self._message_handler:
            asyncio.create_task(self._message_handler("trade", trade_data))
    
    def _on_orderbook(self, book_data: Dict):
        if self._message_handler:
            asyncio.create_task(self._message_handler("orderbook", book_data))


class BlockchainMonitorWrapper:
    """Wrapper for BlockchainMonitor."""
    
    def __init__(self):
        self.state = ComponentState.STOPPED
        self._monitor = None
        self._event_handler: Optional[Callable] = None
        
    async def start(self, event_handler: Callable) -> bool:
        """Start blockchain monitor."""
        try:
            from .blockchain_monitor import BlockchainMonitor
            self._event_handler = event_handler
            self._monitor = BlockchainMonitor()
            # Set up callbacks
            self._monitor.on_event = self._on_event
            await self._monitor.start()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start blockchain monitor: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        if self._monitor:
            await self._monitor.stop()
        self.state = ComponentState.STOPPED
        return True
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="blockchain_monitor",
            state=self.state,
            latency_ms=50.0,  # Block time
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Running" if self.state == ComponentState.RUNNING else "Stopped"
        )
    
    def _on_event(self, event: Any):
        if self._event_handler:
            asyncio.create_task(self._event_handler(event))


class LatencyExecutorWrapper:
    """Wrapper for UltraLowLatencyExecutor."""
    
    def __init__(self, config: TradingConfig):
        self.state = ComponentState.STOPPED
        self._executor = None
        self.config = config
        
    async def start(self) -> bool:
        """Start latency executor."""
        try:
            from .latency_executor import UltraLowLatencyExecutor
            self._executor = UltraLowLatencyExecutor()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start latency executor: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        self.state = ComponentState.STOPPED
        return True
    
    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """Execute a trading signal."""
        if not self._executor:
            return {"success": False, "error": "Executor not initialized"}
        
        start_time = time.time()
        
        # Convert signal to execution format
        # This is simplified - real implementation would be more complex
        result = {
            "success": True,
            "signal_id": id(signal),
            "execution_time_ms": (time.time() - start_time) * 1000,
            "mode": self.config.mode.value
        }
        
        return result
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="latency_executor",
            state=self.state,
            latency_ms=50.0,
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Ready" if self.state == ComponentState.RUNNING else "Stopped"
        )


class SmartRouterWrapper:
    """Wrapper for SmartOrderRouter."""
    
    def __init__(self, config: TradingConfig):
        self.state = ComponentState.STOPPED
        self._router = None
        self.config = config
        
    async def start(self) -> bool:
        """Start smart router."""
        try:
            from .smart_router import SmartOrderRouter
            self._router = SmartOrderRouter()
            await self._router.start()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start smart router: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        if self._router:
            await self._router.stop()
        self.state = ComponentState.STOPPED
        return True
    
    async def route_order(self, signal: Signal) -> Dict[str, Any]:
        """Route an order."""
        return {"route": "direct", "estimated_gas": 50000}
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="smart_router",
            state=self.state,
            latency_ms=5.0,
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Running" if self.state == ComponentState.RUNNING else "Stopped"
        )


class ArbitrageDetectorWrapper:
    """Wrapper for ArbitrageDetector."""
    
    def __init__(self):
        self.state = ComponentState.STOPPED
        self._detector = None
        self._opportunity_handler: Optional[Callable] = None
        
    async def start(self, opportunity_handler: Callable) -> bool:
        """Start arbitrage detector."""
        try:
            from .arbitrage_detector import ArbitrageDetector
            self._opportunity_handler = opportunity_handler
            self._detector = ArbitrageDetector()
            # Set up callback
            self._detector.on_opportunity = self._on_opportunity
            await self._detector.start()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start arbitrage detector: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        if self._detector:
            await self._detector.stop()
        self.state = ComponentState.STOPPED
        return True
    
    def _on_opportunity(self, opportunity: Dict):
        if self._opportunity_handler:
            asyncio.create_task(self._opportunity_handler(opportunity))
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="arbitrage_detector",
            state=self.state,
            latency_ms=20.0,
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Scanning" if self.state == ComponentState.RUNNING else "Stopped"
        )


class PredictiveSystemWrapper:
    """Wrapper for PredictiveEntrySystem."""
    
    def __init__(self):
        self.state = ComponentState.STOPPED
        self._system = None
        self._signal_handler: Optional[Callable] = None
        
    async def start(self, signal_handler: Callable) -> bool:
        """Start predictive system."""
        try:
            from .predictive_entry import PredictiveEntrySystem
            self._signal_handler = signal_handler
            self._system = PredictiveEntrySystem()
            # Set up callback
            self._system.on_signal = self._on_signal
            await self._system.start()
            self.state = ComponentState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start predictive system: {e}")
            self.state = ComponentState.ERROR
            return False
    
    async def stop(self) -> bool:
        if self._system:
            await self._system.stop()
        self.state = ComponentState.STOPPED
        return True
    
    def _on_signal(self, signal_data: Dict):
        if self._signal_handler:
            asyncio.create_task(self._signal_handler(signal_data))
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="predictive_system",
            state=self.state,
            latency_ms=2.0,
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Predicting" if self.state == ComponentState.RUNNING else "Stopped"
        )


class NotificationManager:
    """Manages notifications and alerts."""
    
    def __init__(self):
        self.state = ComponentState.STOPPED
        self._handlers: List[Callable] = []
        
    async def start(self) -> bool:
        self.state = ComponentState.RUNNING
        return True
    
    async def stop(self) -> bool:
        self.state = ComponentState.STOPPED
        return True
    
    def add_handler(self, handler: Callable):
        self._handlers.append(handler)
    
    async def notify(self, level: str, message: str, data: Dict = None):
        """Send notification."""
        notification = {
            "level": level,
            "message": message,
            "data": data or {},
            "timestamp": time.time()
        }
        
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(notification)
                else:
                    handler(notification)
            except Exception as e:
                logger.error(f"Notification handler error: {e}")
    
    async def get_health(self) -> ComponentHealth:
        return ComponentHealth(
            name="notification_manager",
            state=self.state,
            latency_ms=1.0,
            error_rate=0.0,
            last_heartbeat=time.time(),
            message="Active" if self.state == ComponentState.RUNNING else "Stopped"
        )


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitBreakerManager:
    """Manages circuit breakers for components."""
    
    def __init__(self):
        self._breakers: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        
    async def check(self, component: str) -> bool:
        """Check if component can operate."""
        async with self._lock:
            if component not in self._breakers:
                return True
            
            breaker = self._breakers[component]
            if breaker["open"]:
                if time.time() - breaker["opened_at"] > breaker["timeout"]:
                    breaker["open"] = False
                    breaker["failures"] = 0
                    logger.info(f"Circuit breaker reset for {component}")
                    return True
                return False
            return True
    
    async def record_failure(self, component: str):
        """Record a component failure."""
        async with self._lock:
            if component not in self._breakers:
                self._breakers[component] = {
                    "open": False,
                    "failures": 0,
                    "threshold": 5,
                    "timeout": 60,
                    "opened_at": 0
                }
            
            breaker = self._breakers[component]
            breaker["failures"] += 1
            
            if breaker["failures"] >= breaker["threshold"]:
                breaker["open"] = True
                breaker["opened_at"] = time.time()
                logger.warning(f"Circuit breaker OPENED for {component}")
    
    async def record_success(self, component: str):
        """Record a component success."""
        async with self._lock:
            if component in self._breakers:
                self._breakers[component]["failures"] = max(
                    0, self._breakers[component]["failures"] - 1
                )
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            name: {
                "open": data["open"],
                "failures": data["failures"]
            }
            for name, data in self._breakers.items()
        }


# =============================================================================
# METRICS COLLECTOR
# =============================================================================

class MetricsCollector:
    """Collects and aggregates performance metrics."""
    
    def __init__(self, window_seconds: int = 60):
        self._latency_history: deque = deque(maxlen=10000)
        self._throughput_counters: Dict[str, List[Tuple[float, int]]] = {
            "signals": [],
            "trades": [],
            "messages": []
        }
        self._error_counts: Dict[str, int] = {}
        self._window_seconds = window_seconds
        self._lock = asyncio.Lock()
        
    async def record_latency(self, stage: str, latency_ms: float):
        """Record a latency measurement."""
        async with self._lock:
            self._latency_history.append({
                "stage": stage,
                "latency_ms": latency_ms,
                "timestamp": time.time()
            })
    
    async def record_throughput(self, counter_type: str, count: int = 1):
        """Record throughput."""
        async with self._lock:
            now = time.time()
            self._throughput_counters[counter_type].append((now, count))
            # Clean old entries
            cutoff = now - self._window_seconds
            self._throughput_counters[counter_type] = [
                (t, c) for t, c in self._throughput_counters[counter_type]
                if t > cutoff
            ]
    
    async def record_error(self, component: str):
        """Record an error."""
        async with self._lock:
            self._error_counts[component] = self._error_counts.get(component, 0) + 1
    
    async def get_metrics(self) -> PerformanceMetrics:
        """Get current metrics."""
        async with self._lock:
            # Calculate latency stats
            latencies = {}
            for entry in self._latency_history:
                stage = entry["stage"]
                if stage not in latencies:
                    latencies[stage] = []
                latencies[stage].append(entry["latency_ms"])
            
            latency_stats = LatencyStats()
            if "detection" in latencies:
                latency_stats.detection_ms = sum(latencies["detection"]) / len(latencies["detection"])
            if "analysis" in latencies:
                latency_stats.analysis_ms = sum(latencies["analysis"]) / len(latencies["analysis"])
            if "risk_check" in latencies:
                latency_stats.risk_check_ms = sum(latencies["risk_check"]) / len(latencies["risk_check"])
            if "routing" in latencies:
                latency_stats.routing_ms = sum(latencies["routing"]) / len(latencies["routing"])
            if "execution" in latencies:
                latency_stats.execution_ms = sum(latencies["execution"]) / len(latencies["execution"])
            
            latency_stats.total_ms = (
                latency_stats.detection_ms +
                latency_stats.analysis_ms +
                latency_stats.risk_check_ms +
                latency_stats.routing_ms +
                latency_stats.execution_ms
            )
            
            # Calculate throughput
            throughput = ThroughputStats()
            now = time.time()
            for counter_type, entries in self._throughput_counters.items():
                total = sum(c for t, c in entries if now - t < 1.0)
                if counter_type == "signals":
                    throughput.signals_per_second = total
                elif counter_type == "trades":
                    throughput.trades_per_second = total
                elif counter_type == "messages":
                    throughput.messages_per_second = total
            
            # Calculate error rates
            total_errors = sum(self._error_counts.values())
            error_rates = {
                comp: count / max(1, len(self._latency_history)) * 100
                for comp, count in self._error_counts.items()
            }
            
            return PerformanceMetrics(
                latency_stats=latency_stats,
                throughput_stats=throughput,
                error_rates=error_rates,
                component_latencies=latencies,
                timestamp=time.time()
            )


# =============================================================================
# STATE MANAGER
# =============================================================================

class StateManager:
    """Manages system state across hot (memory), warm (SQLite), and cold (PostgreSQL) storage."""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self._hot_state: Dict[str, Any] = {}
        self._warm_db_path = "trading_state.db"
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize state storage."""
        # Initialize SQLite for warm state
        import sqlite3
        conn = sqlite3.connect(self._warm_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)
        conn.commit()
        conn.close()
        logger.info("State manager initialized")
    
    async def get_hot(self, key: str, default=None) -> Any:
        """Get hot state (memory)."""
        return self._hot_state.get(key, default)
    
    async def set_hot(self, key: str, value: Any):
        """Set hot state."""
        self._hot_state[key] = value
    
    async def get_warm(self, key: str) -> Optional[Any]:
        """Get warm state (SQLite)."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._warm_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM state WHERE key = ?", (key,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
            return None
        except Exception as e:
            logger.error(f"Error reading warm state: {e}")
            return None
    
    async def set_warm(self, key: str, value: Any):
        """Set warm state."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._warm_db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), time.time())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error writing warm state: {e}")
    
    async def sync_hot_to_warm(self, keys: List[str]):
        """Sync hot state to warm storage."""
        for key in keys:
            value = self._hot_state.get(key)
            if value is not None:
                await self.set_warm(key, value)


# =============================================================================
# MAIN UNIFIED TRADING SYSTEM
# =============================================================================

class UnifiedRealTimeTradingSystem:
    """
    Unified Real-Time Trading System for Polymarket.
    
    Orchestrates all real-time components into one high-performance trading engine.
    
    Components:
    - WebSocket Client (CLOB data)
    - Blockchain Monitor (Polygon events)
    - Ultra-Low Latency Executor
    - Predictive Entry System
    - Arbitrage Detector
    - Smart Order Router
    - Notification Manager
    
    Usage:
        >>> system = UnifiedRealTimeTradingSystem(
        ...     mode=TradingMode.PAPER,
        ...     speed=SpeedMode.BALANCED,
        ...     risk=RiskProfile.MODERATE
        ... )
        >>> 
        >>> # Start all components
        >>> await system.start()
        >>> 
        >>> # Get status
        >>> status = await system.get_status()
        >>> print(f"Health: {status.health}")
        >>> 
        >>> # Stop gracefully
        >>> await system.stop()
    """
    
    def __init__(
        self,
        mode: TradingMode = TradingMode.PAPER,
        speed: SpeedMode = SpeedMode.BALANCED,
        risk: RiskProfile = RiskProfile.MODERATE,
        custom_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the unified trading system.
        
        Args:
            mode: Trading mode (PAPER, LIVE, BACKTEST, SIMULATION)
            speed: Speed optimization mode (ULTRA, BALANCED, ECONOMY)
            risk: Risk profile (CONSERVATIVE, MODERATE, AGGRESSIVE)
            custom_config: Optional custom configuration overrides
        """
        # Configuration
        self.config = TradingConfig(mode=mode, speed=speed, risk=risk)
        if custom_config:
            for key, value in custom_config.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
        
        # System state
        self._state = SystemState.INITIALIZING
        self._start_time: Optional[float] = None
        self._shutdown_event = asyncio.Event()
        
        # Components
        self._websocket: Optional[WebSocketClientWrapper] = None
        self._blockchain: Optional[BlockchainMonitorWrapper] = None
        self._executor: Optional[LatencyExecutorWrapper] = None
        self._router: Optional[SmartRouterWrapper] = None
        self._arbitrage: Optional[ArbitrageDetectorWrapper] = None
        self._predictive: Optional[PredictiveSystemWrapper] = None
        self._notifications: Optional[NotificationManager] = None
        
        # Support systems
        self._circuit_breaker = CircuitBreakerManager()
        self._metrics = MetricsCollector()
        self._state_manager = StateManager(self.config)
        
        # Signal processing
        self._signal_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.config.max_signal_queue_size
        )
        self._execution_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.config.max_execution_queue_size
        )
        self._processed_signals = 0
        self._active_signals: Set[int] = set()
        
        # Threading
        self._executor_pool = ThreadPoolExecutor(
            max_workers=self.config.signal_processing_threads
        )
        self._processing_tasks: List[asyncio.Task] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._error_count = 0
        self._last_errors: deque = deque(maxlen=100)
        
        logger.info(f"UnifiedTradingSystem initialized: {mode.value}/{speed.value}/{risk.value}")
    
    # ======================================================================
    # LIFECYCLE METHODS
    # ======================================================================
    
    async def start(self) -> bool:
        """
        Start all components and begin processing.
        
        Returns:
            True if startup successful, False otherwise
        """
        if self._state == SystemState.RUNNING:
            logger.warning("System already running")
            return True
        
        self._state = SystemState.INITIALIZING
        self._start_time = time.time()
        
        try:
            logger.info("Starting Unified Trading System...")
            
            # Initialize state manager
            await self._state_manager.initialize()
            
            # Start notification manager first
            self._notifications = NotificationManager()
            await self._notifications.start()
            await self._notifications.notify(
                "info", "Trading system starting", self.config.to_dict()
            )
            
            # Start components based on configuration
            success = True
            
            if self.config.enable_websocket:
                self._websocket = WebSocketClientWrapper()
                if not await self._websocket.start(self._handle_websocket_message):
                    logger.error("Failed to start WebSocket client")
                    success = False
            
            if self.config.enable_blockchain:
                self._blockchain = BlockchainMonitorWrapper()
                if not await self._blockchain.start(self._handle_blockchain_event):
                    logger.error("Failed to start blockchain monitor")
                    success = False
            
            # Core execution components
            self._executor = LatencyExecutorWrapper(self.config)
            if not await self._executor.start():
                logger.error("Failed to start latency executor")
                success = False
            
            self._router = SmartRouterWrapper(self.config)
            if not await self._router.start():
                logger.error("Failed to start smart router")
                success = False
            
            if self.config.enable_arbitrage:
                self._arbitrage = ArbitrageDetectorWrapper()
                if not await self._arbitrage.start(self._handle_arbitrage_opportunity):
                    logger.error("Failed to start arbitrage detector")
                    success = False
            
            if self.config.enable_prediction:
                self._predictive = PredictiveSystemWrapper()
                if not await self._predictive.start(self._handle_prediction_signal):
                    logger.error("Failed to start predictive system")
                    success = False
            
            if not success:
                logger.error("Some components failed to start")
                await self._notifications.notify(
                    "error", "Some components failed to start"
                )
                # Continue with degraded operation
            
            # Start processing pipelines
            await self._start_processing_pipelines()
            
            # Start monitoring
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            self._state = SystemState.RUNNING
            self._shutdown_event.clear()
            
            await self._notifications.notify(
                "info", "Trading system started successfully"
            )
            
            logger.info("Unified Trading System started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")
            self._state = SystemState.ERROR
            await self._notifications.notify("error", f"Startup failed: {str(e)}")
            return False
    
    async def stop(self, timeout: float = 30.0) -> bool:
        """
        Graceful shutdown of all components.
        
        Args:
            timeout: Maximum time to wait for shutdown
            
        Returns:
            True if shutdown successful
        """
        if self._state in (SystemState.STOPPED, SystemState.STOPPING):
            return True
        
        logger.info("Stopping Unified Trading System...")
        self._state = SystemState.STOPPING
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Cancel processing tasks
            for task in self._processing_tasks:
                task.cancel()
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
            
            # Wait for queues to drain
            try:
                await asyncio.wait_for(
                    self._drain_queues(),
                    timeout=timeout * 0.5
                )
            except asyncio.TimeoutError:
                logger.warning("Queue drain timeout")
            
            # Stop components in reverse order
            components = [
                ("predictive", self._predictive),
                ("arbitrage", self._arbitrage),
                ("router", self._router),
                ("executor", self._executor),
                ("blockchain", self._blockchain),
                ("websocket", self._websocket),
                ("notifications", self._notifications),
            ]
            
            for name, component in components:
                if component:
                    try:
                        await asyncio.wait_for(component.stop(), timeout=5.0)
                        logger.debug(f"Stopped {name}")
                    except Exception as e:
                        logger.error(f"Error stopping {name}: {e}")
            
            # Shutdown thread pool
            self._executor_pool.shutdown(wait=False)
            
            self._state = SystemState.STOPPED
            logger.info("Unified Trading System stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            self._state = SystemState.ERROR
            return False
    
    async def pause(self) -> bool:
        """
        Pause trading (keep connections, stop processing).
        
        Returns:
            True if paused successfully
        """
        if self._state != SystemState.RUNNING:
            logger.warning(f"Cannot pause from state: {self._state}")
            return False
        
        self._state = SystemState.PAUSED
        
        # Pause processing but keep connections
        for task in self._processing_tasks:
            # Tasks check state and will pause
            pass
        
        await self._notifications.notify("warning", "Trading paused")
        logger.info("Trading paused")
        return True
    
    async def resume(self) -> bool:
        """
        Resume trading from pause.
        
        Returns:
            True if resumed successfully
        """
        if self._state != SystemState.PAUSED:
            logger.warning(f"Cannot resume from state: {self._state}")
            return False
        
        self._state = SystemState.RUNNING
        await self._notifications.notify("info", "Trading resumed")
        logger.info("Trading resumed")
        return True
    
    async def emergency_stop(self) -> bool:
        """
        Immediate halt of all trading activity.
        
        Returns:
            True if emergency stop executed
        """
        logger.critical("EMERGENCY STOP TRIGGERED")
        
        self._state = SystemState.STOPPING
        
        # Cancel all tasks immediately
        for task in self._processing_tasks:
            task.cancel()
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        # Stop executor immediately
        if self._executor:
            await self._executor.stop()
        
        await self._notifications.notify(
            "critical", "EMERGENCY STOP - All trading halted"
        )
        
        self._state = SystemState.STOPPED
        return True
    
    # ======================================================================
    # STATUS AND METRICS
    # ======================================================================
    
    async def get_status(self) -> SystemStatus:
        """
        Get complete system status.
        
        Returns:
            SystemStatus with all component states
        """
        component_states = {}
        
        components = [
            ("websocket", self._websocket),
            ("blockchain", self._blockchain),
            ("executor", self._executor),
            ("router", self._router),
            ("arbitrage", self._arbitrage),
            ("predictive", self._predictive),
            ("notifications", self._notifications),
        ]
        
        for name, component in components:
            if component:
                try:
                    health = await component.get_health()
                    component_states[name] = health.state
                except Exception as e:
                    component_states[name] = ComponentState.ERROR
            else:
                component_states[name] = ComponentState.STOPPED
        
        # Determine overall health
        running_count = sum(1 for s in component_states.values() if s == ComponentState.RUNNING)
        total_count = len(component_states)
        
        if running_count == total_count:
            health = "healthy"
        elif running_count >= total_count * 0.7:
            health = "degraded"
        else:
            health = "critical"
        
        uptime = time.time() - self._start_time if self._start_time else 0
        
        return SystemStatus(
            state=self._state,
            component_states={k: v.value for k, v in component_states.items()},
            health=health,
            uptime_seconds=uptime,
            active_signals=len(self._active_signals),
            processed_signals=self._processed_signals,
            errors_last_minute=sum(1 for e in self._last_errors 
                                   if time.time() - e < 60),
            timestamp=time.time()
        )
    
    async def get_metrics(self) -> PerformanceMetrics:
        """
        Get performance metrics.
        
        Returns:
            PerformanceMetrics with latency, throughput, and error stats
        """
        return await self._metrics.get_metrics()
    
    async def get_config(self) -> TradingConfig:
        """
        Get current configuration.
        
        Returns:
            TradingConfig object
        """
        return self.config
    
    # ======================================================================
    # SIGNAL PROCESSING PIPELINE
    # ======================================================================
    
    async def process_websocket_trade(self, trade: Dict[str, Any]) -> Optional[Signal]:
        """
        Process WebSocket trade update.
        
        Args:
            trade: Trade data from WebSocket
            
        Returns:
            Signal if actionable, None otherwise
        """
        start_time = time.time()
        
        try:
            # Determine priority based on trade size
            size = trade.get("size", 0)
            if size > 10000:  # Large trade
                priority = SignalPriority.WHALE_URGENT
            elif size > 1000:  # Medium trade
                priority = SignalPriority.WHALE_NORMAL
            else:
                priority = SignalPriority.WEBSOCKET
            
            signal = Signal(
                priority=priority,
                timestamp=time.time(),
                signal_type="websocket_trade",
                data=trade,
                source="websocket",
                market_id=trade.get("market_id"),
                confidence=0.5,
                expected_profit=0.0
            )
            
            await self._signal_queue.put(signal)
            await self._metrics.record_latency("detection", (time.time() - start_time) * 1000)
            await self._metrics.record_throughput("signals")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error processing WebSocket trade: {e}")
            await self._metrics.record_error("websocket_processor")
            return None
    
    async def process_blockchain_event(self, event: Dict[str, Any]) -> Optional[Signal]:
        """
        Process blockchain event.
        
        Args:
            event: Blockchain event data
            
        Returns:
            Signal if actionable, None otherwise
        """
        start_time = time.time()
        
        try:
            signal = Signal(
                priority=SignalPriority.BLOCKCHAIN,
                timestamp=time.time(),
                signal_type="blockchain_event",
                data=event,
                source="blockchain",
                market_id=event.get("market_id"),
                confidence=0.6,
                expected_profit=0.0
            )
            
            await self._signal_queue.put(signal)
            await self._metrics.record_latency("detection", (time.time() - start_time) * 1000)
            await self._metrics.record_throughput("signals")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error processing blockchain event: {e}")
            await self._metrics.record_error("blockchain_processor")
            return None
    
    async def process_prediction(self, prediction: Dict[str, Any]) -> Optional[Signal]:
        """
        Process predictive entry signal.
        
        Args:
            prediction: Prediction signal data
            
        Returns:
            Signal if actionable, None otherwise
        """
        start_time = time.time()
        
        try:
            confidence = prediction.get("confidence", 0.5)
            
            signal = Signal(
                priority=SignalPriority.PREDICTION,
                timestamp=time.time(),
                signal_type="prediction",
                data=prediction,
                source="predictive_system",
                market_id=prediction.get("market_id"),
                confidence=confidence,
                expected_profit=prediction.get("expected_profit", 0.0)
            )
            
            await self._signal_queue.put(signal)
            await self._metrics.record_latency("detection", (time.time() - start_time) * 1000)
            await self._metrics.record_throughput("signals")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error processing prediction: {e}")
            await self._metrics.record_error("prediction_processor")
            return None
    
    async def process_arbitrage(self, opportunity: Dict[str, Any]) -> Optional[Signal]:
        """
        Process arbitrage opportunity.
        
        Args:
            opportunity: Arbitrage opportunity data
            
        Returns:
            Signal if actionable, None otherwise
        """
        start_time = time.time()
        
        try:
            profit = opportunity.get("profit_percent", 0)
            
            # Higher priority for larger profit
            if profit > 1.0:
                priority = SignalPriority.WHALE_NORMAL
            else:
                priority = SignalPriority.ARBITRAGE
            
            signal = Signal(
                priority=priority,
                timestamp=time.time(),
                signal_type="arbitrage",
                data=opportunity,
                source="arbitrage_detector",
                market_id=opportunity.get("market_id"),
                confidence=min(0.9, profit / 10),  # Scale with profit
                expected_profit=profit
            )
            
            await self._signal_queue.put(signal)
            await self._metrics.record_latency("detection", (time.time() - start_time) * 1000)
            await self._metrics.record_throughput("signals")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error processing arbitrage: {e}")
            await self._metrics.record_error("arbitrage_processor")
            return None
    
    # ======================================================================
    # INTERNAL HANDLERS
    # ======================================================================
    
    async def _handle_websocket_message(self, msg_type: str, data: Dict):
        """Handle messages from WebSocket client."""
        await self._metrics.record_throughput("messages")
        
        if msg_type == "trade":
            await self.process_websocket_trade(data)
        elif msg_type == "orderbook":
            # Process orderbook updates
            pass
    
    async def _handle_blockchain_event(self, event: Any):
        """Handle blockchain events."""
        await self._metrics.record_throughput("messages")
        await self.process_blockchain_event(event.__dict__ if hasattr(event, '__dict__') else {"event": str(event)})
    
    async def _handle_arbitrage_opportunity(self, opportunity: Dict):
        """Handle arbitrage opportunities."""
        await self.process_arbitrage(opportunity)
    
    async def _handle_prediction_signal(self, signal: Dict):
        """Handle predictive signals."""
        await self.process_prediction(signal)
    
    # ======================================================================
    # PROCESSING PIPELINES
    # ======================================================================
    
    async def _start_processing_pipelines(self):
        """Start signal processing pipelines."""
        # Signal processing workers
        for i in range(self.config.signal_processing_threads):
            task = asyncio.create_task(
                self._signal_processor_loop(f"processor_{i}")
            )
            self._processing_tasks.append(task)
        
        # Execution workers
        for i in range(self.config.execution_threads):
            task = asyncio.create_task(
                self._execution_loop(f"executor_{i}")
            )
            self._processing_tasks.append(task)
        
        logger.info(f"Started {len(self._processing_tasks)} processing workers")
    
    async def _signal_processor_loop(self, name: str):
        """Main signal processing loop."""
        logger.debug(f"Signal processor {name} started")
        
        while not self._shutdown_event.is_set():
            try:
                # Check state
                if self._state == SystemState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get signal with timeout
                try:
                    signal = await asyncio.wait_for(
                        self._signal_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process signal
                await self._process_signal(signal)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in signal processor {name}: {e}")
                self._error_count += 1
                self._last_errors.append(time.time())
        
        logger.debug(f"Signal processor {name} stopped")
    
    async def _process_signal(self, signal: Signal):
        """
        Process a single signal through the pipeline.
        
        Pipeline stages:
        1. Pattern Analysis (1-5ms)
        2. Prediction Check (if applicable)
        3. Risk Check (1-2ms)
        4. Route Selection (1-2ms)
        5. Queue for execution
        """
        signal_id = id(signal)
        self._active_signals.add(signal_id)
        
        try:
            # Stage 1: Pattern Analysis
            analysis_start = time.time()
            analyzed = await self._analyze_signal(signal)
            await self._metrics.record_latency(
                "analysis",
                (time.time() - analysis_start) * 1000
            )
            
            if not analyzed.get("valid", False):
                return
            
            # Stage 2: Risk Check
            risk_start = time.time()
            risk_ok = await self._risk_check(signal, analyzed)
            await self._metrics.record_latency(
                "risk_check",
                (time.time() - risk_start) * 1000
            )
            
            if not risk_ok:
                logger.debug(f"Signal {signal_id} failed risk check")
                return
            
            # Stage 3: Route Selection
            route_start = time.time()
            route = await self._select_route(signal, analyzed)
            await self._metrics.record_latency(
                "routing",
                (time.time() - route_start) * 1000
            )
            
            # Queue for execution
            execution_item = {
                "signal": signal,
                "analysis": analyzed,
                "route": route,
                "queued_at": time.time()
            }
            
            await self._execution_queue.put((signal.priority.value, execution_item))
            
        except Exception as e:
            logger.error(f"Error processing signal {signal_id}: {e}")
            await self._metrics.record_error("signal_processing")
        finally:
            self._active_signals.discard(signal_id)
    
    async def _analyze_signal(self, signal: Signal) -> Dict[str, Any]:
        """
        Analyze signal patterns and confidence.
        
        Returns:
            Analysis result with validity and metadata
        """
        # Basic analysis - extend based on pattern engine
        return {
            "valid": signal.confidence > 0.3,
            "confidence": signal.confidence,
            "expected_profit": signal.expected_profit,
            "market_id": signal.market_id,
            "side": signal.data.get("side", "buy"),
            "size": signal.data.get("size", 0)
        }
    
    async def _risk_check(self, signal: Signal, analysis: Dict) -> bool:
        """
        Perform risk management checks.
        
        Returns:
            True if signal passes all risk checks
        """
        # Check circuit breaker
        if not await self._circuit_breaker.check("executor"):
            logger.warning("Circuit breaker open for executor")
            return False
        
        # Position size check
        size = analysis.get("size", 0)
        if size > self.config.max_position_size:
            logger.warning(f"Position size {size} exceeds maximum")
            return False
        
        # Concurrent trades check
        if len(self._active_signals) >= self.config.max_concurrent_trades:
            logger.warning("Max concurrent trades reached")
            return False
        
        # Mode-specific checks
        if self.config.mode == TradingMode.PAPER:
            # More lenient in paper mode
            return True
        
        return True
    
    async def _select_route(self, signal: Signal, analysis: Dict) -> Dict[str, Any]:
        """
        Select optimal execution route.
        
        Returns:
            Route configuration
        """
        if not self._router:
            return {"type": "direct", "estimated_gas": 50000}
        
        try:
            route = await self._router.route_order(signal)
            return route
        except Exception as e:
            logger.error(f"Route selection error: {e}")
            return {"type": "direct", "estimated_gas": 50000}
    
    async def _execution_loop(self, name: str):
        """Main execution loop."""
        logger.debug(f"Execution worker {name} started")
        
        while not self._shutdown_event.is_set():
            try:
                # Check state
                if self._state == SystemState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                
                # Check auto-trading enabled
                if not self.config.enable_auto_trading:
                    await asyncio.sleep(0.5)
                    continue
                
                # Get execution item
                try:
                    _, item = await asyncio.wait_for(
                        self._execution_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Execute
                await self._execute_signal(item)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in execution worker {name}: {e}")
                await self._metrics.record_error("execution")
        
        logger.debug(f"Execution worker {name} stopped")
    
    async def _execute_signal(self, item: Dict[str, Any]):
        """
        Execute a trading signal.
        
        Args:
            item: Execution item with signal, analysis, and route
        """
        signal = item["signal"]
        route = item["route"]
        
        start_time = time.time()
        
        try:
            # Check circuit breaker
            if not await self._circuit_breaker.check("executor"):
                logger.warning("Circuit breaker open, skipping execution")
                return
            
            # Execute via latency executor
            if self._executor:
                result = await self._executor.execute(signal)
                
                if result.get("success"):
                    await self._circuit_breaker.record_success("executor")
                    await self._notifications.notify(
                        "success",
                        f"Trade executed: {signal.signal_type}",
                        {"market_id": signal.market_id, "result": result}
                    )
                    self._processed_signals += 1
                    await self._metrics.record_throughput("trades")
                else:
                    await self._circuit_breaker.record_failure("executor")
                    await self._notifications.notify(
                        "error",
                        f"Trade failed: {result.get('error', 'unknown')}",
                        {"signal": signal.signal_type}
                    )
            
            # Record latency
            await self._metrics.record_latency(
                "execution",
                (time.time() - start_time) * 1000
            )
            
        except Exception as e:
            logger.error(f"Execution error: {e}")
            await self._circuit_breaker.record_failure("executor")
            await self._metrics.record_error("execution")
    
    async def _drain_queues(self):
        """Drain all queues gracefully."""
        # Process remaining signals
        while not self._signal_queue.empty():
            try:
                signal = self._signal_queue.get_nowait()
                await self._process_signal(signal)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error draining signal queue: {e}")
        
        # Process remaining executions
        while not self._execution_queue.empty():
            try:
                _, item = self._execution_queue.get_nowait()
                await self._execute_signal(item)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error draining execution queue: {e}")
    
    # ======================================================================
    # MONITORING
    # ======================================================================
    
    async def _monitoring_loop(self):
        """Continuous monitoring and health checks."""
        while not self._shutdown_event.is_set():
            try:
                # Check component health
                await self._check_component_health()
                
                # Check performance degradation
                await self._check_performance()
                
                # Sync state periodically
                await self._sync_state()
                
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(1.0)
    
    async def _check_component_health(self):
        """Check health of all components."""
        components = [
            ("websocket", self._websocket),
            ("blockchain", self._blockchain),
            ("executor", self._executor),
            ("router", self._router),
            ("arbitrage", self._arbitrage),
            ("predictive", self._predictive),
        ]
        
        for name, component in components:
            if not component:
                continue
            
            try:
                health = await component.get_health()
                
                if health.state == ComponentState.ERROR:
                    logger.error(f"Component {name} in error state")
                    await self._notifications.notify(
                        "error",
                        f"Component {name} error: {health.message}"
                    )
                    await self._circuit_breaker.record_failure(name)
                elif health.latency_ms > 1000:
                    logger.warning(f"Component {name} high latency: {health.latency_ms}ms")
                    
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                await self._circuit_breaker.record_failure(name)
    
    async def _check_performance(self):
        """Check for performance degradation."""
        metrics = await self._metrics.get_metrics()
        
        # Check latency targets
        if metrics.latency_stats.total_ms > 500:  # 500ms total target
            logger.warning(f"High total latency: {metrics.latency_stats.total_ms:.1f}ms")
        
        if metrics.latency_stats.execution_ms > self.config.target_execution_ms * 2:
            logger.warning(f"Execution latency degraded: {metrics.latency_stats.execution_ms:.1f}ms")
            await self._notifications.notify(
                "warning",
                f"High execution latency: {metrics.latency_stats.execution_ms:.1f}ms"
            )
        
        # Check error rates
        for component, rate in metrics.error_rates.items():
            if rate > 5.0:  # 5% error rate
                logger.error(f"High error rate on {component}: {rate:.1f}%")
                await self._circuit_breaker.record_failure(component)
    
    async def _sync_state(self):
        """Synchronize state to warm storage."""
        # Sync important hot state to SQLite
        keys_to_sync = [
            "active_positions",
            "daily_pnl",
            "trade_count"
        ]
        await self._state_manager.sync_hot_to_warm(keys_to_sync)
    
    # ======================================================================
    # UTILITY METHODS
    # ======================================================================
    
    def add_notification_handler(self, handler: Callable):
        """
        Add a custom notification handler.
        
        Args:
            handler: Callback function for notifications
        """
        if self._notifications:
            self._notifications.add_handler(handler)
    
    async def submit_signal(self, signal: Signal) -> bool:
        """
        Manually submit a signal for processing.
        
        Args:
            signal: Signal to process
            
        Returns:
            True if signal queued successfully
        """
        try:
            await self._signal_queue.put(signal)
            return True
        except asyncio.QueueFull:
            logger.error("Signal queue full")
            return False
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get current queue statistics.
        
        Returns:
            Dict with queue sizes
        """
        return {
            "signal_queue": self._signal_queue.qsize(),
            "execution_queue": self._execution_queue.qsize(),
            "active_signals": len(self._active_signals)
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_trading_system(
    mode: str = "paper",
    speed: str = "balanced",
    risk: str = "moderate",
    **kwargs
) -> UnifiedRealTimeTradingSystem:
    """
    Factory function to create a trading system with string parameters.
    
    Args:
        mode: "paper", "live", "backtest", or "simulation"
        speed: "ultra", "balanced", or "economy"
        risk: "conservative", "moderate", or "aggressive"
        **kwargs: Additional configuration options
        
    Returns:
        Configured UnifiedRealTimeTradingSystem
        
    Example:
        >>> system = create_trading_system(
        ...     mode="paper",
        ...     speed="ultra",
        ...     risk="conservative",
        ...     enable_auto_trading=False
        ... )
    """
    mode_enum = TradingMode(mode.lower())
    speed_enum = SpeedMode(speed.lower())
    risk_enum = RiskProfile(risk.lower())
    
    return UnifiedRealTimeTradingSystem(
        mode=mode_enum,
        speed=speed_enum,
        risk=risk_enum,
        custom_config=kwargs
    )


async def quick_start(
    mode: str = "paper",
    auto_trade: bool = False
) -> UnifiedRealTimeTradingSystem:
    """
    Quick start a trading system with common defaults.
    
    Args:
        mode: Trading mode
        auto_trade: Enable automatic trade execution
        
    Returns:
        Started UnifiedRealTimeTradingSystem
        
    Example:
        >>> system = await quick_start(mode="paper", auto_trade=False)
        >>> # System is running
        >>> await system.stop()
    """
    system = create_trading_system(
        mode=mode,
        speed="balanced",
        risk="moderate",
        enable_auto_trading=auto_trade
    )
    
    success = await system.start()
    if not success:
        raise RuntimeError("Failed to start trading system")
    
    return system


# =============================================================================
# MAIN ENTRY POINT (for testing)
# =============================================================================

async def main():
    """Main entry point for testing."""
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Unified Real-Time Trading System")
    print("=" * 60)
    
    # Create system in paper mode
    system = create_trading_system(
        mode="paper",
        speed="balanced",
        risk="moderate",
        enable_auto_trading=False  # Safe default
    )
    
    # Add notification handler
    async def on_notification(notification):
        print(f"[NOTIFY {notification['level'].upper()}] {notification['message']}")
    
    system.add_notification_handler(on_notification)
    
    # Start system
    print("\nStarting system...")
    success = await system.start()
    
    if not success:
        print("Failed to start system")
        return
    
    try:
        # Run for a bit
        print("\nSystem running. Press Ctrl+C to stop...")
        for i in range(30):
            await asyncio.sleep(1)
            
            # Print status every 5 seconds
            if i % 5 == 0:
                status = await system.get_status()
                metrics = await system.get_metrics()
                queues = system.get_queue_stats()
                
                print(f"\n--- Status (t={i}s) ---")
                print(f"State: {status.state.value}")
                print(f"Health: {status.health}")
                print(f"Components: {status.component_states}")
                print(f"Active Signals: {status.active_signals}")
                print(f"Queue Stats: {queues}")
                print(f"Latency: {metrics.latency_stats.total_ms:.1f}ms total")
                
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        await system.stop()
        print("System stopped")
        
        # Final status
        final_status = await system.get_status()
        print(f"\nFinal Status:")
        print(f"  Uptime: {final_status.uptime_seconds:.1f}s")
        print(f"  Signals Processed: {final_status.processed_signals}")
        print(f"  Errors: {final_status.errors_last_minute}")


if __name__ == "__main__":
    asyncio.run(main())
