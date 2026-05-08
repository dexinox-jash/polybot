"""
Bet Tracker & Replication System

Real-time monitoring of top winners' bets.
When they place a bet, we detect it and evaluate if we should copy.
"""

import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json


class ReplicationStatus(Enum):
    """Status of a replication trade."""
    DETECTED = "detected"           # Winner placed bet
    EVALUATING = "evaluating"       # Calculating EV
    APPROVED = "approved"           # +EV, ready to copy
    REJECTED = "rejected"           # -EV or too risky
    EXECUTED = "executed"           # We copied
    PENDING_FILL = "pending_fill"   # Order not yet filled
    FILLED = "filled"               # Our copy filled
    TRACKING = "tracking"           # Monitoring position
    CLOSED = "closed"               # Position closed


@dataclass
class WinnerBet:
    """A bet placed by a top winner."""
    # Identification
    bet_id: str
    winner_address: str
    winner_name: Optional[str]
    
    # Bet details
    market_id: str
    market_question: str
    category: str
    
    # Position
    direction: str  # 'YES' or 'NO'
    size: float
    entry_price: float
    position_value: float
    
    # Timing
    timestamp: datetime
    market_close_time: datetime
    
    # Market context at entry
    market_probability: float
    volume_24h: float
    liquidity: float
    spread: float
    
    # Replication tracking
    our_replication: Optional['ReplicationTrade'] = None


@dataclass
class ReplicationTrade:
    """Our copy of a winner's bet."""
    # Link to original
    original_bet: WinnerBet
    replication_id: str
    
    # Our position
    status: ReplicationStatus
    our_size: float
    our_entry: float
    fill_price: Optional[float]
    
    # EV analysis
    ev_percent: float
    confidence: float
    kelly_fraction: float
    
    # Timing
    detected_at: datetime
    decided_at: Optional[datetime]
    executed_at: Optional[datetime]
    closed_at: Optional[datetime]
    
    # Results
    pnl: float = 0.0
    replication_quality: float = 0.0  # How well we replicated
    
    # Reasoning
    decision_reason: str = ""
    rejection_reason: Optional[str] = None


@dataclass
class ReplicationSignal:
    """Signal to replicate a winner's bet."""
    winner_bet: WinnerBet
    replication_trade: ReplicationTrade
    
    # Composite scores
    winner_reliability: float  # 0-1
    ev_score: float
    timing_score: float
    risk_score: float
    overall_score: float
    
    # Recommendation
    action: str  # 'COPY_NOW', 'WAIT', 'SKIP'
    urgency: str  # 'immediate', 'high', 'medium', 'low'
    suggested_size: float
    max_slippage: float
    
    # Market conditions
    market_trend: str
    whale_consensus: Optional[str]
    time_to_close: timedelta


class BetTracker:
    """
    Tracks top winners' bets in real-time.
    Generates replication signals when +EV opportunities arise.
    """
    
    def __init__(self, winner_discovery):
        """
        Initialize bet tracker.
        
        Args:
            winner_discovery: WinnerDiscovery instance with tracked winners
        """
        self.winners = winner_discovery
        
        # Tracking state
        self.monitored_winners: Set[str] = set()
        self.active_bets: Dict[str, WinnerBet] = {}  # bet_id -> bet
        self.our_replications: Dict[str, ReplicationTrade] = {}  # rep_id -> replication
        
        # History
        self.bet_history: List[WinnerBet] = []
        self.replication_history: List[ReplicationTrade] = []
        
        # Performance tracking
        self.replication_stats = {
            'total_attempted': 0,
            'total_executed': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_slippage': 0.0,
        }
        
        # Configuration
        self.config = {
            'min_ev_percent': 2.0,  # Minimum 2% edge
            'max_time_to_close_minutes': 30,  # Don't copy close-to-expiry
            'max_slippage_percent': 1.0,  # Max 1% slippage
            'min_liquidity': 10000,  # $10k minimum liquidity
            'copy_delay_seconds': 5,  # Wait 5s to avoid front-running ourselves
        }
    
    def start_monitoring(self, winner_addresses: List[str]):
        """Start monitoring specific winners."""
        for addr in winner_addresses:
            self.monitored_winners.add(addr.lower())
        
        print(f"🔍 Now monitoring {len(self.monitored_winners)} top winners")
    
    async def monitor_loop(self):
        """Main monitoring loop - checks for new bets."""
        print("🔄 Bet monitoring started...")
        
        while True:
            try:
                # Poll for new bets from monitored winners
                new_bets = await self._poll_for_new_bets()
                
                for bet in new_bets:
                    await self._process_new_bet(bet)
                
                # Update existing replications
                self._update_replications()
                
                await asyncio.sleep(1)  # 1-second polling interval
                
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _poll_for_new_bets(self) -> List[WinnerBet]:
        """
        Poll blockchain/API for new bets from monitored winners.
        
        In production, this would query The Graph or listen to events.
        """
        # Placeholder - would integrate with actual data source
        return []
    
    async def _process_new_bet(self, bet: WinnerBet):
        """Process a newly detected winner bet."""
        print(f"\n🎯 NEW BET DETECTED!")
        print(f"   Winner: {bet.winner_name or bet.winner_address[:10]}")
        print(f"   Market: {bet.market_question[:50]}...")
        print(f"   Direction: {bet.direction}")
        print(f"   Size: ${bet.size:,.0f}")
        print(f"   Price: ${bet.entry_price:.4f}")
        
        # Store bet
        self.active_bets[bet.bet_id] = bet
        self.bet_history.append(bet)
        
        # Create replication evaluation
        replication = ReplicationTrade(
            original_bet=bet,
            replication_id=f"rep_{bet.bet_id}_{int(datetime.now().timestamp())}",
            status=ReplicationStatus.EVALUATING,
            our_size=0.0,
            our_entry=bet.entry_price,
            fill_price=None,
            ev_percent=0.0,
            confidence=0.0,
            kelly_fraction=0.0,
            detected_at=datetime.now(),
            decided_at=None,
            executed_at=None,
            closed_at=None,
        )
        
        self.our_replications[replication.replication_id] = replication
        bet.our_replication = replication
        
        # Evaluate replication opportunity
        signal = self._evaluate_replication(bet, replication)
        
        if signal.action == 'COPY_NOW':
            await self._execute_replication(replication, signal)
        elif signal.action == 'WAIT':
            print(f"   ⏳ Waiting for better entry...")
            replication.status = ReplicationStatus.DETECTED
        else:
            print(f"   ❌ Skipping: {signal.replication_trade.rejection_reason}")
            replication.status = ReplicationStatus.REJECTED
            replication.rejection_reason = signal.replication_trade.rejection_reason
    
    def _evaluate_replication(
        self,
        bet: WinnerBet,
        replication: ReplicationTrade
    ) -> ReplicationSignal:
        """
        Evaluate if we should copy this bet.
        
        Returns ReplicationSignal with recommendation.
        """
        # Get winner's profile
        winner = self.winners.get_winner_profile(bet.winner_address)
        
        if not winner:
            return ReplicationSignal(
                winner_bet=bet,
                replication_trade=replication,
                winner_reliability=0,
                ev_score=0,
                timing_score=0,
                risk_score=0,
                overall_score=0,
                action='SKIP',
                urgency='low',
                suggested_size=0,
                max_slippage=0,
                market_trend='unknown',
                whale_consensus=None,
                time_to_close=timedelta(0)
            )
        
        # Calculate components
        reliability = winner.true_win_rate * winner.profit_factor / 3
        reliability = min(1.0, reliability)
        
        # EV calculation (simplified)
        # Assume winner's win rate is their edge
        edge = winner.true_win_rate - 0.5
        ev_percent = edge * 100
        
        # Timing score
        time_to_close = bet.market_close_time - datetime.now()
        if time_to_close.total_seconds() < 300:  # < 5 min
            timing_score = 0.3  # Risky
        elif time_to_close.total_seconds() < 1800:  # < 30 min
            timing_score = 0.7
        else:
            timing_score = 0.9
        
        # Risk score
        risk_factors = []
        risk_score = 1.0
        
        if bet.spread > 0.02:  # Wide spread
            risk_factors.append("Wide spread")
            risk_score *= 0.8
        
        if bet.liquidity < self.config['min_liquidity']:
            risk_factors.append("Low liquidity")
            risk_score *= 0.7
        
        if winner.vanity_gap > 0.2:
            risk_factors.append("Winner manipulates stats")
            risk_score *= 0.6
        
        # Overall score
        overall = (reliability * 0.4 + 
                   (ev_percent / 10) * 0.3 + 
                   timing_score * 0.2 + 
                   risk_score * 0.1)
        
        # Decision
        if ev_percent < self.config['min_ev_percent']:
            action = 'SKIP'
            reason = f"EV too low ({ev_percent:.1f}%)"
        elif risk_score < 0.5:
            action = 'SKIP'
            reason = f"Too risky: {', '.join(risk_factors)}"
        elif overall > 0.7:
            action = 'COPY_NOW'
            reason = "High confidence replication"
        elif overall > 0.5:
            action = 'WAIT'
            reason = "Marginal - wait for confirmation"
        else:
            action = 'SKIP'
            reason = "Overall score too low"
        
        # Kelly sizing
        kelly = (winner.true_win_rate * 2 - 1) / 1  # Simplified
        kelly = max(0, kelly * 0.5)  # Half-Kelly
        suggested_size = 10000 * kelly  # Assuming $10k bankroll
        
        replication.ev_percent = ev_percent
        replication.confidence = overall
        replication.kelly_fraction = kelly
        replication.decision_reason = reason if action == 'COPY_NOW' else ''
        replication.rejection_reason = reason if action == 'SKIP' else None
        
        return ReplicationSignal(
            winner_bet=bet,
            replication_trade=replication,
            winner_reliability=reliability,
            ev_score=ev_percent,
            timing_score=timing_score,
            risk_score=risk_score,
            overall_score=overall,
            action=action,
            urgency='immediate' if overall > 0.8 else 'high' if overall > 0.6 else 'medium',
            suggested_size=suggested_size,
            max_slippage=self.config['max_slippage_percent'],
            market_trend='bullish' if bet.direction == 'YES' else 'bearish',
            whale_consensus=bet.direction,
            time_to_close=time_to_close
        )
    
    async def _execute_replication(self, replication: ReplicationTrade, signal: ReplicationSignal):
        """Execute the replication trade."""
        print(f"\n💰 EXECUTING REPLICATION")
        print(f"   Winner: {replication.original_bet.winner_name}")
        print(f"   Market: {replication.original_bet.market_question[:40]}...")
        print(f"   Direction: {replication.original_bet.direction}")
        print(f"   Size: ${signal.suggested_size:.0f}")
        print(f"   EV: {replication.ev_percent:.1f}%")
        print(f"   Confidence: {replication.confidence:.1%}")
        
        # In production, this would place actual orders
        # For now, simulate
        replication.status = ReplicationStatus.EXECUTED
        replication.executed_at = datetime.now()
        replication.our_size = signal.suggested_size
        replication.fill_price = replication.original_bet.entry_price * (1 + 0.001)  # Small slippage
        
        self.replication_stats['total_attempted'] += 1
        self.replication_stats['total_executed'] += 1
        
        print(f"   ✅ Replication executed at ${replication.fill_price:.4f}")
    
    def _update_replications(self):
        """Update status of existing replications."""
        current_time = datetime.now()
        
        for rep in list(self.our_replications.values()):
            if rep.status == ReplicationStatus.EXECUTED:
                # Check if filled
                rep.status = ReplicationStatus.FILLED
                rep.fill_price = rep.our_entry
                
            elif rep.status == ReplicationStatus.FILLED:
                # Track P&L
                rep.status = ReplicationStatus.TRACKING
                
            elif rep.status == ReplicationStatus.TRACKING:
                # Check if market closed
                if current_time > rep.original_bet.market_close_time:
                    rep.status = ReplicationStatus.CLOSED
                    rep.closed_at = current_time
                    # Calculate P&L (would need actual outcome)
                    self.replication_history.append(rep)
    
    def get_active_replications(self) -> List[ReplicationTrade]:
        """Get all currently active replications."""
        return [
            r for r in self.our_replications.values()
            if r.status in [ReplicationStatus.EXECUTED, 
                          ReplicationStatus.FILLED, 
                          ReplicationStatus.TRACKING]
        ]
    
    def get_replication_performance(self) -> Dict:
        """Get performance statistics of our copying."""
        closed = [r for r in self.replication_history if r.status == ReplicationStatus.CLOSED]
        
        if not closed:
            return {'message': 'No completed replications yet'}
        
        total_pnl = sum(r.pnl for r in closed)
        winners = sum(1 for r in closed if r.pnl > 0)
        
        return {
            'total_replications': len(self.replication_history),
            'completed': len(closed),
            'win_rate': winners / len(closed) if closed else 0,
            'total_pnl': total_pnl,
            'avg_pnl_per_trade': total_pnl / len(closed) if closed else 0,
            'avg_replication_quality': np.mean([r.replication_quality for r in closed]) if closed else 0,
        }
    
    def generate_replication_report(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("REPLICATION TRACKING REPORT")
        lines.append("=" * 70)
        
        # Monitored winners
        lines.append(f"\n📊 Monitored Winners: {len(self.monitored_winners)}")
        
        # Active bets
        lines.append(f"🎯 Active Winner Bets: {len(self.active_bets)}")
        
        # Our replications
        active = self.get_active_replications()
        lines.append(f"💰 Our Active Replications: {len(active)}")
        
        # Performance
        perf = self.get_replication_performance()
        if 'message' not in perf:
            lines.append(f"\n📈 Performance:")
            lines.append(f"   Total P&L: ${perf['total_pnl']:+.2f}")
            lines.append(f"   Win Rate: {perf['win_rate']:.1%}")
            lines.append(f"   Avg per Trade: ${perf['avg_pnl_per_trade']:.2f}")
        
        # Recent replications
        lines.append(f"\n📝 Recent Replications:")
        recent = sorted(self.replication_history, key=lambda x: x.executed_at or datetime.min, reverse=True)[:5]
        for rep in recent:
            status_emoji = "✅" if rep.pnl > 0 else "❌" if rep.pnl < 0 else "⏳"
            lines.append(f"   {status_emoji} {rep.original_bet.market_question[:40]}... "
                       f"${rep.pnl:+.2f}")
        
        return "\n".join(lines)
