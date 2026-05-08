"""
Dynamic Position Sizing for PolyBot Trading System

Implements adaptive position sizing based on:
- Kelly Criterion for optimal bet sizing
- Whale size correlation analysis
- Signal confidence weighting
- Market liquidity constraints
- Drawdown protection

This module provides intelligent position sizing that adjusts to market conditions
and historical performance to maximize long-term growth while managing risk.
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SizingDecision(Enum):
    """Position sizing decision outcomes."""
    FULL_SIZE = "full_size"           # 100% of calculated size
    REDUCED_SIZE = "reduced_size"     # 75% of calculated size
    HALF_SIZE = "half_size"           # 50% of calculated size
    SKIP_TOO_SMALL = "skip_too_small" # Whale size below minimum
    SKIP_LOW_CONF = "skip_low_conf"   # Confidence too low
    SKIP_LIQUIDITY = "skip_liquidity" # Insufficient market liquidity
    SKIP_DRAWDOWN = "skip_drawdown"   # In drawdown protection mode


@dataclass
class SizingResult:
    """Result of position size calculation with full context."""
    # Position size
    position_size: float              # Final calculated position size in USD
    
    # Decision tracking
    decision: SizingDecision          # Why this size was chosen
    confidence_tier: str              # 'high', 'medium', 'low', 'skip'
    
    # Component breakdown
    base_size: float                  # Initial base size calculation
    kelly_adjusted_size: float        # After Kelly Criterion
    confidence_multiplier: float      # Applied confidence factor
    liquidity_cap: float              # Maximum allowed by liquidity
    risk_adjusted_size: float         # After drawdown adjustment
    
    # Risk metrics
    risk_amount: float                # USD at risk for this position
    risk_percent: float               # Percentage of balance at risk
    
    # Context
    whale_size_tier: str              # 'large', 'medium', 'small'
    market_liquidity_percent: float   # Position as % of daily volume
    
    # Logging
    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class DynamicPositionSizer:
    """
    Advanced dynamic position sizing for whale-copy trading.
    
    Implements Kelly Criterion-based sizing with multiple safety constraints:
    - Whale correlation analysis (follow larger whales more closely)
    - Confidence-based scaling (high confidence = full size)
    - Liquidity caps (never exceed 1% of daily volume)
    - Drawdown protection (reduce size during losing streaks)
    
    Example:
        sizer = DynamicPositionSizer()
        result = sizer.calculate_position_size(
            whale_size=50000.0,
            confidence=0.85,
            current_balance=10000.0,
            market_liquidity=2000000.0,
            win_rate=0.58,
            profit_factor=1.6,
            current_drawdown=0.05,
            risk_per_trade=0.02
        )
        print(f"Position size: ${result.position_size:.2f}")
    """
    
    # Whale size thresholds
    WHALE_SIZE_LARGE = 100000.0       # $100k+ = large whale
    WHALE_SIZE_SMALL = 10000.0        # <$10k = too small to follow
    WHALE_CAP_SIZE = 500.0            # Cap position at $500 for very large whales
    
    # Confidence thresholds
    CONF_HIGH = 0.8                   # >80% = full size
    CONF_MEDIUM = 0.6                 # 60-80% = 75% size
    CONF_LOW = 0.5                    # 50-60% = 50% size
    CONF_MINIMUM = 0.5                # <50% = skip
    
    # Liquidity constraints
    MAX_LIQUIDITY_PERCENT = 0.01      # Max 1% of daily volume
    
    # Position size limits
    MAX_POSITION_PERCENT_OF_BALANCE = 0.20  # Max 20% of balance per trade
    DEFAULT_WHALE_FOLLOW_RATIO = 0.02       # Follow whale with 2% of their size
    
    # Kelly Criterion settings
    DEFAULT_KELLY_FRACTION = 0.5      # Half-Kelly for safety
    MIN_WIN_RATE_FOR_KELLY = 0.52     # Need at least 52% win rate
    DEFAULT_PROFIT_FACTOR = 1.5       # Assumed 1.5x profit factor
    
    # Drawdown protection
    DRAWDOWN_LIGHT = 0.10             # 10% drawdown = reduce 25%
    DRAWDOWN_MODERATE = 0.15          # 15% drawdown = reduce 50%
    DRAWDOWN_SEVERE = 0.20            # 20% drawdown = reduce 75%
    
    def __init__(
        self,
        kelly_fraction: float = DEFAULT_KELLY_FRACTION,
        risk_per_trade: float = 0.02,
        max_position_size: Optional[float] = None,
        min_position_size: float = 20.0,
        enable_drawdown_protection: bool = True
    ):
        """
        Initialize the dynamic position sizer.
        
        Args:
            kelly_fraction: Fraction of Kelly to use (0.5 = half-Kelly)
            risk_per_trade: Maximum risk per trade as decimal (0.02 = 2%)
            max_position_size: Absolute maximum position size in USD
            min_position_size: Minimum viable position size in USD
            enable_drawdown_protection: Whether to reduce size in drawdown
        """
        self.kelly_fraction = kelly_fraction
        self.risk_per_trade = risk_per_trade
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.enable_drawdown_protection = enable_drawdown_protection
        
        # History for analytics
        self.sizing_history: List[SizingResult] = []
        
        logger.info(
            f"DynamicPositionSizer initialized: "
            f"kelly_fraction={kelly_fraction}, risk_per_trade={risk_per_trade:.1%}"
        )
    
    def calculate_position_size(
        self,
        whale_size: float,
        confidence: float,
        current_balance: float,
        market_liquidity: float,
        win_rate: float = 0.55,
        profit_factor: float = 1.5,
        current_drawdown: float = 0.0,
        risk_per_trade: Optional[float] = None
    ) -> SizingResult:
        """
        Calculate optimal position size based on multiple factors.
        
        The algorithm follows these steps:
        1. Validate inputs and check skip conditions
        2. Calculate base size from whale correlation
        3. Apply Kelly Criterion adjustment
        4. Apply confidence multiplier
        5. Apply liquidity cap
        6. Apply drawdown protection
        7. Apply final risk limits
        
        Args:
            whale_size: Whale's trade size in USD
            confidence: Signal confidence (0.0-1.0)
            current_balance: Available trading balance
            market_liquidity: Market daily volume for liquidity cap
            win_rate: Historical win rate (0.0-1.0)
            profit_factor: Average win/average loss ratio
            current_drawdown: Current drawdown from peak (0.0-1.0)
            risk_per_trade: Override default risk per trade
            
        Returns:
            SizingResult with full calculation breakdown
        """
        reasoning = []
        warnings = []
        
        # Use provided risk or default
        max_risk = risk_per_trade if risk_per_trade is not None else self.risk_per_trade
        
        # ========== STEP 1: Input Validation & Skip Conditions ==========
        
        # Check whale size minimum
        if whale_size < self.WHALE_SIZE_SMALL:
            reasoning.append(f"Whale size ${whale_size:,.0f} below minimum ${self.WHALE_SIZE_SMALL:,.0f}")
            logger.debug(f"Skipping: Whale size too small (${whale_size:,.0f})")
            return self._create_skip_result(
                SizingDecision.SKIP_TOO_SMALL, confidence, reasoning, warnings
            )
        
        # Check confidence minimum
        if confidence < self.CONF_MINIMUM:
            reasoning.append(f"Confidence {confidence:.1%} below minimum {self.CONF_MINIMUM:.1%}")
            logger.debug(f"Skipping: Confidence too low ({confidence:.1%})")
            return self._create_skip_result(
                SizingDecision.SKIP_LOW_CONF, confidence, reasoning, warnings
            )
        
        # Check for zero/negative balance
        if current_balance <= 0:
            warnings.append("Zero or negative balance")
            return self._create_skip_result(
                SizingDecision.SKIP_LIQUIDITY, confidence, reasoning, warnings
            )
        
        # Determine confidence tier
        if confidence >= self.CONF_HIGH:
            confidence_tier = 'high'
            confidence_multiplier = 1.0
        elif confidence >= self.CONF_MEDIUM:
            confidence_tier = 'medium'
            confidence_multiplier = 0.75
        else:
            confidence_tier = 'low'
            confidence_multiplier = 0.5
        
        reasoning.append(f"Confidence tier: {confidence_tier} ({confidence:.1%})")
        reasoning.append(f"Confidence multiplier: {confidence_multiplier:.0%}")
        
        # Determine whale size tier
        if whale_size >= self.WHALE_SIZE_LARGE:
            whale_size_tier = 'large'
            reasoning.append(f"Large whale detected (${whale_size:,.0f})")
        else:
            whale_size_tier = 'medium'
            reasoning.append(f"Medium whale detected (${whale_size:,.0f})")
        
        # ========== STEP 2: Base Size Calculation ==========
        
        # Base size: min(whale_size * 2%, balance * 20%)
        size_from_whale = whale_size * self.DEFAULT_WHALE_FOLLOW_RATIO
        size_from_balance = current_balance * self.MAX_POSITION_PERCENT_OF_BALANCE
        base_size = min(size_from_whale, size_from_balance)
        
        reasoning.append(f"Base size from whale: ${size_from_whale:,.2f} (2% of ${whale_size:,.0f})")
        reasoning.append(f"Base size from balance: ${size_from_balance:,.2f} (20% of ${current_balance:,.0f})")
        reasoning.append(f"Selected base size: ${base_size:,.2f}")
        
        # Special case: Cap very large whale follows
        if whale_size >= self.WHALE_SIZE_LARGE and base_size > self.WHALE_CAP_SIZE:
            base_size = self.WHALE_CAP_SIZE
            reasoning.append(f"Capped at ${self.WHALE_CAP_SIZE:,.0f} due to large whale size")
            warnings.append("Position capped due to whale size limits")
        
        # ========== STEP 3: Kelly Criterion Adjustment ==========
        
        kelly_size = self._apply_kelly_criterion(
            base_size=base_size,
            balance=current_balance,
            win_rate=win_rate,
            profit_factor=profit_factor
        )
        
        reasoning.append(
            f"Kelly Criterion: ${kelly_size:,.2f} "
            f"(win_rate={win_rate:.1%}, pf={profit_factor:.2f})"
        )
        
        # ========== STEP 4: Apply Confidence Multiplier ==========
        
        confidence_adjusted_size = kelly_size * confidence_multiplier
        
        if confidence_multiplier < 1.0:
            reasoning.append(
                f"Reduced to ${confidence_adjusted_size:,.2f} due to {confidence_tier} confidence"
            )
        
        # ========== STEP 5: Liquidity Cap ==========
        
        liquidity_cap = market_liquidity * self.MAX_LIQUIDITY_PERCENT
        liquidity_constrained_size = min(confidence_adjusted_size, liquidity_cap)
        market_liquidity_percent = liquidity_constrained_size / market_liquidity if market_liquidity > 0 else 0
        
        if liquidity_constrained_size < confidence_adjusted_size:
            reasoning.append(
                f"Reduced to ${liquidity_constrained_size:,.2f} due to liquidity cap "
                f"(max {self.MAX_LIQUIDITY_PERCENT:.1%} of ${market_liquidity:,.0f} volume)"
            )
            warnings.append("Position limited by market liquidity")
        
        # ========== STEP 6: Drawdown Protection ==========
        
        drawdown_adjusted_size = self._apply_drawdown_protection(
            size=liquidity_constrained_size,
            drawdown=current_drawdown
        )
        
        if drawdown_adjusted_size < liquidity_constrained_size:
            reduction_pct = 1 - (drawdown_adjusted_size / liquidity_constrained_size)
            reasoning.append(
                f"Reduced to ${drawdown_adjusted_size:,.2f} due to drawdown protection "
                f"({current_drawdown:.1%} drawdown, -{reduction_pct:.0%} size)"
            )
            warnings.append(f"Drawdown protection active: {current_drawdown:.1%}")
        
        # ========== STEP 7: Apply Risk Limits ==========
        
        # Calculate risk amount based on assumed 5% stop loss
        assumed_stop_distance = 0.05
        risk_amount = drawdown_adjusted_size * assumed_stop_distance
        risk_percent = risk_amount / current_balance
        
        # Limit by max risk per trade
        max_risk_amount = current_balance * max_risk
        if risk_amount > max_risk_amount:
            risk_constrained_size = max_risk_amount / assumed_stop_distance
            reasoning.append(
                f"Limited to ${risk_constrained_size:,.2f} to maintain {max_risk:.1%} max risk "
                f"(${(risk_constrained_size * assumed_stop_distance):,.2f} at risk)"
            )
        else:
            risk_constrained_size = drawdown_adjusted_size
        
        # Apply absolute max position size if configured
        if self.max_position_size and risk_constrained_size > self.max_position_size:
            final_size = self.max_position_size
            reasoning.append(f"Capped at absolute max: ${self.max_position_size:,.0f}")
        else:
            final_size = risk_constrained_size
        
        # Check minimum size
        if final_size < self.min_position_size:
            reasoning.append(f"Final size ${final_size:,.2f} below minimum ${self.min_position_size:,.0f}")
            return self._create_skip_result(
                SizingDecision.SKIP_TOO_SMALL, confidence, reasoning, warnings
            )
        
        # Determine decision type
        if confidence_tier == 'high':
            decision = SizingDecision.FULL_SIZE
        elif confidence_tier == 'medium':
            decision = SizingDecision.REDUCED_SIZE
        else:
            decision = SizingDecision.HALF_SIZE
        
        # Recalculate final risk metrics
        final_risk_amount = final_size * assumed_stop_distance
        final_risk_percent = final_risk_amount / current_balance
        
        reasoning.append(f"FINAL POSITION SIZE: ${final_size:,.2f}")
        reasoning.append(f"Risk amount: ${final_risk_amount:,.2f} ({final_risk_percent:.2%} of balance)")
        
        # Build result
        result = SizingResult(
            position_size=final_size,
            decision=decision,
            confidence_tier=confidence_tier,
            base_size=base_size,
            kelly_adjusted_size=kelly_size,
            confidence_multiplier=confidence_multiplier,
            liquidity_cap=liquidity_cap,
            risk_adjusted_size=drawdown_adjusted_size,
            risk_amount=final_risk_amount,
            risk_percent=final_risk_percent,
            whale_size_tier=whale_size_tier,
            market_liquidity_percent=market_liquidity_percent,
            reasoning=reasoning,
            warnings=warnings
        )
        
        # Log and store
        self._log_sizing_decision(result, whale_size, confidence, current_balance)
        self.sizing_history.append(result)
        
        return result
    
    def _apply_kelly_criterion(
        self,
        base_size: float,
        balance: float,
        win_rate: float,
        profit_factor: float
    ) -> float:
        """
        Apply Kelly Criterion for optimal bet sizing.
        
        Standard Kelly formula: f = (bp - q) / b
        Where:
        - b = average win / average loss (profit_factor - 1)
        - p = probability of win
        - q = probability of loss (1 - p)
        
        We use half-Kelly for safety.
        
        Args:
            base_size: Initial position size estimate
            balance: Current account balance
            win_rate: Historical probability of winning
            profit_factor: Average win / average loss ratio
            
        Returns:
            Kelly-adjusted position size
        """
        # Validate inputs
        if win_rate < self.MIN_WIN_RATE_FOR_KELLY or win_rate >= 1.0 or profit_factor <= 1.0:
            # Edge case: can't apply Kelly meaningfully
            return base_size * self.kelly_fraction
        
        # Calculate Kelly fraction
        p = win_rate
        q = 1 - p
        
        # b = odds received on win (profit factor - 1 represents net odds)
        b = profit_factor - 1
        
        if b <= 0:
            # No edge, use conservative fraction of base
            return base_size * self.kelly_fraction
        
        # Standard Kelly: f = (bp - q) / b
        kelly_fraction_full = (b * p - q) / b
        
        # If Kelly suggests not betting or negative edge, fall back to conservative base
        if kelly_fraction_full <= 0:
            return base_size * self.kelly_fraction
        
        # Clamp to reasonable range for trading (max 25% of bankroll per Kelly)
        kelly_fraction_full = min(0.25, kelly_fraction_full)
        
        # Apply conservative fraction (half-Kelly by default)
        kelly_fraction_conservative = kelly_fraction_full * self.kelly_fraction
        
        # Ensure we have a meaningful fraction
        kelly_fraction_conservative = max(0.01, kelly_fraction_conservative)
        
        # Calculate Kelly-based size
        kelly_based_size = balance * kelly_fraction_conservative
        
        # Blend with base size - use average for balanced approach
        # This ensures we follow the whale but Kelly informs the sizing
        final_size = (kelly_based_size + base_size) / 2
        
        # Don't exceed base size (whale following limit)
        final_size = min(final_size, base_size)
        
        return final_size
    
    def _apply_drawdown_protection(self, size: float, drawdown: float) -> float:
        """
        Reduce position size during drawdown periods.
        
        Drawdown thresholds:
        - < 10%: No reduction
        - 10-15%: Reduce 25%
        - 15-20%: Reduce 50%
        - > 20%: Reduce 75%
        
        Args:
            size: Proposed position size
            drawdown: Current drawdown as decimal (0.0-1.0)
            
        Returns:
            Drawdown-adjusted position size
        """
        if not self.enable_drawdown_protection or drawdown <= 0:
            return size
        
        if drawdown >= self.DRAWDOWN_SEVERE:
            return size * 0.25  # 75% reduction
        elif drawdown >= self.DRAWDOWN_MODERATE:
            return size * 0.50  # 50% reduction
        elif drawdown >= self.DRAWDOWN_LIGHT:
            return size * 0.75  # 25% reduction
        else:
            return size
    
    def _create_skip_result(
        self,
        decision: SizingDecision,
        confidence: float,
        reasoning: List[str],
        warnings: List[str]
    ) -> SizingResult:
        """Create a skip result with zero position size."""
        
        # Determine confidence tier
        if confidence >= self.CONF_HIGH:
            confidence_tier = 'high'
        elif confidence >= self.CONF_MEDIUM:
            confidence_tier = 'medium'
        elif confidence >= self.CONF_MINIMUM:
            confidence_tier = 'low'
        else:
            confidence_tier = 'skip'
        
        result = SizingResult(
            position_size=0.0,
            decision=decision,
            confidence_tier=confidence_tier,
            base_size=0.0,
            kelly_adjusted_size=0.0,
            confidence_multiplier=0.0,
            liquidity_cap=0.0,
            risk_adjusted_size=0.0,
            risk_amount=0.0,
            risk_percent=0.0,
            whale_size_tier='small',
            market_liquidity_percent=0.0,
            reasoning=reasoning,
            warnings=warnings
        )
        
        # Still log the skip decision
        self.sizing_history.append(result)
        
        return result
    
    def _log_sizing_decision(
        self,
        result: SizingResult,
        whale_size: float,
        confidence: float,
        balance: float
    ):
        """Log the sizing decision with full context."""
        
        if result.position_size > 0:
            logger.info(
                f"Position sizing decision: ${result.position_size:,.2f} "
                f"(whale=${whale_size:,.0f}, conf={confidence:.1%}, "
                f"balance=${balance:,.0f})"
            )
            
            if result.warnings:
                for warning in result.warnings:
                    logger.warning(f"  Warning: {warning}")
        else:
            logger.info(
                f"Position skipped: {result.decision.value} "
                f"(whale=${whale_size:,.0f}, conf={confidence:.1%})"
            )
    
    def get_sizing_statistics(self) -> Dict:
        """
        Get statistics on recent sizing decisions.
        
        Returns:
            Dictionary with sizing statistics
        """
        if not self.sizing_history:
            return {'message': 'No sizing decisions yet'}
        
        # Recent history (last 100)
        recent = self.sizing_history[-100:]
        
        # Calculate statistics
        sizes = [r.position_size for r in recent if r.position_size > 0]
        skips = [r for r in recent if r.position_size == 0]
        
        stats = {
            'total_decisions': len(self.sizing_history),
            'recent_decisions': len(recent),
            'trades_accepted': len(sizes),
            'trades_skipped': len(skips),
            'acceptance_rate': len(sizes) / len(recent) if recent else 0,
            'avg_position_size': sum(sizes) / len(sizes) if sizes else 0,
            'max_position_size': max(sizes) if sizes else 0,
            'min_position_size': min(sizes) if sizes else 0,
        }
        
        # Skip reasons
        skip_reasons = {}
        for skip in skips:
            reason = skip.decision.value
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        stats['skip_reasons'] = skip_reasons
        
        # Confidence tier distribution
        tier_dist = {}
        for r in recent:
            tier = r.confidence_tier
            tier_dist[tier] = tier_dist.get(tier, 0) + 1
        stats['confidence_distribution'] = tier_dist
        
        return stats
    
    def get_position_size_simple(
        self,
        whale_size: float,
        confidence: float,
        current_balance: float,
        market_liquidity: float,
        win_rate: float = 0.55
    ) -> float:
        """
        Simple interface that returns just the position size.
        
        Args:
            whale_size: Whale's trade size
            confidence: Signal confidence (0.0-1.0)
            current_balance: Available balance
            market_liquidity: Daily market volume
            win_rate: Historical win rate
            
        Returns:
            Position size in USD (0.0 if trade should be skipped)
        """
        result = self.calculate_position_size(
            whale_size=whale_size,
            confidence=confidence,
            current_balance=current_balance,
            market_liquidity=market_liquidity,
            win_rate=win_rate
        )
        return result.position_size


class PositionSizingConfig:
    """
    Configuration presets for different trading styles.
    
    Provides pre-configured sizer instances for:
    - Conservative (lower risk, smaller positions)
    - Moderate (balanced approach)
    - Aggressive (higher risk, larger positions)
    """
    
    @staticmethod
    def conservative() -> DynamicPositionSizer:
        """Conservative sizing: Lower risk, smaller positions."""
        return DynamicPositionSizer(
            kelly_fraction=0.3,      # Very conservative Kelly
            risk_per_trade=0.01,      # 1% max risk
            max_position_size=1000,   # $1k max per trade
            min_position_size=25,     # $25 min
            enable_drawdown_protection=True
        )
    
    @staticmethod
    def moderate() -> DynamicPositionSizer:
        """Moderate sizing: Balanced approach (default)."""
        return DynamicPositionSizer(
            kelly_fraction=0.5,      # Half-Kelly
            risk_per_trade=0.02,      # 2% max risk
            max_position_size=None,   # No absolute max
            min_position_size=20,     # $20 min
            enable_drawdown_protection=True
        )
    
    @staticmethod
    def aggressive() -> DynamicPositionSizer:
        """Aggressive sizing: Higher risk, larger positions."""
        return DynamicPositionSizer(
            kelly_fraction=0.7,      # More aggressive Kelly
            risk_per_trade=0.03,      # 3% max risk
            max_position_size=5000,   # $5k max per trade
            min_position_size=15,     # $15 min
            enable_drawdown_protection=False  # Disable drawdown protection
        )


# Convenience function for quick sizing
def calculate_position_size(
    whale_size: float,
    confidence: float,
    current_balance: float,
    market_liquidity: float,
    win_rate: float = 0.55,
    profit_factor: float = 1.5,
    current_drawdown: float = 0.0,
    risk_per_trade: float = 0.02
) -> float:
    """
    Quick function to calculate position size without creating a sizer instance.
    
    Args:
        whale_size: Whale's trade size in USD
        confidence: Signal confidence (0.0-1.0)
        current_balance: Available trading balance
        market_liquidity: Market daily volume
        win_rate: Historical win rate (0.0-1.0)
        profit_factor: Average win/average loss ratio
        current_drawdown: Current drawdown from peak (0.0-1.0)
        risk_per_trade: Max risk per trade as decimal
        
    Returns:
        Position size in USD (0.0 if trade should be skipped)
    """
    sizer = DynamicPositionSizer(risk_per_trade=risk_per_trade)
    result = sizer.calculate_position_size(
        whale_size=whale_size,
        confidence=confidence,
        current_balance=current_balance,
        market_liquidity=market_liquidity,
        win_rate=win_rate,
        profit_factor=profit_factor,
        current_drawdown=current_drawdown
    )
    return result.position_size
