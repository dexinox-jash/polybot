"""
PolyBot Backtesting Module

A comprehensive backtesting framework for testing copy-trading strategies
on historical Polymarket data.

Features:
- Multiple strategy types (copy all, high-confidence, large trades, etc.)
- Realistic fee modeling (2% per trade)
- Slippage modeling based on liquidity and volatility
- Kelly Criterion position sizing
- Monte Carlo simulation
- Risk analysis (VaR, drawdown, heat maps)
- Comprehensive performance metrics
- Async data loading from subgraph/database

Example Usage:
    import asyncio
    from polymarket_tracker.backtesting import BacktestEngine, StrategyConfig, StrategyType
    
    async def main():
        # Initialize engine
        engine = BacktestEngine(
            initial_capital=10000.0,
            start_date=datetime.now() - timedelta(days=90),
            end_date=datetime.now()
        )
        
        # Load historical data
        await engine.load_historical_data(
            whale_addresses=["0x1234...", "0x5678..."],
            data_source="subgraph"
        )
        
        # Configure strategy
        config = StrategyConfig(
            strategy_type=StrategyType.COPY_HIGH_CONFIDENCE,
            name="High Confidence Strategy",
            min_whale_confidence=0.7,
            position_size_percent=0.02,
        )
        
        # Run backtest
        result = engine.run_backtest(config)
        
        # Generate report
        print(engine.generate_report(result))
        
        # Export results
        engine.export_report_json(result, "backtest_report.json")
    
    asyncio.run(main())
"""

from .backtest_engine import (
    # Main engine
    BacktestEngine,
    
    # Data classes
    BacktestResult,
    BacktestTrade,
    StrategyConfig,
    MonteCarloResult,
    EquityPoint,
    
    # Enums
    StrategyType,
    TradeStatus,
    
    # Pre-built strategies
    create_copy_all_strategy,
    create_high_confidence_strategy,
    create_large_trades_strategy,
    create_crypto_only_strategy,
    create_kelly_strategy,
    create_top_winners_strategy,
    
    # Utilities
    run_strategy_comparison,
    optimize_strategy,
)

__all__ = [
    # Main engine
    'BacktestEngine',
    
    # Data classes
    'BacktestResult',
    'BacktestTrade',
    'StrategyConfig',
    'MonteCarloResult',
    'EquityPoint',
    
    # Enums
    'StrategyType',
    'TradeStatus',
    
    # Pre-built strategies
    'create_copy_all_strategy',
    'create_high_confidence_strategy',
    'create_large_trades_strategy',
    'create_crypto_only_strategy',
    'create_kelly_strategy',
    'create_top_winners_strategy',
    
    # Utilities
    'run_strategy_comparison',
    'optimize_strategy',
]

__version__ = "1.0.0"
