"""
PolyBot Automation Module

Comprehensive workflow automation system for PolyBot trading operations.

This module provides:
- Scheduled daily workflows (scan, analyze, report)
- Continuous market monitoring
- Smart decision making with risk awareness
- Health monitoring and alerting
- Graceful error recovery and state persistence

Main Components:
    WorkflowScheduler: Central scheduler for all automation tasks
    WorkflowConfig: Configuration dataclass for workflow settings
    WorkflowState: Persistent state management

Example Usage:
    # Run as a service
    >>> asyncio.run(run_scheduler_forever())
    
    # Or use programmatically
    >>> scheduler = WorkflowScheduler()
    >>> await scheduler.start()
    >>> # ... runs in background ...
    >>> await scheduler.stop()
    
    # Run workflow once
    >>> scheduler = WorkflowScheduler()
    >>> results = await scheduler.run_full_daily_workflow()
    
    # Custom configuration
    >>> config = WorkflowConfig(
    ...     scan_time="10:00",
    ...     auto_trade_enabled=False,
    ...     monitoring_enabled=True
    ... )
    >>> scheduler = WorkflowScheduler(config=config)

Environment Variables:
    WORKFLOW_SCAN_TIME: Daily scan time (default: "09:00")
    WORKFLOW_REPORT_TIME: Daily report time (default: "18:00")
    WORKFLOW_AUTO_TRADE: Enable auto-trading (default: "false")
    WORKFLOW_MONITORING: Enable continuous monitoring (default: "true")
    WORKFLOW_PNL_INTERVAL: P&L update interval in minutes (default: "15")
    WORKFLOW_TIMEZONE: Timezone for scheduling (default: "America/New_York")

Command Line Usage:
    # Start scheduler service
    $ python -m polymarket_tracker.automation.workflow_scheduler start
    
    # Run workflow once
    $ python -m polymarket_tracker.automation.workflow_scheduler run-once
    
    # Run specific task
    $ python -m polymarket_tracker.automation.workflow_scheduler run-task --task scan
    
    # Check status
    $ python -m polymarket_tracker.automation.workflow_scheduler status

Scheduled Tasks:
    - Daily Scan: Winner discovery at configured time
    - Deep Analysis: Opportunity analysis after scan
    - P&L Updates: Regular portfolio updates
    - Daily Report: Summary report at end of day
    - Health Checks: System health monitoring
    - Position Monitor: Stop/take-profit monitoring

Workflow:
    09:00 - Daily scan for winners
    09:05 - Deep analysis
    09:10 - If high EV found → notification (manual execution)
    Throughout day - Continuous monitoring
    18:00 - Daily report
"""

from .workflow_scheduler import (
    WorkflowScheduler,
    WorkflowConfig,
    WorkflowState,
    WorkflowStatus,
    TaskStatus,
    ScheduledTask,
    run_scheduler_forever,
    create_scheduler_cli,
)

__all__ = [
    # Main classes
    "WorkflowScheduler",
    "WorkflowConfig", 
    "WorkflowState",
    
    # Enums
    "WorkflowStatus",
    "TaskStatus",
    
    # Data classes
    "ScheduledTask",
    
    # Functions
    "run_scheduler_forever",
    "create_scheduler_cli",
]

__version__ = "1.0.0"
