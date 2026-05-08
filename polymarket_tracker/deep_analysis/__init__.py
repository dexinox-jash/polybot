"""
Deep Analysis Module for Polymarket Copy Trading Bot

Provides comprehensive, institutional-grade analysis for copy trading decisions.

Modules:
- winner_intelligence: Deep winner profile analysis
- advanced_ev: Advanced EV calculations with Monte Carlo
- multi_factor_model: Multi-factor scoring system
- research_engine: Comprehensive research report generation
"""

from .winner_intelligence import WinnerIntelligence, DeepWinnerProfile
from .advanced_ev import AdvancedEVCalculator, ScenarioAnalysis, AdvancedEV
from .multi_factor_model import (
    MultiFactorModel, 
    MultiFactorScore, 
    FactorScore, 
    FactorCategory,
    FactorWeights
)
from .research_engine import ResearchEngine, ResearchReport

__all__ = [
    # Core classes
    'WinnerIntelligence',
    'DeepWinnerProfile',
    'AdvancedEVCalculator',
    'ScenarioAnalysis',
    'AdvancedEV',
    'MultiFactorModel',
    'MultiFactorScore',
    'FactorScore',
    'FactorCategory',
    'FactorWeights',
    'ResearchEngine',
    'ResearchReport',
]
