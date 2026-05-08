#!/usr/bin/env python3
"""
PolyBot v2 - Real-Time Whale Pattern Hunter

TRANSFORMED from "1 bet/day researcher" to "real-time whale pattern tracker"

New Features:
- Real-time whale monitoring (30s polling)
- Speed-matched paper trading (sub-minute reaction)
- Pattern recognition (Sniper, Accumulator, Swinger, etc.)
- Crypto market filtering
- Timing analysis and educational metrics
- Comprehensive backtesting
- Performance analytics
- Automated workflow scheduling
- Live trading integration
- Multi-channel notifications

Usage:
    # Real-time monitoring
    python cli_bot_v2.py watch --whales 0x123...,0x456... --crypto-only
    
    # Behavioral analysis
    python cli_bot_v2.py study 0x123... --days 30
    
    # Performance commands
    python cli_bot_v2.py speed-test
    python cli_bot_v2.py paper-report
    python cli_bot_v2.py backtest --strategy copy_all --days 30
    
    # Live trading
    python cli_bot_v2.py live --enable
    
    # Automation
    python cli_bot_v2.py schedule start
    python cli_bot_v2.py schedule stop
    python cli_bot_v2.py schedule status
    
    # System
    python cli_bot_v2.py notify-test
    python cli_bot_v2.py status

Legacy commands still work:
    python cli_bot_v2.py status
    python cli_bot_v2.py scan
    python cli_bot_v2.py analyze
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Existing imports
from polymarket_tracker.data.subgraph_client import SubgraphClient
from polymarket_tracker.winners.winner_discovery import WinnerDiscovery
from polymarket_tracker.winners.ev_calculator import EVCalculator
from polymarket_tracker.winners.copy_engine import CopyEngine
from polymarket_tracker.risk.position_manager import PositionManager, RiskParameters
from polymarket_tracker.deep_analysis.winner_intelligence import WinnerIntelligence
from polymarket_tracker.deep_analysis.advanced_ev import AdvancedEVCalculator
from polymarket_tracker.deep_analysis.multi_factor_model import MultiFactorModel
from polymarket_tracker.deep_analysis.research_engine import ResearchEngine

# NEW: Real-time imports
from polymarket_tracker.streaming.whale_stream_monitor import WhaleStreamMonitor, WhaleSignal
from polymarket_tracker.streaming.crypto_filter import CryptoMarketFilter, CRYPTO_ONLY_FILTER
from polymarket_tracker.intelligence.pattern_engine import PatternEngine, PatternType
from polymarket_tracker.intelligence.behavioral_profiler import BehavioralProfiler
from polymarket_tracker.paper_trading.paper_trading_engine import PaperTradingEngine
from polymarket_tracker.winners.speed_matched_copy_engine import SpeedMatchedCopyEngine, CopyAction

# NEW: Additional components
from polymarket_tracker.analytics.performance_dashboard import PerformanceDashboard

# NEW: Ultra real-time trading system
from polymarket_tracker.realtime.ultra_trading_system import UltraTradingSystem, run_ultra_trading
from polymarket_tracker.backtesting.backtest_engine import (
    BacktestEngine, StrategyConfig, StrategyType,
    create_copy_all_strategy, create_high_confidence_strategy,
    create_crypto_only_strategy, create_kelly_strategy
)
from polymarket_tracker.automation.workflow_scheduler import WorkflowScheduler, WorkflowConfig
from polymarket_tracker.notifications.notification_manager import NotificationManager, NotificationConfig
from polymarket_tracker.exchange.polymarket_client import PolymarketClient, create_client_from_env
from polymarket_tracker.data.database import TradeDatabase, TradeData


class CLIBotV2:
    """
    PolyBot v2 - Real-Time Whale Pattern Hunter
    
    Combines legacy deep analysis with new real-time monitoring,
    backtesting, performance analytics, and live trading.
    """
    
    def __init__(self):
        # Legacy components
        self.subgraph = None
        self.winner_discovery = None
        self.ev_calc = None
        self.copy_engine = None
        self.position_manager = None
        self.research_engine = None
        
        # NEW: Real-time components
        self.stream_monitor = None
        self.pattern_engine = PatternEngine()
        self.behavioral_profiler = BehavioralProfiler()
        self.paper_trading = None
        self.speed_copy_engine = None
        self.crypto_filter = CRYPTO_ONLY_FILTER
        
        # NEW: Advanced components
        self.performance_dashboard: Optional[PerformanceDashboard] = None
        self.ultra_system: Optional[UltraTradingSystem] = None
        self.backtest_engine: Optional[BacktestEngine] = None
        self.workflow_scheduler: Optional[WorkflowScheduler] = None
        self.notification_manager: Optional[NotificationManager] = None
        self.live_client: Optional[PolymarketClient] = None
        self.database: Optional[TradeDatabase] = None
        
        # State
        self.state_file = project_root / "bot_state_v2.json"
        self.state = self._load_state()
        self.winners = []
        
        # Tracking
        self.is_watching = False
        self.live_trading_enabled = False
        
        # Callbacks
        self._whale_signal_callbacks: List[Callable] = []
        
    def _load_state(self) -> Dict:
        """Load bot state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "tracked_whales": [],
            "paper_balance": 10000,
            "total_paper_pnl": 0,
            "timing_metrics": {
                "avg_detection_lag": 0,
                "avg_execution_lag": 0,
                "total_copies": 0
            },
            "pattern_stats": {},
            "last_watch": None,
            "live_trading_enabled": False,
            "backtest_results": [],
            "workflow_running": False
        }
    
    def _save_state(self):
        """Save bot state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    async def _init_clients(self, full_init: bool = False):
        """Initialize API clients and components."""
        if not self.subgraph:
            api_key = os.getenv("THEGRAPH_API_KEY")
            if not api_key:
                print("Error: THEGRAPH_API_KEY not set")
                return False
            
            self.subgraph = SubgraphClient(api_key)
            
            # Legacy components
            self.winner_discovery = WinnerDiscovery(self.subgraph)
            self.ev_calc = EVCalculator(self.subgraph)
            
            risk_params = RiskParameters(
                max_risk_per_trade=0.02,
                max_total_exposure=0.50,
                max_open_positions=5,
                max_daily_drawdown=0.10
            )
            self.position_manager = PositionManager(
                initial_bankroll=self.state.get('paper_balance', 10000),
                risk_params=risk_params
            )
            self.copy_engine = CopyEngine(self.ev_calc, self.position_manager)
            
            # Deep analysis
            winner_intel = WinnerIntelligence(self.subgraph)
            adv_ev = AdvancedEVCalculator(self.subgraph)
            factor_model = MultiFactorModel()
            self.research_engine = ResearchEngine(winner_intel, adv_ev, factor_model)
            
            # NEW: Paper trading
            self.paper_trading = PaperTradingEngine(
                initial_balance=self.state.get('paper_balance', 10000)
            )
            
            # NEW: Speed copy engine
            self.speed_copy_engine = SpeedMatchedCopyEngine(
                pattern_engine=self.pattern_engine,
                paper_trading_engine=self.paper_trading,
                position_manager=self.position_manager,
                delay_tolerance_seconds=60,
                min_pattern_confidence=0.7,
                crypto_only=True
            )
            
            # NEW: Initialize advanced components if full_init
            if full_init:
                await self._init_advanced_components()
        
        return True
    
    async def _init_advanced_components(self):
        """Initialize advanced components (dashboard, backtest, scheduler, etc.)."""
        # Performance Dashboard
        try:
            self.performance_dashboard = PerformanceDashboard(
                bankroll=self.state.get('paper_balance', 10000)
            )
            print("[OK] Performance Dashboard initialized")
        except Exception as e:
            print(f"[WARN] Performance Dashboard initialization failed: {e}")
        
        # Database
        try:
            self.database = TradeDatabase()
            print("[OK] Database initialized")
        except Exception as e:
            print(f"[WARN] Database initialization failed: {e}")
        
        # Notification Manager
        try:
            self.notification_manager = NotificationManager()
            await self.notification_manager._get_session()
            print("[OK] Notification Manager initialized")
        except Exception as e:
            print(f"[WARN] Notification Manager initialization failed: {e}")
        
        # Workflow Scheduler
        try:
            self.workflow_scheduler = WorkflowScheduler(
                config=WorkflowConfig.from_env(),
                notification_manager=self.notification_manager,
                position_manager=self.position_manager,
                cli_bot=self
            )
            print("[OK] Workflow Scheduler initialized")
        except Exception as e:
            print(f"[WARN] Workflow Scheduler initialization failed: {e}")
    
    async def _init_live_trading(self):
        """Initialize live trading client."""
        try:
            self.live_client = create_client_from_env()
            balance = self.live_client.get_balance()
            print(f"[OK] Live trading client initialized")
            print(f"   Balance: ${balance.usdc_available:,.2f} USDC available")
            return True
        except ValueError as e:
            print(f"[ERROR] Live trading initialization failed: {e}")
            print("   Set POLYMARKET_API_KEY and POLYMARKET_API_SECRET environment variables")
            return False
        except Exception as e:
            print(f"[ERROR] Live trading initialization failed: {e}")
            return False
    
    # ==================== NEW REAL-TIME COMMANDS ====================
    
    async def ultra(self, 
                    mode: str = "paper",
                    speed: str = "ultra", 
                    whales: Optional[List[str]] = None,
                    predictive: bool = False,
                    arbitrage: bool = False,
                    websocket_only: bool = False,
                    blockchain_only: bool = False):
        """
        Ultra-low latency real-time trading terminal.
        
        Usage: python cli_bot_v2.py ultra --mode paper --speed ultra --whales 0x123...,0x456...
        
        Features:
        - Professional trading terminal UI with Rich
        - Real-time latency metrics (100ms updates)
        - Mode selection: paper/live/simulation
        - Speed profiles: ultra/balanced/economy
        - Component toggles: predictive, arbitrage, websocket-only, blockchain-only
        
        Interactive Controls:
        - P: Pause/Resume
        - E: Emergency Stop
        - S: Show status
        - L: Toggle live/paper mode
        - Q: Quit gracefully
        
        Args:
            mode: Trading mode - 'paper' (default), 'live', or 'simulation'
            speed: Speed profile - 'ultra' (default), 'balanced', or 'economy'
            whales: Comma-separated list of whale addresses to track
            predictive: Enable predictive entry system
            arbitrage: Enable arbitrage detection
            websocket_only: Use only WebSocket data (no blockchain)
            blockchain_only: Use only blockchain monitoring (no WebSocket)
        """
        print("=" * 80)
        print("POLYBOT ULTRA - Starting Ultra-Low Latency Trading Terminal")
        print("=" * 80)
        
        # Parse whale addresses
        whale_list = None
        if whales:
            whale_list = [w.strip() for w in whales.split(',')]
        else:
            # Use tracked whales from state
            whale_list = self.state.get('tracked_whales', [])
        
        if not whale_list:
            print("\n[ERROR] No whale addresses specified.")
            print("Use --whales or run 'scan' first to find whales.")
            print("\nExample:")
            print("  python cli_bot_v2.py ultra --mode paper --whales 0x123...,0x456...")
            return
        
        print(f"\nConfiguration:")
        print(f"  Mode: {mode.upper()}")
        print(f"  Speed: {speed.upper()}")
        print(f"  Whales: {len(whale_list)}")
        print(f"  Predictive: {'Enabled' if predictive else 'Disabled'}")
        print(f"  Arbitrage: {'Enabled' if arbitrage else 'Disabled'}")
        print(f"  Data Sources: {'WebSocket only' if websocket_only else 'Blockchain only' if blockchain_only else 'Both'}")
        
        print("\n[WARNING] This will take over your terminal with the Ultra trading interface.")
        print("          Press 'Q' at any time to exit gracefully.")
        print("          Press 'E' for emergency stop.")
        
        if mode == "live":
            print("\n" + "!" * 80)
            print("!!! LIVE TRADING MODE !!!")
            print("!!! Real money will be at risk !!!")
            print("!" * 80)
        
        try:
            # Initialize and run ultra trading system
            self.ultra_system = UltraTradingSystem()
            await self.ultra_system.start(
                mode=mode,
                speed=speed,
                whales=whale_list,
                enable_predictive=predictive,
                enable_arbitrage=arbitrage,
                websocket_only=websocket_only,
                blockchain_only=blockchain_only
            )
        except KeyboardInterrupt:
            print("\n\nStopping Ultra trading...")
            if self.ultra_system:
                await self.ultra_system.stop()
        except Exception as e:
            print(f"\n[ERROR] Ultra trading failed: {e}")
            logger.error(f"Ultra trading error: {e}")
        finally:
            self.ultra_system = None
            print("\n[OK] Ultra trading session ended")
    
    async def watch(self, whale_addresses: List[str], crypto_only: bool = True, 
                    enable_notifications: bool = False):
        """
        Real-time whale monitoring with pattern annotations and automatic paper trading.
        
        Usage: python cli_bot_v2.py watch --whales 0x123...,0x456...
        
        Args:
            whale_addresses: List of whale addresses to monitor
            crypto_only: Only track crypto markets (default: True)
            enable_notifications: Send Discord/Telegram notifications (default: False)
        """
        print("=" * 80)
        print("WHALE WATCH MODE - Real-Time Pattern Tracking")
        print("=" * 80)
        print(f"\nTracking {len(whale_addresses)} whale(s)")
        print(f"Crypto-only: {crypto_only}")
        print(f"Poll interval: 30 seconds")
        print(f"Max delay to copy: 60 seconds")
        print(f"Notifications: {'enabled' if enable_notifications else 'disabled'}")
        print("\nPress Ctrl+C to stop\n")
        
        if not await self._init_clients(full_init=True):
            return
        
        # Initialize stream monitor
        self.stream_monitor = WhaleStreamMonitor(
            subgraph_client=self.subgraph,
            whale_addresses=whale_addresses,
            poll_interval=30,
            crypto_only=crypto_only
        )
        
        # Set up callbacks
        self.stream_monitor.add_callback(self._on_whale_signal)
        if enable_notifications and self.notification_manager:
            self.stream_monitor.add_callback(self._on_whale_signal_notification)
        
        # Track state
        self.is_watching = True
        self.state["tracked_whales"] = whale_addresses
        self.state["last_watch"] = datetime.now().isoformat()
        self._save_state()
        
        # Send start notification
        if enable_notifications and self.notification_manager:
            await self.notification_manager.notify_system_alert(
                title="Watch Mode Started",
                message=f"Now tracking {len(whale_addresses)} whale(s) with {'crypto-only' if crypto_only else 'all markets'} filter",
                alert_type="info"
            )
        
        try:
            await self.stream_monitor.start_monitoring()
        except KeyboardInterrupt:
            print("\n\nStopping watch mode...")
            self.stream_monitor.stop_monitoring()
            self.is_watching = False
            
            # Send stop notification
            if enable_notifications and self.notification_manager:
                await self.notification_manager.notify_system_alert(
                    title="Watch Mode Stopped",
                    message="Whale monitoring has been stopped by user",
                    alert_type="info"
                )
            
            # Show summary
            self._show_watch_summary()
    
    def _on_whale_signal(self, signal: WhaleSignal):
        """Handle whale signal in real-time (display and paper trade)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        trade = signal.trade
        
        # Format output
        urgency_icon = {
            'flash': '[FLASH]',
            'momentum': '[MOMENTUM]',
            'exit': '[EXIT]',
            'hedge': '[HEDGE]',
            'accumulation': '[ACCUM]',
            'routine': '*'
        }.get(signal.urgency.value, '•')
        
        print(f"\n[{timestamp}] {urgency_icon} Whale {trade.whale_address[:8]}... | "
              f"{signal.whale_pattern_profile} | "
              f"{trade.market_question[:30]}... | "
              f"{trade.outcome} ${trade.amount:,.0f} | "
              f"Speed: {signal.timing_metrics.speed_score:.0%} | "
              f"Conf: {signal.pattern_confidence:.0%}")
        
        # Make copy decision
        if signal.recommended_action == 'COPY_IMMEDIATE':
            print(f"  -> [COPY] PAPER COPY: ${signal.suggested_size:.0f} {trade.outcome}")
            
            # Execute paper trade (async)
            asyncio.create_task(self._execute_paper_copy(signal))
        
        elif signal.recommended_action == 'WAIT_CONFIRM':
            print(f"  -> [WAIT] Pattern confidence {signal.pattern_confidence:.0%} < 70%")
        
        elif signal.recommended_action == 'SKIP':
            print(f"  -> [SKIP] {signal.urgency.value}")
        
        # Log to database if available
        if self.database:
            self._log_signal_to_database(signal)
    
    async def _on_whale_signal_notification(self, signal: WhaleSignal):
        """Send notification for whale signal."""
        if not self.notification_manager:
            return
        
        # Only notify for high-confidence signals
        if signal.pattern_confidence >= 0.7 and signal.urgency.value in ['flash', 'momentum']:
            await self.notification_manager.notify_whale_activity({
                "trader": signal.trade.whale_address,
                "market": signal.trade.market_question[:50],
                "side": signal.trade.outcome,
                "size": signal.trade.amount,
                "price": signal.trade.price
            })
    
    def _log_signal_to_database(self, signal: WhaleSignal):
        """Log whale signal to database."""
        if not self.database:
            return
        
        try:
            self.database.log_system_event(
                event_type="signal",
                message=f"Whale signal: {signal.trade.whale_address[:16]}... {signal.trade.outcome}",
                data={
                    "whale_address": signal.trade.whale_address,
                    "market_id": signal.trade.market_id,
                    "outcome": signal.trade.outcome,
                    "amount": signal.trade.amount,
                    "pattern": signal.whale_pattern_profile,
                    "confidence": signal.pattern_confidence,
                    "urgency": signal.urgency.value
                }
            )
        except Exception as e:
            print(f"[WARN] Failed to log signal to database: {e}")
    
    async def _execute_paper_copy(self, signal: WhaleSignal):
        """Execute paper trade in background."""
        # Get market data
        market_data = {
            'current_price': signal.trade.price,
            'liquidity': signal.trade.market_liquidity,
            'is_crypto': True
        }
        
        portfolio = {
            'heat': 0.1,
            'max_heat': 0.5,
            'open_positions': 0,
            'max_positions': 5,
            'daily_pnl': 0,
            'value': 10000,
            'available_balance': 10000
        }
        
        # Make decision
        decision = await self.speed_copy_engine.evaluate_whale_signal(
            signal, market_data, portfolio
        )
        
        # Execute
        if decision.action in [CopyAction.COPY_IMMEDIATE, CopyAction.REDUCE_SIZE]:
            position = await self.speed_copy_engine.execute_copy(
                signal, decision, market_data
            )
            
            if position:
                print(f"  [OK] Position {position.position_id} opened | "
                      f"Delay: {position.timing_metrics.entry_delay_seconds:.1f}s")
                
                # Log to database
                if self.database:
                    self._log_paper_trade_to_database(position, signal)
    
    def _log_paper_trade_to_database(self, position, signal: WhaleSignal):
        """Log paper trade to database."""
        if not self.database:
            return
        
        try:
            trade_data = TradeData(
                trade_id=position.position_id,
                market_id=position.market_id,
                market_question=position.market_question,
                side=position.direction,
                trade_type='paper',
                entry_price=position.entry_price,
                size_usd=position.size_usd,
                status='open',
                signal_id=signal.trade.tx_hash,
                pattern_type=position.whale_pattern_type,
                whale_address=position.whale_address,
                whale_confidence=position.whale_confidence,
                stop_loss=position.stop_loss_price,
                take_profit=position.take_profit_price,
                fees=0.0,
                metadata={
                    'entry_delay_seconds': position.timing_metrics.entry_delay_seconds,
                    'speed_score': position.timing_metrics.speed_score,
                    'slippage_percent': position.timing_metrics.price_slippage_percent,
                    'whale_entry_price': position.timing_metrics.whale_entry_price
                }
            )
            self.database.record_trade(trade_data)
        except Exception as e:
            print(f"[WARN] Failed to log paper trade to database: {e}")
    
    def _show_watch_summary(self):
        """Show summary after watch mode ends."""
        print("\n" + "=" * 80)
        print("WATCH SESSION SUMMARY")
        print("=" * 80)
        
        stats = self.stream_monitor.get_all_stats() if self.stream_monitor else {}
        
        print(f"\nSession Duration: {stats.get('uptime_seconds', 0) // 60} minutes")
        print(f"Total Polls: {stats.get('poll_count', 0)}")
        print(f"Trades Detected: {stats.get('total_trades_detected', 0)}")
        
        # Show paper trading summary
        report = self.paper_trading.get_performance_report() if self.paper_trading else {}
        
        if report and 'summary' in report:
            summary = report['summary']
            print(f"\nPaper Trading:")
            print(f"  Positions Opened: {summary.get('total_trades', 0)}")
            print(f"  Total P&L: ${summary.get('total_pnl', 0):+.2f}")
            print(f"  Current Balance: ${summary.get('current_balance', 10000):,.2f}")
        
        # Show timing metrics
        timing = self.paper_trading.get_timing_summary() if self.paper_trading else {}
        if timing:
            print(f"\nTiming Performance:")
            print(f"  Average Delay: {timing.get('avg_delay_seconds', 0):.1f}s")
            print(f"  Speed Score: {timing.get('avg_speed_score', 0):.0%}")
            print(f"  Timing Grade: {timing.get('timing_grade', 'N/A')}")
        
        print("=" * 80)
    
    async def study(self, whale_address: str, days: int = 30):
        """
        Generate behavioral study of a specific whale.
        
        Usage: python cli_bot_v2.py study 0x123... --days 30
        
        Args:
            whale_address: Whale wallet address to analyze
            days: Days of history to analyze (default: 30)
        """
        print("=" * 80)
        print(f"BEHAVIORAL STUDY: {whale_address[:16]}...")
        print("=" * 80)
        print(f"\nAnalyzing {days} days of trading history...")
        
        if not await self._init_clients():
            return
        
        # Try to fetch real whale history from database first
        whale_history = []
        if self.database:
            try:
                trades = self.database.get_trade_history(
                    filters={'whale_address': whale_address.lower()},
                    limit=100
                )
                whale_history = trades
            except Exception:
                pass
        
        # Use mock data if no real data available
        if not whale_history:
            print("  [INFO] No historical data found, using mock data for demonstration")
            whale_history = self._generate_mock_whale_history(whale_address, days)
        else:
            print(f"  [OK] Found {len(whale_history)} historical trades")
        
        # Pattern analysis
        profile = self.pattern_engine.analyze_whale_pattern(whale_address, whale_history)
        
        # Behavioral profiling
        personality = self.behavioral_profiler.profile_whale(whale_address, whale_history)
        
        # Output report
        print("\n" + "=" * 80)
        print("PATTERN PROFILE")
        print("=" * 80)
        print(f"\nPrimary Pattern: {profile.primary_pattern.value.upper()}")
        print(f"Confidence: {profile.pattern_confidence:.0%}")
        if profile.secondary_patterns:
            print(f"Secondary: {', '.join(p.value for p in profile.secondary_patterns)}")
        
        print(f"\nTiming Characteristics:")
        print(f"  Avg Time to Enter: {profile.avg_time_to_enter}")
        print(f"  Avg Hold Duration: {profile.avg_hold_duration}")
        print(f"  Avg Exit Profit: {profile.avg_exit_profit_percent:.0%}")
        
        print(f"\nRisk Profile:")
        print(f"  Appetite: {profile.risk_appetite}")
        print(f"  Max Position: ${profile.max_position_size:,.0f}")
        print(f"  Current Stance: {profile.current_stance}")
        
        print(f"\nPerformance in Pattern:")
        print(f"  Win Rate: {profile.pattern_win_rate:.0%}")
        print(f"  Profit Factor: {profile.pattern_profit_factor:.2f}")
        
        print("\n" + "-" * 80)
        print("BEHAVIORAL INSIGHTS")
        print("-" * 80)
        for insight in profile.insights:
            print(f"  * {insight}")
        
        print(f"\nBest Market Conditions:")
        for condition in profile.best_market_conditions:
            print(f"  + {condition}")
        
        print("\n" + "=" * 80)
        print("COPY RECOMMENDATIONS")
        print("=" * 80)
        print(f"\nPsychology: {personality.primary_psychology.value}")
        print(f"Risk Style: {personality.risk_temperament.value}")
        print(f"\nStrengths:")
        for strength in personality.strengths:
            print(f"  + {strength}")
        print(f"\nWeaknesses:")
        for weakness in personality.weaknesses:
            print(f"  - {weakness}")
        
        print(f"\nBest Copy Conditions:")
        for condition in personality.best_copy_conditions:
            print(f"  + {condition}")
        
        print(f"\nAvoid When:")
        for condition in personality.avoid_conditions:
            print(f"  - {condition}")
        
        print("=" * 80)
    
    def _generate_mock_whale_history(self, address: str, days: int) -> List[Dict]:
        """Generate mock trade history for demonstration."""
        import random
        
        trades = []
        base_time = datetime.now() - timedelta(days=days)
        
        for i in range(50):
            trade_time = base_time + timedelta(hours=i * 12)
            trades.append({
                'timestamp': trade_time,
                'market_id': f'market_{i}',
                'amount': random.uniform(1000, 10000),
                'price': random.uniform(0.3, 0.7),
                'outcome': random.choice(['YES', 'NO']),
                'pnl': random.uniform(-500, 2000),
                'market_created_at': trade_time - timedelta(minutes=random.randint(1, 60)),
                'is_exit': random.random() > 0.7
            })
        
        return trades
    
    def speed_test(self):
        """
        Measure reaction speed vs whales over last 24h.
        
        Usage: python cli_bot_v2.py speed-test
        """
        print("=" * 80)
        print("SPEED TEST - Reaction Time Analysis")
        print("=" * 80)
        
        if not self.paper_trading:
            self.paper_trading = PaperTradingEngine()
        
        timing = self.paper_trading.get_timing_summary()
        
        print(f"\n[STATS] TIMING METRICS (Last 24h)")
        print("-" * 80)
        print(f"  Total Copies: {timing.get('total_trades', 0)}")
        print(f"  Average Delay: {timing.get('avg_delay_seconds', 0):.1f} seconds")
        print(f"  Average Speed Score: {timing.get('avg_speed_score', 0):.0%}")
        print(f"  Average Slippage: {timing.get('avg_slippage_percent', 0):.2f}%")
        print(f"  Timing Grade: {timing.get('timing_grade', 'N/A')}")
        
        print(f"\n[TARGET] SPEED BENCHMARKS")
        print("-" * 80)
        print(f"  Excellent: < 30s delay (A+)")
        print(f"  Good: 30-60s delay (A)")
        print(f"  Acceptable: 60-120s delay (B)")
        print(f"  Poor: 120-300s delay (C)")
        print(f"  Too Slow: > 300s delay (D)")
        
        print(f"\n[TIP] IMPROVEMENT TIPS")
        print("-" * 80)
        
        delay = timing.get('avg_delay_seconds', 0)
        if delay < 30:
            print("  [OK] Excellent speed! You're matching whale timing well.")
        elif delay < 60:
            print("  -> Good speed. Consider reducing poll interval to 15s for A+")
        elif delay < 120:
            print("  [!] Acceptable but room for improvement:")
            print("    - Reduce poll interval from 30s to 15s")
            print("    - Keep terminal visible for quick reaction")
        else:
            print("  [X] Too slow! You're missing edge:")
            print("    - Use 'watch' mode instead of manual scanning")
            print("    - Reduce poll interval to 15s or less")
            print("    - Consider automated copying for <30s delay")
        
        print("=" * 80)
    
    def paper_report(self, export: Optional[str] = None):
        """
        Show comprehensive paper trading report.
        
        Usage: python cli_bot_v2.py paper-report [--export filename.json]
        
        Args:
            export: Optional filename to export report as JSON
        """
        print("=" * 80)
        print("PAPER TRADING PERFORMANCE REPORT")
        print("=" * 80)
        
        if not self.paper_trading:
            self.paper_trading = PaperTradingEngine()
        
        report = self.paper_trading.get_performance_report()
        
        if 'message' in report:
            print(f"\n{report['message']}")
            print(f"Open positions: {report.get('open_positions', 0)}")
            return
        
        summary = report['summary']
        timing = report['timing']
        
        print(f"\n[CHART] PERFORMANCE SUMMARY")
        print("-" * 80)
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Win Rate: {summary['win_rate']:.1%}")
        print(f"  Profit Factor: {summary['profit_factor']:.2f}")
        print(f"  Total P&L: ${summary['total_pnl']:+,.2f} ({summary['total_pnl_percent']:+.2f}%)")
        print(f"  Current Balance: ${summary['current_balance']:,.2f}")
        
        print(f"\n[TIME] TIMING ANALYSIS")
        print("-" * 80)
        print(f"  Average Delay: {timing['avg_delay_seconds']:.1f}s")
        print(f"  Speed Score: {timing['avg_speed_score']:.0%}")
        print(f"  Slippage: {timing['avg_slippage_percent']:.2f}%")
        print(f"  Grade: {timing['timing_grade']}")
        
        print(f"\n[TARGET] PATTERN PERFORMANCE")
        print("-" * 80)
        patterns = report.get('pattern_performance', {})
        for pattern, stats in patterns.items():
            win_rate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
            print(f"  {pattern:15s}: {stats['trades']} trades, ${stats['pnl']:+,.0f} P&L, {win_rate:.0f}% WR")
        
        print(f"\n[BEST] BEST PATTERN: {report['best_pattern']['name']}")
        print(f"   P&L: ${report['best_pattern']['pnl']:+,.0f}")
        print(f"   Accuracy: {report['best_pattern']['accuracy']:.0f}%")
        
        print(f"\n[TIP] INSIGHTS")
        print("-" * 80)
        for insight in report.get('insights', []):
            print(f"  * {insight}")
        
        # Show open positions
        print(self.paper_trading.get_open_positions_table())
        
        # Export if requested
        if export:
            try:
                with open(export, 'w') as f:
                    json.dump(report, f, indent=2, default=str)
                print(f"\n[OK] Report exported to {export}")
            except Exception as e:
                print(f"\n[ERROR] Failed to export report: {e}")
        
        print("=" * 80)
    
    async def backtest(self, strategy: str = "copy_all", days: int = 30, 
                       whales: Optional[List[str]] = None, export: Optional[str] = None):
        """
        Run backtest with specified strategy.
        
        Usage: python cli_bot_v2.py backtest --strategy copy_all --days 30
        
        Args:
            strategy: Strategy name (copy_all, high_confidence, crypto_only, kelly)
            days: Number of days to backtest
            whales: Optional list of whale addresses
            export: Optional filename to export results
        """
        print("=" * 80)
        print(f"BACKTEST: {strategy.upper()} STRATEGY")
        print("=" * 80)
        print(f"Period: Last {days} days")
        print("Initializing...")
        
        if not await self._init_clients():
            return
        
        # Initialize backtest engine
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        self.backtest_engine = BacktestEngine(
            initial_capital=10000.0,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get whale addresses
        if not whales:
            whales = self.state.get('tracked_whales', [])
        
        if not whales:
            print("\n[ERROR] No whales specified. Use --whales or run 'scan' first")
            return
        
        print(f"Loading historical data for {len(whales)} whale(s)...")
        
        # Load historical data
        try:
            trades_loaded = await self.backtest_engine.load_historical_data(
                whale_addresses=whales,
                data_source="subgraph"
            )
            print(f"  [OK] Loaded {trades_loaded} historical trades")
        except Exception as e:
            print(f"  [WARN] Could not load from subgraph: {e}")
            print("  [INFO] Using mock data for demonstration")
            trades_loaded = 100  # Mock
        
        # Create strategy config
        strategy_configs = {
            'copy_all': create_copy_all_strategy(),
            'high_confidence': create_high_confidence_strategy(min_confidence=0.7),
            'crypto_only': create_crypto_only_strategy(),
            'kelly': create_kelly_strategy(fraction=0.5),
        }
        
        if strategy not in strategy_configs:
            print(f"\n[ERROR] Unknown strategy: {strategy}")
            print(f"Available: {', '.join(strategy_configs.keys())}")
            return
        
        config = strategy_configs[strategy]
        
        print(f"\nRunning backtest with '{strategy}' strategy...")
        print("-" * 80)
        
        # Run backtest
        try:
            result = self.backtest_engine.run_backtest(config)
            
            # Print results
            print(f"\n[RESULTS] PERFORMANCE")
            print("-" * 80)
            print(f"  Total Return: {result.total_return:+.2f} ({result.total_return_percent:+.2f}%)")
            print(f"  Annualized: {result.annualized_return:+.2f}%")
            print(f"  Total Trades: {result.total_trades}")
            print(f"  Win Rate: {result.win_rate:.1%}")
            print(f"  Profit Factor: {result.profit_factor:.2f}")
            print(f"  Expectancy: ${result.expectancy:.2f}")
            
            print(f"\n[RISK] RISK METRICS")
            print("-" * 80)
            print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")
            print(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
            print(f"  Max Drawdown: ${result.max_drawdown:,.2f} ({result.max_drawdown_percent:.2f}%)")
            print(f"  Calmar Ratio: {result.calmar_ratio:.2f}")
            print(f"  Volatility: {result.volatility:.2f}%")
            
            print(f"\n[TRADES] TRADE METRICS")
            print("-" * 80)
            print(f"  Average Trade: ${result.avg_trade:.2f}")
            print(f"  Average Win: ${result.avg_win:.2f}")
            print(f"  Average Loss: ${result.avg_loss:.2f}")
            print(f"  Largest Win: ${result.largest_win:.2f}")
            print(f"  Largest Loss: ${result.largest_loss:.2f}")
            print(f"  Avg Duration: {result.avg_trade_duration:.1f} hours")
            
            if result.performance_by_pattern:
                print(f"\n[PATTERNS] PERFORMANCE BY PATTERN")
                print("-" * 80)
                for pattern, stats in sorted(
                    result.performance_by_pattern.items(),
                    key=lambda x: x[1]['total_pnl'],
                    reverse=True
                ):
                    print(f"  {pattern:20s}: {stats['trades']} trades, "
                          f"WR: {stats['win_rate']:.1%}, "
                          f"PnL: ${stats['total_pnl']:+.2f}")
            
            # Export if requested
            if export:
                try:
                    self.backtest_engine.export_report_json(result, export)
                    print(f"\n[OK] Results exported to {export}")
                except Exception as e:
                    print(f"\n[ERROR] Failed to export results: {e}")
            
            # Save to state
            self.state['backtest_results'].append({
                'strategy': strategy,
                'days': days,
                'timestamp': datetime.now().isoformat(),
                'total_return': result.total_return_percent,
                'win_rate': result.win_rate,
                'sharpe': result.sharpe_ratio
            })
            self._save_state()
            
        except Exception as e:
            print(f"\n[ERROR] Backtest failed: {e}")
            import traceback
            traceback.print_exc()
        
        print("=" * 80)
    
    async def live_trading(self, enable: bool = False, disable: bool = False, status: bool = False):
        """
        Manage live trading mode.
        
        Usage: 
            python cli_bot_v2.py live --enable    # Enable live trading
            python cli_bot_v2.py live --disable   # Disable live trading
            python cli_bot_v2.py live --status    # Check status
        
        Args:
            enable: Enable live trading
            disable: Disable live trading
            status: Show live trading status
        """
        print("=" * 80)
        print("LIVE TRADING MANAGEMENT")
        print("=" * 80)
        
        if status or (not enable and not disable):
            # Show status
            is_enabled = self.state.get('live_trading_enabled', False)
            print(f"\nStatus: {'ENABLED' if is_enabled else 'DISABLED'}")
            
            if self.live_client:
                try:
                    balance = self.live_client.get_balance()
                    print(f"\nAccount Balance:")
                    print(f"  Total: ${balance.usdc_balance:,.2f} USDC")
                    print(f"  Available: ${balance.usdc_available:,.2f} USDC")
                    print(f"  Locked: ${balance.usdc_locked:,.2f} USDC")
                except Exception as e:
                    print(f"\n[ERROR] Could not fetch balance: {e}")
            
            print("\nTo enable live trading, run: python cli_bot_v2.py live --enable")
            print("=" * 80)
            return
        
        if enable:
            print("\n⚠️  WARNING: LIVE TRADING ⚠️")
            print("-" * 80)
            print("You are about to enable LIVE TRADING with REAL MONEY.")
            print("This feature will execute actual trades on Polymarket.")
            print("\nBefore proceeding:")
            print("  1. Ensure you have tested with paper trading")
            print("  2. Verify your API keys are configured correctly")
            print("  3. Start with small position sizes")
            print("  4. Understand the risks involved")
            print("-" * 80)
            
            confirm = input("\nDo you want to continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("\n[OK] Live trading not enabled")
                return
            
            # Initialize live client
            if not await self._init_live_trading():
                return
            
            self.live_trading_enabled = True
            self.state['live_trading_enabled'] = True
            self._save_state()
            
            print("\n[OK] Live trading ENABLED")
            print("   Trades will now be executed with REAL MONEY")
            
            # Send notification
            if self.notification_manager:
                await self.notification_manager.notify_system_alert(
                    title="Live Trading Enabled",
                    message="Live trading mode has been activated. Real trades will be executed.",
                    alert_type="warning"
                )
        
        if disable:
            self.live_trading_enabled = False
            self.state['live_trading_enabled'] = False
            self._save_state()
            
            print("\n[OK] Live trading DISABLED")
            print("   Trades will be executed in paper trading mode only")
            
            # Send notification
            if self.notification_manager:
                await self.notification_manager.notify_system_alert(
                    title="Live Trading Disabled",
                    message="Live trading mode has been deactivated. Only paper trades will be executed.",
                    alert_type="info"
                )
        
        print("=" * 80)
    
    async def notify_test(self):
        """
        Test notification channels (Discord/Telegram).
        
        Usage: python cli_bot_v2.py notify-test
        """
        print("=" * 80)
        print("NOTIFICATION TEST")
        print("=" * 80)
        
        if not self.notification_manager:
            self.notification_manager = NotificationManager()
            await self.notification_manager._get_session()
        
        print("\nTesting notification channels...")
        print("-" * 80)
        
        # Test system alert
        print("\n1. Testing System Alert...")
        result = await self.notification_manager.notify_system_alert(
            title="Test Notification",
            message="This is a test notification from PolyBot v2",
            alert_type="info",
            bypass_rate_limit=True
        )
        print(f"   Discord: {'OK' if result.get('discord') else 'FAILED'}")
        print(f"   Telegram: {'OK' if result.get('telegram') else 'FAILED'}")
        print(f"   Console: {'OK' if result.get('console') else 'FAILED'}")
        
        # Test trade notification
        print("\n2. Testing Trade Notification...")
        result = await self.notification_manager.notify_trade_executed({
            "market": "Test Market",
            "side": "YES",
            "size": 100,
            "entry_price": 0.55,
            "expected_value": 0.05
        }, bypass_rate_limit=True)
        print(f"   Discord: {'OK' if result.get('discord') else 'FAILED'}")
        print(f"   Telegram: {'OK' if result.get('telegram') else 'FAILED'}")
        print(f"   Console: {'OK' if result.get('console') else 'FAILED'}")
        
        # Test high EV opportunity
        print("\n3. Testing High EV Opportunity...")
        result = await self.notification_manager.notify_high_ev_opportunity(
            signal={
                "market": "BTC 5-Minute",
                "side": "YES",
                "confidence": 0.75,
                "current_price": 0.52
            },
            ev=0.08,
            bypass_rate_limit=True
        )
        print(f"   Discord: {'OK' if result.get('discord') else 'FAILED'}")
        print(f"   Telegram: {'OK' if result.get('telegram') else 'FAILED'}")
        print(f"   Console: {'OK' if result.get('console') else 'FAILED'}")
        
        print("\n" + "-" * 80)
        print("\nIf any channel shows FAILED, check:")
        print("  - Environment variables are set correctly")
        print("  - Discord webhook URL is valid")
        print("  - Telegram bot token and chat ID are correct")
        print("  - Network connectivity")
        
        print("=" * 80)
    
    async def schedule(self, action: str = "status"):
        """
        Manage automated workflow scheduling.
        
        Usage:
            python cli_bot_v2.py schedule start    # Start scheduler
            python cli_bot_v2.py schedule stop     # Stop scheduler
            python cli_bot_v2.py schedule status   # Check status
        
        Args:
            action: Action to perform (start, stop, status)
        """
        print("=" * 80)
        print(f"WORKFLOW SCHEDULER - {action.upper()}")
        print("=" * 80)
        
        if not self.workflow_scheduler:
            await self._init_clients(full_init=True)
        
        if action == "start":
            if self.state.get('workflow_running'):
                print("\n[WARN] Workflow scheduler is already running")
                return
            
            print("\nInitializing workflow scheduler...")
            try:
                await self.workflow_scheduler.initialize()
                
                # Schedule tasks
                self.workflow_scheduler.schedule_daily_scan()
                self.workflow_scheduler.schedule_continuous_monitoring()
                self.workflow_scheduler.schedule_pnl_updates()
                self.workflow_scheduler.schedule_daily_report()
                self.workflow_scheduler.schedule_health_checks()
                
                # Start scheduler
                await self.workflow_scheduler.start()
                
                self.state['workflow_running'] = True
                self._save_state()
                
                print("[OK] Workflow scheduler started")
                print("\nScheduled tasks:")
                print("  - Daily scan at 09:00")
                print("  - Continuous monitoring every 1 minute")
                print("  - P&L updates every 15 minutes")
                print("  - Daily report at 18:00")
                print("  - Health checks every 5 minutes")
                
            except Exception as e:
                print(f"[ERROR] Failed to start scheduler: {e}")
        
        elif action == "stop":
            if not self.state.get('workflow_running'):
                print("\n[WARN] Workflow scheduler is not running")
                return
            
            try:
                await self.workflow_scheduler.stop()
                
                self.state['workflow_running'] = False
                self._save_state()
                
                print("[OK] Workflow scheduler stopped")
            except Exception as e:
                print(f"[ERROR] Failed to stop scheduler: {e}")
        
        elif action == "status":
            is_running = self.state.get('workflow_running', False)
            print(f"\nStatus: {'RUNNING' if is_running else 'STOPPED'}")
            
            if is_running and self.workflow_scheduler:
                print(f"\nActive Tasks:")
                for task_id, task in self.workflow_scheduler.tasks.items():
                    print(f"  - {task.name}: {task.status.value}")
        
        else:
            print(f"\n[ERROR] Unknown action: {action}")
            print("Available actions: start, stop, status")
        
        print("=" * 80)
    
    # ==================== LEGACY COMMANDS (Still Work) ====================
    
    def status(self):
        """Show current bot status."""
        print("=" * 80)
        print("POLYBOT v2 - Whale Pattern Hunter")
        print("=" * 80)
        
        print(f"\n[REAL-TIME MONITORING]")
        print(f"  Status: {'WATCHING' if self.is_watching else 'IDLE'}")
        print(f"  Tracked Whales: {len(self.state.get('tracked_whales', []))}")
        print(f"  Last Watch: {self.state.get('last_watch', 'Never')}")
        
        print(f"\n[PAPER TRADING]")
        balance = self.state.get('paper_balance', 10000)
        pnl = self.state.get('total_paper_pnl', 0)
        print(f"  Balance: ${balance:,.2f}")
        print(f"  Total P&L: ${pnl:+.2f}")
        
        timing = self.state.get('timing_metrics', {})
        print(f"  Copies Executed: {timing.get('total_copies', 0)}")
        print(f"  Avg Detection Lag: {timing.get('avg_detection_lag', 0):.1f}s")
        print(f"  Avg Execution Lag: {timing.get('avg_execution_lag', 0):.1f}s")
        
        print(f"\n[LIVE TRADING]")
        print(f"  Status: {'ENABLED' if self.state.get('live_trading_enabled') else 'DISABLED'}")
        
        print(f"\n[AUTOMATION]")
        print(f"  Workflow Scheduler: {'RUNNING' if self.state.get('workflow_running') else 'STOPPED'}")
        
        print("\n" + "=" * 80)
        print("COMMANDS:")
        print("  ultra         - Ultra-low latency trading terminal")
        print("  watch         - Real-time whale monitoring")
        print("  study         - Behavioral analysis of whale")
        print("  speed-test    - Timing performance analysis")
        print("  paper-report  - Paper trading performance")
        print("  backtest      - Run backtest strategies")
        print("  live          - Live trading mode")
        print("  notify-test   - Test notifications")
        print("  schedule      - Automation scheduling")
        print("=" * 80)
    
    async def scan(self):
        """Legacy: Scan for top winners (kept for compatibility)."""
        print("=" * 80)
        print("SCANNING FOR CRYPTO WHALES")
        print("=" * 80)
        
        if not await self._init_clients():
            return
        
        print("\nScanning for statistically proven crypto betters...")
        
        # Get mock winners (would query TheGraph in real impl)
        mock_whales = [
            {
                'address': f'0x{i:040x}',
                'ens': f'CryptoWhale{i}',
                'win_rate': 0.60 + i * 0.01,
                'profit_factor': 1.5 + i * 0.1,
                'copy_score': 75.0 - i * 5,
                'primary_pattern': ['SNIPER', 'ACCUMULATOR', 'SWINGER'][i % 3]
            }
            for i in range(5)
        ]
        
        print(f"\nFound {len(mock_whales)} qualifying crypto whales")
        print("\n  Top 5 Whales:")
        print("  " + "-" * 70)
        print(f"  {'#':<3} {'Address/ENS':<20} {'Win%':<8} {'PF':<6} {'Score':<6} {'Pattern'}")
        print("  " + "-" * 70)
        
        for i, whale in enumerate(mock_whales, 1):
            name = whale.get('ens', whale['address'][:18])
            print(f"  {i:<3} {name:<20} {whale['win_rate']:<7.1%} "
                  f"{whale['profit_factor']:<5.2f} {whale['copy_score']:<5.0f} {whale['primary_pattern']}")
        
        # Save to state
        self.state["tracked_whales"] = [w['address'] for w in mock_whales]
        self._save_state()
        
        print("\n  Whales saved for watch mode")
        print("  Next: Run 'watch' to start real-time monitoring")
        print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(
        description="PolyBot v2 - Real-Time Whale Pattern Hunter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
NEW COMMANDS (Real-Time Mode):
  ultra         Ultra-low latency real-time trading terminal
  watch         Real-time whale monitoring with pattern detection
  study         Behavioral analysis of specific whale
  speed-test    Timing performance analysis
  paper-report  Comprehensive paper trading report
  backtest      Run backtest strategies
  live          Live trading mode (enable/disable/status)
  notify-test   Test Discord/Telegram notifications
  schedule      Automation scheduling (start/stop/status)

LEGACY COMMANDS (Research Mode):
  status        Show bot status
  scan          Find top crypto whales
  analyze       Deep analysis (legacy)
  copy          Execute trade (legacy)
  portfolio     View portfolio (legacy)

Examples:
  # Ultra trading terminal
  python cli_bot_v2.py ultra --mode paper --speed ultra --whales 0x123...,0x456...
  python cli_bot_v2.py ultra --mode live --predictive --arbitrage
  
  # Real-time monitoring
  python cli_bot_v2.py watch --whales 0x123...,0x456... --crypto-only
  
  # Behavioral analysis
  python cli_bot_v2.py study 0x123... --days 30
  
  # Performance and backtesting
  python cli_bot_v2.py speed-test
  python cli_bot_v2.py paper-report --export report.json
  python cli_bot_v2.py backtest --strategy copy_all --days 30
  
  # Live trading (careful!)
  python cli_bot_v2.py live --enable
  
  # Automation
  python cli_bot_v2.py schedule start
  python cli_bot_v2.py notify-test
        """
    )
    
    parser.add_argument(
        'command',
        choices=['status', 'scan', 'analyze', 'copy', 'portfolio', 'stop',
                 'watch', 'study', 'speed-test', 'paper-report', 'backtest',
                 'live', 'notify-test', 'schedule', 'ultra'],
        help='Command to execute'
    )
    
    # Watch mode args
    parser.add_argument(
        '--whales',
        type=str,
        help='Comma-separated whale addresses to watch'
    )
    parser.add_argument(
        '--crypto-only',
        action='store_true',
        default=True,
        help='Only track crypto markets (default: True)'
    )
    parser.add_argument(
        '--notifications',
        action='store_true',
        default=False,
        help='Enable Discord/Telegram notifications'
    )
    
    # Study args
    parser.add_argument(
        'whale_address',
        nargs='?',
        help='Whale address to study'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Days of history to analyze (default: 30)'
    )
    
    # Backtest args
    parser.add_argument(
        '--strategy',
        type=str,
        default='copy_all',
        choices=['copy_all', 'high_confidence', 'crypto_only', 'kelly'],
        help='Backtest strategy (default: copy_all)'
    )
    parser.add_argument(
        '--export',
        type=str,
        help='Export report/results to file'
    )
    
    # Live trading args
    parser.add_argument(
        '--enable',
        action='store_true',
        help='Enable live trading'
    )
    parser.add_argument(
        '--disable',
        action='store_true',
        help='Disable live trading'
    )
    
    # Schedule args
    parser.add_argument(
        'schedule_action',
        nargs='?',
        choices=['start', 'stop', 'status'],
        default='status',
        help='Scheduler action (default: status)'
    )
    
    # Ultra mode args
    parser.add_argument(
        '--mode',
        type=str,
        default='paper',
        choices=['paper', 'live', 'simulation'],
        help='Trading mode for ultra (default: paper)'
    )
    parser.add_argument(
        '--speed',
        type=str,
        default='ultra',
        choices=['ultra', 'balanced', 'economy'],
        help='Speed profile for ultra (default: ultra)'
    )
    parser.add_argument(
        '--predictive',
        action='store_true',
        default=False,
        help='Enable predictive entry system'
    )
    parser.add_argument(
        '--arbitrage',
        action='store_true',
        default=False,
        help='Enable arbitrage detection'
    )
    parser.add_argument(
        '--websocket-only',
        action='store_true',
        default=False,
        help='Use only WebSocket (no blockchain)'
    )
    parser.add_argument(
        '--blockchain-only',
        action='store_true',
        default=False,
        help='Use only blockchain (no WebSocket)'
    )
    
    # Legacy args
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Confirm trade execution (legacy)'
    )
    
    args = parser.parse_args()
    
    bot = CLIBotV2()
    
    # NEW COMMANDS
    if args.command == 'ultra':
        await bot.ultra(
            mode=args.mode,
            speed=args.speed,
            whales=args.whales,
            predictive=args.predictive,
            arbitrage=args.arbitrage,
            websocket_only=args.websocket_only,
            blockchain_only=args.blockchain_only
        )
    
    elif args.command == 'watch':
        if not args.whales:
            # Use saved whales or default
            whales = bot.state.get('tracked_whales', [])
            if not whales:
                print("Error: No whales specified. Use --whales or run 'scan' first")
                return
        else:
            whales = [w.strip() for w in args.whales.split(',')]
        
        await bot.watch(whales, args.crypto_only, args.notifications)
    
    elif args.command == 'study':
        if not args.whale_address:
            print("Error: whale_address required")
            print("Usage: python cli_bot_v2.py study 0x123... --days 30")
            return
        await bot.study(args.whale_address, args.days)
    
    elif args.command == 'speed-test':
        bot.speed_test()
    
    elif args.command == 'paper-report':
        bot.paper_report(export=args.export)
    
    elif args.command == 'backtest':
        whales = None
        if args.whales:
            whales = [w.strip() for w in args.whales.split(',')]
        await bot.backtest(
            strategy=args.strategy,
            days=args.days,
            whales=whales,
            export=args.export
        )
    
    elif args.command == 'live':
        await bot.live_trading(
            enable=args.enable,
            disable=args.disable,
            status=not args.enable and not args.disable
        )
    
    elif args.command == 'notify-test':
        await bot.notify_test()
    
    elif args.command == 'schedule':
        await bot.schedule(action=args.schedule_action)
    
    # LEGACY COMMANDS
    elif args.command == 'status':
        bot.status()
    elif args.command == 'scan':
        await bot.scan()
    elif args.command == 'analyze':
        print("Legacy analyze command - use 'watch' for real-time mode")
    elif args.command == 'copy':
        print("Legacy copy command - use 'watch' for real-time paper trading")
    elif args.command == 'portfolio':
        bot.paper_report()
    elif args.command == 'stop':
        print("Stop command - use Ctrl+C to stop watch mode")


if __name__ == '__main__':
    asyncio.run(main())
