"""
Intelligence Module - Behavioral Pattern Recognition

Analyzes whale trading patterns beyond statistics:
- Pattern detection (Sniper, Accumulator, Swinger, etc.)
- Behavioral profiling
- Timing analysis
- Predictive insights
"""

from .pattern_engine import PatternEngine, PatternType, PatternProfile
from .behavioral_profiler import BehavioralProfiler, WhalePersonality

__all__ = [
    'PatternEngine',
    'PatternType',
    'PatternProfile',
    'BehavioralProfiler',
    'WhalePersonality',
]
