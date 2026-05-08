"""
Paper Trading Module - Educational Trade Tracking

Simulates real-time trade execution with timing analysis:
- Tracks entry/exit deltas vs whales
- Measures execution quality
- Provides performance benchmarking
- Educational insights on timing
"""

from .paper_trading_engine import PaperTradingEngine, PaperPosition, TimingMetrics

__all__ = [
    'PaperTradingEngine',
    'PaperPosition',
    'TimingMetrics',
]
