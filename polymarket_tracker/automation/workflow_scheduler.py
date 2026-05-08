"""
PolyBot Automated Daily Workflow Scheduler

Comprehensive automation system that orchestrates the entire daily workflow:
- Scheduled scans for winners
- Continuous market monitoring
- P&L tracking and reporting
- Smart decision making
- Risk management integration
- Notification delivery

Uses APScheduler for reliable task scheduling with persistence and recovery.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Coroutine
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# APScheduler imports
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.events import (
        EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED,
        JobExecutionEvent, JobErrorEvent
    )
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

# PolyBot imports
from polymarket_tracker.notifications.notification_manager import (
    NotificationManager, NotificationConfig, NotificationType
)
from polymarket_tracker.risk.position_manager import PositionManager, RiskParameters


# Configure logging
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"
    STOPPED = "stopped"


class TaskStatus(Enum):
    """Individual task status."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"
    DISABLED = "disabled"


@dataclass
class WorkflowConfig:
    """Configuration for the workflow scheduler."""
    
    # Timing configuration
    scan_time: str = "09:00"  # Daily scan time (HH:MM)
    report_time: str = "18:00"  # Daily report time (HH:MM)
    analyze_time: Optional[str] = "09:05"  # Analysis time (HH:MM, None to run after scan)
    
    # Feature toggles
    monitoring_enabled: bool = True
    auto_trade_enabled: bool = False  # Require manual confirmation by default
    notification_enabled: bool = True
    health_checks_enabled: bool = True
    
    # Intervals (minutes)
    pnl_update_interval: int = 15
    health_check_interval: int = 5
    monitoring_interval: int = 1
    position_check_interval: int = 2
    
    # Risk overrides
    risk_override: bool = False  # Emergency override (use with caution!)
    max_daily_trades: int = 1
    min_ev_threshold: float = 0.05  # 5% minimum EV
    
    # Market conditions
    require_market_open: bool = True
    max_market_volatility: float = 0.5  # Skip if volatility > 50%
    
    # Persistence
    state_file: str = "workflow_state.json"
    log_dir: str = "logs/workflow"
    
    # Timezone
    timezone: str = "America/New_York"  # Default to US Eastern
    
    @classmethod
    def from_env(cls) -> "WorkflowConfig":
        """Load configuration from environment variables."""
        return cls(
            scan_time=os.getenv("WORKFLOW_SCAN_TIME", "09:00"),
            report_time=os.getenv("WORKFLOW_REPORT_TIME", "18:00"),
            analyze_time=os.getenv("WORKFLOW_ANALYZE_TIME") or "09:05",
            monitoring_enabled=os.getenv("WORKFLOW_MONITORING", "true").lower() == "true",
            auto_trade_enabled=os.getenv("WORKFLOW_AUTO_TRADE", "false").lower() == "true",
            notification_enabled=os.getenv("WORKFLOW_NOTIFICATIONS", "true").lower() == "true",
            health_checks_enabled=os.getenv("WORKFLOW_HEALTH_CHECKS", "true").lower() == "true",
            pnl_update_interval=int(os.getenv("WORKFLOW_PNL_INTERVAL", "15")),
            health_check_interval=int(os.getenv("WORKFLOW_HEALTH_INTERVAL", "5")),
            risk_override=os.getenv("WORKFLOW_RISK_OVERRIDE", "false").lower() == "true",
            max_daily_trades=int(os.getenv("WORKFLOW_MAX_DAILY_TRADES", "1")),
            min_ev_threshold=float(os.getenv("WORKFLOW_MIN_EV", "0.05")),
            timezone=os.getenv("WORKFLOW_TIMEZONE", "America/New_York"),
        )


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""
    task_id: str
    name: str
    job_id: Optional[str] = None
    status: TaskStatus = TaskStatus.SCHEDULED
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    last_result: Optional[Any] = None
    last_error: Optional[str] = None
    run_count: int = 0
    fail_count: int = 0


@dataclass
class WorkflowState:
    """Persistent workflow state."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run_date: Optional[str] = None
    daily_trade_count: int = 0
    daily_pnl: float = 0.0
    total_trades: int = 0
    total_pnl: float = 0.0
    winners_cached: bool = False
    analysis_completed: bool = False
    trades_executed_today: List[Dict] = field(default_factory=list)
    errors_today: List[Dict] = field(default_factory=list)
    status: str = WorkflowStatus.IDLE.value
    
    def reset_daily(self):
        """Reset daily counters."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_run_date != today:
            self.last_run_date = today
            self.daily_trade_count = 0
            self.daily_pnl = 0.0
            self.winners_cached = False
            self.analysis_completed = False
            self.trades_executed_today = []
            self.errors_today = []


class WorkflowScheduler:
    """
    Automated Daily Workflow Scheduler for PolyBot.
    
    Orchestrates the complete trading workflow with:
    - Scheduled daily scans and analysis
    - Continuous market monitoring
    - Smart decision making
    - Risk-aware execution
    - Comprehensive logging and notifications
    
    Example:
        scheduler = WorkflowScheduler()
        await scheduler.start()
        # Runs in background, executing scheduled tasks
        await scheduler.stop()
    """
    
    # Task IDs
    TASK_DAILY_SCAN = "daily_scan"
    TASK_CONTINUOUS_MONITOR = "continuous_monitor"
    TASK_PNL_UPDATE = "pnl_update"
    TASK_DAILY_REPORT = "daily_report"
    TASK_HEALTH_CHECK = "health_check"
    TASK_DEEP_ANALYZE = "deep_analyze"
    TASK_POSITION_MONITOR = "position_monitor"
    
    def __init__(
        self,
        config: Optional[WorkflowConfig] = None,
        notification_manager: Optional[NotificationManager] = None,
        position_manager: Optional[PositionManager] = None,
        cli_bot=None
    ):
        """
        Initialize the workflow scheduler.
        
        Args:
            config: Workflow configuration
            notification_manager: Notification manager for alerts
            position_manager: Position manager for risk tracking
            cli_bot: CLIBot instance for executing commands
        """
        self.config = config or WorkflowConfig.from_env()
        self.notifier = notification_manager or NotificationManager()
        self.position_manager = position_manager
        self.cli_bot = cli_bot
        
        # Scheduler
        self.scheduler: Optional[Any] = None
        self._scheduler_available = APSCHEDULER_AVAILABLE
        
        # State
        self.state = self._load_state()
        self.tasks: Dict[str, ScheduledTask] = {}
        self.workflow_status = WorkflowStatus.IDLE
        
        # Tracking
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._initialized = False
        
        # Callbacks
        self._scan_callback: Optional[Callable] = None
        self._analyze_callback: Optional[Callable] = None
        self._trade_callback: Optional[Callable] = None
        
        # Statistics
        self.start_time: Optional[datetime] = None
        self.cycle_count = 0
        
        # Ensure log directory exists
        Path(self.config.log_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"WorkflowScheduler initialized (ID: {self.state.workflow_id})")
    
    def _load_state(self) -> WorkflowState:
        """Load workflow state from file."""
        state_file = Path(self.config.state_file)
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                return WorkflowState(**data)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return WorkflowState()
    
    def _save_state(self):
        """Save workflow state to file."""
        try:
            with open(self.config.state_file, 'w') as f:
                json.dump(asdict(self.state), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _reset_daily_if_needed(self):
        """Reset daily counters if it's a new day."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.last_run_date != today:
            logger.info(f"New day detected ({today}), resetting daily counters")
            self.state.reset_daily()
            self._save_state()
    
    # ==================== Initialization ====================
    
    async def initialize(self):
        """Initialize the scheduler and components."""
        if self._initialized:
            return
        
        logger.info("Initializing WorkflowScheduler...")
        
        # Check dependencies
        if not self._scheduler_available:
            logger.warning("APScheduler not available. Installing...")
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "apscheduler"])
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                from apscheduler.triggers.cron import CronTrigger
                from apscheduler.triggers.interval import IntervalTrigger
                self._scheduler_available = True
            except Exception as e:
                logger.error(f"Failed to install APScheduler: {e}")
                raise RuntimeError("APScheduler is required but not available")
        
        # Initialize scheduler
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        self.scheduler = AsyncIOScheduler(timezone=self.config.timezone)
        
        # Add event listeners
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        
        # Initialize notification manager session
        await self.notifier._get_session()
        
        self._initialized = True
        logger.info("WorkflowScheduler initialization complete")
    
    def _on_job_executed(self, event: JobExecutionEvent):
        """Handle successful job execution."""
        task_id = self._get_task_id_from_job(event.job_id)
        if task_id and task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED
            task.last_run = datetime.now()
            task.run_count += 1
            logger.debug(f"Job {event.job_id} executed successfully")
    
    def _on_job_error(self, event: JobErrorEvent):
        """Handle job execution error."""
        task_id = self._get_task_id_from_job(event.job_id)
        if task_id and task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.FAILED
            task.fail_count += 1
            task.last_error = str(event.exception)
            logger.error(f"Job {event.job_id} failed: {event.exception}")
    
    def _get_task_id_from_job(self, job_id: str) -> Optional[str]:
        """Get task ID from job ID."""
        for task_id, task in self.tasks.items():
            if task.job_id == job_id:
                return task_id
        return None
    
    # ==================== Task Registration ====================
    
    def register_scan_callback(self, callback: Callable[[], Coroutine]):
        """Register callback for daily scan."""
        self._scan_callback = callback
    
    def register_analyze_callback(self, callback: Callable[[], Coroutine]):
        """Register callback for deep analysis."""
        self._analyze_callback = callback
    
    def register_trade_callback(self, callback: Callable[[Dict], Coroutine]):
        """Register callback for trade execution."""
        self._trade_callback = callback
    
    # ==================== Scheduled Tasks ====================
    
    def schedule_daily_scan(self, time_str: Optional[str] = None) -> ScheduledTask:
        """
        Schedule daily winner discovery scan.
        
        Args:
            time_str: Time in "HH:MM" format (uses config if not provided)
            
        Returns:
            ScheduledTask instance
        """
        time_str = time_str or self.config.scan_time
        hour, minute = map(int, time_str.split(":"))
        
        task = ScheduledTask(
            task_id=self.TASK_DAILY_SCAN,
            name="Daily Winner Scan"
        )
        
        if self.scheduler:
            from apscheduler.triggers.cron import CronTrigger
            job = self.scheduler.add_job(
                self._run_daily_scan,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=self.TASK_DAILY_SCAN,
                name="Daily Winner Scan",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_DAILY_SCAN] = task
        logger.info(f"Scheduled daily scan at {time_str}")
        return task
    
    def schedule_continuous_monitoring(self) -> ScheduledTask:
        """
        Schedule continuous whale and market monitoring.
        
        Returns:
            ScheduledTask instance
        """
        task = ScheduledTask(
            task_id=self.TASK_CONTINUOUS_MONITOR,
            name="Continuous Monitoring"
        )
        
        if self.scheduler and self.config.monitoring_enabled:
            from apscheduler.triggers.interval import IntervalTrigger
            job = self.scheduler.add_job(
                self._run_continuous_monitor,
                trigger=IntervalTrigger(minutes=self.config.monitoring_interval),
                id=self.TASK_CONTINUOUS_MONITOR,
                name="Continuous Monitoring",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_CONTINUOUS_MONITOR] = task
        logger.info(f"Scheduled continuous monitoring every {self.config.monitoring_interval} min")
        return task
    
    def schedule_pnl_updates(self, interval_minutes: Optional[int] = None) -> ScheduledTask:
        """
        Schedule regular P&L updates.
        
        Args:
            interval_minutes: Update interval (uses config if not provided)
            
        Returns:
            ScheduledTask instance
        """
        interval = interval_minutes or self.config.pnl_update_interval
        
        task = ScheduledTask(
            task_id=self.TASK_PNL_UPDATE,
            name="P&L Update"
        )
        
        if self.scheduler:
            from apscheduler.triggers.interval import IntervalTrigger
            job = self.scheduler.add_job(
                self._run_pnl_update,
                trigger=IntervalTrigger(minutes=interval),
                id=self.TASK_PNL_UPDATE,
                name="P&L Update",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_PNL_UPDATE] = task
        logger.info(f"Scheduled P&L updates every {interval} min")
        return task
    
    def schedule_daily_report(self, time_str: Optional[str] = None) -> ScheduledTask:
        """
        Schedule daily summary report.
        
        Args:
            time_str: Time in "HH:MM" format (uses config if not provided)
            
        Returns:
            ScheduledTask instance
        """
        time_str = time_str or self.config.report_time
        hour, minute = map(int, time_str.split(":"))
        
        task = ScheduledTask(
            task_id=self.TASK_DAILY_REPORT,
            name="Daily Report"
        )
        
        if self.scheduler:
            from apscheduler.triggers.cron import CronTrigger
            job = self.scheduler.add_job(
                self._run_daily_report,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=self.TASK_DAILY_REPORT,
                name="Daily Report",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_DAILY_REPORT] = task
        logger.info(f"Scheduled daily report at {time_str}")
        return task
    
    def schedule_health_checks(self, interval_minutes: Optional[int] = None) -> ScheduledTask:
        """
        Schedule system health monitoring.
        
        Args:
            interval_minutes: Check interval (uses config if not provided)
            
        Returns:
            ScheduledTask instance
        """
        interval = interval_minutes or self.config.health_check_interval
        
        task = ScheduledTask(
            task_id=self.TASK_HEALTH_CHECK,
            name="Health Check"
        )
        
        if self.scheduler and self.config.health_checks_enabled:
            from apscheduler.triggers.interval import IntervalTrigger
            job = self.scheduler.add_job(
                self._run_health_check,
                trigger=IntervalTrigger(minutes=interval),
                id=self.TASK_HEALTH_CHECK,
                name="Health Check",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_HEALTH_CHECK] = task
        logger.info(f"Scheduled health checks every {interval} min")
        return task
    
    def schedule_position_monitoring(self) -> ScheduledTask:
        """
        Schedule position monitoring (stops, take profits).
        
        Returns:
            ScheduledTask instance
        """
        task = ScheduledTask(
            task_id=self.TASK_POSITION_MONITOR,
            name="Position Monitor"
        )
        
        if self.scheduler:
            from apscheduler.triggers.interval import IntervalTrigger
            job = self.scheduler.add_job(
                self._run_position_monitor,
                trigger=IntervalTrigger(minutes=self.config.position_check_interval),
                id=self.TASK_POSITION_MONITOR,
                name="Position Monitor",
                replace_existing=True
            )
            task.job_id = job.id
            task.next_run = job.next_run_time
        
        self.tasks[self.TASK_POSITION_MONITOR] = task
        logger.info(f"Scheduled position monitoring every {self.config.position_check_interval} min")
        return task
    
    # ==================== Task Execution ====================
    
    async def _run_daily_scan(self):
        """Execute daily winner scan."""
        logger.info("=" * 60)
        logger.info("DAILY SCAN STARTED")
        logger.info("=" * 60)
        
        self._reset_daily_if_needed()
        task = self.tasks.get(self.TASK_DAILY_SCAN)
        if task:
            task.status = TaskStatus.RUNNING
        
        try:
            # Send notification
            if self.config.notification_enabled:
                await self.notifier.notify_system_alert(
                    title="Daily Scan Started",
                    message=f"Starting daily winner discovery at {datetime.now().strftime('%H:%M')}",
                    alert_type="info"
                )
            
            # Check if we should execute today
            if not await self.should_execute_today():
                logger.info("Conditions not met for today's scan")
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.last_result = "skipped"
                return
            
            # Execute scan via callback or cli_bot
            scan_result = None
            if self._scan_callback:
                scan_result = await self._scan_callback()
            elif self.cli_bot:
                await self.cli_bot.scan()
                scan_result = self.cli_bot.state.get("winners_cached", [])
            
            # Update state
            self.state.winners_cached = bool(scan_result)
            self._save_state()
            
            # Log result
            winner_count = len(scan_result) if isinstance(scan_result, list) else 0
            logger.info(f"Daily scan complete. Found {winner_count} winners.")
            
            if task:
                task.status = TaskStatus.COMPLETED
                task.last_result = {"winners_found": winner_count}
            
            # Trigger analysis after scan (if configured)
            if self.config.analyze_time == "immediate":
                await asyncio.sleep(5)  # Brief delay
                await self._run_deep_analyze()
                
        except Exception as e:
            logger.error(f"Daily scan failed: {e}")
            if task:
                task.status = TaskStatus.FAILED
                task.last_error = str(e)
            self._log_error("daily_scan", e)
            
            if self.config.notification_enabled:
                await self.notifier.notify_error(
                    error_message="Daily scan failed",
                    error_details=str(e)
                )
    
    async def _run_deep_analyze(self):
        """Execute deep analysis for best opportunity."""
        logger.info("=" * 60)
        logger.info("DEEP ANALYSIS STARTED")
        logger.info("=" * 60)
        
        task = self.tasks.get(self.TASK_DEEP_ANALYZE)
        if task:
            task.status = TaskStatus.RUNNING
        
        try:
            # Check if winners are cached
            if not self.state.winners_cached:
                logger.warning("No winners cached. Run scan first.")
                if task:
                    task.status = TaskStatus.FAILED
                    task.last_error = "No winners cached"
                return
            
            # Check daily trade limit
            if self.state.daily_trade_count >= self.config.max_daily_trades:
                logger.info(f"Daily trade limit reached ({self.config.max_daily_trades})")
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.last_result = "limit_reached"
                return
            
            # Execute analysis
            analysis_result = None
            if self._analyze_callback:
                analysis_result = await self._analyze_callback()
            elif self.cli_bot:
                await self.cli_bot.analyze()
                analysis_result = self.cli_bot.state.get("recommended_trade")
            
            self.state.analysis_completed = True
            
            # Check if high EV opportunity found
            if analysis_result:
                ev = analysis_result.get("ev", 0)
                if ev >= self.config.min_ev_threshold * 100:  # Convert from % to decimal
                    logger.info(f"High EV opportunity found: {ev:+.1f}%")
                    
                    # Notify about opportunity
                    if self.config.notification_enabled:
                        await self.notifier.notify_high_ev_opportunity(
                            signal=analysis_result,
                            ev=ev / 100,  # Convert back to decimal
                            bypass_rate_limit=True
                        )
                    
                    # Auto-trade or manual confirmation
                    if self.config.auto_trade_enabled and self.config.risk_override:
                        logger.warning("AUTO-TRADE ENABLED - Executing trade")
                        await self._execute_trade_opportunity(analysis_result)
                    else:
                        logger.info("Manual confirmation required for trade execution")
                else:
                    logger.info(f"No high EV opportunity (found: {ev:+.1f}%, min: {self.config.min_ev_threshold:.1%})")
            
            if task:
                task.status = TaskStatus.COMPLETED
                task.last_result = analysis_result
                
            self._save_state()
            
        except Exception as e:
            logger.error(f"Deep analysis failed: {e}")
            if task:
                task.status = TaskStatus.FAILED
                task.last_error = str(e)
            self._log_error("deep_analyze", e)
    
    async def _run_continuous_monitor(self):
        """Execute continuous monitoring."""
        try:
            # This would integrate with whale trackers, etc.
            logger.debug("Running continuous market monitoring...")
            
            # Placeholder for actual monitoring logic
            # Would check for whale activity, price movements, etc.
            
            self.cycle_count += 1
            
        except Exception as e:
            logger.error(f"Continuous monitor error: {e}")
    
    async def _run_pnl_update(self):
        """Execute P&L update."""
        try:
            logger.debug("Running P&L update...")
            
            # Get portfolio data
            portfolio_value = 10000  # Default
            daily_pnl = 0
            
            if self.position_manager:
                summary = self.position_manager.get_portfolio_summary()
                portfolio_value = summary.get('bankroll', portfolio_value)
                daily_pnl = summary.get('daily_pnl', 0)
            elif self.cli_bot:
                portfolio_value = self.cli_bot.state.get('portfolio_value', portfolio_value)
                daily_pnl = self.cli_bot.state.get('daily_pnl', 0)
            
            # Update state
            self.state.daily_pnl = daily_pnl
            self._save_state()
            
            # Check for significant changes
            if abs(daily_pnl) > portfolio_value * 0.05:  # 5% move
                logger.info(f"Significant P&L change: ${daily_pnl:+.2f}")
                if self.config.notification_enabled:
                    await self.notifier.notify_system_alert(
                        title="Significant P&L Change",
                        message=f"Daily P&L: ${daily_pnl:+.2f} ({daily_pnl/portfolio_value:+.1%})",
                        alert_type="warning" if daily_pnl < 0 else "info"
                    )
                    
        except Exception as e:
            logger.error(f"P&L update error: {e}")
    
    async def _run_daily_report(self):
        """Execute daily summary report."""
        logger.info("=" * 60)
        logger.info("DAILY REPORT")
        logger.info("=" * 60)
        
        try:
            # Compile daily stats
            stats = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "total_trades": self.state.daily_trade_count,
                "total_pnl": self.state.daily_pnl,
                "win_rate": 0,  # Would calculate from actual results
                "avg_trade": 0,
                "analysis_completed": self.state.analysis_completed,
                "winners_cached": self.state.winners_cached,
            }
            
            # Add position manager stats if available
            if self.position_manager:
                pm_stats = self.position_manager.get_trade_statistics()
                if isinstance(pm_stats, dict) and 'win_rate' in pm_stats:
                    stats['win_rate'] = pm_stats['win_rate'] * 100
                    stats['avg_trade'] = pm_stats.get('avg_r_multiple', 0)
            
            # Send notification
            if self.config.notification_enabled:
                await self.notifier.notify_daily_summary(stats, bypass_rate_limit=True)
            
            # Log to file
            report_file = Path(self.config.log_dir) / f"report_{datetime.now().strftime('%Y%m%d')}.json"
            with open(report_file, 'w') as f:
                json.dump(stats, f, indent=2)
            
            logger.info(f"Daily report generated: {report_file}")
            
        except Exception as e:
            logger.error(f"Daily report error: {e}")
    
    async def _run_health_check(self):
        """Execute system health check."""
        try:
            logger.debug("Running health check...")
            
            issues = []
            
            # Check API connectivity
            api_healthy = await self.check_api_health()
            if not api_healthy:
                issues.append("API connectivity issue")
            
            # Check disk space
            # Check memory usage
            # Check position manager health
            
            if issues:
                logger.warning(f"Health check issues: {', '.join(issues)}")
                if self.config.notification_enabled:
                    await self.notifier.notify_system_alert(
                        title="Health Check Warning",
                        message="; ".join(issues),
                        alert_type="warning"
                    )
            else:
                logger.debug("Health check passed")
                
        except Exception as e:
            logger.error(f"Health check error: {e}")
    
    async def _run_position_monitor(self):
        """Monitor positions for stops, take profits."""
        try:
            if not self.position_manager:
                return
            
            # Check for exit conditions
            # This would be called more frequently in real implementation
            logger.debug("Monitoring positions...")
            
        except Exception as e:
            logger.error(f"Position monitor error: {e}")
    
    # ==================== Workflow Automation ====================
    
    async def run_full_daily_workflow(self) -> Dict[str, Any]:
        """
        Execute the complete automated daily workflow.
        
        Workflow:
        1. Check status
        2. Scan for winners (if not cached)
        3. Analyze opportunities
        4. Execute trades if criteria met
        5. Update portfolio
        6. Send notifications
        
        Returns:
            Dictionary with workflow results
        """
        logger.info("=" * 60)
        logger.info("FULL DAILY WORKFLOW STARTED")
        logger.info("=" * 60)
        
        self.workflow_status = WorkflowStatus.RUNNING
        results = {
            "started_at": datetime.now().isoformat(),
            "steps_completed": [],
            "errors": [],
            "trade_executed": False
        }
        
        try:
            # Step 1: Check status
            logger.info("Step 1: Checking status...")
            self._reset_daily_if_needed()
            results["steps_completed"].append("status_check")
            
            # Step 2: Scan for winners (if needed)
            if not self.state.winners_cached:
                logger.info("Step 2: Scanning for winners...")
                await self._run_daily_scan()
                results["steps_completed"].append("winner_scan")
            else:
                logger.info("Step 2: Using cached winners")
                results["steps_completed"].append("winner_cache")
            
            # Step 3: Analyze opportunities
            logger.info("Step 3: Analyzing opportunities...")
            await self._run_deep_analyze()
            results["steps_completed"].append("deep_analysis")
            
            # Step 4: Execute trade if criteria met and enabled
            trade = None
            if self.cli_bot:
                trade = self.cli_bot.state.get("recommended_trade")
            
            if trade and self.config.auto_trade_enabled:
                logger.info("Step 4: Auto-executing trade...")
                executed = await self._execute_trade_opportunity(trade)
                results["trade_executed"] = executed
                results["steps_completed"].append("trade_execution")
            else:
                logger.info("Step 4: Trade execution skipped (manual mode or no trade)")
                results["steps_completed"].append("trade_skipped")
            
            # Step 5: Update portfolio
            logger.info("Step 5: Updating portfolio...")
            await self._run_pnl_update()
            results["steps_completed"].append("portfolio_update")
            
            # Step 6: Send notifications
            logger.info("Step 6: Sending notifications...")
            await self.send_status_update()
            results["steps_completed"].append("notifications")
            
            results["completed_at"] = datetime.now().isoformat()
            results["status"] = "success"
            
            self.workflow_status = WorkflowStatus.COMPLETED
            logger.info("=" * 60)
            logger.info("FULL DAILY WORKFLOW COMPLETED")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            results["errors"].append(str(e))
            results["status"] = "failed"
            self.workflow_status = WorkflowStatus.ERROR
            self._log_error("full_workflow", e)
        
        return results
    
    async def _execute_trade_opportunity(self, trade: Dict) -> bool:
        """
        Execute a trade opportunity.
        
        Args:
            trade: Trade details dictionary
            
        Returns:
            True if executed successfully
        """
        try:
            # Check risk constraints
            can_trade, reason = await self.check_risk_constraints()
            if not can_trade:
                logger.warning(f"Trade blocked by risk constraints: {reason}")
                return False
            
            # Execute via callback or cli_bot
            if self._trade_callback:
                await self._trade_callback(trade)
            elif self.cli_bot:
                self.cli_bot.copy_trade(auto_confirm=True)
            
            # Update state
            self.state.daily_trade_count += 1
            self.state.total_trades += 1
            self.state.trades_executed_today.append({
                "time": datetime.now().isoformat(),
                "trade": trade
            })
            self._save_state()
            
            # Notify
            if self.config.notification_enabled:
                await self.notifier.notify_trade_executed({
                    "market": trade.get("market", "Unknown"),
                    "side": trade.get("side", "YES"),
                    "size": trade.get("size", 0),
                    "entry_price": trade.get("price", 0.5),
                    "expected_value": trade.get("ev", 0) / 100
                }, bypass_rate_limit=True)
            
            logger.info(f"Trade executed: {trade.get('market', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return False
    
    # ==================== Smart Decision Making ====================
    
    async def should_execute_today(self) -> bool:
        """
        Check if conditions are right for today's execution.
        
        Checks:
        - Daily trade limit not exceeded
        - Market conditions favorable
        - Risk constraints satisfied
        - No circuit breakers active
        
        Returns:
            True if should execute today
        """
        # Check daily limit
        if self.state.daily_trade_count >= self.config.max_daily_trades:
            logger.info(f"Daily trade limit reached ({self.config.max_daily_trades})")
            return False
        
        # Check market conditions
        market_healthy = await self.evaluate_market_conditions()
        if not market_healthy:
            logger.info("Market conditions not favorable")
            return False
        
        # Check risk constraints
        can_trade, _ = await self.check_risk_constraints()
        if not can_trade:
            logger.info("Risk constraints blocking execution")
            return False
        
        return True
    
    async def evaluate_market_conditions(self) -> bool:
        """
        Check overall market health.
        
        Returns:
            True if market conditions are favorable
        """
        # Placeholder for market condition checks
        # Would check:
        # - Market volatility
        # - Liquidity
        # - Correlation spikes
        # - News/events
        
        return True  # Default to allowing execution
    
    async def check_risk_constraints(self) -> tuple[bool, str]:
        """
        Verify portfolio risk limits.
        
        Returns:
            (can_trade, reason)
        """
        # Check daily loss limit
        if self.position_manager:
            portfolio = self.position_manager.get_portfolio_summary()
            daily_pnl = portfolio.get('daily_pnl', 0)
            bankroll = portfolio.get('bankroll', 10000)
            
            if daily_pnl < -bankroll * 0.1:  # 10% daily loss
                return False, "Daily loss limit exceeded"
            
            # Check drawdown
            drawdown = portfolio.get('current_drawdown', 0)
            if drawdown > 0.2:  # 20% max drawdown
                return False, f"Max drawdown exceeded: {drawdown:.1%}"
        
        # Check if already at max positions
        if self.cli_bot and len(self.cli_bot.state.get('current_positions', [])) >= 5:
            return False, "Max open positions reached"
        
        return True, "OK"
    
    # ==================== Monitoring & Alerts ====================
    
    async def monitor_positions(self) -> List[Dict]:
        """
        Check all positions for stops, take profits, time exits.
        
        Returns:
            List of positions needing action
        """
        actions_needed = []
        
        if self.position_manager:
            # Get current market prices (placeholder)
            market_prices = {}
            
            # Update positions and check for exits
            actions = self.position_manager.update_positions(market_prices)
            
            for action in actions:
                position = action['position']
                reason = action['reason']
                
                logger.info(f"Position {position.position_id} needs action: {reason}")
                
                # Notify
                if self.config.notification_enabled:
                    await self.notifier.notify_position_update({
                        "market": position.market_id,
                        "status": "exit_signal",
                        "exit_reason": reason,
                        "pnl": position.unrealized_pnl,
                        "pnl_percent": position.unrealized_pnl_pct * 100
                    })
                
                actions_needed.append(action)
        
        return actions_needed
    
    async def check_api_health(self) -> bool:
        """
        Verify API connectivity.
        
        Returns:
            True if all APIs are healthy
        """
        # Placeholder for API health checks
        # Would check:
        # - Subgraph connectivity
        # - Polymarket API
        # - Notification services
        
        return True
    
    async def send_status_update(self) -> Dict[str, bool]:
        """
        Send regular status report.
        
        Returns:
            Dictionary with notification results
        """
        # Build status message
        status_msg = f"""
<b>📊 PolyBot Status Update</b>

<b>Workflow:</b> {self.workflow_status.value}
<b>Uptime:</b> {self._get_uptime()}
<b>Daily Trades:</b> {self.state.daily_trade_count} / {self.config.max_daily_trades}
<b>Daily P&L:</b> ${self.state.daily_pnl:+.2f}
<b>Winners Cached:</b> {'✅' if self.state.winners_cached else '❌'}
<b>Analysis Complete:</b> {'✅' if self.state.analysis_completed else '❌'}
""".strip()
        
        return await self.notifier._send_all_channels(
            notif_type=NotificationType.SYSTEM_ALERT,
            telegram_message=status_msg,
            bypass_rate_limit=True
        )
    
    def _get_uptime(self) -> str:
        """Get formatted uptime string."""
        if not self.start_time:
            return "N/A"
        
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m {seconds}s"
    
    # ==================== Control Methods ====================
    
    async def start(self):
        """Start the workflow scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        logger.info("=" * 60)
        logger.info("STARTING WORKFLOW SCHEDULER")
        logger.info("=" * 60)
        
        # Initialize
        await self.initialize()
        
        # Reset daily counters if needed
        self._reset_daily_if_needed()
        
        # Schedule all tasks
        self._schedule_all_tasks()
        
        # Start scheduler
        if self.scheduler:
            self.scheduler.start()
        
        self._running = True
        self.start_time = datetime.now()
        self.workflow_status = WorkflowStatus.RUNNING
        
        # Send startup notification
        if self.config.notification_enabled:
            await self.notifier.notify_system_alert(
                title="Workflow Scheduler Started",
                message=f"PolyBot automation is now running. Daily scan at {self.config.scan_time}",
                alert_type="info"
            )
        
        logger.info("Workflow scheduler started successfully")
        logger.info(f"Daily scan scheduled for {self.config.scan_time}")
        logger.info(f"Daily report scheduled for {self.config.report_time}")
        
        # Keep running until shutdown
        try:
            while self._running and not self._shutdown_event.is_set():
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
    
    def _schedule_all_tasks(self):
        """Schedule all default tasks."""
        self.schedule_daily_scan()
        
        if self.config.monitoring_enabled:
            self.schedule_continuous_monitoring()
        
        self.schedule_pnl_updates()
        self.schedule_daily_report()
        
        if self.config.health_checks_enabled:
            self.schedule_health_checks()
        
        self.schedule_position_monitoring()
        
        logger.info(f"Scheduled {len(self.tasks)} tasks")
    
    async def stop(self, timeout: float = 30.0):
        """
        Stop the workflow scheduler gracefully.
        
        Args:
            timeout: Maximum time to wait for graceful shutdown
        """
        if not self._running:
            return
        
        logger.info("=" * 60)
        logger.info("STOPPING WORKFLOW SCHEDULER")
        logger.info("=" * 60)
        
        self._running = False
        self.workflow_status = WorkflowStatus.STOPPED
        self._shutdown_event.set()
        
        # Stop scheduler
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        
        # Save state
        self._save_state()
        
        # Close notification manager
        await self.notifier.close()
        
        # Send shutdown notification
        try:
            if self.config.notification_enabled:
                await self.notifier.notify_system_alert(
                    title="Workflow Scheduler Stopped",
                    message=f"PolyBot automation stopped. Daily P&L: ${self.state.daily_pnl:+.2f}",
                    alert_type="info"
                )
        except:
            pass  # Ignore errors during shutdown
        
        logger.info("Workflow scheduler stopped")
    
    async def pause(self):
        """Pause all scheduled tasks."""
        if self.scheduler:
            self.scheduler.pause()
        self.workflow_status = WorkflowStatus.PAUSED
        logger.info("Workflow scheduler paused")
    
    async def resume(self):
        """Resume all scheduled tasks."""
        if self.scheduler:
            self.scheduler.resume()
        self.workflow_status = WorkflowStatus.RUNNING
        logger.info("Workflow scheduler resumed")
    
    async def run_once(self, task_id: str) -> Any:
        """
        Run a specific task immediately (one-time execution).
        
        Args:
            task_id: ID of the task to run
            
        Returns:
            Task result
        """
        task_map = {
            self.TASK_DAILY_SCAN: self._run_daily_scan,
            self.TASK_PNL_UPDATE: self._run_pnl_update,
            self.TASK_DAILY_REPORT: self._run_daily_report,
            self.TASK_HEALTH_CHECK: self._run_health_check,
            self.TASK_DEEP_ANALYZE: self._run_deep_analyze,
        }
        
        if task_id not in task_map:
            raise ValueError(f"Unknown task: {task_id}")
        
        logger.info(f"Running task {task_id} on-demand...")
        return await task_map[task_id]()
    
    # ==================== Utility Methods ====================
    
    def _log_error(self, context: str, error: Exception):
        """Log an error to state."""
        self.state.errors_today.append({
            "timestamp": datetime.now().isoformat(),
            "context": context,
            "error": str(error)
        })
        self._save_state()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            "workflow_id": self.state.workflow_id,
            "status": self.workflow_status.value,
            "running": self._running,
            "uptime": self._get_uptime(),
            "cycle_count": self.cycle_count,
            "daily_stats": {
                "trades": self.state.daily_trade_count,
                "pnl": self.state.daily_pnl,
                "winners_cached": self.state.winners_cached,
                "analysis_complete": self.state.analysis_completed
            },
            "tasks": {
                task_id: {
                    "name": task.name,
                    "status": task.status.value,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "run_count": task.run_count
                }
                for task_id, task in self.tasks.items()
            },
            "config": {
                "scan_time": self.config.scan_time,
                "report_time": self.config.report_time,
                "auto_trade": self.config.auto_trade_enabled,
                "monitoring": self.config.monitoring_enabled
            }
        }
    
    def get_task_list(self) -> List[Dict]:
        """Get list of all scheduled tasks."""
        return [
            {
                "id": task.task_id,
                "name": task.name,
                "status": task.status.value,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "run_count": task.run_count
            }
            for task in self.tasks.values()
        ]


# ==================== Convenience Functions ====================

async def run_scheduler_forever(config: Optional[WorkflowConfig] = None):
    """
    Run the workflow scheduler indefinitely.
    
    This is the main entry point for running the scheduler as a service.
    
    Example:
        asyncio.run(run_scheduler_forever())
    """
    scheduler = WorkflowScheduler(config=config)
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(scheduler.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler
    
    try:
        await scheduler.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await scheduler.stop()
    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        await scheduler.stop()


def create_scheduler_cli():
    """
    Create CLI entry point for the workflow scheduler.
    
    Usage:
        python -m polymarket_tracker.automation.workflow_scheduler start
        python -m polymarket_tracker.automation.workflow_scheduler status
        python -m polymarket_tracker.automation.workflow_scheduler stop
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="PolyBot Workflow Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start       Start the workflow scheduler
  stop        Stop the scheduler gracefully
  status      Show current status
  run-once    Run workflow once immediately
  run-task    Run a specific task (scan, analyze, report)
        """
    )
    
    parser.add_argument(
        'command',
        choices=['start', 'stop', 'status', 'run-once', 'run-task'],
        help='Command to execute'
    )
    parser.add_argument(
        '--task',
        choices=['scan', 'analyze', 'report', 'pnl', 'health'],
        help='Task to run (for run-task command)'
    )
    parser.add_argument(
        '--auto-trade',
        action='store_true',
        help='Enable auto-trading (use with caution!)'
    )
    parser.add_argument(
        '--scan-time',
        default='09:00',
        help='Daily scan time (HH:MM)'
    )
    
    args = parser.parse_args()
    
    async def main():
        config = WorkflowConfig.from_env()
        
        if args.scan_time:
            config.scan_time = args.scan_time
        if args.auto_trade:
            config.auto_trade_enabled = True
        
        if args.command == 'start':
            await run_scheduler_forever(config)
            
        elif args.command == 'run-once':
            scheduler = WorkflowScheduler(config=config)
            results = await scheduler.run_full_daily_workflow()
            print(json.dumps(results, indent=2))
            
        elif args.command == 'run-task':
            if not args.task:
                print("Error: --task required")
                return
            
            scheduler = WorkflowScheduler(config=config)
            await scheduler.initialize()
            
            task_map = {
                'scan': scheduler.TASK_DAILY_SCAN,
                'analyze': scheduler.TASK_DEEP_ANALYZE,
                'report': scheduler.TASK_DAILY_REPORT,
                'pnl': scheduler.TASK_PNL_UPDATE,
                'health': scheduler.TASK_HEALTH_CHECK
            }
            
            result = await scheduler.run_once(task_map[args.task])
            print(f"Task completed: {result}")
            
        elif args.command == 'status':
            scheduler = WorkflowScheduler(config=config)
            status = scheduler.get_status()
            print(json.dumps(status, indent=2))
    
    asyncio.run(main())


if __name__ == "__main__":
    create_scheduler_cli()
