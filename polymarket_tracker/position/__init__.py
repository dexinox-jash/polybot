"""
Position management module for PolyBot.

Provides dynamic position sizing based on:
- Kelly Criterion
- Whale correlation
- Signal confidence
- Market liquidity
- Drawdown protection
"""

from .dynamic_sizer import (
    DynamicPositionSizer,
    PositionSizingConfig,
    SizingResult,
    SizingDecision,
    calculate_position_size
)

__all__ = [
    'DynamicPositionSizer',
    'PositionSizingConfig',
    'SizingResult',
    'SizingDecision',
    'calculate_position_size',
]
