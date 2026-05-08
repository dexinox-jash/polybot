"""
Signal Interference Engine

Models how different signals can constructively or destructively interfere,
similar to wave interference in quantum mechanics.

Constructive interference: Multiple signals align → stronger conviction
Destructive interference: Signals contradict → uncertainty, no trade
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class InterferenceType(Enum):
    """Types of signal interference."""
    CONSTRUCTIVE = "constructive"      # Signals amplify each other
    DESTRUCTIVE = "destructive"        # Signals cancel each other
    PARTIAL = "partial"                # Partial alignment
    ORTHOGONAL = "orthogonal"          # Signals independent
    ENTANGLED = "entangled"            # Quantum-like correlation


@dataclass
class SignalInterference:
    """Result of interference calculation between signals."""
    signal_1: str
    signal_2: str
    interference_type: InterferenceType
    interference_strength: float  # 0 to 1
    phase_difference: float       # radians
    resultant_amplitude: float    # Combined strength
    confidence_adjustment: float  # How much to adjust confidence
    reasoning: List[str]


class InterferenceEngine:
    """
    Calculates how trading signals interfere with each other.
    
    In quantum terms: |Ψ_total⟩ = |Ψ_1⟩ + |Ψ_2⟩ + ... + |Ψ_n⟩
    
    The resultant probability is NOT just sum of probabilities,
    but involves complex amplitudes and phases.
    """
    
    def __init__(self):
        """Initialize interference engine."""
        self.interference_history: List[SignalInterference] = []
        self.coherence_matrix: Dict[Tuple[str, str], float] = {}
        
    def calculate_interference(
        self,
        signal_1_id: str,
        signal_2_id: str,
        direction_1: str,
        direction_2: str,
        confidence_1: float,
        confidence_2: float,
        phase_1: float = 0.0,
        phase_2: float = 0.0,
        correlation: float = 0.0
    ) -> SignalInterference:
        """
        Calculate interference between two signals.
        
        Args:
            signal_1_id, signal_2_id: Signal identifiers
            direction_1, direction_2: 'LONG' or 'SHORT'
            confidence_1, confidence_2: Signal strengths (0-1)
            phase_1, phase_2: Signal phases (radians)
            correlation: Historical correlation between these signals (-1 to 1)
            
        Returns:
            SignalInterference result
        """
        # Amplitudes from confidences
        amp_1 = np.sqrt(confidence_1)
        amp_2 = np.sqrt(confidence_2)
        
        # Phase difference
        phase_diff = phase_2 - phase_1
        
        # Direction factor: same direction = constructive, opposite = destructive
        if direction_1 == direction_2:
            direction_factor = 1.0
        else:
            direction_factor = -1.0
        
        # Calculate interference
        # |Ψ_total|² = |Ψ_1|² + |Ψ_2|² + 2|Ψ_1||Ψ_2|cos(Δφ)
        resultant_prob = (
            confidence_1 +
            confidence_2 +
            2 * amp_1 * amp_2 * np.cos(phase_diff) * direction_factor * (1 + correlation) / 2
        )
        
        resultant_amp = np.sqrt(max(0, resultant_prob))
        
        # Determine interference type
        if direction_factor > 0:
            if np.cos(phase_diff) > 0.5:
                interference_type = InterferenceType.CONSTRUCTIVE
                strength = min(1.0, resultant_amp / max(amp_1, amp_2))
                confidence_adj = strength * 0.2
                reasoning = [
                    f"Same direction ({direction_1})",
                    f"Phase aligned (Δφ={phase_diff:.2f}rad)",
                    f"Constructive interference: {strength:.1%} boost"
                ]
            elif np.cos(phase_diff) < -0.5:
                interference_type = InterferenceType.DESTRUCTIVE
                strength = max(0, 1 - resultant_amp / max(amp_1, amp_2))
                confidence_adj = -strength * 0.3
                reasoning = [
                    f"Same direction BUT phase opposition",
                    f"Destructive interference: {strength:.1%} reduction",
                    "Signals partially cancel"
                ]
            else:
                interference_type = InterferenceType.PARTIAL
                strength = 0.5
                confidence_adj = 0.0
                reasoning = ["Partial alignment"]
        else:
            # Opposite directions
            if np.cos(phase_diff) > 0.5:
                interference_type = InterferenceType.DESTRUCTIVE
                strength = min(1.0, 1 - resultant_amp / max(amp_1, amp_2))
                confidence_adj = -strength * 0.4
                reasoning = [
                    f"Opposite directions ({direction_1} vs {direction_2})",
                    f"Strong destructive interference: {strength:.1%}",
                    "High uncertainty - consider no trade"
                ]
            else:
                interference_type = InterferenceType.ORTHOGONAL
                strength = 0.0
                confidence_adj = 0.0
                reasoning = [
                    "Opposite directions with phase shift",
                    "Signals are approximately orthogonal",
                    "Independent information"
                ]
        
        interference = SignalInterference(
            signal_1=signal_1_id,
            signal_2=signal_2_id,
            interference_type=interference_type,
            interference_strength=strength,
            phase_difference=phase_diff,
            resultant_amplitude=resultant_amp,
            confidence_adjustment=confidence_adj,
            reasoning=reasoning
        )
        
        self.interference_history.append(interference)
        return interference
    
    def calculate_multi_signal_interference(
        self,
        signals: List[Dict]
    ) -> Dict:
        """
        Calculate interference for multiple signals.
        
        Returns combined amplitude and confidence adjustment.
        """
        if len(signals) < 2:
            return {
                'resultant_amplitude': signals[0]['confidence'] if signals else 0,
                'confidence_adjustment': 0,
                'interference_matrix': {}
            }
        
        # Calculate pairwise interference
        interference_matrix = {}
        total_adjustment = 0
        
        for i, sig1 in enumerate(signals):
            for j, sig2 in enumerate(signals[i+1:], i+1):
                key = (sig1['id'], sig2['id'])
                
                interference = self.calculate_interference(
                    signal_1_id=sig1['id'],
                    signal_2_id=sig2['id'],
                    direction_1=sig1['direction'],
                    direction_2=sig2['direction'],
                    confidence_1=sig1['confidence'],
                    confidence_2=sig2['confidence'],
                    phase_1=sig1.get('phase', 0),
                    phase_2=sig2.get('phase', 0),
                    correlation=sig1.get('correlation', 0)
                )
                
                interference_matrix[key] = interference
                total_adjustment += interference.confidence_adjustment
        
        # Calculate resultant amplitude (vector sum)
        # Start with first signal
        total_real = np.sqrt(signals[0]['confidence']) * np.cos(signals[0].get('phase', 0))
        total_imag = np.sqrt(signals[0]['confidence']) * np.sin(signals[0].get('phase', 0))
        
        for sig in signals[1:]:
            amp = np.sqrt(sig['confidence'])
            phase = sig.get('phase', 0)
            total_real += amp * np.cos(phase)
            total_imag += amp * np.sin(phase)
        
        resultant_amp = np.sqrt(total_real**2 + total_imag**2)
        
        return {
            'resultant_amplitude': resultant_amp,
            'confidence_adjustment': total_adjustment / len(interference_matrix) if interference_matrix else 0,
            'interference_matrix': interference_matrix,
            'net_confidence': min(1.0, max(0, sum(s['confidence'] for s in signals) / len(signals) + total_adjustment))
        }
    
    def detect_resonance(self, frequency_data: Dict[str, float]) -> List[Dict]:
        """
        Detect when multiple signals resonate at same frequency.
        
        Resonance occurs when signals align in time/space.
        """
        resonances = []
        
        # Look for clusters of similar frequencies
        frequencies = list(frequency_data.items())
        
        for i, (sig1, freq1) in enumerate(frequencies):
            for sig2, freq2 in frequencies[i+1:]:
                # Check if frequencies are harmonically related
                ratio = max(freq1, freq2) / min(freq1, freq2) if min(freq1, freq2) > 0 else 0
                
                # Near integer ratio = resonance
                if abs(ratio - round(ratio)) < 0.1 and ratio > 0:
                    resonances.append({
                        'signals': [sig1, sig2],
                        'frequencies': [freq1, freq2],
                        'ratio': ratio,
                        'harmonic': round(ratio),
                        'strength': 1 - abs(ratio - round(ratio))
                    })
        
        return resonances
    
    def get_interference_report(self) -> Dict:
        """Generate report on recent interference patterns."""
        if not self.interference_history:
            return {'message': 'No interference data yet'}
        
        recent = self.interference_history[-100:]
        
        type_counts = {}
        for intf in recent:
            type_counts[intf.interference_type.value] = type_counts.get(intf.interference_type.value, 0) + 1
        
        avg_strength = np.mean([i.interference_strength for i in recent])
        avg_adjustment = np.mean([i.confidence_adjustment for i in recent])
        
        return {
            'total_interferences': len(self.interference_history),
            'recent_count': len(recent),
            'type_distribution': type_counts,
            'average_strength': avg_strength,
            'average_confidence_adjustment': avg_adjustment,
            'dominant_pattern': max(type_counts.items(), key=lambda x: x[1])[0] if type_counts else 'none'
        }
