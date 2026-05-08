"""
Market State Vector - Quantum-Inspired Representation

Represents the market as a superposition of basis states:
|Ψ⟩ = α|Bullish⟩ + β|Bearish⟩ + γ|Ranging⟩ + δ|Volatile⟩

Where |α|² + |β|² + |γ|² + |δ|² = 1 (probability conservation)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json


class MarketBasisState(Enum):
    """Fundamental market states (basis vectors)."""
    BULLISH_TREND = "bullish_trend"
    BEARISH_TREND = "bearish_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT_PENDING = "breakout_pending"
    REVERSAL_IMMINENT = "reversal_imminent"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"


@dataclass
class StateAmplitude:
    """
    Complex amplitude for a basis state.
    
    amplitude = magnitude * e^(i * phase)
    probability = |amplitude|² = magnitude²
    """
    state: MarketBasisState
    magnitude: float  # |α| (0 to 1)
    phase: float      # θ in radians (0 to 2π)
    confidence: float # Measurement confidence (0 to 1)
    timestamp: datetime
    
    @property
    def probability(self) -> float:
        """|α|² - probability of measuring this state."""
        return self.magnitude ** 2
    
    @property
    def complex_value(self) -> complex:
        """α = |α| * e^(iθ)."""
        return self.magnitude * np.exp(1j * self.phase)
    
    def __repr__(self):
        return f"StateAmplitude({self.state.value}, |α|={self.magnitude:.3f}, θ={self.phase:.2f}rad, P={self.probability:.3f})"


class MarketStateVector:
    """
    Quantum-inspired market state representation.
    
    The market exists in superposition until "measured" (trade executed).
    |Ψ⟩ = Σ αᵢ|φᵢ⟩ where |φᵢ⟩ are basis states
    """
    
    def __init__(self, market_id: str):
        self.market_id = market_id
        self.amplitudes: Dict[MarketBasisState, StateAmplitude] = {}
        self.last_update = datetime.now()
        self.coherence_time: float = 300.0  # 5 minutes (decoherence)
        self.entangled_markets: List[str] = []
        self.history: List[Dict] = []
        
    def initialize_uniform(self):
        """Initialize with equal superposition (maximal uncertainty)."""
        n_states = len(MarketBasisState)
        magnitude = 1.0 / np.sqrt(n_states)
        
        for state in MarketBasisState:
            self.amplitudes[state] = StateAmplitude(
                state=state,
                magnitude=magnitude,
                phase=random.uniform(0, 2 * np.pi),
                confidence=0.5,
                timestamp=datetime.now()
            )
    
    def update_from_observables(self, observables: Dict[str, float]):
        """
        Update state vector based on market observables.
        
        Observables: price, volume, volatility, order_flow, etc.
        Uses Hamiltonian-inspired evolution.
        """
        # Calculate energy for each state (lower = more likely)
        energies = self._calculate_energies(observables)
        
        # Update amplitudes based on energy (Schrödinger-like evolution)
        for state in MarketBasisState:
            energy = energies.get(state, 1.0)
            
            # Higher probability for lower energy states
            target_prob = np.exp(-energy) / sum(np.exp(-e) for e in energies.values())
            
            # Smooth transition (quantum tunneling effect)
            current_amp = self.amplitudes.get(state)
            if current_amp:
                # Gradually shift amplitude
                current_prob = current_amp.probability
                new_prob = 0.7 * current_prob + 0.3 * target_prob
                
                # Update magnitude (phase evolves continuously)
                new_magnitude = np.sqrt(new_prob)
                new_phase = (current_amp.phase + 0.1 * energy) % (2 * np.pi)
                
                self.amplitudes[state] = StateAmplitude(
                    state=state,
                    magnitude=new_magnitude,
                    phase=new_phase,
                    confidence=min(1.0, current_amp.confidence + 0.05),
                    timestamp=datetime.now()
                )
        
        # Renormalize (conservation of probability)
        self._renormalize()
        self.last_update = datetime.now()
        
        # Store history
        self._record_state()
    
    def _calculate_energies(self, observables: Dict[str, float]) -> Dict[MarketBasisState, float]:
        """
        Calculate 'energy' for each state based on observables.
        Lower energy = more probable state.
        """
        price = observables.get('price', 0.5)
        momentum = observables.get('momentum', 0)
        volatility = observables.get('volatility', 0.1)
        volume = observables.get('volume', 1.0)
        whale_imbalance = observables.get('whale_imbalance', 0)
        
        energies = {}
        
        # BULLISH: Low price + positive momentum
        energies[MarketBasisState.BULLISH_TREND] = (
            (0.6 - price) * 2 +  # Lower price = more upside
            max(0, -momentum) * 3 +  # Want positive momentum
            volatility  # Some volatility is good
        )
        
        # BEARISH: High price + negative momentum
        energies[MarketBasisState.BEARISH_TREND] = (
            (price - 0.4) * 2 +
            max(0, momentum) * 3 +
            volatility
        )
        
        # RANGING: Low volatility, no clear momentum
        energies[MarketBasisState.RANGING] = (
            abs(momentum) * 2 +  # Penalize strong momentum
            (volatility - 0.05) * 5  # Want low volatility
        )
        
        # HIGH_VOLATILITY: High volatility, indecision
        energies[MarketBasisState.HIGH_VOLATILITY] = (
            (0.2 - volatility) * 5 +  # Need high volatility
            abs(momentum)  # But some direction
        )
        
        # LOW_VOLATILITY: Very low volatility, calm
        energies[MarketBasisState.LOW_VOLATILITY] = (
            (volatility - 0.02) * 10  # Need very low vol
        )
        
        # BREAKOUT_PENDING: Compression before expansion
        energies[MarketBasisState.BREAKOUT_PENDING] = (
            (volatility - 0.03) * 3 +  # Low but not too low
            abs(momentum) * 2  # Building momentum
        )
        
        # REVERSAL_IMMINENT: Extreme readings
        energies[MarketBasisState.REVERSAL_IMMINENT] = (
            (0.7 - abs(price - 0.5) * 2) +  # Extreme price
            abs(momentum) * 0.5  # Strong momentum (exhaustion)
        )
        
        # ACCUMULATION: Whale buying, steady price
        energies[MarketBasisState.ACCUMULATION] = (
            max(0, -whale_imbalance) * 2 +  # Want positive whale flow
            abs(momentum) * 2  # But stealth (low momentum)
        )
        
        # DISTRIBUTION: Whale selling
        energies[MarketBasisState.DISTRIBUTION] = (
            max(0, whale_imbalance) * 2 +  # Want negative whale flow
            abs(momentum) * 2
        )
        
        return energies
    
    def _renormalize(self):
        """Ensure Σ|αᵢ|² = 1 (probability conservation)."""
        total_prob = sum(amp.probability for amp in self.amplitudes.values())
        
        if total_prob > 0 and abs(total_prob - 1.0) > 0.001:
            scale = 1.0 / np.sqrt(total_prob)
            for state, amp in self.amplitudes.items():
                self.amplitudes[state] = StateAmplitude(
                    state=state,
                    magnitude=amp.magnitude * scale,
                    phase=amp.phase,
                    confidence=amp.confidence,
                    timestamp=amp.timestamp
                )
    
    def measure(self, basis_state: MarketBasisState) -> Tuple[bool, float]:
        """
        'Measure' the state - collapses superposition to one outcome.
        
        Returns: (measured, probability)
        """
        if basis_state not in self.amplitudes:
            return False, 0.0
        
        prob = self.amplitudes[basis_state].probability
        
        # Simulate measurement (collapse)
        measured = random.random() < prob
        
        # After measurement, state collapses (in reality, this would reset)
        # For trading, we don't actually collapse - we use probability
        
        return measured, prob
    
    def get_dominant_state(self) -> Tuple[MarketBasisState, float]:
        """Get the state with highest probability."""
        if not self.amplitudes:
            return MarketBasisState.RANGING, 0.0
        
        dominant = max(self.amplitudes.items(), key=lambda x: x[1].probability)
        return dominant[0], dominant[1].probability
    
    def get_state_distribution(self) -> Dict[MarketBasisState, float]:
        """Get probability distribution over all states."""
        return {state: amp.probability for state, amp in self.amplitudes.items()}
    
    def calculate_expectation_value(self, operator: Dict[MarketBasisState, float]) -> float:
        """
        Calculate expectation value: ⟨Ψ|O|Ψ⟩ = Σ |αᵢ|² Oᵢ
        
        Operator is a dictionary mapping states to values.
        """
        expectation = 0.0
        for state, amp in self.amplitudes.items():
            value = operator.get(state, 0)
            expectation += amp.probability * value
        return expectation
    
    def entangle_with(self, other_market_id: str, correlation: float):
        """
        Entangle this market with another.
        Correlated markets affect each other's states.
        """
        if other_market_id not in self.entangled_markets:
            self.entangled_markets.append(other_market_id)
    
    def apply_entanglement_effect(self, other_state_vector: 'MarketStateVector', correlation: float):
        """
        Apply influence from entangled market.
        
        If Market A is bullish and A↔B are correlated, increase B's bullish amplitude.
        """
        if not self.entangled_markets or other_state_vector.market_id not in self.entangled_markets:
            return
        
        # Get dominant state of other market
        other_dominant, other_prob = other_state_vector.get_dominant_state()
        
        # Boost corresponding state in this market
        if other_dominant in self.amplitudes:
            current = self.amplitudes[other_dominant]
            # Interference: add correlated amplitude
            boost = correlation * other_prob * 0.1
            new_magnitude = min(0.99, current.magnitude + boost)
            
            self.amplitudes[other_dominant] = StateAmplitude(
                state=other_dominant,
                magnitude=new_magnitude,
                phase=current.phase,
                confidence=min(1.0, current.confidence + 0.1),
                timestamp=datetime.now()
            )
            
            self._renormalize()
    
    def _record_state(self):
        """Record state for historical analysis."""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'amplitudes': {
                state.value: {
                    'magnitude': amp.magnitude,
                    'phase': amp.phase,
                    'probability': amp.probability
                }
                for state, amp in self.amplitudes.items()
            },
            'dominant_state': self.get_dominant_state()[0].value,
            'dominant_probability': self.get_dominant_state()[1]
        })
        
        # Keep only last 1000 states
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
    
    def get_entropy(self) -> float:
        """
        Calculate von Neumann entropy: S = -Σ pᵢ log(pᵢ)
        
        Higher entropy = more uncertainty (mixed state)
        Lower entropy = more certainty (pure state)
        """
        entropy = 0.0
        for amp in self.amplitudes.values():
            p = amp.probability
            if p > 0:
                entropy -= p * np.log2(p)
        return entropy
    
    def is_pure_state(self, threshold: float = 0.7) -> bool:
        """Check if state is nearly pure (one state dominates)."""
        _, prob = self.get_dominant_state()
        return prob >= threshold
    
    def to_json(self) -> str:
        """Serialize state vector."""
        data = {
            'market_id': self.market_id,
            'last_update': self.last_update.isoformat(),
            'amplitudes': [
                {
                    'state': amp.state.value,
                    'magnitude': amp.magnitude,
                    'phase': amp.phase,
                    'probability': amp.probability,
                    'confidence': amp.confidence
                }
                for amp in self.amplitudes.values()
            ],
            'dominant': {
                'state': self.get_dominant_state()[0].value,
                'probability': self.get_dominant_state()[1]
            },
            'entropy': self.get_entropy()
        }
        return json.dumps(data, indent=2)


import random
