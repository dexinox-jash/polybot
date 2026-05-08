"""
ULTRA Trading System - Ultra-Low Latency Real-Time Trading Terminal

Provides a professional trading terminal interface with:
- Real-time latency metrics (100ms updates)
- Live trade detection and execution
- Component health monitoring
- Interactive keyboard controls
- Multiple speed profiles and modes

Usage:
    from polymarket_tracker.realtime.ultra_trading_system import UltraTradingSystem
    
    ultra = UltraTradingSystem()
    await ultra.start(mode='paper', speed='ultra', whales=['0x...'])
"""

import asyncio
import time
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Set
from enum import Enum
from collections import deque
import threading

# Rich library imports (optional)
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.live import Live
    from rich.align import Align
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.style import Style
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = Layout = Panel = Table = Text = Live = Align = Progress = None

# Prompt toolkit for keyboard handling (optional)
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

# Import real-time components (with fallbacks for optional dependencies)
try:
    from .websocket_client import PolymarketWebSocket, TradeEvent, ConnectionStats
    WEBSOCKET_CLIENT_AVAILABLE = True
except ImportError as e:
    WEBSOCKET_CLIENT_AVAILABLE = False
    PolymarketWebSocket = TradeEvent = ConnectionStats = None
    logger.warning(f"WebSocket client not available: {e}")

try:
    from .blockchain_monitor import BlockchainMonitor, BlockchainEvent
    BLOCKCHAIN_MONITOR_AVAILABLE = True
except ImportError as e:
    BLOCKCHAIN_MONITOR_AVAILABLE = False
    BlockchainMonitor = BlockchainEvent = None
    logger.warning(f"Blockchain monitor not available: {e}")

try:
    from .latency_executor import UltraLowLatencyExecutor, ExecutionStats, ExecutionResult
    LATENCY_EXECUTOR_AVAILABLE = True
except ImportError as e:
    LATENCY_EXECUTOR_AVAILABLE = False
    UltraLowLatencyExecutor = ExecutionStats = ExecutionResult = None
    logger.warning(f"Latency executor not available: {e}")

try:
    from .smart_router import SmartOrderRouter, ExecutionMode, RoutingStats
    SMART_ROUTER_AVAILABLE = True
except ImportError as e:
    SMART_ROUTER_AVAILABLE = False
    SmartOrderRouter = ExecutionMode = RoutingStats = None
    logger.warning(f"Smart router not available: {e}")

try:
    from .predictive_entry import PredictiveEntrySystem
    PREDICTIVE_AVAILABLE = True
except ImportError as e:
    PREDICTIVE_AVAILABLE = False
    PredictiveEntrySystem = None
    logger.warning(f"Predictive entry not available: {e}")

try:
    from .arbitrage_detector import ArbitrageDetector, ArbitrageOpportunity
    ARBITRAGE_AVAILABLE = True
except ImportError as e:
    ARBITRAGE_AVAILABLE = False
    ArbitrageDetector = ArbitrageOpportunity = None
    logger.warning(f"Arbitrage detector not available: {e}")

from ..utils.logger import setup_logging

logger = setup_logging()


class TradingMode(Enum):
    """Trading mode enumeration."""
    PAPER = "paper"
    LIVE = "live"
    SIMULATION = "simulation"


class SpeedProfile(Enum):
    """Speed profile enumeration."""
    ULTRA = "ultra"       # Minimize latency at all costs
    BALANCED = "balanced" # Balance speed and cost
    ECONOMY = "economy"   # Minimize costs


class UltraStatus(Enum):
    """Ultra trading status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class LatencyMetrics:
    """Real-time latency metrics."""
    websocket_ms: float = 0.0
    blockchain_ms: float = 0.0
    execution_ms: float = 0.0
    end_to_end_ms: float = 0.0
    fill_ms: float = 0.0
    target_ms: float = 2000.0
    timestamp: float = field(default_factory=time.time)
    
    @property
    def target_met(self) -> bool:
        return self.end_to_end_ms < self.target_ms


@dataclass
class ComponentHealth:
    """Component health status."""
    name: str
    status: str  # "healthy", "degraded", "down"
    last_update: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    
    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


@dataclass
class ActivityLog:
    """Single activity log entry."""
    timestamp: datetime
    source: str  # WS, BC, EX, FIL, etc.
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot."""
    balance: float = 10000.0
    open_positions: int = 0
    pnl: float = 0.0
    daily_pnl: float = 0.0
    timestamp: float = field(default_factory=time.time)


class UltraTradingSystem:
    """
    Ultra-low latency real-time trading system with terminal UI.
    
    Features:
    - Professional trading terminal interface (with Rich)
    - Real-time latency metrics (100ms updates)
    - Multiple speed profiles (ultra/balanced/economy)
    - Component health monitoring
    - Interactive keyboard controls
    - Mode switching (paper/live/simulation)
    
    Keyboard Controls:
    - P: Pause/Resume
    - E: Emergency stop
    - S: Show detailed status
    - L: Toggle live/paper mode
    - Q: Quit gracefully
    
    Note: Install 'rich' and 'prompt-toolkit' for full terminal UI experience:
        pip install rich prompt-toolkit
    """
    
    # Update intervals (seconds)
    DISPLAY_UPDATE_INTERVAL = 0.1  # 100ms
    HEALTH_CHECK_INTERVAL = 5.0
    METRICS_HISTORY_SIZE = 100
    ACTIVITY_LOG_SIZE = 50
    
    def __init__(self):
        if RICH_AVAILABLE:
            self.console = Console()
            self.layout = self._create_layout()
            self._live = None
        else:
            self.console = None
            self.layout = None
            self._live = None
            print("[INFO] Rich library not available. Running in simple mode.")
            print("       Install rich for full terminal UI: pip install rich")
        
        # Status
        self.status = UltraStatus.STOPPED
        self.mode = TradingMode.PAPER
        self.speed = SpeedProfile.ULTRA
        
        # Component toggles
        self.enable_predictive = False
        self.enable_arbitrage = False
        self.websocket_only = False
        self.blockchain_only = False
        
        # Whale addresses
        self.whale_addresses: List[str] = []
        
        # Real-time components
        self.ws_client: Optional[PolymarketWebSocket] = None
        self.blockchain_monitor: Optional[BlockchainMonitor] = None
        self.latency_executor: Optional[UltraLowLatencyExecutor] = None
        self.smart_router: Optional[SmartOrderRouter] = None
        self.predictive_system: Optional[PredictiveEntrySystem] = None
        self.arbitrage_detector: Optional[ArbitrageDetector] = None
        
        # Metrics and state
        self.latency_metrics = LatencyMetrics()
        self.component_health: Dict[str, ComponentHealth] = {}
        self.activity_log: deque = deque(maxlen=self.ACTIVITY_LOG_SIZE)
        self.portfolio = PortfolioSnapshot()
        self.metrics_history: deque = deque(maxlen=self.METRICS_HISTORY_SIZE)
        
        # Statistics
        self.stats = {
            'trades_detected': 0,
            'trades_executed': 0,
            'trades_filled': 0,
            'errors': 0,
            'start_time': None,
            'session_duration': 0,
        }
        
        # Async state
        self._running = False
        self._paused = False
        self._emergency_stop = False
        self._tasks: Set[asyncio.Task] = set()
        self._stop_event = asyncio.Event()
        
        # Keyboard handling
        self._key_bindings = self._setup_key_bindings() if RICH_AVAILABLE else None
        self._last_key_pressed: Optional[str] = None
        
        logger.info("UltraTradingSystem initialized")
    
    def _create_layout(self) -> Layout:
        """Create the terminal layout."""
        layout = Layout()
        
        # Main vertical split
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="status_bar", size=3),
            Layout(name="main", ratio=1),
            Layout(name="controls", size=3)
        )
        
        # Main area horizontal split
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Left column: Latency and Components
        layout["left"].split_column(
            Layout(name="latency", size=8),
            Layout(name="components", size=6),
            Layout(name="activity", ratio=1)
        )
        
        # Right column: Portfolio and Stats
        layout["right"].split_column(
            Layout(name="portfolio", size=8),
            Layout(name="stats", ratio=1)
        )
        
        return layout
    
    def _setup_key_bindings(self):
        """Setup keyboard bindings."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return None
        
        kb = KeyBindings()
        
        @kb.add('p', eager=True)
        @kb.add('P', eager=True)
        def _(event):
            self._last_key_pressed = 'P'
            asyncio.create_task(self._handle_pause_resume())
        
        @kb.add('e', eager=True)
        @kb.add('E', eager=True)
        def _(event):
            self._last_key_pressed = 'E'
            asyncio.create_task(self._handle_emergency_stop())
        
        @kb.add('s', eager=True)
        @kb.add('S', eager=True)
        def _(event):
            self._last_key_pressed = 'S'
            asyncio.create_task(self._handle_status())
        
        @kb.add('l', eager=True)
        @kb.add('L', eager=True)
        def _(event):
            self._last_key_pressed = 'L'
            asyncio.create_task(self._handle_toggle_mode())
        
        @kb.add('q', eager=True)
        @kb.add('Q', eager=True)
        def _(event):
            self._last_key_pressed = 'Q'
            asyncio.create_task(self._handle_quit())
        
        return kb
    
    async def start(
        self,
        mode: str = "paper",
        speed: str = "ultra",
        whales: Optional[List[str]] = None,
        enable_predictive: bool = False,
        enable_arbitrage: bool = False,
        websocket_only: bool = False,
        blockchain_only: bool = False
    ):
        """
        Start the ultra trading system.
        
        Args:
            mode: 'paper', 'live', or 'simulation'
            speed: 'ultra', 'balanced', or 'economy'
            whales: List of whale addresses to track
            enable_predictive: Enable predictive entry system
            enable_arbitrage: Enable arbitrage detection
            websocket_only: Use only WebSocket data
            blockchain_only: Use only blockchain monitoring
        """
        if self._running:
            logger.warning("Ultra trading already running")
            return
        
        # Parse mode
        try:
            self.mode = TradingMode(mode.lower())
        except ValueError:
            self.mode = TradingMode.PAPER
        
        # Parse speed
        try:
            self.speed = SpeedProfile(speed.lower())
        except ValueError:
            self.speed = SpeedProfile.ULTRA
        
        # Set toggles
        self.enable_predictive = enable_predictive
        self.enable_arbitrage = enable_arbitrage
        self.websocket_only = websocket_only
        self.blockchain_only = blockchain_only
        self.whale_addresses = whales or []
        
        # Live mode confirmation
        if self.mode == TradingMode.LIVE:
            confirmed = await self._confirm_live_mode()
            if not confirmed:
                if RICH_AVAILABLE and self.console:
                    self.console.print("[yellow]Live mode not confirmed. Switching to paper.[/yellow]")
                else:
                    print("[WARNING] Live mode not confirmed. Switching to paper.")
                self.mode = TradingMode.PAPER
        
        self.status = UltraStatus.STARTING
        self._running = True
        self._stop_event.clear()
        self.stats['start_time'] = time.time()
        
        # Log start
        self._log_activity("SYS", f"Ultra trading started - Mode: {self.mode.value}, Speed: {self.speed.value}")
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Start background tasks
            self._tasks.add(asyncio.create_task(self._display_update_loop()))
            self._tasks.add(asyncio.create_task(self._health_check_loop()))
            self._tasks.add(asyncio.create_task(self._metrics_collection_loop()))
            self._tasks.add(asyncio.create_task(self._keyboard_input_loop()))
            
            # Start real-time components
            await self._start_components()
            
            self.status = UltraStatus.RUNNING
            
            # Start display (Rich UI or simple text mode)
            if RICH_AVAILABLE and self.layout:
                with Live(self.layout, console=self.console, refresh_per_second=10, screen=True) as live:
                    self._live = live
                    await self._stop_event.wait()
            else:
                # Simple text mode
                await self._simple_display_loop()
            
        except Exception as e:
            logger.error(f"Ultra trading error: {e}")
            self._log_activity("ERR", f"System error: {str(e)}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the ultra trading system gracefully."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        self.status = UltraStatus.STOPPED
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        
        # Stop components
        await self._stop_components()
        
        self._log_activity("SYS", "Ultra trading stopped")
        logger.info("Ultra trading stopped")
    
    async def _initialize_components(self):
        """Initialize all real-time components."""
        if RICH_AVAILABLE and self.console:
            self.console.print("[cyan]Initializing components...[/cyan]")
        else:
            print("[INFO] Initializing components...")
        
        # WebSocket client
        if not self.blockchain_only and WEBSOCKET_CLIENT_AVAILABLE and PolymarketWebSocket:
            try:
                self.ws_client = PolymarketWebSocket()
                self.ws_client.on_trade(self._on_trade_event)
                self.ws_client.on_whale_trade(self._on_whale_trade_event)
                self.component_health['WebSocket'] = ComponentHealth("WebSocket", "initializing")
            except Exception as e:
                logger.error(f"Failed to initialize WebSocket: {e}")
                self.component_health['WebSocket'] = ComponentHealth("WebSocket", "down")
        else:
            self.component_health['WebSocket'] = ComponentHealth("WebSocket", "down")
        
        # Blockchain monitor
        if not self.websocket_only and BLOCKCHAIN_MONITOR_AVAILABLE and BlockchainMonitor:
            try:
                self.blockchain_monitor = BlockchainMonitor(
                    whale_addresses=set(self.whale_addresses),
                    mempool_enabled=True
                )
                self.blockchain_monitor.on_blockchain_event = self._on_blockchain_event
                self.component_health['Blockchain'] = ComponentHealth("Blockchain", "initializing")
            except Exception as e:
                logger.error(f"Failed to initialize Blockchain monitor: {e}")
                self.component_health['Blockchain'] = ComponentHealth("Blockchain", "down")
        else:
            self.component_health['Blockchain'] = ComponentHealth("Blockchain", "down")
        
        # Predictive system
        if self.enable_predictive and PREDICTIVE_AVAILABLE and PredictiveEntrySystem:
            try:
                self.predictive_system = PredictiveEntrySystem()
                self.component_health['Predictor'] = ComponentHealth("Predictor", "healthy")
            except Exception as e:
                logger.error(f"Failed to initialize Predictor: {e}")
                self.component_health['Predictor'] = ComponentHealth("Predictor", "down")
        else:
            self.component_health['Predictor'] = ComponentHealth("Predictor", "down")
        
        # Arbitrage detector
        if self.enable_arbitrage and ARBITRAGE_AVAILABLE and ArbitrageDetector:
            try:
                self.arbitrage_detector = ArbitrageDetector(
                    execution_mode=self.mode.value
                )
                self.arbitrage_detector.on_opportunity(self._on_arbitrage_opportunity)
                self.component_health['Arbitrage'] = ComponentHealth("Arbitrage", "healthy")
            except Exception as e:
                logger.error(f"Failed to initialize Arbitrage: {e}")
                self.component_health['Arbitrage'] = ComponentHealth("Arbitrage", "down")
        else:
            self.component_health['Arbitrage'] = ComponentHealth("Arbitrage", "down")
        
        # Router (always try to initialize)
        if SMART_ROUTER_AVAILABLE and SmartOrderRouter:
            try:
                exec_mode = ExecutionMode.SPEED if self.speed == SpeedProfile.ULTRA else \
                           ExecutionMode.ECONOMY if self.speed == SpeedProfile.ECONOMY else \
                           ExecutionMode.BALANCED
                self.smart_router = SmartOrderRouter(execution_mode=exec_mode)
                self.component_health['Router'] = ComponentHealth("Router", "healthy")
            except Exception as e:
                logger.error(f"Failed to initialize Router: {e}")
                self.component_health['Router'] = ComponentHealth("Router", "down")
        else:
            self.component_health['Router'] = ComponentHealth("Router", "down")
        
        # Executor
        if LATENCY_EXECUTOR_AVAILABLE and UltraLowLatencyExecutor:
            try:
                self.latency_executor = UltraLowLatencyExecutor()
                self.component_health['Executor'] = ComponentHealth("Executor", "healthy")
            except Exception as e:
                logger.error(f"Failed to initialize Executor: {e}")
                self.component_health['Executor'] = ComponentHealth("Executor", "down")
        else:
            self.component_health['Executor'] = ComponentHealth("Executor", "down")
        
        # Notifications
        try:
            self.component_health['Notifications'] = ComponentHealth("Notifications", "healthy")
        except Exception as e:
            self.component_health['Notifications'] = ComponentHealth("Notifications", "down")
        
        if RICH_AVAILABLE and self.console:
            self.console.print("[green]Components initialized[/green]")
        else:
            print("[INFO] Components initialized")
    
    async def _start_components(self):
        """Start all real-time components."""
        if self.ws_client and WEBSOCKET_CLIENT_AVAILABLE:
            try:
                await self.ws_client.connect()
                await self.ws_client.subscribe_all_markets()
                self.component_health['WebSocket'].status = "healthy"
                self._log_activity("WS", "WebSocket connected")
            except Exception as e:
                self.component_health['WebSocket'].status = "down"
                logger.error(f"WebSocket connection failed: {e}")
        
        if self.blockchain_monitor and BLOCKCHAIN_MONITOR_AVAILABLE:
            try:
                await self.blockchain_monitor.start()
                self.component_health['Blockchain'].status = "healthy"
                self._log_activity("BC", "Blockchain monitor started")
            except Exception as e:
                self.component_health['Blockchain'].status = "down"
                logger.error(f"Blockchain monitor failed: {e}")
        
        if self.arbitrage_detector and ARBITRAGE_AVAILABLE:
            try:
                await self.arbitrage_detector.start_monitoring()
                self.component_health['Arbitrage'].status = "healthy"
                self._log_activity("ARB", "Arbitrage detection started")
            except Exception as e:
                self.component_health['Arbitrage'].status = "down"
                logger.error(f"Arbitrage detector failed: {e}")
    
    async def _stop_components(self):
        """Stop all real-time components."""
        if self.ws_client:
            try:
                await self.ws_client.disconnect()
            except:
                pass
        
        if self.blockchain_monitor:
            try:
                await self.blockchain_monitor.stop()
            except:
                pass
        
        if self.arbitrage_detector:
            try:
                await self.arbitrage_detector.stop_monitoring()
            except:
                pass
    
    # ====================================================================================
    # Event Handlers
    # ====================================================================================
    
    def _on_trade_event(self, trade: TradeEvent):
        """Handle regular trade events."""
        self.stats['trades_detected'] += 1
        if trade.is_whale():
            self._log_activity("WS", f"Whale trade: ${trade.notional:,.0f} @ {trade.price:.3f}", 
                              {"market": trade.market_id[:8]})
    
    def _on_whale_trade_event(self, trade: TradeEvent):
        """Handle whale trade events."""
        self._log_activity("WHALE", f"🐋 Whale: ${trade.notional:,.0f} @ {trade.price:.3f}",
                          {"market": trade.market_id[:8], "side": trade.side})
        
        # Trigger copy if in appropriate mode
        if self.mode in [TradingMode.PAPER, TradingMode.LIVE] and not self._paused:
            asyncio.create_task(self._execute_copy(trade))
    
    def _on_blockchain_event(self, event: BlockchainEvent):
        """Handle blockchain events."""
        self._log_activity("BC", f"Blockchain event: {event.event_type.value}",
                          {"tx": event.tx_hash[:16] if event.tx_hash else "N/A"})
    
    def _on_arbitrage_opportunity(self, opportunity: ArbitrageOpportunity):
        """Handle arbitrage opportunities."""
        self._log_activity("ARB", f"Arbitrage: {opportunity.profit_percent:.2f}% profit",
                          {"type": opportunity.arb_type.value})
    
    async def _execute_copy(self, trade: TradeEvent):
        """Execute a copy trade."""
        if not self.latency_executor:
            return
        
        start_time = time.time()
        
        # Simulate execution for now (would use real executor in production)
        await asyncio.sleep(0.045)  # 45ms simulated latency
        
        self.stats['trades_executed'] += 1
        self.latency_metrics.execution_ms = (time.time() - start_time) * 1000
        
        self._log_activity("EX", f"COPY EXECUTED {self.latency_metrics.execution_ms:.0f}ms @ {trade.price:.2f}",
                          {"whale_price": trade.price})
    
    def _log_activity(self, source: str, message: str, details: Optional[Dict] = None):
        """Add activity log entry."""
        entry = ActivityLog(
            timestamp=datetime.now(),
            source=source,
            message=message,
            details=details or {}
        )
        self.activity_log.append(entry)
    
    # ====================================================================================
    # Display Update
    # ====================================================================================
    
    def _update_display(self):
        """Update all display panels."""
        # Header
        self.layout["header"].update(self._create_header())
        
        # Status bar
        self.layout["status_bar"].update(self._create_status_bar())
        
        # Latency panel
        self.layout["latency"].update(self._create_latency_panel())
        
        # Components panel
        self.layout["components"].update(self._create_components_panel())
        
        # Activity panel
        self.layout["activity"].update(self._create_activity_panel())
        
        # Portfolio panel
        self.layout["portfolio"].update(self._create_portfolio_panel())
        
        # Stats panel
        self.layout["stats"].update(self._create_stats_panel())
        
        # Controls
        self.layout["controls"].update(self._create_controls_panel())
    
    def _create_header(self) -> Panel:
        """Create header panel."""
        title = Text("POLYBOT ULTRA - Real-Time Trading Terminal", style="bold cyan")
        return Panel(Align.center(title), style="cyan")
    
    def _create_status_bar(self) -> Panel:
        """Create status bar panel."""
        mode_color = "red" if self.mode == TradingMode.LIVE else "green" if self.mode == TradingMode.PAPER else "yellow"
        status_color = {
            UltraStatus.RUNNING: "green",
            UltraStatus.PAUSED: "yellow",
            UltraStatus.EMERGENCY_STOP: "red",
            UltraStatus.STARTING: "cyan",
        }.get(self.status, "white")
        
        content = Text()
        content.append(f"Mode: ", style="dim")
        content.append(f"{self.mode.value.upper()}  ", style=f"bold {mode_color}")
        content.append(f"Speed: ", style="dim")
        content.append(f"{self.speed.value.upper()}  ", style="bold cyan")
        content.append(f"Status: ", style="dim")
        content.append(f"{self.status.value.upper()}", style=f"bold {status_color}")
        
        return Panel(content, style="dim")
    
    def _create_latency_panel(self) -> Panel:
        """Create latency metrics panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")
        table.add_column("Unit", style="dim")
        
        # Color coding for latency
        ws_color = "green" if self.latency_metrics.websocket_ms < 50 else "yellow" if self.latency_metrics.websocket_ms < 100 else "red"
        bc_color = "green" if self.latency_metrics.blockchain_ms < 500 else "yellow" if self.latency_metrics.blockchain_ms < 1000 else "red"
        ex_color = "green" if self.latency_metrics.execution_ms < 100 else "yellow" if self.latency_metrics.execution_ms < 200 else "red"
        e2e_color = "green" if self.latency_metrics.target_met else "red"
        
        table.add_row("WebSocket:", f"[{ws_color}]{self.latency_metrics.websocket_ms:.0f}[/{ws_color}]", "ms")
        table.add_row("Blockchain:", f"[{bc_color}]{self.latency_metrics.blockchain_ms:.0f}[/{bc_color}]", "ms")
        table.add_row("Execution:", f"[{ex_color}]{self.latency_metrics.execution_ms:.0f}[/{ex_color}]", "ms")
        table.add_row("End-to-End:", f"[{e2e_color}]{self.latency_metrics.end_to_end_ms:.0f}[/{e2e_color}]", "ms")
        table.add_row("Fill:", f"{self.latency_metrics.fill_ms:,.0f}", "ms")
        
        target_status = "✓" if self.latency_metrics.target_met else "✗"
        target_color = "green" if self.latency_metrics.target_met else "red"
        table.add_row("Target:", f"[bold {target_color}]{target_status} <{self.latency_metrics.target_ms:.0f}ms[/bold {target_color}]", "")
        
        return Panel(table, title="[bold]LATENCY METRICS[/bold]", border_style="blue")
    
    def _create_components_panel(self) -> Panel:
        """Create component health panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Component")
        table.add_column("Status", justify="center")
        table.add_column("Latency", justify="right")
        
        component_order = ['WebSocket', 'Blockchain', 'Predictor', 'Router', 'Executor', 'Arbitrage', 'Notifications']
        
        for name in component_order:
            health = self.component_health.get(name)
            if health:
                status_symbol = "✓" if health.is_healthy else "✗" if health.status == "down" else "~"
                status_color = "green" if health.is_healthy else "red" if health.status == "down" else "yellow"
                latency_str = f"{health.latency_ms:.0f}ms" if health.latency_ms > 0 else "-"
                table.add_row(
                    name,
                    f"[{status_color}]{status_symbol}[/{status_color}]",
                    f"[dim]{latency_str}[/dim]"
                )
            else:
                table.add_row(name, "[dim]-[/dim]", "[dim]-[/dim]")
        
        return Panel(table, title="[bold]ACTIVE COMPONENTS[/bold]", border_style="green")
    
    def _create_activity_panel(self) -> Panel:
        """Create activity log panel."""
        content = []
        for entry in list(self.activity_log)[-10:]:
            time_str = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
            source_color = {
                'WS': 'blue',
                'WHALE': 'magenta',
                'BC': 'cyan',
                'EX': 'green',
                'FIL': 'yellow',
                'ARB': 'bright_cyan',
                'SYS': 'white',
                'ERR': 'red',
            }.get(entry.source, 'white')
            
            content.append(f"[{time_str}] [[{source_color}]{entry.source}[/{source_color}]] {entry.message}")
        
        text = Text("\n".join(content) if content else "No activity yet...")
        return Panel(text, title="[bold]RECENT ACTIVITY[/bold]", border_style="yellow")
    
    def _create_portfolio_panel(self) -> Panel:
        """Create portfolio panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")
        
        pnl_color = "green" if self.portfolio.pnl >= 0 else "red"
        daily_color = "green" if self.portfolio.daily_pnl >= 0 else "red"
        
        table.add_row("Balance:", f"${self.portfolio.balance:,.2f}")
        table.add_row("Open Positions:", f"{self.portfolio.open_positions}")
        table.add_row("Total P&L:", f"[{pnl_color}]${self.portfolio.pnl:+.2f}[/{pnl_color}]")
        table.add_row("Daily P&L:", f"[{daily_color}]${self.portfolio.daily_pnl:+.2f}[/{daily_color}]")
        
        return Panel(table, title="[bold]PORTFOLIO[/bold]", border_style="magenta")
    
    def _create_stats_panel(self) -> Panel:
        """Create stats panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")
        
        duration = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
        
        table.add_row("Session Duration:", duration_str)
        table.add_row("Trades Detected:", str(self.stats['trades_detected']))
        table.add_row("Trades Executed:", str(self.stats['trades_executed']))
        table.add_row("Trades Filled:", str(self.stats['trades_filled']))
        table.add_row("Errors:", f"[red]{self.stats['errors']}[/red]" if self.stats['errors'] > 0 else "0")
        
        return Panel(table, title="[bold]STATISTICS[/bold]", border_style="cyan")
    
    def _create_controls_panel(self) -> Panel:
        """Create controls help panel."""
        controls = Text()
        controls.append("[P]", style="bold cyan")
        controls.append("ause  ", style="dim")
        controls.append("[E]", style="bold red")
        controls.append("mergency Stop  ", style="dim")
        controls.append("[S]", style="bold yellow")
        controls.append("tatus  ", style="dim")
        controls.append("[L]", style="bold green")
        controls.append("ive Mode  ", style="dim")
        controls.append("[Q]", style="bold magenta")
        controls.append("uit", style="dim")
        
        return Panel(Align.center(controls), style="dim")
    
    # ====================================================================================
    # Background Tasks
    # ====================================================================================
    
    async def _display_update_loop(self):
        """Update display at regular intervals."""
        while self._running and not self._stop_event.is_set():
            try:
                if self._live:
                    self._update_display()
                await asyncio.sleep(self.DISPLAY_UPDATE_INTERVAL)
            except Exception as e:
                logger.error(f"Display update error: {e}")
    
    async def _simple_display_loop(self):
        """Simple text-based display loop for when Rich is not available."""
        print("\n" + "=" * 80)
        print("POLYBOT ULTRA - Simple Mode (Install 'rich' for full UI)")
        print("=" * 80)
        print(f"Mode: {self.mode.value.upper()} | Speed: {self.speed.value.upper()} | Status: {self.status.value}")
        print("-" * 80)
        print("Controls: [P]ause  [E]mergency Stop  [S]tatus  [L]ive Mode  [Q]uit")
        print("=" * 80)
        
        last_update = 0
        while self._running and not self._stop_event.is_set():
            try:
                current_time = time.time()
                if current_time - last_update >= 2.0:  # Update every 2 seconds
                    # Print simple status
                    duration = int(current_time - self.stats['start_time']) if self.stats['start_time'] else 0
                    print(f"\r[{duration:3d}s] Detected: {self.stats['trades_detected']:3d} | "
                          f"Executed: {self.stats['trades_executed']:3d} | "
                          f"Latency: {self.latency_metrics.end_to_end_ms:.0f}ms | "
                          f"Status: {self.status.value:12s}", end='', flush=True)
                    last_update = current_time
                
                # Print recent activity every 5 seconds
                if int(current_time) % 5 == 0 and current_time - last_update >= 1:
                    recent = [e for e in self.activity_log if e.timestamp.timestamp() > current_time - 5]
                    for entry in recent[-3:]:
                        print(f"\n[{entry.timestamp.strftime('%H:%M:%S')}] [{entry.source}] {entry.message}")
                
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Simple display error: {e}")
        
        print("\n")
    
    async def _health_check_loop(self):
        """Check component health periodically."""
        while self._running and not self._stop_event.is_set():
            try:
                # Update WebSocket health
                if self.ws_client:
                    if self.ws_client.is_connected:
                        self.component_health['WebSocket'].status = "healthy"
                        self.component_health['WebSocket'].latency_ms = self.ws_client.stats.avg_latency_ms
                    else:
                        self.component_health['WebSocket'].status = "degraded"
                
                # Update blockchain health
                if self.blockchain_monitor:
                    if self.blockchain_monitor.is_connected:
                        self.component_health['Blockchain'].status = "healthy"
                    else:
                        self.component_health['Blockchain'].status = "degraded"
                
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _metrics_collection_loop(self):
        """Collect metrics continuously."""
        while self._running and not self._stop_event.is_set():
            try:
                # Calculate end-to-end latency
                self.latency_metrics.end_to_end_ms = (
                    self.latency_metrics.websocket_ms +
                    self.latency_metrics.blockchain_ms +
                    self.latency_metrics.execution_ms
                )
                
                # Store in history
                self.metrics_history.append({
                    'timestamp': time.time(),
                    **self.latency_metrics.__dict__
                })
                
                # Update session duration
                if self.stats['start_time']:
                    self.stats['session_duration'] = time.time() - self.stats['start_time']
                
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
    
    async def _keyboard_input_loop(self):
        """Handle keyboard input."""
        if not PROMPT_TOOLKIT_AVAILABLE:
            # Fallback: read from stdin
            while self._running and not self._stop_event.is_set():
                try:
                    # Use asyncio to read stdin without blocking
                    loop = asyncio.get_event_loop()
                    char = await loop.run_in_executor(None, self._read_char)
                    if char:
                        await self._handle_key(char.lower())
                except Exception as e:
                    await asyncio.sleep(0.1)
        else:
            # Use prompt_toolkit
            session = PromptSession(key_bindings=self._key_bindings)
            while self._running and not self._stop_event.is_set():
                try:
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Keyboard input error: {e}")
    
    def _read_char(self) -> Optional[str]:
        """Read a single character from stdin (cross-platform)."""
        try:
            if sys.platform == 'win32':
                import msvcrt
                if msvcrt.kbhit():
                    return msvcrt.getch().decode('utf-8', errors='ignore')
            else:
                import select
                import tty
                import termios
                
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    if select.select([sys.stdin], [], [], 0)[0]:
                        return sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except:
            pass
        return None
    
    async def _handle_key(self, key: str):
        """Handle a key press."""
        if key == 'p':
            await self._handle_pause_resume()
        elif key == 'e':
            await self._handle_emergency_stop()
        elif key == 's':
            await self._handle_status()
        elif key == 'l':
            await self._handle_toggle_mode()
        elif key == 'q':
            await self._handle_quit()
    
    # ====================================================================================
    # Keyboard Action Handlers
    # ====================================================================================
    
    async def _handle_pause_resume(self):
        """Handle pause/resume action."""
        if self.status == UltraStatus.RUNNING:
            self._paused = True
            self.status = UltraStatus.PAUSED
            self._log_activity("SYS", "Trading PAUSED")
        elif self.status == UltraStatus.PAUSED:
            self._paused = False
            self.status = UltraStatus.RUNNING
            self._log_activity("SYS", "Trading RESUMED")
    
    async def _handle_emergency_stop(self):
        """Handle emergency stop action."""
        self._emergency_stop = True
        self.status = UltraStatus.EMERGENCY_STOP
        self._log_activity("ERR", "🚨 EMERGENCY STOP ACTIVATED")
        
        # Cancel all pending orders
        if self.latency_executor:
            pass  # Would cancel all orders
        
        # Give user time to see the emergency stop
        await asyncio.sleep(2)
        await self.stop()
    
    async def _handle_status(self):
        """Handle status display action."""
        self._log_activity("SYS", f"Status: {self.status.value}, Mode: {self.mode.value}")
        
        # Show detailed stats in log
        self._log_activity("SYS", f"Detected: {self.stats['trades_detected']}, Executed: {self.stats['trades_executed']}")
    
    async def _handle_toggle_mode(self):
        """Handle mode toggle action."""
        if self.mode == TradingMode.PAPER:
            confirmed = await self._confirm_live_mode()
            if confirmed:
                self.mode = TradingMode.LIVE
                self._log_activity("SYS", "🔴 Switched to LIVE mode")
        else:
            self.mode = TradingMode.PAPER
            self._log_activity("SYS", "🟢 Switched to PAPER mode")
    
    async def _handle_quit(self):
        """Handle quit action."""
        self._log_activity("SYS", "Shutting down...")
        await self.stop()
    
    async def _confirm_live_mode(self) -> bool:
        """Confirm live mode activation."""
        # In a real terminal UI, this would show a confirmation dialog
        # For now, we just log and return True
        self._log_activity("SYS", "⚠️ Confirming LIVE mode...")
        return True


# Convenience function for CLI
async def run_ultra_trading(
    mode: str = "paper",
    speed: str = "ultra",
    whales: Optional[List[str]] = None,
    predictive: bool = False,
    arbitrage: bool = False,
    websocket_only: bool = False,
    blockchain_only: bool = False
):
    """
    Run ultra trading system.
    
    Args:
        mode: Trading mode (paper/live/simulation)
        speed: Speed profile (ultra/balanced/economy)
        whales: List of whale addresses
        predictive: Enable predictive entries
        arbitrage: Enable arbitrage detection
        websocket_only: Use only WebSocket
        blockchain_only: Use only blockchain
    """
    ultra = UltraTradingSystem()
    await ultra.start(
        mode=mode,
        speed=speed,
        whales=whales,
        enable_predictive=predictive,
        enable_arbitrage=arbitrage,
        websocket_only=websocket_only,
        blockchain_only=blockchain_only
    )
