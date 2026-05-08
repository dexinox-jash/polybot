"""
Machine Learning Ensemble Layer

Multi-model ensemble for prediction with:
- Gradient Boosting (XGBoost/LightGBM)
- Neural Networks (LSTM/Transformer)
- Random Forest
- Online Learning (adaptive to new data)
- Meta-learner (stacking)

All models vote with weighted confidence.
"""

from .base_models import LSTMModel, XGBoostModel, RandomForestModel
from .transformer_model import TimeSeriesTransformer
from .ensemble_voter import EnsembleVoter, ModelPrediction
from .online_learner import OnlineLearner, AdaptiveWeights
from .feature_engineering import FeatureEngineer, MarketFeatures

__all__ = [
    'LSTMModel',
    'XGBoostModel',
    'RandomForestModel',
    'TimeSeriesTransformer',
    'EnsembleVoter',
    'ModelPrediction',
    'OnlineLearner',
    'AdaptiveWeights',
    'FeatureEngineer',
    'MarketFeatures',
]
