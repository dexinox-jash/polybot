"""
Master Orchestrator - The Brain of the Masterpiece

Coordinates all components in a quantum-inspired probabilistic framework:
1. Data Ingestion (multiple sources)
2. Quantum State Representation (superposition)
3. ML Ensemble (multi-model prediction)
4. Signal Interference (constructive/destructive)
5. Autonomous AI (reasoning & explanation)
6. Risk Management (multi-dimensional)
7. Execution (smart order routing)
8. Learning (continuous improvement)

This is the central hub that makes everything work together.
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json
import logging

# Import all our components
from .quantum_engine import MarketStateVector, StateAmplitude, MarketBasisState
from .quantum_engine.interference_engine import InterferenceEngine
from .ml_ensemble import EnsembleVoter, ModelPrediction
from .autonomous_ai import LLMReasoner, MarketAnalysis
from .risk.position_manager import PositionManager, RiskParameters
from .data.btc_market_scanner import BTCMarketScanner
from .data.micro_whale_tracker import MicroWhaleTracker


logger = logging.getLogger(__name__)


@dataclass
class SystemState:
    """Complete system state snapshot."""
    timestamp: datetime
    market_states: Dict[str, MarketStateVector]
    active_signals: List[Dict]
    open_positions: Dict[str, Dict]
    portfolio_value: float
    daily_pnl: float
    risk_metrics: Dict
    ml_predictions: List[ModelPrediction]
    interference_matrix: Dict
    ai_analysis: Optional[MarketAnalysis]
    
    def to_json(self) -> str:
        """Serialize state."""
        return json.dumps({
            'timestamp': self.timestamp.isoformat(),
            'portfolio_value': self.portfolio_value,
            'daily_pnl': self.daily_pnl,
            'active_markets': len(self.market_states),
            'active_signals': len(self.active_signals),
            'open_positions': len(self.open_positions),
        }, indent=2)


@dataclass
class TradeDecision:
    """Final trade decision with full context."""
    decision: str  # 'ENTER_LONG', 'ENTER_SHORT', 'HOLD', 'EXIT'
    confidence: float
    position_size: float
    market_id: str
    
    # Component contributions
    quantum_state: Optional[MarketBasisState]
    quantum_probability: float
    ml_prediction: float
    ml_confidence: float
    interference_boost: float
    ai_sentiment: str
    ai_confidence: float
    risk_assessment: Dict
    
    # Execution details
    entry_price: float
    stop_loss: float
    take_profit: float
    time_exit: datetime
    
    # Explanation
    reasoning: List[str]
    component_breakdown: Dict[str, float]
    uncertainty_factors: List[str]


class MasterOrchestrator:
    """
    The masterpiece - a quantum-inspired, AI-powered trading intelligence system.
    
    Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    MASTER ORCHESTRATOR                       │
    ├─────────────────────────────────────────────────────────────┤
    │  Data Layer → Quantum States → ML Ensemble → Interference   │
    │       ↓              ↓              ↓            ↓          │
    │  Whale Track    State Vector   Predictions   Combined       │
    │       ↓              ↓              ↓            ↓          │
    │                    ↓─────────────────┘            ↓         │
    │                         ↓                          ↓        │
    │                    AI Reasoning → Risk Mgmt → Execution     │
    │                         ↓              ↓            ↓       │
    │                    Explanation    Position    Order Mgmt    │
    │                                                          │
    │  ←←←←←←←←←←←←←← Learning Loop ←←←←←←←←←←←←←←←←←←←←←     │
    └─────────────────────────────────────────────────────────────┘
    """
    
    def __init__(
        self,
        bankroll: float = 10000,
        api_keys: Dict[str, str] = None
    ):
        """
        Initialize the masterpiece.
        
        Args:
            bankroll: Starting capital
            api_keys: Dict of API keys for various services
        """
        self.bankroll = bankroll
        self.api_keys = api_keys or {}
        
        logger.info("🚀 Initializing Master Orchestrator...")
        
        # Initialize all components
        self._init_components()
        
        # System state
        self.state = SystemState(
            timestamp=datetime.now(),
            market_states={},
            active_signals=[],
            open_positions={},
            portfolio_value=bankroll,
            daily_pnl=0.0,
            risk_metrics={},
            ml_predictions=[],
            interference_matrix={},
            ai_analysis=None
        )
        
        # Performance tracking
        self.decision_history: deque = deque(maxlen=10000)
        self.performance_metrics = {
            'total_decisions': 0,
            'correct_decisions': 0,
            'total_pnl': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
        
        # Configuration
        self.config = {
            'quantum_weight': 0.25,
            'ml_weight': 0.35,
            'interference_weight': 0.20,
            'ai_weight': 0.20,
            'min_confidence': 0.65,
            'max_positions': 5,
            'update_interval_ms': 100
        }
        
        self.running = False
        logger.info("✅ Master Orchestrator initialized")
    
    def _init_components(self):
        """Initialize all system components."""
        # Data layer
        self.scanner = BTCMarketScanner()
        self.whale_tracker = MicroWhaleTracker()
        
        # Quantum layer
        self.state_vectors: Dict[str, MarketStateVector] = {}
        self.interference_engine = InterferenceEngine()
        
        # ML layer
        self.ensemble = EnsembleVoter([
            'lstm', 'xgboost', 'transformer', 'random_forest'
        ])
        
        # AI layer
        self.llm_reasoner = LLMReasoner(
            api_key=self.api_keys.get('openai') or self.api_keys.get('anthropic')
        )
        
        # Risk layer
        self.position_manager = PositionManager(
            initial_bankroll=self.bankroll,
            risk_params=RiskParameters()
        )
        
        logger.info("  ✓ All components initialized")
    
    async def run(self):
        """Main execution loop."""
        self.running = True
        logger.info("🎯 Starting main execution loop...")
        
        try:
            while self.running:
                cycle_start = datetime.now()
                
                # 1. Update market data
                await self._update_market_data()
                
                # 2. Update quantum states
                self._update_quantum_states()
                
                # 3. Get ML predictions
                self._generate_ml_predictions()
                
                # 4. Calculate signal interference
                self._calculate_interference()
                
                # 5. AI reasoning
                self._generate_ai_analysis()
                
                # 6. Make decisions
                decisions = self._make_trade_decisions()
                
                # 7. Execute decisions
                await self._execute_decisions(decisions)
                
                # 8. Update risk/positions
                self._update_risk_management()
                
                # 9. Learning loop
                self._learning_loop()
                
                # 10. Update system state
                self._update_system_state()
                
                # Calculate cycle time
                cycle_time = (datetime.now() - cycle_start).total_seconds() * 1000
                
                if self.state.active_signals:
                    logger.info(f"🔄 Cycle complete in {cycle_time:.1f}ms | "
                              f"Signals: {len(self.state.active_signals)} | "
                              f"P&L: ${self.state.daily_pnl:+.2f}")
                
                # Wait for next cycle
                await asyncio.sleep(self.config['update_interval_ms'] / 1000)
                
        except Exception as e:
            logger.error(f"❌ Orchestrator error: {e}", exc_info=True)
            self.running = False
            raise
    
    async def _update_market_data(self):
        """Fetch latest market data from all sources."""
        # This would integrate with real APIs
        # For now, simulate data updates
        pass
    
    def _update_quantum_states(self):
        """Update quantum state vectors for all markets."""
        for market_id in self.scanner.active_markets:
            if market_id not in self.state_vectors:
                # Initialize new state vector
                self.state_vectors[market_id] = MarketStateVector(market_id)
                self.state_vectors[market_id].initialize_uniform()
            
            # Get observables from market data
            market = self.scanner.active_markets.get(market_id)
            if market:
                observables = {
                    'price': market.yes_price,
                    'momentum': market.momentum,
                    'volatility': market.volatility,
                    'volume': market.volume_5min,
                    'whale_imbalance': market.whale_imbalance
                }
                
                # Update state vector
                self.state_vectors[market_id].update_from_observables(observables)
        
        # Update entanglement effects
        self._apply_entanglement()
    
    def _apply_entanglement(self):
        """Apply quantum entanglement between correlated markets."""
        # If BTC/USD is bullish, BTC volatility likely increases
        # These markets are "entangled"
        
        market_ids = list(self.state_vectors.keys())
        for i, id1 in enumerate(market_ids):
            for id2 in market_ids[i+1:]:
                # Check if entangled
                if self._are_markets_entangled(id1, id2):
                    correlation = 0.7  # Would calculate from historical data
                    self.state_vectors[id1].apply_entanglement_effect(
                        self.state_vectors[id2], correlation
                    )
    
    def _are_markets_entangled(self, id1: str, id2: str) -> bool:
        """Check if two markets are correlated/entangled."""
        # Simplified: check if both are BTC markets
        return 'BTC' in id1 and 'BTC' in id2
    
    def _generate_ml_predictions(self):
        """Generate predictions from ML ensemble."""
        predictions = []
        
        for market_id, state_vector in self.state_vectors.items():
            # Get dominant state as feature
            dominant_state, prob = state_vector.get_dominant_state()
            
            # Create model predictions (simulated for now)
            model_preds = [
                ModelPrediction(
                    model_name='lstm',
                    prediction=0.6 if dominant_state.value in ['bullish_trend', 'accumulation'] else 0.4,
                    confidence=0.75,
                    direction='LONG' if dominant_state.value in ['bullish_trend', 'accumulation'] else 'SHORT',
                    features_used=['price', 'volume', 'momentum'],
                    timestamp=datetime.now(),
                    latency_ms=15
                ),
                ModelPrediction(
                    model_name='xgboost',
                    prediction=prob,
                    confidence=0.70,
                    direction='LONG' if prob > 0.6 else 'SHORT' if prob < 0.4 else 'NEUTRAL',
                    features_used=['order_flow', 'whale_activity', 'volatility'],
                    timestamp=datetime.now(),
                    latency_ms=8
                ),
            ]
            
            predictions.extend(model_preds)
        
        self.state.ml_predictions = predictions
    
    def _calculate_interference(self):
        """Calculate interference between signals."""
        # Convert predictions to interference format
        signals = [
            {
                'id': p.model_name,
                'direction': p.direction,
                'confidence': p.confidence,
                'phase': 0.0  # Would calculate from timing
            }
            for p in self.state.ml_predictions
        ]
        
        if len(signals) >= 2:
            result = self.interference_engine.calculate_multi_signal_interference(signals)
            self.state.interference_matrix = result
    
    def _generate_ai_analysis(self):
        """Generate AI reasoning about current state."""
        # Get dominant market
        if not self.state_vectors:
            return
        
        dominant_market = max(
            self.state_vectors.items(),
            key=lambda x: x[1].get_dominant_state()[1]
        )
        
        market_id, state_vector = dominant_market
        dominant_state, prob = state_vector.get_dominant_state()
        
        # Create market data for AI
        market_data = {
            'market_id': market_id,
            'dominant_state': dominant_state.value,
            'probability': prob,
            'entropy': state_vector.get_entropy()
        }
        
        signals = [
            {
                'model': p.model_name,
                'direction': p.direction,
                'confidence': p.confidence,
                'prediction': p.prediction
            }
            for p in self.state.ml_predictions
        ]
        
        # Get AI analysis
        analysis = self.llm_reasoner.analyze_market(
            market_data=market_data,
            signals=signals,
            indicators={'momentum': 0.02, 'volatility': 0.15},
            whale_data={'imbalance': 0.3},
            portfolio=self.position_manager.get_portfolio_summary()
        )
        
        self.state.ai_analysis = analysis
    
    def _make_trade_decisions(self) -> List[TradeDecision]:
        """Make final trade decisions combining all components."""
        decisions = []
        
        for market_id, state_vector in self.state_vectors.items():
            # Get quantum state
            dominant_state, quantum_prob = state_vector.get_dominant_state()
            
            # Get ML ensemble vote
            ml_vote = self.ensemble.vote(self.state.ml_predictions)
            
            # Get interference boost
            interference = self.state.interference_matrix.get('confidence_adjustment', 0)
            
            # Get AI sentiment
            ai_sentiment = self.state.ai_analysis.sentiment if self.state.ai_analysis else 'neutral'
            ai_confidence = self.state.ai_analysis.confidence if self.state.ai_analysis else 0.5
            
            # Calculate composite score
            quantum_score = quantum_prob if dominant_state in [
                MarketBasisState.BULLISH_TREND,
                MarketBasisState.ACCUMULATION
            ] else 1 - quantum_prob
            
            composite = (
                quantum_score * self.config['quantum_weight'] +
                ml_vote.prediction * self.config['ml_weight'] +
                (1 + interference) * 0.5 * self.config['interference_weight'] +
                (ai_confidence if ai_sentiment == 'bullish' else 1 - ai_confidence) * self.config['ai_weight']
            )
            
            # Determine decision
            if composite > 0.7:
                decision = 'ENTER_LONG'
                confidence = composite
            elif composite < 0.3:
                decision = 'ENTER_SHORT'
                confidence = 1 - composite
            else:
                decision = 'HOLD'
                confidence = 0.5
            
            # Create decision object
            trade_decision = TradeDecision(
                decision=decision,
                confidence=confidence,
                position_size=self._calculate_position_size(confidence),
                market_id=market_id,
                quantum_state=dominant_state,
                quantum_probability=quantum_prob,
                ml_prediction=ml_vote.prediction,
                ml_confidence=ml_vote.confidence,
                interference_boost=interference,
                ai_sentiment=ai_sentiment,
                ai_confidence=ai_confidence,
                risk_assessment=self.position_manager.get_portfolio_summary(),
                entry_price=0.5,  # Would get from market
                stop_loss=0.48,
                take_profit=0.53,
                time_exit=datetime.now() + timedelta(minutes=4),
                reasoning=self._generate_reasoning(
                    decision, dominant_state, ml_vote, ai_sentiment, interference
                ),
                component_breakdown={
                    'quantum': quantum_score,
                    'ml': ml_vote.prediction,
                    'interference': interference,
                    'ai': ai_confidence
                },
                uncertainty_factors=[
                    f"Quantum entropy: {state_vector.get_entropy():.2f}",
                    f"ML dissension: {ml_vote.dissension_index:.2f}"
                ]
            )
            
            if decision != 'HOLD':
                decisions.append(trade_decision)
                self.state.active_signals.append({
                    'market_id': market_id,
                    'decision': decision,
                    'confidence': confidence,
                    'timestamp': datetime.now()
                })
        
        return decisions
    
    def _calculate_position_size(self, confidence: float) -> float:
        """Calculate position size based on confidence."""
        # Kelly-inspired sizing
        kelly = (confidence * 2 - 1)  # Scale to -1 to 1
        kelly = max(0, kelly * 0.5)  # Half-Kelly, no negative
        
        return self.bankroll * kelly * 0.02  # Max 2% risk
    
    def _generate_reasoning(
        self,
        decision: str,
        quantum_state: MarketBasisState,
        ml_vote,
        ai_sentiment: str,
        interference: float
    ) -> List[str]:
        """Generate human-readable reasoning."""
        reasoning = []
        
        reasoning.append(f"Quantum state: {quantum_state.value} ({self.config['quantum_weight']:.0%} weight)")
        reasoning.append(f"ML ensemble: {ml_vote.direction} with {ml_vote.confidence:.0%} confidence ({self.config['ml_weight']:.0%} weight)")
        reasoning.append(f"AI sentiment: {ai_sentiment} ({self.config['ai_weight']:.0%} weight)")
        
        if abs(interference) > 0.1:
            reasoning.append(f"Signal interference: {interference:+.1%} boost ({self.config['interference_weight']:.0%} weight)")
        
        return reasoning
    
    async def _execute_decisions(self, decisions: List[TradeDecision]):
        """Execute trade decisions."""
        for decision in decisions:
            if decision.confidence < self.config['min_confidence']:
                logger.info(f"⛈ Decision below confidence threshold: {decision.decision}")
                continue
            
            # Check risk limits
            can_trade, reason = self._check_risk_limits(decision)
            if not can_trade:
                logger.info(f"⛔ Risk limit: {reason}")
                continue
            
            # Log decision
            logger.info(f"🎯 {decision.decision} | {decision.market_id} | "
                      f"Confidence: {decision.confidence:.1%} | "
                      f"Size: ${decision.position_size:.0f}")
            
            # Record for learning
            self.decision_history.append({
                'timestamp': datetime.now().isoformat(),
                'decision': decision.decision,
                'market_id': decision.market_id,
                'confidence': decision.confidence,
                'components': decision.component_breakdown
            })
            
            self.performance_metrics['total_decisions'] += 1
    
    def _check_risk_limits(self, decision: TradeDecision) -> Tuple[bool, str]:
        """Check if decision passes risk limits."""
        portfolio = self.position_manager.get_portfolio_summary()
        
        # Max positions
        if portfolio['open_positions'] >= self.config['max_positions']:
            return False, "Max positions reached"
        
        # Daily loss limit
        if portfolio['daily_pnl'] < -self.bankroll * 0.1:
            return False, "Daily loss limit hit"
        
        return True, "OK"
    
    def _update_risk_management(self):
        """Update risk metrics and position tracking."""
        # Update portfolio state
        portfolio = self.position_manager.get_portfolio_summary()
        self.state.portfolio_value = portfolio['bankroll']
        self.state.daily_pnl = portfolio['daily_pnl']
        
        # Update risk metrics
        self.state.risk_metrics = {
            'exposure_pct': portfolio.get('exposure_pct', 0),
            'drawdown': portfolio.get('current_drawdown', 0),
            'var_95': self._calculate_var(),
            'sharpe': self.performance_metrics['sharpe_ratio']
        }
    
    def _calculate_var(self) -> float:
        """Calculate Value at Risk (95%)."""
        if len(self.decision_history) < 30:
            return 0.0
        
        # Simplified VaR calculation
        returns = [d.get('return', 0) for d in list(self.decision_history)[-30:]]
        if returns:
            return np.percentile(returns, 5)
        return 0.0
    
    def _learning_loop(self):
        """Continuous learning and adaptation."""
        # Update ML ensemble weights based on performance
        # This would use actual outcomes
        
        # Adapt component weights based on recent performance
        if len(self.decision_history) > 50:
            recent = list(self.decision_history)[-50:]
            # Would calculate which components performed best
            # and adjust weights accordingly
            pass
    
    def _update_system_state(self):
        """Update the master system state."""
        self.state = SystemState(
            timestamp=datetime.now(),
            market_states=self.state_vectors,
            active_signals=self.state.active_signals,
            open_positions=self.state.open_positions,
            portfolio_value=self.state.portfolio_value,
            daily_pnl=self.state.daily_pnl,
            risk_metrics=self.state.risk_metrics,
            ml_predictions=self.state.ml_predictions,
            interference_matrix=self.state.interference_matrix,
            ai_analysis=self.state.ai_analysis
        )
    
    def stop(self):
        """Stop the orchestrator."""
        self.running = False
        logger.info("🛑 Master Orchestrator stopped")
    
    def get_status_report(self) -> Dict:
        """Generate comprehensive status report."""
        return {
            'timestamp': datetime.now().isoformat(),
            'running': self.running,
            'bankroll': self.bankroll,
            'portfolio_value': self.state.portfolio_value,
            'daily_pnl': self.state.daily_pnl,
            'active_markets': len(self.state_vectors),
            'active_signals': len(self.state.active_signals),
            'total_decisions': self.performance_metrics['total_decisions'],
            'component_weights': self.config,
            'risk_metrics': self.state.risk_metrics,
            'recent_decisions': list(self.decision_history)[-10:]
        }
