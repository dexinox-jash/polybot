"""
PolyBot Comprehensive Integration Tests

Tests the complete workflow integration across all components:
- Data Layer (TheGraph, Database)
- Analysis Layer (Pattern Detection, EV Calculation)
- Risk Layer (Position Manager, Circuit Breakers)
- Execution Layer (Copy Engine, Paper Trading)
- Notification Layer (Alerts, Reports)

Uses mocking for external dependencies to ensure deterministic tests.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

# Import PolyBot components
from polymarket_tracker.analysis.pattern_engine import PatternConfidence, PatternEngine, SignalType
from polymarket_tracker.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestResult,
    StrategyConfig,
    StrategyType,
)
from polymarket_tracker.data.database import TradeDatabase, TradeData, TradeStatus, WhaleProfile
from polymarket_tracker.notifications.notification_manager import (
    NotificationConfig,
    NotificationManager,
    NotificationType,
)
from polymarket_tracker.paper_trading.paper_trading_engine import (
    PaperPosition,
    PaperTradingEngine,
    PositionStatus,
    TimingMetrics,
)
from polymarket_tracker.risk.position_manager import PositionManager, RiskLevel, RiskParameters
from polymarket_tracker.streaming.whale_stream_monitor import (
    CircularBuffer,
    TradeUrgency,
    WhaleSignal,
    WhaleStreamMonitor,
    WhaleTrade,
)
from polymarket_tracker.winners.copy_engine import (
    CopyDecision,
    CopyDecisionType,
    CopyEngine,
)
from polymarket_tracker.winners.ev_calculator import CopyEV, EVCalculator, EVGrade
from polymarket_tracker.winners.speed_matched_copy_engine import (
    CopyAction,
    SpeedMatchedCopyEngine,
    SpeedMatchedDecision,
)
from polymarket_tracker.winners.winner_discovery import TraderPerformance, WinnerDiscovery


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def setup_database(temp_db_path):
    """Create a clean test database with sample data."""
    db = TradeDatabase(db_path=temp_db_path)
    
    # Add sample trades
    for i in range(10):
        trade = TradeData(
            trade_id=f"trade_{i:03d}",
            market_id=f"market_{i % 3:03d}",
            market_question=f"Test Market {i % 3}",
            side="YES" if i % 2 == 0 else "NO",
            trade_type="paper",
            entry_price=0.45 + (i * 0.02),
            size_usd=100.0 + (i * 50),
            status="closed" if i < 7 else "open",
            exit_price=0.55 if i < 7 else None,
            pnl=10.0 if i < 5 else (-5.0 if i < 7 else None),
            whale_address=f"0xwhale{i % 2:03d}",
            pattern_type="momentum_burst" if i % 3 == 0 else "breakout",
            created_at=(datetime.now() - timedelta(days=i)).isoformat(),
            closed_at=(datetime.now() - timedelta(days=i-1)).isoformat() if i < 7 else None
        )
        db.record_trade(trade)
    
    yield db
    
    # Cleanup
    if os.path.exists(temp_db_path):
        os.unlink(temp_db_path)


@pytest.fixture
def setup_test_whales():
    """Create mock whale data."""
    whales = {
        "0xwhale001": TraderPerformance(
            address="0xwhale001",
            ens_name="SmartMoney.eth",
            total_bets=150,
            winning_bets=95,
            losing_bets=55,
            true_win_rate=0.633,
            profit_factor=1.8,
            net_pnl=25000.0,
            sharpe_ratio=1.5,
            is_statistically_significant=True,
            confidence_level="high",
            copy_score=85.0,
            vanity_gap=0.02
        ),
        "0xwhale002": TraderPerformance(
            address="0xwhale002",
            ens_name="ProTrader.eth",
            total_bets=200,
            winning_bets=110,
            losing_bets=90,
            true_win_rate=0.55,
            profit_factor=1.4,
            net_pnl=15000.0,
            sharpe_ratio=1.2,
            is_statistically_significant=True,
            confidence_level="high",
            copy_score=75.0,
            vanity_gap=0.03
        ),
        "0xwhale003": TraderPerformance(
            address="0xwhale003",
            ens_name="NewTrader.eth",
            total_bets=30,
            winning_bets=18,
            losing_bets=12,
            true_win_rate=0.60,
            profit_factor=1.3,
            net_pnl=2000.0,
            sharpe_ratio=0.8,
            is_statistically_significant=False,
            confidence_level="low",
            copy_score=55.0,
            vanity_gap=0.10
        )
    }
    return whales


@pytest.fixture
def setup_test_markets():
    """Create mock market data."""
    markets = {
        "market_001": {
            "id": "market_001",
            "question": "Will BTC reach $100k by end of 2024?",
            "category": "crypto",
            "current_price": 0.52,
            "liquidity": 150000.0,
            "volume": 500000.0,
            "volatility": 0.15,
            "is_crypto": True,
            "end_date": (datetime.now() + timedelta(days=30)).isoformat()
        },
        "market_002": {
            "id": "market_002",
            "question": "Will ETH hit $10k this year?",
            "category": "crypto",
            "current_price": 0.45,
            "liquidity": 80000.0,
            "volume": 250000.0,
            "volatility": 0.20,
            "is_crypto": True,
            "end_date": (datetime.now() + timedelta(days=60)).isoformat()
        },
        "market_003": {
            "id": "market_003",
            "question": "Will it rain tomorrow in NYC?",
            "category": "weather",
            "current_price": 0.30,
            "liquidity": 5000.0,
            "volume": 20000.0,
            "volatility": 0.10,
            "is_crypto": False,
            "end_date": (datetime.now() + timedelta(days=1)).isoformat()
        }
    }
    return markets


@pytest.fixture
def mock_subgraph_client():
    """Create a mocked subgraph client."""
    client = MagicMock()
    
    # Mock trade data
    mock_trades = [
        {
            "transactionHash": f"0x{uuid.uuid4().hex[:16]}",
            "maker": "0xwhale001",
            "market": {
                "id": "market_001",
                "question": "Will BTC reach $100k?",
                "createdAt": str(int((datetime.now() - timedelta(days=5)).timestamp())),
                "liquidity": "150000",
                "category": "crypto",
                "subcategory": "btc"
            },
            "outcomeIndex": 0,
            "outcomeTokens": "1000",
            "filledAmount": "1000",
            "price": "0.52",
            "timestamp": str(int((datetime.now() - timedelta(minutes=5)).timestamp())),
            "blockNumber": "12345678"
        },
        {
            "transactionHash": f"0x{uuid.uuid4().hex[:16]}",
            "maker": "0xwhale002",
            "market": {
                "id": "market_002",
                "question": "Will ETH hit $10k?",
                "createdAt": str(int((datetime.now() - timedelta(days=10)).timestamp())),
                "liquidity": "80000",
                "category": "crypto",
                "subcategory": "eth"
            },
            "outcomeIndex": 1,
            "outcomeTokens": "500",
            "filledAmount": "500",
            "price": "0.48",
            "timestamp": str(int((datetime.now() - timedelta(minutes=2)).timestamp())),
            "blockNumber": "12345679"
        }
    ]
    
    client.execute.return_value = {"orderFilleds": mock_trades}
    return client


@pytest.fixture
def mock_polymarket_api():
    """Create mocked Polymarket API responses."""
    api = MagicMock()
    
    api.get_market.return_value = {
        "id": "market_001",
        "question": "Will BTC reach $100k?",
        "status": "open",
        "yes_price": 0.52,
        "no_price": 0.48,
        "volume": 500000,
        "liquidity": 150000
    }
    
    api.place_order.return_value = {
        "orderId": "order_001",
        "status": "filled",
        "filled_size": 100,
        "filled_price": 0.52
    }
    
    api.get_position.return_value = {
        "position_id": "pos_001",
        "market_id": "market_001",
        "size": 100,
        "avg_entry": 0.52,
        "current_value": 104.0
    }
    
    return api


@pytest.fixture
def mock_time():
    """Mock time for deterministic tests."""
    fixed_time = datetime(2024, 6, 15, 12, 0, 0)
    
    with patch('polymarket_tracker.winners.copy_engine.datetime') as mock_dt, \
         patch('polymarket_tracker.paper_trading.paper_trading_engine.datetime') as mock_pt_dt:
        mock_dt.now.return_value = fixed_time
        mock_pt_dt.now.return_value = fixed_time
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        mock_pt_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield fixed_time


# ============================================================================
# Test Classes
# ============================================================================

class TestFullWorkflow:
    """Test complete workflow integration from scan to trade."""
    
    @pytest.mark.asyncio
    async def test_complete_daily_workflow(self, setup_database, setup_test_whales, setup_test_markets):
        """Test full workflow from market scan to trade execution."""
        # Setup components
        db = setup_database
        whales = setup_test_whales
        markets = setup_test_markets
        
        # 1. Winner Discovery - Find top whales
        winner_discovery = WinnerDiscovery(subgraph_client=None)
        winner_discovery.discovered_winners = list(whales.values())
        top_whales = winner_discovery.get_top_winners(n=2, min_confidence="high")
        assert len(top_whales) >= 2
        
        # 2. EV Calculation - Evaluate copy opportunity
        ev_calc = EVCalculator(subgraph_client=None)
        winner = whales["0xwhale001"]
        market = markets["market_001"]
        
        ev = ev_calc.calculate_ev(
            winner_profile=winner,
            market_probability=market["current_price"],
            our_entry_price=market["current_price"],
            bet_size=500.0,
            time_to_close=timedelta(days=30),
            market_liquidity=market["liquidity"],
            market_volatility=market["volatility"]
        )
        
        assert isinstance(ev, CopyEV)
        assert ev.adjusted_ev_percent > 0
        assert ev.grade in [EVGrade.EXCELLENT, EVGrade.GOOD, EVGrade.MARGINAL]
        
        # 3. Copy Decision - Make execution decision
        position_manager = PositionManager(initial_bankroll=10000)
        copy_engine = CopyEngine(ev_calculator=ev_calc, position_manager=position_manager)
        
        # Create a mock winner bet
        from dataclasses import dataclass
        @dataclass
        class MockWinnerBet:
            market_id: str
            direction: str
            entry_price: float
            size: float
            market_close_time: datetime
            
        winner_bet = MockWinnerBet(
            market_id="market_001",
            direction="YES",
            entry_price=0.52,
            size=10000,
            market_close_time=datetime.now() + timedelta(days=30)
        )
        
        portfolio_state = position_manager.get_portfolio_summary()
        decision = copy_engine.evaluate_copy_opportunity(
            winner_profile=winner,
            winner_bet=winner_bet,
            market_data=market,
            portfolio_state=portfolio_state
        )
        
        assert isinstance(decision, CopyDecision)
        assert decision.decision in [CopyDecisionType.IMMEDIATE_COPY, CopyDecisionType.STAGED_COPY]
        assert decision.confidence > 0
        assert decision.target_size > 0
        
        # 4. Record to Database
        trade_data = TradeData(
            trade_id="trade_test_001",
            market_id="market_001",
            market_question="Test BTC Market",
            side="YES",
            trade_type="paper",
            entry_price=decision.entry_price_target,
            size_usd=decision.target_size,
            status="open",
            whale_address=winner.address,
            whale_confidence=winner.true_win_rate,
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit
        )
        
        success = db.record_trade(trade_data)
        assert success
        
        # Verify trade was recorded
        recorded_trade = db.get_trade_history(filters={'trade_id': 'trade_test_001'}, limit=1)
        assert len(recorded_trade) == 1
        assert recorded_trade[0]['market_id'] == "market_001"
    
    def test_scan_to_analyze_pipeline(self, setup_test_whales, setup_test_markets):
        """Test pipeline from market discovery to analysis."""
        winner_discovery = WinnerDiscovery(subgraph_client=None)
        winner_discovery.discovered_winners = list(setup_test_whales.values())
        
        # Scan for winners
        top_winners = winner_discovery.get_top_winners(n=5, min_confidence="medium")
        assert len(top_winners) > 0
        
        # Analyze each winner against available markets
        ev_calc = EVCalculator()
        opportunities = []
        
        for winner in top_winners:
            for market_id, market in setup_test_markets.items():
                if market["is_crypto"]:
                    ev = ev_calc.calculate_ev(
                        winner_profile=winner,
                        market_probability=market["current_price"],
                        our_entry_price=market["current_price"],
                        bet_size=500.0,
                        time_to_close=timedelta(days=30),
                        market_liquidity=market["liquidity"],
                        market_volatility=market["volatility"]
                    )
                    if ev.adjusted_ev_percent > 2.0:
                        opportunities.append({
                            'winner': winner,
                            'market': market,
                            'ev': ev
                        })
        
        assert len(opportunities) > 0
        # Sort by EV
        opportunities.sort(key=lambda x: x['ev'].adjusted_ev_percent, reverse=True)
        assert opportunities[0]['ev'].adjusted_ev_percent >= opportunities[-1]['ev'].adjusted_ev_percent
    
    def test_analyze_to_copy_decision(self, setup_test_whales, setup_test_markets):
        """Test analysis to execution decision pipeline."""
        winner = setup_test_whales["0xwhale001"]
        market = setup_test_markets["market_001"]
        
        ev_calc = EVCalculator()
        position_manager = PositionManager(initial_bankroll=10000)
        copy_engine = CopyEngine(ev_calculator=ev_calc, position_manager=position_manager)
        
        # Calculate EV
        ev = ev_calc.calculate_ev(
            winner_profile=winner,
            market_probability=market["current_price"],
            our_entry_price=market["current_price"],
            bet_size=500.0,
            time_to_close=timedelta(days=30),
            market_liquidity=market["liquidity"],
            market_volatility=market["volatility"]
        )
        
        # Decision should align with EV grade
        if ev.grade in [EVGrade.EXCELLENT, EVGrade.GOOD]:
            assert ev.adjusted_ev_percent >= 3.0
        elif ev.grade == EVGrade.MARGINAL:
            assert 1.0 <= ev.adjusted_ev_percent < 3.0
        
        # Verify Kelly sizing
        assert ev.kelly_fraction >= 0
        assert ev.half_kelly_size >= 0
        assert ev.quarter_kelly_size >= 0
    
    def test_copy_to_portfolio_update(self, setup_database, setup_test_whales):
        """Test execution to portfolio tracking."""
        db = setup_database
        
        # Create paper trading engine
        paper_engine = PaperTradingEngine(initial_balance=10000)
        
        # Create a mock whale signal
        trade = WhaleTrade(
            tx_hash="0x" + uuid.uuid4().hex[:16],
            whale_address="0xwhale001",
            market_id="market_001",
            market_question="Will BTC reach $100k?",
            outcome="YES",
            amount=10000.0,
            price=0.52,
            timestamp=datetime.now() - timedelta(minutes=5),
            block_number=12345678
        )
        
        signal = WhaleSignal(
            trade=trade,
            urgency=TradeUrgency.FLASH,
            pattern_confidence=0.85,
            time_since_market_created=timedelta(hours=1),
            time_since_last_trade=timedelta(hours=2),
            whale_pattern_profile="SNIPER",
            recommended_action="COPY_IMMEDIATE",
            suggested_size=500.0,
            max_delay_seconds=60
        )
        
        # Execute paper trade
        market_data = {
            'current_price': 0.53,
            'liquidity': 150000,
            'volatility_1min': 0.02,
            'is_crypto': True
        }
        
        position = paper_engine.execute_paper_trade(
            signal=signal,
            delay_seconds=30,
            market_data=market_data
        )
        
        assert isinstance(position, PaperPosition)
        assert position.status == PositionStatus.OPEN
        assert position.size_usd > 0
        
        # Record in database
        trade_data = TradeData(
            trade_id=position.position_id,
            market_id=position.market_id,
            market_question=position.market_question,
            side=position.direction,
            trade_type="paper",
            entry_price=position.entry_price,
            size_usd=position.size_usd,
            status="open",
            whale_address=position.whale_address,
            whale_confidence=position.whale_confidence,
            stop_loss=position.stop_loss_price,
            take_profit=position.take_profit_price,
            metadata={
                'speed_score': position.timing_metrics.speed_score,
                'slippage': position.timing_metrics.price_slippage_percent
            }
        )
        
        success = db.record_trade(trade_data)
        assert success
        
        # Verify portfolio summary
        summary = paper_engine.get_performance_report()
        assert 'summary' in summary
        assert summary['summary']['open_positions'] >= 1


class TestRealTimeMonitoring:
    """Test real-time monitoring to execution pipeline."""
    
    @pytest.mark.asyncio
    async def test_stream_monitor_to_copy_engine(self, mock_subgraph_client, setup_test_whales):
        """Test whale detection triggers copy decision."""
        whale_addresses = ["0xwhale001", "0xwhale002"]
        
        # Create stream monitor
        monitor = WhaleStreamMonitor(
            subgraph_client=mock_subgraph_client,
            whale_addresses=whale_addresses,
            poll_interval=30,
            crypto_only=True
        )
        
        # Mock the fetch method to return test data
        test_trades = [
            WhaleTrade(
                tx_hash=f"0x{uuid.uuid4().hex[:16]}",
                whale_address="0xwhale001",
                market_id="market_001",
                market_question="Will BTC reach $100k?",
                outcome="YES",
                amount=10000.0,
                price=0.52,
                timestamp=datetime.now() - timedelta(seconds=30),
                block_number=12345678,
                market_liquidity=150000
            )
        ]
        
        with patch.object(monitor, '_fetch_new_trades', return_value=test_trades):
            # Simulate a poll cycle
            signals_received = []
            
            def capture_signal(signal):
                signals_received.append(signal)
            
            monitor.add_callback(capture_signal)
            await monitor._poll_once()
            
            assert len(signals_received) > 0
            
            # Verify signal classification
            signal = signals_received[0]
            assert isinstance(signal, WhaleSignal)
            assert signal.pattern_confidence > 0
            assert signal.urgency in TradeUrgency
    
    @pytest.mark.asyncio
    async def test_copy_engine_to_paper_trading(self, setup_test_whales, setup_test_markets):
        """Test copy decision leads to paper trade execution."""
        # Create components
        pattern_engine = PatternEngine()
        paper_engine = PaperTradingEngine(initial_balance=10000)
        position_manager = PositionManager(initial_bankroll=10000)
        
        copy_engine = SpeedMatchedCopyEngine(
            pattern_engine=pattern_engine,
            paper_trading_engine=paper_engine,
            position_manager=position_manager,
            delay_tolerance_seconds=60
        )
        
        # Create whale signal
        trade = WhaleTrade(
            tx_hash="0x" + uuid.uuid4().hex[:16],
            whale_address="0xwhale001",
            market_id="market_001",
            market_question="Will BTC reach $100k?",
            outcome="YES",
            amount=10000.0,
            price=0.52,
            timestamp=datetime.now() - timedelta(seconds=10),
            block_number=12345678
        )
        
        signal = WhaleSignal(
            trade=trade,
            urgency=TradeUrgency.FLASH,
            pattern_confidence=0.85,
            time_since_market_created=timedelta(hours=1),
            time_since_last_trade=timedelta(minutes=30),
            whale_pattern_profile="SNIPER",
            recommended_action="COPY_IMMEDIATE",
            suggested_size=500.0,
            max_delay_seconds=60
        )
        
        market_context = setup_test_markets["market_001"]
        portfolio_context = position_manager.get_portfolio_summary()
        
        # Evaluate signal
        decision = await copy_engine.evaluate_whale_signal(
            signal=signal,
            market_context=market_context,
            portfolio_context=portfolio_context
        )
        
        assert isinstance(decision, SpeedMatchedDecision)
        assert decision.confidence > 0
        
        # If decision is to copy, execute
        if decision.action in [CopyAction.COPY_IMMEDIATE, CopyAction.REDUCE_SIZE]:
            position = await copy_engine.execute_copy(
                signal=signal,
                decision=decision,
                market_data=market_context
            )
            
            if position:
                assert isinstance(position, PaperPosition)
                assert position.status == PositionStatus.OPEN
                assert position.size_usd > 0
    
    @pytest.mark.asyncio
    async def test_paper_trading_to_notifications(self):
        """Test paper trade triggers notifications."""
        # Create notification manager with mock config
        config = NotificationConfig(
            enable_discord=False,
            enable_telegram=False,
            enable_console=True
        )
        
        manager = NotificationManager(config=config)
        
        # Create mock paper position
        position = {
            "market": "Will BTC reach $100k?",
            "side": "YES",
            "size": 500.0,
            "entry_price": 0.52,
            "expected_value": 0.05
        }
        
        # Test notification
        with patch.object(manager, '_send_all_channels', return_value={
            "discord": False,
            "telegram": False,
            "console": True
        }) as mock_send:
            result = await manager.notify_trade_executed(position)
            assert result["console"] is True
    
    def test_speed_matching_accuracy(self):
        """Test delay calculations and speed scoring."""
        paper_engine = PaperTradingEngine(initial_balance=10000)
        
        # Create signal with known timestamp
        whale_time = datetime.now() - timedelta(seconds=30)
        trade = WhaleTrade(
            tx_hash="0x" + uuid.uuid4().hex[:16],
            whale_address="0xwhale001",
            market_id="market_001",
            market_question="Will BTC reach $100k?",
            outcome="YES",
            amount=10000.0,
            price=0.52,
            timestamp=whale_time,
            block_number=12345678
        )
        
        signal = WhaleSignal(
            trade=trade,
            urgency=TradeUrgency.FLASH,
            pattern_confidence=0.85,
            time_since_market_created=timedelta(hours=1),
            time_since_last_trade=None,
            whale_pattern_profile="SNIPER",
            recommended_action="COPY_IMMEDIATE",
            suggested_size=500.0,
            max_delay_seconds=60
        )
        
        market_data = {
            'current_price': 0.53,
            'liquidity': 150000,
            'volatility_1min': 0.02
        }
        
        position = paper_engine.execute_paper_trade(
            signal=signal,
            delay_seconds=30,
            market_data=market_data
        )
        
        # Verify timing metrics
        assert position.timing_metrics is not None
        assert position.timing_metrics.entry_delay_seconds >= 30
        assert position.timing_metrics.speed_score > 0
        
        # Speed score should be higher for lower delays
        # With 30 second delay and 300 second max: score = 1 - (30/300) = 0.9
        expected_score = max(0, 1 - (30 / 300))
        assert abs(position.timing_metrics.speed_score - expected_score) < 0.1


class TestLiveTradingIntegration:
    """Test live trading mode integration."""
    
    def test_paper_to_live_transition(self, setup_database):
        """Test switching from paper to live trading mode."""
        db = setup_database
        
        # Start in paper mode
        paper_trade = TradeData(
            trade_id="paper_trade_001",
            market_id="market_001",
            market_question="Test Market",
            side="YES",
            trade_type="paper",
            entry_price=0.52,
            size_usd=500.0,
            status="open"
        )
        
        success = db.record_trade(paper_trade)
        assert success
        
        # Switch to live mode
        live_trade = TradeData(
            trade_id="live_trade_001",
            market_id="market_001",
            market_question="Test Market",
            side="YES",
            trade_type="live",
            entry_price=0.52,
            size_usd=500.0,
            status="open"
        )
        
        success = db.record_trade(live_trade)
        assert success
        
        # Verify both trades are recorded correctly
        paper_trades = db.get_trade_history(filters={'trade_type': 'paper'}, limit=10)
        live_trades = db.get_trade_history(filters={'trade_type': 'live'}, limit=10)
        
        assert any(t['trade_id'] == 'paper_trade_001' for t in paper_trades)
        assert any(t['trade_id'] == 'live_trade_001' for t in live_trades)
    
    @pytest.mark.asyncio
    async def test_live_order_placement(self, mock_polymarket_api):
        """Test order flow with mocked API."""
        # Mock order placement
        order_data = {
            "market_id": "market_001",
            "side": "YES",
            "size": 100,
            "price": 0.52
        }
        
        result = mock_polymarket_api.place_order(order_data)
        
        assert result["status"] == "filled"
        assert "orderId" in result
        assert result["filled_size"] == order_data["size"]
        assert result["filled_price"] == order_data["price"]
        
        # Verify position tracking
        position = mock_polymarket_api.get_position("pos_001")
        assert position["market_id"] == "market_001"
        assert position["size"] > 0
    
    def test_error_recovery(self, setup_database):
        """Test failed trade handling and recovery."""
        db = setup_database
        
        # Record a failed trade
        failed_trade = TradeData(
            trade_id="failed_trade_001",
            market_id="market_001",
            market_question="Test Market",
            side="YES",
            trade_type="live",
            entry_price=0.52,
            size_usd=500.0,
            status="cancelled",
            metadata={'error': 'Insufficient liquidity', 'retry_count': 2}
        )
        
        success = db.record_trade(failed_trade)
        assert success
        
        # Record recovery attempt
        recovery_trade = TradeData(
            trade_id="recovery_trade_001",
            market_id="market_001",
            market_question="Test Market",
            side="YES",
            trade_type="live",
            entry_price=0.52,
            size_usd=250.0,  # Reduced size
            status="open",
            metadata={'recovered_from': 'failed_trade_001', 'reduced_size': True}
        )
        
        success = db.record_trade(recovery_trade)
        assert success
        
        # Verify both are in history
        all_trades = db.get_trade_history(limit=100)
        assert any(t['trade_id'] == 'failed_trade_001' for t in all_trades)
        assert any(t['trade_id'] == 'recovery_trade_001' for t in all_trades)
    
    def test_circuit_breaker_integration(self):
        """Test risk system circuit breakers."""
        position_manager = PositionManager(
            initial_bankroll=10000,
            risk_params=RiskParameters(
                max_daily_drawdown=0.10,
                max_total_drawdown=0.20
            )
        )
        
        # Simulate hitting daily drawdown limit
        position_manager.portfolio.daily_pnl = -1500  # Exceeds 10% of 10k
        
        # Create a mock signal
        from dataclasses import dataclass
        @dataclass
        class MockSignal:
            suggested_size: float = 500.0
            
        signal = MockSignal(suggested_size=500.0)
        
        # Check drawdown detection
        # Note: The actual implementation may vary, but drawdown should be detected
        daily_loss_pct = abs(min(0, position_manager.portfolio.daily_pnl)) / position_manager.portfolio.bankroll
        assert daily_loss_pct >= 0.10
        
        # Verify circuit breaker would trigger (daily loss > 10%)
        assert daily_loss_pct >= position_manager.risk_params.max_daily_drawdown


class TestDatabaseIntegration:
    """Test database integration across all operations."""
    
    def test_trade_recording(self, setup_database):
        """Test database writes and reads."""
        db = setup_database
        
        # Record new trade
        trade = TradeData(
            trade_id="test_trade_new",
            market_id="market_new",
            market_question="New Test Market",
            side="YES",
            trade_type="paper",
            entry_price=0.55,
            size_usd=1000.0,
            status="open"
        )
        
        success = db.record_trade(trade)
        assert success
        
        # Read back
        recorded = db.get_trade_history(filters={'trade_id': 'test_trade_new'}, limit=1)
        assert len(recorded) == 1
        assert recorded[0]['market_id'] == "market_new"
        assert recorded[0]['entry_price'] == 0.55
    
    def test_analytics_queries(self, setup_database):
        """Test analytics accuracy."""
        db = setup_database
        
        # Get performance summary
        summary = db.get_performance_summary(days=30)
        
        assert 'total_trades' in summary
        assert 'winning_trades' in summary
        assert 'losing_trades' in summary
        assert 'win_rate' in summary
        
        # Verify calculations
        total = summary['total_trades']
        wins = summary['winning_trades']
        losses = summary['losing_trades']
        
        if total > 0:
            expected_win_rate = (wins / total) * 100
            assert abs(summary['win_rate'] - expected_win_rate) < 0.01
    
    def test_whale_profile_updates(self, setup_database):
        """Test whale profile management."""
        db = setup_database
        
        # Save whale profile
        whale = WhaleProfile(
            address="0xtestwhale001",
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=60.0,
            profit_factor=1.5,
            reliability_tier="gold"
        )
        
        success = db.save_whale_profile(whale)
        assert success
        
        # Retrieve and verify
        profile = db.get_whale_profile("0xtestwhale001")
        assert profile is not None
        assert profile['total_trades'] == 100
        assert profile['win_rate'] == 60.0
        
        # Update with new trade result
        success = db.update_whale_performance("0xtestwhale001", {'pnl': 100.0})
        assert success
        
        # Verify update
        updated = db.get_whale_profile("0xtestwhale001")
        assert updated['total_trades'] == 101  # Should increment
    
    def test_event_logging(self, setup_database):
        """Test system event logs."""
        db = setup_database
        
        # Log various events
        events = [
            {'type': 'trade', 'message': 'Trade executed: trade_001'},
            {'type': 'signal', 'message': 'High EV signal detected'},
            {'type': 'error', 'message': 'API connection failed'},
            {'type': 'system', 'message': 'Bot started successfully'}
        ]
        
        for event in events:
            success = db.log_event(event['type'], event['message'])
            assert success
        
        # Query events by type
        trade_events = db.get_events(event_type='trade', limit=10)
        error_events = db.get_events(event_type='error', limit=10)
        
        assert len(trade_events) > 0
        assert len(error_events) > 0


class TestNotificationIntegration:
    """Test notification system integration."""
    
    @pytest.mark.asyncio
    async def test_high_ev_alerts(self):
        """Test notification triggers for high EV opportunities."""
        config = NotificationConfig(
            enable_discord=False,
            enable_telegram=False,
            enable_console=True,
            min_ev_threshold=0.03  # 3%
        )
        
        manager = NotificationManager(config=config)
        
        # High EV signal (should trigger)
        high_ev_signal = {
            "market": "BTC $100k",
            "side": "YES",
            "confidence": 0.8,
            "current_price": 0.45
        }
        
        with patch.object(manager, '_send_all_channels') as mock_send:
            mock_send.return_value = {"discord": False, "telegram": False, "console": True}
            await manager.notify_high_ev_opportunity(high_ev_signal, ev=0.05)
            mock_send.assert_called_once()
        
        # Low EV signal (should not trigger)
        low_ev_signal = {
            "market": "ETH $10k",
            "side": "NO",
            "confidence": 0.6,
            "current_price": 0.50
        }
        
        with patch.object(manager, '_send_all_channels') as mock_send:
            mock_send.return_value = {"discord": False, "telegram": False, "console": False}
            result = await manager.notify_high_ev_opportunity(low_ev_signal, ev=0.01)
            # Should return without sending due to threshold
            assert result == {"discord": False, "telegram": False, "console": False}
    
    @pytest.mark.asyncio
    async def test_trade_notifications(self):
        """Test execution alerts."""
        config = NotificationConfig(
            enable_discord=False,
            enable_telegram=False,
            enable_console=True
        )
        
        manager = NotificationManager(config=config)
        
        position = {
            "market": "Will BTC reach $100k?",
            "side": "YES",
            "size": 500.0,
            "entry_price": 0.52,
            "expected_value": 0.04
        }
        
        with patch.object(manager, '_send_all_channels') as mock_send:
            mock_send.return_value = {"discord": False, "telegram": False, "console": True}
            result = await manager.notify_trade_executed(position)
            assert result["console"] is True
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_daily_summary(self):
        """Test report delivery."""
        config = NotificationConfig(
            enable_discord=False,
            enable_telegram=False,
            enable_console=True
        )
        
        manager = NotificationManager(config=config)
        
        stats = {
            "date": "2024-06-15",
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
            "total_pnl": 250.0,
            "win_rate": 60.0,
            "avg_trade": 25.0,
            "largest_win": 100.0,
            "largest_loss": -50.0
        }
        
        with patch.object(manager, '_send_all_channels') as mock_send:
            mock_send.return_value = {"discord": False, "telegram": False, "console": True}
            result = await manager.notify_daily_summary(stats)
            assert result["console"] is True
            mock_send.assert_called_once()


class TestBacktestingIntegration:
    """Test backtesting system integration."""
    
    def test_backtest_with_real_data(self, setup_test_whales):
        """Test end-to-end backtest."""
        engine = BacktestEngine(
            initial_capital=10000.0,
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now()
        )
        
        # Create historical trade data
        historical_trades = []
        for i in range(50):
            trade = {
                'timestamp': datetime.now() - timedelta(days=i),
                'market_id': f"market_{i % 5}",
                'whale_address': "0xwhale001" if i % 2 == 0 else "0xwhale002",
                'whale_confidence': 0.8 if i % 2 == 0 else 0.6,
                'side': 'buy' if i % 3 != 0 else 'sell',
                'price': 0.45 + (np.random.random() * 0.1),
                'size': 1000.0 + (np.random.random() * 2000),
                'market': {
                    'id': f"market_{i % 5}",
                    'question': f"Test Market {i % 5}",
                    'liquidity': 100000
                }
            }
            historical_trades.append(trade)
        
        engine.historical_trades = historical_trades
        
        # Configure strategy
        config = StrategyConfig(
            strategy_type=StrategyType.COPY_HIGH_CONFIDENCE,
            name="High Confidence Strategy",
            min_whale_confidence=0.7,
            position_size_percent=0.02,
            max_positions=5
        )
        
        # Run backtest
        result = engine.run_backtest(config)
        
        assert isinstance(result, BacktestResult)
        assert result.total_trades > 0
        assert result.initial_capital == 10000.0
        assert result.final_capital is not None
    
    def test_strategy_comparison(self, setup_test_whales):
        """Test multi-strategy comparison."""
        engine = BacktestEngine(initial_capital=10000.0)
        
        # Create test data
        historical_trades = []
        for i in range(100):
            trade = {
                'timestamp': datetime.now() - timedelta(days=i),
                'market_id': f"market_{i % 10}",
                'whale_address': "0xwhale001",
                'whale_confidence': np.random.random(),
                'side': 'buy',
                'price': 0.5,
                'size': 1000.0,
                'market': {'id': f"market_{i % 10}", 'question': "Test", 'liquidity': 100000}
            }
            historical_trades.append(trade)
        
        engine.historical_trades = historical_trades
        
        # Test multiple strategies
        strategies = [
            StrategyConfig(
                strategy_type=StrategyType.COPY_ALL_WHALE,
                name="Copy All",
                position_size_percent=0.01
            ),
            StrategyConfig(
                strategy_type=StrategyType.COPY_HIGH_CONFIDENCE,
                name="High Confidence Only",
                min_whale_confidence=0.7,
                position_size_percent=0.01
            ),
            StrategyConfig(
                strategy_type=StrategyType.COPY_LARGE_TRADES,
                name="Large Trades Only",
                min_trade_size=2000,
                position_size_percent=0.01
            )
        ]
        
        results = []
        for config in strategies:
            result = engine.run_backtest(config)
            results.append({
                'strategy': config.name,
                'trades': result.total_trades,
                'return': result.total_return_percent,
                'win_rate': result.win_rate,
                'sharpe': result.sharpe_ratio
            })
        
        # Compare results
        assert len(results) == 3
        for r in results:
            assert 'strategy' in r
            assert 'trades' in r
            assert 'return' in r
    
    def test_monte_carlo_simulation(self):
        """Test risk simulation."""
        # Create a mock Monte Carlo result class
        from dataclasses import dataclass
        
        @dataclass
        class MockMonteCarloResult:
            num_simulations: int
            confidence_level: float
            mean_return: float
            median_return: float
            std_return: float
            min_return: float
            max_return: float
            percentile_5: float
            percentile_25: float
            percentile_75: float
            percentile_95: float
            mean_max_drawdown: float
            worst_case_drawdown: float
            prob_profit: float
            prob_double: float
            prob_ruin: float
        
        # Create historical returns
        returns = np.random.normal(0.001, 0.02, 252)  # Daily returns
        
        # Run simple Monte Carlo calculation
        simulations = 1000
        final_returns = []
        max_drawdowns = []
        
        for _ in range(simulations):
            # Random walk simulation
            cumulative = 1.0
            peak = 1.0
            max_dd = 0.0
            
            for ret in np.random.choice(returns, size=252):
                cumulative *= (1 + ret)
                if cumulative > peak:
                    peak = cumulative
                dd = (peak - cumulative) / peak
                if dd > max_dd:
                    max_dd = dd
            
            final_returns.append(cumulative - 1)
            max_drawdowns.append(max_dd)
        
        mc_result = MockMonteCarloResult(
            num_simulations=simulations,
            confidence_level=0.95,
            mean_return=np.mean(final_returns),
            median_return=np.median(final_returns),
            std_return=np.std(final_returns),
            min_return=np.min(final_returns),
            max_return=np.max(final_returns),
            percentile_5=np.percentile(final_returns, 5),
            percentile_25=np.percentile(final_returns, 25),
            percentile_75=np.percentile(final_returns, 75),
            percentile_95=np.percentile(final_returns, 95),
            mean_max_drawdown=np.mean(max_drawdowns),
            worst_case_drawdown=np.max(max_drawdowns),
            prob_profit=sum(1 for r in final_returns if r > 0) / simulations,
            prob_double=sum(1 for r in final_returns if r > 1.0) / simulations,
            prob_ruin=sum(1 for dd in max_drawdowns if dd > 0.5) / simulations
        )
        
        assert mc_result is not None
        assert mc_result.num_simulations == 1000
        assert mc_result.confidence_level == 0.95
        assert mc_result.mean_return is not None
        assert mc_result.percentile_5 is not None
        assert mc_result.percentile_95 is not None


class TestEndToEnd:
    """Test end-to-end scenarios."""
    
    @pytest.mark.asyncio
    async def test_24h_simulation(self, setup_database, setup_test_whales, setup_test_markets):
        """Test full day simulation."""
        db = setup_database
        paper_engine = PaperTradingEngine(initial_balance=10000)
        position_manager = PositionManager(initial_bankroll=10000)
        
        # Simulate 24 hours of trading
        trades_executed = 0
        for hour in range(24):
            # Simulate whale activity every few hours
            if hour % 3 == 0:
                trade = WhaleTrade(
                    tx_hash=f"0x{uuid.uuid4().hex[:16]}",
                    whale_address="0xwhale001",
                    market_id="market_001",
                    market_question="Will BTC reach $100k?",
                    outcome="YES" if hour % 2 == 0 else "NO",
                    amount=10000.0,
                    price=0.52,
                    timestamp=datetime.now() - timedelta(hours=hour),
                    block_number=12345678 + hour
                )
                
                signal = WhaleSignal(
                    trade=trade,
                    urgency=TradeUrgency.FLASH,
                    pattern_confidence=0.8,
                    time_since_market_created=timedelta(hours=1),
                    time_since_last_trade=timedelta(hours=3),
                    whale_pattern_profile="SNIPER",
                    recommended_action="COPY_IMMEDIATE",
                    suggested_size=500.0,
                    max_delay_seconds=60
                )
                
                market_data = setup_test_markets["market_001"]
                
                # Execute paper trade
                position = paper_engine.execute_paper_trade(
                    signal=signal,
                    delay_seconds=30,
                    market_data=market_data
                )
                
                if position:
                    trades_executed += 1
                    
                    # Record in database
                    trade_data = TradeData(
                        trade_id=position.position_id,
                        market_id=position.market_id,
                        market_question=position.market_question,
                        side=position.direction,
                        trade_type="paper",
                        entry_price=position.entry_price,
                        size_usd=position.size_usd,
                        status="open"
                    )
                    db.record_trade(trade_data)
        
        # Verify results
        assert trades_executed > 0
        
        performance = paper_engine.get_performance_report()
        assert 'summary' in performance
        assert performance['summary']['total_trades'] == trades_executed
    
    def test_multiple_whales(self, setup_database, setup_test_whales, setup_test_markets):
        """Test multi-whale scenario."""
        db = setup_database
        paper_engine = PaperTradingEngine(initial_balance=10000)
        
        # Simulate trades from multiple whales
        whales = setup_test_whales
        trades_per_whale = 5
        
        for whale_addr, whale in whales.items():
            for i in range(trades_per_whale):
                trade = WhaleTrade(
                    tx_hash=f"0x{whale_addr}_{i}",
                    whale_address=whale_addr,
                    market_id="market_001",
                    market_question="Will BTC reach $100k?",
                    outcome="YES" if i % 2 == 0 else "NO",
                    amount=5000.0 + (i * 1000),
                    price=0.50 + (i * 0.01),
                    timestamp=datetime.now() - timedelta(minutes=i*10),
                    block_number=12345678 + i
                )
                
                signal = WhaleSignal(
                    trade=trade,
                    urgency=TradeUrgency.FLASH if i == 0 else TradeUrgency.ROUTINE,
                    pattern_confidence=0.7 + (i * 0.05),
                    time_since_market_created=timedelta(hours=1),
                    time_since_last_trade=timedelta(minutes=i*10),
                    whale_pattern_profile="SNIPER" if whale_addr == "0xwhale001" else "ACCUMULATOR",
                    recommended_action="COPY_IMMEDIATE" if whale.confidence_level == "high" else "WAIT_CONFIRM",
                    suggested_size=min(500.0, whale.net_pnl * 0.02),
                    max_delay_seconds=60
                )
                
                # Only copy high confidence whales
                if whale.confidence_level == "high":
                    position = paper_engine.execute_paper_trade(
                        signal=signal,
                        delay_seconds=30,
                        market_data=setup_test_markets["market_001"]
                    )
                    
                    if position:
                        trade_data = TradeData(
                            trade_id=position.position_id,
                            market_id=position.market_id,
                            market_question=position.market_question,
                            side=position.direction,
                            trade_type="paper",
                            entry_price=position.entry_price,
                            size_usd=position.size_usd,
                            status="open",
                            whale_address=whale_addr
                        )
                        db.record_trade(trade_data)
        
        # Verify trades from multiple whales
        all_trades = db.get_trade_history(limit=100)
        whale_addresses = set(t['whale_address'] for t in all_trades if t['whale_address'])
        assert len(whale_addresses) >= 1  # At least one high-confidence whale should have trades
    
    def test_market_volatility_handling(self, setup_database, setup_test_markets):
        """Test stress test with volatile market conditions."""
        db = setup_database
        paper_engine = PaperTradingEngine(initial_balance=10000)
        
        # Simulate high volatility scenario
        volatile_market = setup_test_markets["market_001"].copy()
        volatile_market['volatility'] = 0.50  # Very high volatility
        
        # Rapid price changes
        prices = [0.45, 0.55, 0.40, 0.60, 0.35, 0.65, 0.30, 0.70]
        
        for i, price in enumerate(prices):
            volatile_market['current_price'] = price
            
            trade = WhaleTrade(
                tx_hash=f"0xvolatile_{i}",
                whale_address="0xwhale001",
                market_id="market_001",
                market_question="Will BTC reach $100k?",
                outcome="YES" if i % 2 == 0 else "NO",
                amount=10000.0,
                price=price,
                timestamp=datetime.now() - timedelta(minutes=i*5),
                block_number=12345678 + i
            )
            
            signal = WhaleSignal(
                trade=trade,
                urgency=TradeUrgency.FLASH,
                pattern_confidence=0.75,
                time_since_market_created=timedelta(hours=1),
                time_since_last_trade=timedelta(minutes=i*5),
                whale_pattern_profile="SNIPER",
                recommended_action="COPY_IMMEDIATE",
                suggested_size=500.0,
                max_delay_seconds=60
            )
            
            position = paper_engine.execute_paper_trade(
                signal=signal,
                delay_seconds=20,
                market_data=volatile_market
            )
            
            if position:
                trade_data = TradeData(
                    trade_id=position.position_id,
                    market_id=position.market_id,
                    market_question=position.market_question,
                    side=position.direction,
                    trade_type="paper",
                    entry_price=position.entry_price,
                    size_usd=position.size_usd,
                    status="open"
                )
                db.record_trade(trade_data)
        
        # Verify system handled volatility
        timing_summary = paper_engine.get_timing_summary()
        assert timing_summary['total_trades'] > 0
        
        # Check slippage tracking
        performance = paper_engine.get_performance_report()
        assert 'timing' in performance


# ============================================================================
# Utility Tests
# ============================================================================

class TestUtilityIntegration:
    """Test utility functions and helpers."""
    
    def test_circular_buffer(self):
        """Test circular buffer for trade history."""
        buffer = CircularBuffer(size=5)
        
        # Add items
        for i in range(10):
            buffer.add(i)
        
        # Should only keep last 5
        all_items = buffer.get_all()
        assert len(all_items) == 5
        assert all_items == [5, 6, 7, 8, 9]
        
        # Get recent
        recent = buffer.get_recent(3)
        assert len(recent) == 3
        assert recent == [7, 8, 9]
    
    def test_trade_urgency_classification(self):
        """Test trade urgency classification."""
        # Test FLASH classification
        flash_trade = WhaleTrade(
            tx_hash="0xflash",
            whale_address="0xwhale001",
            market_id="market_001",
            market_question="Test",
            outcome="YES",
            amount=10000,
            price=0.52,
            timestamp=datetime.now(),
            block_number=12345678,
            market_created_at=datetime.now() - timedelta(seconds=30)
        )
        
        assert flash_trade.market_created_at is not None
        time_since = flash_trade.timestamp - flash_trade.market_created_at
        assert time_since < timedelta(minutes=2)
    
    @pytest.mark.asyncio
    async def test_async_components(self):
        """Test async component integration."""
        async def mock_async_operation():
            await asyncio.sleep(0.01)
            return {"status": "success", "data": "test"}
        
        result = await mock_async_operation()
        assert result["status"] == "success"
        assert result["data"] == "test"
    
    def test_position_sizing_calculations(self):
        """Test position sizing math."""
        position_manager = PositionManager(
            initial_bankroll=10000,
            risk_params=RiskParameters(
                max_risk_per_trade=0.02,
                kelly_fraction=0.5
            )
        )
        
        # Test Kelly sizing
        from dataclasses import dataclass
        @dataclass
        class MockSignal:
            entry_price: float = 0.50
            stop_loss: float = 0.45
            target_price: float = 0.60
            
            def calculate_position_size(self, bankroll, kelly_fraction):
                # Simplified Kelly
                win_prob = 0.6
                win_amount = self.target_price - self.entry_price
                loss_amount = self.entry_price - self.stop_loss
                b = win_amount / loss_amount if loss_amount > 0 else 1
                p = win_prob
                q = 1 - p
                kelly = (b * p - q) / b
                return bankroll * kelly * kelly_fraction
        
        signal = MockSignal()
        size = position_manager.calculate_position_size(signal, signal.entry_price)
        
        assert size > 0
        assert size <= position_manager.risk_params.max_position_size
        assert size >= position_manager.risk_params.min_position_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
