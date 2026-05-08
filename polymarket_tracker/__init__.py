"""
Polymarket Deep Analysis Copy-Trading Bot

Maximum research depth. Comprehensive calculations. No compromises.
Smart API usage: Fetch once, analyze deeply, cache everything.

Target: 1 exceptional bet per day with institutional-grade analysis.
"""

from .deep_analysis.winner_intelligence import WinnerIntelligence, DeepWinnerProfile
from .deep_analysis.multi_factor_model import MultiFactorModel, FactorWeights, MultiFactorScore, FactorScore, FactorCategory
from .deep_analysis.advanced_ev import AdvancedEVCalculator, ScenarioAnalysis, AdvancedEV
from .deep_analysis.research_engine import ResearchEngine, ResearchReport
from .winners.winner_discovery import WinnerDiscovery, TraderPerformance

__all__ = [
    # Deep Analysis
    "WinnerIntelligence",
    "DeepWinnerProfile", 
    "MultiFactorModel",
    "FactorWeights",
    "MultiFactorScore",
    "FactorScore",
    "FactorCategory",
    "AdvancedEVCalculator",
    "ScenarioAnalysis",
    "AdvancedEV",
    "ResearchEngine",
    "ResearchReport",
    # Winners
    "WinnerDiscovery",
    "TraderPerformance",
]
