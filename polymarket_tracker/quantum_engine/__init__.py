"""
Quantum-Inspired Probabilistic Market State Engine

Uses superposition, interference, and collapse concepts to model
market states as probability distributions rather than discrete values.

Key Concepts:
- Market State Superposition: All possible states exist simultaneously
- Interference: Signals can constructively/destructively interfere
- Collapse: Observation (execution) forces state resolution
- Entanglement: Correlated markets affect each other instantaneously
"""

from .state_vector import MarketStateVector, StateAmplitude
from .wave_function import MarketWaveFunction, ProbabilityDensity
from .interference_engine import InterferenceEngine, SignalInterference
from .collapse_predictor import CollapsePredictor, StateCollapse

__all__ = [
    'MarketStateVector',
    'StateAmplitude',
    'MarketWaveFunction',
    'ProbabilityDensity',
    'InterferenceEngine',
    'SignalInterference',
    'CollapsePredictor',
    'StateCollapse',
]
