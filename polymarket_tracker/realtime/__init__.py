"""
Ultra-Low Latency Real-Time Execution Module

Provides sub-100ms trade execution capabilities for Polymarket trading.

Key Components:
- UltraLowLatencyExecutor: Main execution engine with <100ms target latency
- ExecutionOrder: Pre-staged order data class
- ExecutionResult: Fill result with latency tracking
- ExecutionStats: Performance metrics and statistics
- SmartOrderRouter: Intelligent order routing with gas optimization
- Route: Routing path configuration
- GasStrategy: Gas pricing strategy
- ExecutionPlan: Comprehensive execution plan with contingencies
- RoutingStats: Routing performance statistics
- PerformanceBenchmark: Comprehensive performance measurement and validation
- LatencyBenchmark: Latency measurement results
- ThroughputBenchmark: Throughput measurement results
- AccuracyBenchmark: Accuracy measurement results
- LoadBenchmark: Load testing results
- ComparisonResult: Performance comparison results
- BenchmarkSuite: Complete benchmark suite container

Execution Strategies:
- Sniper Entry: Match or beat whale prices
- Market with Limit: Market orders with price ceilings
- Iceberg: Split large orders to hide size
- TWAP: Time-weighted average price execution
- Speed Mode: Max gas, direct route, no batching
- Economy Mode: Optimal gas, batched, patient execution
- Stealth Mode: Small orders, random timing, hide intent
- Whale Mode: Max size, sweep orderbook, accept slippage

Benchmarking:
- WebSocket Latency: <10ms target
- Blockchain Detection: <500ms target
- Execution Latency: <100ms target
- Fill Latency: <3s target
- End-to-End: <2s target
- Throughput: >1000 msg/sec target
- Detection Accuracy: >99% target

Example:
    >>> from polymarket_tracker.realtime import UltraLowLatencyExecutor
    >>> executor = UltraLowLatencyExecutor(polymarket_client)
    >>> 
    >>> # Pre-stage an order
    >>> order = executor.prepare_order(
    ...     market_id="0x123...",
    ...     side="buy",
    ...     size=100,
    ...     price=0.65
    ... )
    >>> 
    >>> # Execute with minimum latency
    >>> result = executor.execute_immediately(signal, market_data)

Smart Routing Example:
    >>> from polymarket_tracker.realtime import SmartOrderRouter, ExecutionMode
    >>> router = SmartOrderRouter(polymarket_client, web3_provider)
    >>> await router.start()
    >>> 
    >>> # Execute with speed optimization
    >>> result = await router.execute(
    ...     market_id="0x123...",
    ...     side="buy",
    ...     size=1000,
    ...     mode=ExecutionMode.SPEED
    ... )

Benchmarking Example:
    >>> from polymarket_tracker.realtime import PerformanceBenchmark
    >>> benchmark = PerformanceBenchmark()
    >>> 
    >>> # Run specific benchmark
    >>> result = await benchmark.benchmark_websocket_latency()
    >>> print(f"WebSocket p95: {result.p95_ms:.2f}ms")
    >>> 
    >>> # Run full suite
    >>> suite = await benchmark.run_full_suite()
    >>> 
    >>> # Generate reports
    >>> benchmark.generate_latency_report()
    >>> benchmark.export_to_json("results.json")
"""

# Core latency executor (always available)
from .latency_executor import (
    UltraLowLatencyExecutor,
    ExecutionOrder,
    ExecutionResult,
    ExecutionStats,
    OrderSide,
    OrderType,
    ExecutionStrategy,
    CircuitBreaker,
    quick_buy,
    quick_sell,
    copy_whale_trade,
)

# Smart Order Router (always available)
from .smart_router import (
    SmartOrderRouter,
    Route,
    GasStrategy,
    ExecutionLeg,
    ExecutionPlan,
    RoutingStats,
    PriceLevel,
    OrderBookSnapshot,
    ExecutionResult as SmartExecutionResult,
    ExecutionVenue,
    ExecutionMode,
    RouteStatus,
    GasSpeed,
    create_smart_router,
    execute_quick_buy,
    execute_quick_sell,
    route_large_order,
)

# Performance Benchmarks (always available)
from .performance_benchmarks import (
    # Main benchmark class
    PerformanceBenchmark,
    # Result data classes
    LatencyBenchmark,
    ThroughputBenchmark,
    AccuracyBenchmark,
    LoadBenchmark,
    ComparisonResult,
    BenchmarkSuite,
    # Target metrics
    TARGETS,
    # Convenience functions
    run_benchmarks,
)

# Optional: WebSocket client (requires websockets)
try:
    from .websocket_client import (
        PolymarketWebSocket,
        PriceLevel as WSPriceLevel,
        OrderBookSnapshot as WSOrderBookSnapshot,
        OrderBookUpdate,
        TradeEvent,
        TickerEvent,
        ConnectionStats,
        SubscriptionType,
        Subscription,
    )
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

# Optional: Blockchain monitor (requires web3)
try:
    from .blockchain_monitor import (
        BlockchainMonitor,
        BlockchainEvent,
        PendingTransaction,
        EventType,
        MempoolStats,
        OrderFilledData,
        PolymarketContracts,
    )
    BLOCKCHAIN_AVAILABLE = True
except (ImportError, NameError):
    BLOCKCHAIN_AVAILABLE = False

# Optional: Arbitrage detector
try:
    from .arbitrage_detector import (
        ArbitrageDetector,
        ArbitrageOpportunity,
    )
    ARBITRAGE_AVAILABLE = True
except ImportError:
    ARBITRAGE_AVAILABLE = False

# Optional: Predictive entry
try:
    from .predictive_entry import (
        PredictiveEntrySystem,
        EntrySignal,
    )
    PREDICTIVE_AVAILABLE = True
except ImportError:
    PREDICTIVE_AVAILABLE = False

__all__ = [
    # Core latency executor
    "UltraLowLatencyExecutor",
    "ExecutionOrder",
    "ExecutionResult",
    "ExecutionStats",
    "OrderSide",
    "OrderType",
    "ExecutionStrategy",
    "CircuitBreaker",
    "quick_buy",
    "quick_sell",
    "copy_whale_trade",
    
    # Smart Order Router
    "SmartOrderRouter",
    "Route",
    "GasStrategy",
    "ExecutionLeg",
    "ExecutionPlan",
    "RoutingStats",
    "PriceLevel",
    "OrderBookSnapshot",
    "SmartExecutionResult",
    "ExecutionVenue",
    "ExecutionMode",
    "RouteStatus",
    "GasSpeed",
    "create_smart_router",
    "execute_quick_buy",
    "execute_quick_sell",
    "route_large_order",
    
    # Performance Benchmarks
    "PerformanceBenchmark",
    "LatencyBenchmark",
    "ThroughputBenchmark",
    "AccuracyBenchmark",
    "LoadBenchmark",
    "ComparisonResult",
    "BenchmarkSuite",
    "TARGETS",
    "run_benchmarks",
]

# Add optional exports if available
if WEBSOCKET_AVAILABLE:
    __all__.extend([
        "PolymarketWebSocket",
        "WSPriceLevel",
        "WSOrderBookSnapshot",
        "OrderBookUpdate",
        "TradeEvent",
        "TickerEvent",
        "ConnectionStats",
        "SubscriptionType",
        "Subscription",
    ])

if BLOCKCHAIN_AVAILABLE:
    __all__.extend([
        "BlockchainMonitor",
        "BlockchainEvent",
        "PendingTransaction",
        "EventType",
        "MempoolStats",
        "OrderFilledData",
        "PolymarketContracts",
    ])

if ARBITRAGE_AVAILABLE:
    __all__.extend([
        "ArbitrageDetector",
        "ArbitrageOpportunity",
    ])

if PREDICTIVE_AVAILABLE:
    __all__.extend([
        "PredictiveEntrySystem",
        "EntrySignal",
    ])
