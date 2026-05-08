"""
Autonomous AI Decision Layer

Uses LLM (GPT-4/Claude) for:
- Market interpretation
- Strategy reasoning
- Risk assessment
- Explainability
- Self-reflection

Combines quantitative signals with qualitative reasoning.
"""

from .llm_reasoner import LLMReasoner, MarketAnalysis
from .strategy_planner import StrategyPlanner, ActionPlan
from .risk_assessor import RiskAssessor, RiskReport
from .explainability_engine import ExplainabilityEngine, DecisionExplanation

__all__ = [
    'LLMReasoner',
    'MarketAnalysis',
    'StrategyPlanner',
    'ActionPlan',
    'RiskAssessor',
    'RiskReport',
    'ExplainabilityEngine',
    'DecisionExplanation',
]
