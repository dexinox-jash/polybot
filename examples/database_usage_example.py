"""
PolyBot Database Usage Examples

Demonstrates how to use the TradeDatabase class for all operations.
Run this to test the database integration.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import to avoid dependency issues with other modules
import importlib.util
spec = importlib.util.spec_from_file_location(
    "database", 
    str(Path(__file__).parent.parent / "polymarket_tracker" / "data" / "database.py")
)
database_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(database_module)

TradeDatabase = database_module.TradeDatabase
TradeData = database_module.TradeData
TradeStatus = database_module.TradeStatus
TradeSide = database_module.TradeSide
TradeType = database_module.TradeType
PatternType = database_module.PatternType
EventType = database_module.EventType
WhaleProfile = database_module.WhaleProfile
MarketCache = database_module.MarketCache


def example_trade_management(db: TradeDatabase):
    """Demonstrate trade recording and management."""
    print("\n" + "="*60)
    print("TRADE MANAGEMENT EXAMPLES")
    print("="*60)
    
    # Record a new paper trade
    trade1 = TradeData(
        trade_id="trade_001",
        market_id="market_123",
        market_question="Will BTC close above $67k in 5 min?",
        side="YES",
        trade_type="paper",
        entry_price=0.52,
        size_usd=100.0,
        status="open",
        signal_id="signal_001",
        pattern_type="momentum_burst",
        whale_address="0xabc123...",
        whale_confidence=0.78,
        stop_loss=0.45,
        take_profit=0.65,
        fees=0.5,
        metadata={"entry_delay_ms": 150, "slippage": 0.001}
    )
    
    success = db.record_trade(trade1)
    print(f"[OK] Recorded trade 1: {success}")
    
    # Record another trade
    trade2 = TradeData(
        trade_id="trade_002",
        market_id="market_124",
        market_question="Will ETH drop below $3.5k?",
        side="NO",
        trade_type="paper",
        entry_price=0.48,
        size_usd=150.0,
        status="closed",
        exit_price=0.62,
        pnl=21.0,
        signal_id="signal_002",
        pattern_type="whale_accumulation",
        whale_address="0xdef456...",
        whale_confidence=0.85,
    )
    
    success = db.record_trade(trade2)
    print(f"[OK] Recorded trade 2: {success}")
    
    # Update trade result
    success = db.update_trade_result(
        trade_id="trade_001",
        exit_price=0.61,
        pnl=18.0,
        status="closed",
        exit_reason="take_profit"
    )
    print(f"[OK] Updated trade 1 result: {success}")
    
    # Get open positions
    open_positions = db.get_open_positions()
    print(f"\nOpen positions: {len(open_positions)}")
    
    # Get trade history
    history = db.get_trade_history(limit=10)
    print(f"\nTrade history ({len(history)} trades):")
    for trade in history:
        print(f"  - {trade['trade_id']}: {trade['side']} @ ${trade['entry_price']:.2f} "
              f"-> P&L: ${trade.get('pnl', 0):.2f}")


def example_whale_profiles(db: TradeDatabase):
    """Demonstrate whale profile management."""
    print("\n" + "="*60)
    print("WHALE PROFILE EXAMPLES")
    print("="*60)
    
    # Save whale profiles
    whale1 = WhaleProfile(
        address="0xabc123...",
        total_trades=45,
        winning_trades=28,
        losing_trades=17,
        total_pnl=1250.0,
        win_rate=62.2,
        profit_factor=1.8,
        avg_trade_size=200.0,
        confluence_score=0.82,
        reliability_tier="gold",
        market_specialization="BTC"
    )
    
    success = db.save_whale_profile(whale1)
    print(f"[OK] Saved whale 1 profile: {success}")
    
    whale2 = WhaleProfile(
        address="0xdef456...",
        total_trades=120,
        winning_trades=75,
        losing_trades=45,
        total_pnl=3200.0,
        win_rate=62.5,
        profit_factor=2.1,
        avg_trade_size=500.0,
        confluence_score=0.91,
        reliability_tier="platinum",
        market_specialization="ETH"
    )
    
    success = db.save_whale_profile(whale2)
    print(f"[OK] Saved whale 2 profile: {success}")
    
    # Get whale profile
    profile = db.get_whale_profile("0xabc123...")
    if profile:
        print(f"\nWhale 0xabc123... profile:")
        print(f"  - Win rate: {profile['win_rate']:.1f}%")
        print(f"  - Profit factor: {profile['profit_factor']:.2f}")
        print(f"  - Tier: {profile['reliability_tier']}")
    
    # Get top whales
    top_whales = db.get_top_whales(limit=5, min_trades=10)
    print(f"\nTop whales ({len(top_whales)} found):")
    for whale in top_whales:
        print(f"  - {whale['address'][:12]}...: {whale['win_rate']:.1f}% WR, "
              f"${whale['total_pnl']:.0f} P&L, {whale['reliability_tier']} tier")


def example_market_cache(db: TradeDatabase):
    """Demonstrate market data caching."""
    print("\n" + "="*60)
    print("MARKET CACHE EXAMPLES")
    print("="*60)
    
    # Cache market data
    market1 = MarketCache(
        market_id="market_123",
        question="Will BTC close above $67k in 5 min?",
        category="Crypto",
        description="Bitcoin 5-minute prediction market",
        yes_price=0.52,
        no_price=0.48,
        volume=150000.0,
        liquidity=50000.0,
        end_date=(datetime.now() + timedelta(minutes=5)).isoformat(),
        status="active"
    )
    
    success = db.cache_market_data("market_123", market1)
    print(f"[OK] Cached market 123: {success}")
    
    market2 = MarketCache(
        market_id="market_124",
        question="Will ETH drop below $3.5k?",
        category="Crypto",
        yes_price=0.35,
        no_price=0.65,
        volume=85000.0,
        liquidity=30000.0,
    )
    
    success = db.cache_market_data("market_124", market2)
    print(f"[OK] Cached market 124: {success}")
    
    # Retrieve cached market
    cached = db.get_cached_market("market_123")
    if cached:
        print(f"\nCached market 123:")
        print(f"  - Question: {cached['question']}")
        print(f"  - YES price: {cached['yes_price']}")
        print(f"  - Volume: ${cached['volume']:,.0f}")
    
    # Get by category
    crypto_markets = db.get_markets_by_category("Crypto")
    print(f"\nCrypto markets: {len(crypto_markets)}")


def example_analytics(db: TradeDatabase):
    """Demonstrate analytics queries."""
    print("\n" + "="*60)
    print("ANALYTICS EXAMPLES")
    print("="*60)
    
    # Performance summary
    summary = db.get_performance_summary(days=30)
    print(f"\nPerformance Summary (30 days):")
    print(f"  - Total trades: {summary.get('total_trades', 0)}")
    print(f"  - Win rate: {summary.get('win_rate', 0):.1f}%")
    print(f"  - Profit factor: {summary.get('profit_factor', 0):.2f}")
    print(f"  - Total P&L: ${summary.get('total_pnl', 0):.2f}")
    print(f"  - Net P&L: ${summary.get('net_pnl', 0):.2f}")
    
    # Win rate
    win_rate = db.get_win_rate(days=30)
    print(f"\nWin rate: {win_rate:.1f}%")
    
    # Profit factor
    pf = db.get_profit_factor(days=30)
    print(f"Profit factor: {pf:.2f}")
    
    # Sharpe ratio
    sharpe = db.get_sharpe_ratio(days=30)
    print(f"Sharpe ratio: {sharpe:.2f}")
    
    # Pattern performance
    patterns = db.get_pattern_performance()
    print(f"\nPattern Performance:")
    for p in patterns:
        print(f"  - {p['pattern_type']}: {p['win_rate']:.1f}% WR, "
              f"${p['total_pnl']:.2f} total")


def example_system_logging(db: TradeDatabase):
    """Demonstrate system event logging."""
    print("\n" + "="*60)
    print("SYSTEM LOGGING EXAMPLES")
    print("="*60)
    
    # Log various events
    db.log_event(EventType.INFO, "Bot started successfully")
    db.log_event(EventType.TRADE, "New trade signal detected", {
        "market_id": "market_123",
        "confidence": 0.85
    })
    db.log_event(EventType.SIGNAL, "Momentum burst pattern detected", {
        "market_id": "market_123",
        "strength": 0.78
    })
    db.log_event(EventType.WARNING, "High slippage detected", {
        "expected": 0.52,
        "actual": 0.535,
        "slippage": 0.015
    })
    
    print(f"[OK] Logged 4 system events")
    
    # Get recent events
    events = db.get_events(limit=10)
    print(f"\nRecent events ({len(events)}):")
    for event in events:
        print(f"  - [{event['event_type'].upper()}] {event['message']}")
    
    # Get only trade events
    trade_events = db.get_events(event_type=EventType.TRADE, limit=5)
    print(f"\nTrade events: {len(trade_events)}")


def example_utility_methods(db: TradeDatabase):
    """Demonstrate utility methods."""
    print("\n" + "="*60)
    print("UTILITY METHODS")
    print("="*60)
    
    # Database stats
    stats = db.get_database_stats()
    print(f"\nDatabase Statistics:")
    print(f"  - trades: {stats.get('trades', 0)} rows")
    print(f"  - whale_profiles: {stats.get('whale_profiles', 0)} rows")
    print(f"  - market_cache: {stats.get('market_cache', 0)} rows")
    print(f"  - system_events: {stats.get('system_events', 0)} rows")
    print(f"  - Database size: {stats.get('database_size_mb', 0):.2f} MB")


def main():
    """Run all examples."""
    print("="*60)
    print("PolyBot Database Integration Demo")
    print("="*60)
    
    # Initialize database (in-memory for demo)
    import tempfile
    import os
    
    # Create temp database file
    temp_db = tempfile.mktemp(suffix=".db")
    
    try:
        with TradeDatabase(temp_db) as db:
            print(f"\nDatabase initialized at: {temp_db}")
            
            # Run examples
            example_trade_management(db)
            example_whale_profiles(db)
            example_market_cache(db)
            example_analytics(db)
            example_system_logging(db)
            example_utility_methods(db)
            
            print("\n" + "="*60)
            print("All examples completed successfully!")
            print("="*60)
            
    finally:
        # Cleanup
        if os.path.exists(temp_db):
            os.remove(temp_db)
            print(f"\nCleaned up temp database: {temp_db}")


if __name__ == "__main__":
    main()
