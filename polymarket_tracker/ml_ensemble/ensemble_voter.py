"""
Ensemble Voter - Meta-Learning Layer

Combines predictions from multiple models using:
1. Weighted voting based on recent performance
2. Bayesian model averaging
3. Stacking with meta-learner
4. Confidence calibration
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import json


@dataclass
class ModelPrediction:
    """Individual model prediction."""
    model_name: str
    prediction: float  # Probability of upward move (0-1)
    confidence: float  # Model's confidence (0-1)
    direction: str     # 'LONG', 'SHORT', 'NEUTRAL'
    features_used: List[str]
    timestamp: datetime
    latency_ms: int
    
    # Model metadata
    model_version: str = "1.0"
    training_date: Optional[datetime] = None
    
    @property
    def weighted_prediction(self) -> float:
        """Prediction weighted by confidence."""
        return self.prediction * self.confidence


@dataclass
class EnsembleVote:
    """Final ensemble decision."""
    prediction: float
    direction: str
    confidence: float
    model_agreement: float  # How much models agree (0-1)
    dissension_index: float  # Measure of disagreement
    uncertainty: float  # Epistemic uncertainty
    
    # Component details
    individual_predictions: List[ModelPrediction]
    model_weights: Dict[str, float]
    reasoning: List[str]
    
    def __post_init__(self):
        if self.reasoning is None:
            self.reasoning = []


class EnsembleVoter:
    """
    Meta-learner that combines multiple model predictions.
    
    Uses dynamic weighting based on recent performance.
    Better performing models get higher weights.
    """
    
    def __init__(self, models: List[str] = None):
        """
        Initialize ensemble voter.
        
        Args:
            models: List of model names in the ensemble
        """
        self.models = models or ['lstm', 'xgboost', 'transformer', 'random_forest']
        
        # Performance tracking
        self.model_performance: Dict[str, deque] = {
            model: deque(maxlen=100) for model in self.models
        }
        
        # Dynamic weights (start equal)
        self.weights: Dict[str, float] = {
            model: 1.0 / len(self.models) for model in self.models
        }
        
        # Calibration data
        self.prediction_history: deque = deque(maxlen=1000)
        
        # Meta-learner ( learns optimal combination )
        self.meta_weights: Dict[str, float] = {}
        
    def vote(self, predictions: List[ModelPrediction]) -> EnsembleVote:
        """
        Combine predictions into ensemble vote.
        
        Args:
            predictions: List of ModelPrediction objects
            
        Returns:
            EnsembleVote with final decision
        """
        if not predictions:
            return EnsembleVote(
                prediction=0.5,
                direction='NEUTRAL',
                confidence=0.0,
                model_agreement=0.0,
                dissension_index=1.0,
                uncertainty=1.0,
                individual_predictions=[],
                model_weights={},
                reasoning=['No predictions provided']
            )
        
        # Filter to known models
        valid_predictions = [
            p for p in predictions 
            if p.model_name in self.weights
        ]
        
        if not valid_predictions:
            return EnsembleVote(
                prediction=0.5,
                direction='NEUTRAL',
                confidence=0.0,
                model_agreement=0.0,
                dissension_index=1.0,
                uncertainty=1.0,
                individual_predictions=predictions,
                model_weights=self.weights,
                reasoning=['No valid model predictions']
            )
        
        # Calculate weighted average
        weighted_sum = 0.0
        total_weight = 0.0
        
        for pred in valid_predictions:
            weight = self.weights.get(pred.model_name, 0.25)
            weighted_sum += pred.prediction * weight * pred.confidence
            total_weight += weight * pred.confidence
        
        if total_weight > 0:
            ensemble_prediction = weighted_sum / total_weight
        else:
            ensemble_prediction = 0.5
        
        # Calculate direction
        if ensemble_prediction > 0.6:
            direction = 'LONG'
        elif ensemble_prediction < 0.4:
            direction = 'SHORT'
        else:
            direction = 'NEUTRAL'
        
        # Calculate model agreement
        long_votes = sum(1 for p in valid_predictions if p.prediction > 0.6)
        short_votes = sum(1 for p in valid_predictions if p.prediction < 0.4)
        neutral_votes = len(valid_predictions) - long_votes - short_votes
        
        max_agreement = max(long_votes, short_votes, neutral_votes)
        agreement = max_agreement / len(valid_predictions)
        
        # Calculate dissension (variance of predictions)
        predictions_array = np.array([p.prediction for p in valid_predictions])
        dissension = np.var(predictions_array) * 4  # Scale to 0-1
        
        # Calculate uncertainty
        # High when models disagree or individual confidences are low
        avg_confidence = np.mean([p.confidence for p in valid_predictions])
        uncertainty = (1 - avg_confidence) * 0.5 + dissension * 0.5
        
        # Final confidence
        confidence = avg_confidence * agreement * (1 - uncertainty)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            valid_predictions, ensemble_prediction, direction, agreement
        )
        
        vote = EnsembleVote(
            prediction=ensemble_prediction,
            direction=direction,
            confidence=confidence,
            model_agreement=agreement,
            dissension_index=dissension,
            uncertainty=uncertainty,
            individual_predictions=valid_predictions,
            model_weights=self.weights.copy(),
            reasoning=reasoning
        )
        
        # Store for learning
        self.prediction_history.append({
            'timestamp': datetime.now().isoformat(),
            'predictions': [p.prediction for p in valid_predictions],
            'ensemble': ensemble_prediction,
            'weights': self.weights.copy()
        })
        
        return vote
    
    def _generate_reasoning(
        self,
        predictions: List[ModelPrediction],
        ensemble_pred: float,
        direction: str,
        agreement: float
    ) -> List[str]:
        """Generate human-readable reasoning."""
        reasoning = []
        
        # Direction consensus
        long_models = [p.model_name for p in predictions if p.prediction > 0.6]
        short_models = [p.model_name for p in predictions if p.prediction < 0.4]
        
        if direction == 'LONG':
            reasoning.append(f"{len(long_models)} models predict UP: {', '.join(long_models)}")
        elif direction == 'SHORT':
            reasoning.append(f"{len(short_models)} models predict DOWN: {', '.join(short_models)}")
        else:
            reasoning.append(f"Mixed signals: {len(long_models)} UP, {len(short_models)} DOWN")
        
        # Agreement level
        if agreement > 0.8:
            reasoning.append(f"Strong consensus ({agreement:.0%} agreement)")
        elif agreement > 0.5:
            reasoning.append(f"Moderate consensus ({agreement:.0%} agreement)")
        else:
            reasoning.append(f"Low consensus ({agreement:.0%} agreement) - exercise caution")
        
        # Top contributing model
        best_model = max(predictions, key=lambda p: p.confidence * self.weights.get(p.model_name, 0.25))
        reasoning.append(f"Highest weight: {best_model.model_name} ({best_model.confidence:.0%} conf)")
        
        # Strength of prediction
        strength = abs(ensemble_pred - 0.5) * 2
        if strength > 0.6:
            reasoning.append(f"Strong conviction ({strength:.0%})")
        elif strength > 0.3:
            reasoning.append(f"Moderate conviction ({strength:.0%})")
        else:
            reasoning.append(f"Weak conviction ({strength:.0%}) - consider sizing down")
        
        return reasoning
    
    def update_weights(self, results: Dict[str, float]):
        """
        Update model weights based on recent performance.
        
        Args:
            results: Dict of {model_name: accuracy_or_return}
        """
        # Store performance
        for model, result in results.items():
            if model in self.model_performance:
                self.model_performance[model].append(result)
        
        # Calculate new weights based on recent performance
        new_weights = {}
        
        for model in self.models:
            history = list(self.model_performance[model])
            if len(history) < 5:
                # Not enough data, keep current weight
                new_weights[model] = self.weights[model]
            else:
                # Weight by recent performance
                # Use exponential decay (more recent = more important)
                n = len(history)
                weights_time = np.exp(np.linspace(-1, 0, n))
                weighted_performance = np.average(history, weights=weights_time)
                
                new_weights[model] = max(0.1, weighted_performance)
        
        # Normalize to sum to 1
        total = sum(new_weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in new_weights.items()}
    
    def calibrate_confidence(self, prediction: float, actual: bool) -> float:
        """
        Calibrate confidence scores based on historical accuracy.
        
        Uses isotonic regression concept (simplified).
        """
        # Find similar historical predictions
        similar = [
            p for p in self.prediction_history
            if abs(p['ensemble'] - prediction) < 0.1
        ]
        
        if len(similar) < 10:
            return prediction  # Not enough data
        
        # Calculate actual accuracy for this prediction range
        # (In real implementation, would store actual outcomes)
        return prediction  # Placeholder
    
    def get_model_rankings(self) -> List[Tuple[str, float]]:
        """Get models ranked by current weight."""
        return sorted(
            self.weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
    
    def get_performance_report(self) -> Dict:
        """Generate performance report for all models."""
        report = {}
        
        for model in self.models:
            history = list(self.model_performance[model])
            if history:
                report[model] = {
                    'recent_accuracy': np.mean(history[-20:]) if len(history) >= 20 else np.mean(history),
                    'total_predictions': len(history),
                    'current_weight': self.weights[model],
                    'trend': 'improving' if len(history) > 5 and np.mean(history[-5:]) > np.mean(history[-10:-5]) else 'stable'
                }
            else:
                report[model] = {
                    'recent_accuracy': None,
                    'total_predictions': 0,
                    'current_weight': self.weights[model],
                    'trend': 'new'
                }
        
        return report
