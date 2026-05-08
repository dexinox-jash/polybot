"""
Speed-Matched Copy Engine - Real-Time Whale Copying

Replaces the daily 1-bet limit with real-time, speed-matched paper trading.

Key features:
- Sub-minute reaction time to whale moves
- Real-time decision making (not batch analysis)
- Pattern-based confidence scoring
- Speed-matched execution with timing tracking
- Educational performance metrics
"""

import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CopyAction(Enum):
    """Possible copy actions."""
    COPY_IMMEDIATE = "copy_immediate"      # Execute within delay tolerance
    WAIT_CONFIRM = "wait_confirm"          # Wait for pattern confirmation
    SKIP = "skip"                          # Don't copy
    REDUCE_SIZE = "reduce_size"            # Copy with smaller size
    SPEED_WARNING = "speed_warning"        # Too slow, skip


@dataclass
class SpeedMatchedDecision:
    """Decision for speed-matched copying."""
    action: CopyAction
    confidence: float
    reason: str
    
    # Execution params
    target_size: float
    max_delay_seconds: int
    
    # Warnings
    warnings: List[str]
    
    # Educational
    speed_score_estimate: float
    expected_slippage: float


class SpeedMatchedCopyEngine:
    """
    Real-time copy engine with speed matching.
    
    Makes decisions in <1 second for whale signals.
    """
    
    def __init__(
        self,
        pattern_engine,
        paper_trading_engine,
        position_manager,
        delay_tolerance_seconds: int = 60,
        min_pattern_confidence: float = 0.7,
        crypto_only: bool = True
    ):
        """
        Initialize speed-matched copy engine.
        
        Args:
            pattern_engine: PatternEngine for pattern analysis
            paper_trading_engine: PaperTradingEngine for execution
            position_manager: PositionManager for risk checks
            delay_tolerance_seconds: Max delay to still copy (default 60s)
            min_pattern_confidence: Minimum pattern confidence to copy
            crypto_only: Only copy crypto markets
        """
        self.pattern_engine = pattern_engine
        self.paper_trading = paper_trading_engine
        self.position_manager = position_manager
        
        self.delay_tolerance = delay_tolerance_seconds
        self.min_pattern_confidence = min_pattern_confidence
        self.crypto_only = crypto_only
        
        # Decision history
        self.decision_count: int = 0
        self.copy_count: int = 0
        self.skip_count: int = 0
        
        # Real-time callbacks
        self.on_decision: Optional[Callable] = None
        
        logger.info(f"SpeedMatchedCopyEngine initialized: "
                   f"{delay_tolerance_seconds}s tolerance, "
                   f"min_confidence={min_pattern_confidence}")
    
    async def evaluate_whale_signal(
        self,
        signal,
        market_context: Dict,
        portfolio_context: Dict
    ) -> SpeedMatchedDecision:
        """
        Real-time decision making for whale signal.
        
        Args:
            signal: WhaleSignal from stream monitor
            market_context: Current market data
            portfolio_context: Current portfolio state
            
        Returns:
            SpeedMatchedDecision with action and params
        """
        self.decision_count += 1
        
        warnings = []
        
        # Check 1: Are we within delay tolerance?
        trade_time = signal.trade.timestamp
        current_time = datetime.now()
        actual_delay = (current_time - trade_time).total_seconds()
        
        if actual_delay > self.delay_tolerance:
            self.skip_count += 1
            return SpeedMatchedDecision(
                action=CopyAction.SPEED_WARNING,
                confidence=0.0,
                reason=f"Too slow: {actual_delay:.0f}s > {self.delay_tolerance}s tolerance",
                target_size=0,
                max_delay_seconds=0,
                warnings=["Improve monitoring speed"],
                speed_score_estimate=0.0,
                expected_slippage=5.0
            )
        
        # Check 2: Pattern confidence
        pattern_confidence = signal.pattern_confidence
        if pattern_confidence < self.min_pattern_confidence:
            self.skip_count += 1
            return SpeedMatchedDecision(
                action=CopyAction.WAIT_CONFIRM,
                confidence=pattern_confidence,
                reason=f"Pattern confidence {pattern_confidence:.0%} < {self.min_pattern_confidence:.0%}",
                target_size=0,
                max_delay_seconds=300,
                warnings=["Wait for more confirmation"],
                speed_score_estimate=max(0, 1 - actual_delay/300),
                expected_slippage=2.0
            )
        
        # Check 3: Crypto filter
        if self.crypto_only:
            is_crypto = market_context.get('is_crypto', False)
            if not is_crypto:
                self.skip_count += 1
                return SpeedMatchedDecision(
                    action=CopyAction.SKIP,
                    confidence=0.0,
                    reason="Not a crypto market",
                    target_size=0,
                    max_delay_seconds=0,
                    warnings=[],
                    speed_score_estimate=0.0,
                    expected_slippage=0.0
                )
        
        # Check 4: Market liquidity
        liquidity = market_context.get('liquidity', 0)
        if liquidity < 10000:
            warnings.append(f"Low liquidity: ${liquidity:,.0f} (may cause slippage)")
        
        # Check 5: Portfolio constraints
        can_trade, constraint_msg = self._check_portfolio_constraints(
            portfolio_context, signal.suggested_size
        )
        
        if not can_trade:
            self.skip_count += 1
            return SpeedMatchedDecision(
                action=CopyAction.SKIP,
                confidence=0.0,
                reason=constraint_msg,
                target_size=0,
                max_delay_seconds=0,
                warnings=[constraint_msg],
                speed_score_estimate=0.0,
                expected_slippage=0.0
            )
        
        # Check 6: Whale's historical performance in this pattern
        pattern_wr = signal.whale_pattern_profile
        # In real implementation, would look up actual win rate
        estimated_wr = 0.60  # Placeholder
        
        if estimated_wr < 0.55:
            warnings.append(f"Whale's pattern WR ({estimated_wr:.0%}) below threshold")
        
        # Calculate speed score
        speed_score = max(0, 1 - (actual_delay / self.delay_tolerance))
        
        # Estimate slippage
        expected_slippage = self._estimate_slippage(
            signal.suggested_size, liquidity, speed_score
        )
        
        # Determine action
        if speed_score > 0.8 and pattern_confidence > 0.8 and not warnings:
            action = CopyAction.COPY_IMMEDIATE
            target_size = signal.suggested_size
        elif warnings:
            action = CopyAction.REDUCE_SIZE
            target_size = signal.suggested_size * 0.5
        else:
            action = CopyAction.COPY_IMMEDIATE
            target_size = signal.suggested_size
        
        self.copy_count += 1
        
        decision = SpeedMatchedDecision(
            action=action,
            confidence=pattern_confidence * speed_score,
            reason=f"Pattern {signal.whale_pattern_profile} with {speed_score:.0%} speed match",
            target_size=target_size,
            max_delay_seconds=self.delay_tolerance - int(actual_delay),
            warnings=warnings,
            speed_score_estimate=speed_score,
            expected_slippage=expected_slippage
        )
        
        # Trigger callback if set
        if self.on_decision:
            self.on_decision(signal, decision)
        
        return decision
    
    async def execute_copy(
        self,
        signal,
        decision: SpeedMatchedDecision,
        market_data: Dict
    ) -> Optional[Dict]:
        """
        Execute the copy decision.
        
        Args:
            signal: Original whale signal
            decision: SpeedMatchedDecision
            market_data: Current market data
            
        Returns:
            PaperPosition or None
        """
        if decision.action in [CopyAction.SKIP, CopyAction.SPEED_WARNING, CopyAction.WAIT_CONFIRM]:
            logger.info(f"Skipping execution: {decision.reason}")
            return None
        
        # Execute paper trade
        delay_seconds = int((datetime.now() - signal.trade.timestamp).total_seconds())
        
        position = self.paper_trading.execute_paper_trade(
            signal=signal,
            delay_seconds=delay_seconds,
            market_data=market_data
        )
        
        logger.info(f"Copy executed: {position.position_id} | "
                   f"Speed score: {position.timing_metrics.speed_score:.0%} | "
                   f"Slippage: {position.timing_metrics.price_slippage_percent:.2f}%")
        
        return position
    
    def _check_portfolio_constraints(
        self,
        portfolio: Dict,
        trade_size: float
    ) -> tuple:
        """
        Check if portfolio can accept new position.
        
        Returns:
            (can_trade: bool, message: str)
        """
        # Check portfolio heat
        current_heat = portfolio.get('heat', 0)
        max_heat = portfolio.get('max_heat', 0.5)
        
        if current_heat >= max_heat:
            return False, f"Portfolio heat at {current_heat:.0%} (max {max_heat:.0%})"
        
        # Check position count
        open_positions = portfolio.get('open_positions', 0)
        max_positions = portfolio.get('max_positions', 5)
        
        if open_positions >= max_positions:
            return False, f"Max positions reached ({open_positions}/{max_positions})"
        
        # Check daily drawdown
        daily_pnl = portfolio.get('daily_pnl', 0)
        portfolio_value = portfolio.get('value', 10000)
        daily_drawdown = abs(min(0, daily_pnl)) / portfolio_value
        
        if daily_drawdown >= 0.10:
            return False, f"Daily drawdown at {daily_drawdown:.0%} - circuit breaker active"
        
        # Check available balance
        available = portfolio.get('available_balance', 0)
        if available < trade_size:
            return False, f"Insufficient balance: ${available:.0f} < ${trade_size:.0f}"
        
        return True, "OK"
    
    def _estimate_slippage(
        self,
        position_size: float,
        liquidity: float,
        speed_score: float
    ) -> float:
        """
        Estimate price slippage.
        
        Args:
            position_size: Trade size in USD
            liquidity: Market liquidity
            speed_score: 0-1 speed score
            
        Returns:
            Estimated slippage percentage
        """
        base_slippage = 0.001  # 0.1% base
        
        # Liquidity impact
        if liquidity > 0:
            liquidity_impact = (position_size / liquidity) * 0.5
        else:
            liquidity_impact = 0.02  # 2% if unknown liquidity
        
        # Speed penalty (slower = more slippage)
        speed_penalty = (1 - speed_score) * 0.01  # Up to 1%
        
        total_slippage = (base_slippage + liquidity_impact + speed_penalty) * 100
        
        return min(total_slippage, 10.0)  # Cap at 10%
    
    def get_stats(self) -> Dict:
        """Get engine statistics."""
        return {
            'total_decisions': self.decision_count,
            'copies_executed': self.copy_count,
            'skipped': self.skip_count,
            'copy_rate': self.copy_count / self.decision_count if self.decision_count > 0 else 0,
            'delay_tolerance': self.delay_tolerance,
            'min_confidence': self.min_pattern_confidence
        }
    
    def set_on_decision_callback(self, callback: Callable):
        """Set callback for decision events."""
        self.on_decision = callback
    
    async def run_continuous_monitoring(
        self,
        stream_monitor,
        market_data_provider
    ):
        """
        Run continuous monitoring and copying loop.
        
        Args:
            stream_monitor: WhaleStreamMonitor instance
            market_data_provider: Function to get current market data
        """
        logger.info("Starting continuous monitoring...")
        
        async def on_signal(signal):
            # Get current context
            market_data = await market_data_provider(signal.trade.market_id)
            portfolio = self.position_manager.get_portfolio_summary()
            
            # Make decision
            decision = await self.evaluate_whale_signal(
                signal, market_data, portfolio
            )
            
            # Execute if appropriate
            if decision.action in [CopyAction.COPY_IMMEDIATE, CopyAction.REDUCE_SIZE]:
                await self.execute_copy(signal, decision, market_data)
        
        # Set callback
        stream_monitor.add_callback(on_signal)
        
        # Start monitoring
        await stream_monitor.start_monitoring()
