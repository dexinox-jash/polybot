"""
Analytics module for comprehensive performance tracking and reporting.

Provides:
- Portfolio analytics and equity tracking
- Trade performance analysis
- Whale performance rankings
- Risk metrics (VaR, CVaR, etc.)
- Automated reporting (daily/weekly/monthly)
- Chart data generation for visualization
"""

from .performance_dashboard import (
    PerformanceDashboard,
    DailyReport,
    WeeklyReport,
    MonthlyReport,
    TradeStats,
    RiskMetrics,
    WhaleRanking,
    PortfolioSummary,
    DrawdownAnalysis,
    MarketPerformance,
    ChartData,
)

__all__ = [
    "PerformanceDashboard",
    "DailyReport",
    "WeeklyReport",
    "MonthlyReport",
    "TradeStats",
    "RiskMetrics",
    "WhaleRanking",
    "PortfolioSummary",
    "DrawdownAnalysis",
    "MarketPerformance",
    "ChartData",
]
