"""
LLM Reasoner - Natural Language Market Intelligence

Uses large language models to:
1. Interpret market conditions in natural language
2. Synthesize multiple signals into coherent narrative
3. Identify non-obvious patterns
4. Generate human-readable analysis
5. Provide reasoning for decisions

This is the "brain" that explains WHY the bot makes decisions.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class MarketAnalysis:
    """Structured market analysis from LLM."""
    summary: str
    key_observations: List[str]
    sentiment: str  # 'bullish', 'bearish', 'neutral', 'uncertain'
    confidence: float
    risks: List[str]
    opportunities: List[str]
    recommended_action: str
    reasoning: str
    uncertainty_factors: List[str]
    timestamp: datetime
    model_used: str = "gpt-4"


class LLMReasoner:
    """
    Uses LLM to reason about market conditions.
    
    This is NOT for prediction (models have no edge there),
    but for synthesis, explanation, and risk identification.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM reasoner.
        
        Args:
            api_key: OpenAI or Anthropic API key
        """
        self.api_key = api_key
        self.analysis_history: List[Dict] = []
        self.prompt_template = self._load_prompt_template()
        
    def _load_prompt_template(self) -> str:
        """Load the prompt template for market analysis."""
        return """
You are an expert quantitative trader analyzing Bitcoin prediction markets on Polymarket.
Your task is to synthesize quantitative signals into a coherent market analysis.

MARKET DATA:
{market_data}

QUANTITATIVE SIGNALS:
{signals}

TECHNICAL INDICATORS:
{indicators}

WHALE ACTIVITY:
{whale_data}

PORTFOLIO STATUS:
{portfolio}

INSTRUCTIONS:
1. Summarize the current market condition in 2-3 sentences
2. List 3-5 key observations from the data
3. Identify the primary sentiment (bullish/bearish/neutral) with confidence level
4. List potential risks that could invalidate the signal
5. List opportunities or confirming factors
6. Recommend an action (enter long/enter short/hold/wait)
7. Explain your reasoning step-by-step
8. Identify factors creating uncertainty

OUTPUT FORMAT (JSON):
{{
    "summary": "...",
    "key_observations": ["...", "..."],
    "sentiment": "bullish|bearish|neutral",
    "confidence": 0.0-1.0,
    "risks": ["...", "..."],
    "opportunities": ["...", "..."],
    "recommended_action": "enter long|enter short|hold|wait",
    "reasoning": "...",
    "uncertainty_factors": ["...", "..."]
}}

Be objective, evidence-based, and acknowledge uncertainty.
"""
    
    def analyze_market(
        self,
        market_data: Dict,
        signals: List[Dict],
        indicators: Dict,
        whale_data: Dict,
        portfolio: Dict
    ) -> MarketAnalysis:
        """
        Generate market analysis using LLM.
        
        In production, this would call OpenAI/Anthropic API.
        For now, we simulate with rule-based analysis.
        """
        # Format data for prompt
        formatted_data = self._format_data(
            market_data, signals, indicators, whale_data, portfolio
        )
        
        if self.api_key:
            # Real LLM call would happen here
            # response = openai.ChatCompletion.create(...)
            analysis = self._call_llm_api(formatted_data)
        else:
            # Simulate LLM reasoning
            analysis = self._simulate_analysis(
                market_data, signals, indicators, whale_data, portfolio
            )
        
        # Store history
        self.analysis_history.append({
            'timestamp': datetime.now().isoformat(),
            'market': market_data.get('market_id'),
            'analysis': analysis
        })
        
        return analysis
    
    def _format_data(
        self,
        market_data: Dict,
        signals: List[Dict],
        indicators: Dict,
        whale_data: Dict,
        portfolio: Dict
    ) -> str:
        """Format data for LLM prompt."""
        return self.prompt_template.format(
            market_data=json.dumps(market_data, indent=2),
            signals=json.dumps(signals, indent=2),
            indicators=json.dumps(indicators, indent=2),
            whale_data=json.dumps(whale_data, indent=2),
            portfolio=json.dumps(portfolio, indent=2)
        )
    
    def _call_llm_api(self, prompt: str) -> MarketAnalysis:
        """Call actual LLM API."""
        # This would integrate with OpenAI or Anthropic
        # For now, return placeholder
        return self._simulate_analysis({}, [], {}, {}, {})
    
    def _simulate_analysis(
        self,
        market_data: Dict,
        signals: List[Dict],
        indicators: Dict,
        whale_data: Dict,
        portfolio: Dict
    ) -> MarketAnalysis:
        """
        Simulate LLM analysis when API not available.
        
        Uses rules to generate plausible analysis.
        """
        # Extract key info
        has_long_signal = any(s.get('direction') == 'LONG' for s in signals)
        has_short_signal = any(s.get('direction') == 'SHORT' for s in signals)
        avg_confidence = sum(s.get('confidence', 0) for s in signals) / max(1, len(signals))
        
        whale_bullish = whale_data.get('imbalance', 0) > 0.3
        whale_bearish = whale_data.get('imbalance', 0) < -0.3
        
        momentum = indicators.get('momentum', 0)
        volatility = indicators.get('volatility', 0.1)
        
        # Determine sentiment
        if has_long_signal and whale_bullish and momentum > 0:
            sentiment = 'bullish'
            confidence = min(0.9, avg_confidence * 1.1)
            recommended = 'enter long'
        elif has_short_signal and whale_bearish and momentum < 0:
            sentiment = 'bearish'
            confidence = min(0.9, avg_confidence * 1.1)
            recommended = 'enter short'
        else:
            sentiment = 'neutral'
            confidence = avg_confidence * 0.7
            recommended = 'wait'
        
        # Generate observations
        observations = []
        if abs(momentum) > 0.02:
            observations.append(f"Strong {'upward' if momentum > 0 else 'downward'} momentum detected ({momentum:.2%})")
        if volatility > 0.15:
            observations.append("Elevated volatility suggests potential breakout")
        if whale_bullish:
            observations.append("Smart money showing accumulation behavior")
        if whale_bearish:
            observations.append("Smart money showing distribution behavior")
        if avg_confidence > 0.75:
            observations.append("Multiple signals showing high conviction alignment")
        
        # Generate risks
        risks = []
        if volatility > 0.2:
            risks.append("High volatility could trigger stop loss prematurely")
        if len(signals) < 2:
            risks.append("Limited signal confirmation - single point of failure")
        if portfolio.get('daily_pnl', 0) < -portfolio.get('bankroll', 10000) * 0.05:
            risks.append("Recent drawdown suggests adverse market regime")
        
        # Generate opportunities
        opportunities = []
        if avg_confidence > 0.7:
            opportunities.append("Strong signal alignment offers favorable risk/reward")
        if abs(whale_data.get('imbalance', 0)) > 0.5:
            opportunities.append("Significant smart money flow provides edge")
        
        # Generate reasoning
        reasoning_parts = [
            f"The primary signal direction is {sentiment.upper()} with {confidence:.0%} confidence.",
            f"Quantitative indicators show momentum of {momentum:.2%} and volatility of {volatility:.1%}.",
        ]
        
        if whale_bullish or whale_bearish:
            reasoning_parts.append(f"Whale activity indicates {sentiment} positioning.")
        
        if avg_confidence > 0.7:
            reasoning_parts.append("High model confidence supports taking the trade.")
        else:
            reasoning_parts.append("Moderate confidence suggests cautious sizing.")
        
        reasoning = " ".join(reasoning_parts)
        
        # Summary
        summary = f"Market showing {sentiment} signals with {confidence:.0%} confidence. "
        summary += f"Momentum is {momentum:.2%} with {volatility:.1%} volatility. "
        if whale_bullish or whale_bearish:
            summary += f"Whale flow {'supports' if (sentiment == 'bullish' and whale_bullish) or (sentiment == 'bearish' and whale_bearish) else 'contradicts'} the signal."
        
        return MarketAnalysis(
            summary=summary,
            key_observations=observations,
            sentiment=sentiment,
            confidence=confidence,
            risks=risks,
            opportunities=opportunities,
            recommended_action=recommended,
            reasoning=reasoning,
            uncertainty_factors=["Market regime could shift rapidly", "5-minute window limits reaction time"],
            timestamp=datetime.now()
        )
    
    def generate_trade_narrative(
        self,
        trade: Dict,
        market_context: Dict
    ) -> str:
        """Generate natural language description of a trade."""
        direction = trade.get('direction', 'unknown')
        size = trade.get('size', 0)
        confidence = trade.get('confidence', 0)
        pattern = trade.get('pattern', 'unknown')
        
        narrative = f"Opening {direction} position of ${size:.0f} based on {pattern} pattern. "
        narrative += f"Signal confidence is {confidence:.0%}. "
        
        if confidence > 0.8:
            narrative += "This is a high-conviction setup with strong alignment across models."
        elif confidence > 0.6:
            narrative += "Moderate conviction - standard position sizing appropriate."
        else:
            narrative += "Lower conviction - consider reduced exposure."
        
        return narrative
    
    def explain_decision(
        self,
        decision: str,
        context: Dict
    ) -> str:
        """Explain why a decision was made (for debugging/auditing)."""
        explanation = f"DECISION: {decision}\n\n"
        explanation += "CONTEXT:\n"
        
        for key, value in context.items():
            explanation += f"  {key}: {value}\n"
        
        explanation += "\nREASONING:\n"
        
        if decision == 'NO_TRADE':
            explanation += "  - Signal confidence below threshold\n"
            explanation += "  - Risk/reward insufficient\n"
            explanation += "  - Portfolio heat too high\n"
        elif decision == 'ENTER_LONG':
            explanation += "  - Bullish pattern detected\n"
            explanation += "  - Whale confluence supporting\n"
            explanation += "  - Risk parameters within limits\n"
        
        return explanation
    
    def get_historical_patterns(self) -> List[Dict]:
        """Identify recurring patterns in analysis history."""
        if len(self.analysis_history) < 10:
            return []
        
        # Count sentiment frequencies
        sentiments = {}
        for entry in self.analysis_history:
            sentiment = entry['analysis'].get('sentiment', 'unknown')
            sentiments[sentiment] = sentiments.get(sentiment, 0) + 1
        
        return [
            {
                'pattern': f"{sentiment} dominance",
                'frequency': count / len(self.analysis_history),
                'count': count
            }
            for sentiment, count in sentiments.items()
        ]
