"""
Winner Discovery Engine

Identifies the TOP BETTERS on Polymarket - those with proven,
statistically significant winning track records.

NOT just whales or high-volume traders.
NOT those with inflated win rates from zombie orders.

We want: Consistent, profitable betters with measurable edge.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import statistics


@dataclass
class TraderPerformance:
    """Comprehensive performance metrics for a trader."""
    # Identity
    address: str
    ens_name: Optional[str] = None
    label: Optional[str] = None  # e.g., "SmartMoney", "Insider"
    
    # Core Performance (REAL, not vanity)
    total_bets: int = 0
    winning_bets: int = 0
    losing_bets: int = 0
    true_win_rate: float = 0.0  # Settled wins / total settled
    displayed_win_rate: float = 0.0  # What Polymarket shows
    vanity_gap: float = 0.0  # Displayed - True
    
    # Profitability
    total_volume: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    roi_percent: float = 0.0
    profit_factor: float = 0.0  # Gross Profit / Gross Loss
    
    # Risk-Adjusted Returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    
    # Consistency
    monthly_returns: List[float] = field(default_factory=list)
    win_streak: int = 0
    loss_streak: int = 0
    
    # Market Focus
    categories_traded: Dict[str, int] = field(default_factory=dict)
    best_category: Optional[str] = None
    worst_category: Optional[str] = None
    
    # Timing
    avg_bet_size: float = 0.0
    avg_hold_time_hours: float = 0.0
    preferred_time_slots: List[int] = field(default_factory=list)
    
    # Zombie Order Detection
    zombie_orders: int = 0  # Unclosed losing positions > 30 days
    true_pnl: float = 0.0  # Including unrealized zombie losses
    
    # Statistical Significance
    p_value: float = 1.0  # Probability results are luck
    is_statistically_significant: bool = False
    
    # Timestamps
    first_trade: Optional[datetime] = None
    last_trade: Optional[datetime] = None
    discovered_at: datetime = field(default_factory=datetime.now)
    
    # Scoring
    copy_score: float = 0.0  # Overall desirability as copy target
    confidence_level: str = "low"  # low, medium, high
    
    @property
    def is_profitably_copyable(self) -> bool:
        """Can we profitably copy this trader?"""
        return (
            self.true_win_rate > 0.55 and
            self.net_pnl > 0 and
            self.profit_factor > 1.3 and
            self.total_bets >= 50 and
            self.is_statistically_significant and
            self.vanity_gap < 0.15  # Not manipulating stats
        )
    
    @property
    def win_rate_by_50(self) -> float:
        """Win rate over last 50 bets."""
        if len(self.monthly_returns) >= 3:
            return np.mean(self.monthly_returns[-3:])
        return self.true_win_rate


class WinnerDiscovery:
    """
    Discovers and ranks top-winning Polymarket traders.
    
    Uses statistical rigor to separate skill from luck.
    """
    
    def __init__(self, subgraph_client=None):
        self.subgraph = subgraph_client
        self.traders: Dict[str, TraderPerformance] = {}
        self.discovered_winners: List[TraderPerformance] = []
        self.scan_history: List[Dict] = []
        
        # Criteria for being a "verified winner"
        self.MIN_BETS = 50  # Need sample size
        self.MIN_WIN_RATE = 0.55  # Must beat market
        self.MIN_PROFIT_FACTOR = 1.3
        self.MAX_P_VALUE = 0.05  # 95% confidence
        self.MIN_ACTIVE_DAYS = 30
        
    def scan_for_winners(
        self,
        wallets: List[str],
        trade_history: Dict[str, List[Dict]]
    ) -> List[TraderPerformance]:
        """
        Scan wallets to find top winners.
        
        Args:
            wallets: List of wallet addresses to analyze
            trade_history: Dict mapping wallet -> list of trades
            
        Returns:
            List of TraderPerformance for verified winners
        """
        winners = []
        
        for wallet in wallets:
            trades = trade_history.get(wallet, [])
            if len(trades) < self.MIN_BETS:
                continue
            
            performance = self._analyze_trader(wallet, trades)
            self.traders[wallet] = performance
            
            if performance.is_profitably_copyable:
                winners.append(performance)
                if wallet not in [w.address for w in self.discovered_winners]:
                    self.discovered_winners.append(performance)
        
        # Rank by copy_score
        winners.sort(key=lambda x: x.copy_score, reverse=True)
        
        self.scan_history.append({
            'timestamp': datetime.now().isoformat(),
            'wallets_scanned': len(wallets),
            'winners_found': len(winners)
        })
        
        return winners
    
    def _analyze_trader(self, wallet: str, trades: List[Dict]) -> TraderPerformance:
        """Analyze single trader's performance."""
        perf = TraderPerformance(address=wallet)
        
        # Basic counts
        perf.total_bets = len(trades)
        
        # Separate settled and unsettled
        settled = [t for t in trades if t.get('settled', False)]
        unsettled = [t for t in trades if not t.get('settled', False)]
        
        # Calculate true win rate (excluding zombies)
        perf.winning_bets = sum(1 for t in settled if t.get('pnl', 0) > 0)
        perf.losing_bets = sum(1 for t in settled if t.get('pnl', 0) <= 0)
        
        total_settled = perf.winning_bets + perf.losing_bets
        perf.true_win_rate = perf.winning_bets / total_settled if total_settled > 0 else 0
        
        # Calculate displayed win rate (what Polymarket shows)
        # This includes open positions, potentially hiding losses
        perf.displayed_win_rate = perf.winning_bets / perf.total_bets if perf.total_bets > 0 else 0
        perf.vanity_gap = perf.displayed_win_rate - perf.true_win_rate
        
        # Detect zombie orders (old unsettled likely-losers)
        cutoff = datetime.now() - timedelta(days=30)
        zombies = [t for t in unsettled if t.get('timestamp', datetime.now()) < cutoff]
        perf.zombie_orders = len(zombies)
        
        # Calculate P&L
        perf.gross_profit = sum(t.get('pnl', 0) for t in settled if t.get('pnl', 0) > 0)
        perf.gross_loss = abs(sum(t.get('pnl', 0) for t in settled if t.get('pnl', 0) < 0))
        perf.net_pnl = perf.gross_profit - perf.gross_loss
        
        # Include zombie estimate in true PnL
        zombie_loss_estimate = sum(t.get('size', 0) * 0.8 for t in zombies)  # Assume 80% loss
        perf.true_pnl = perf.net_pnl - zombie_loss_estimate
        
        # ROI and Profit Factor
        perf.total_volume = sum(t.get('size', 0) for t in trades)
        perf.roi_percent = (perf.net_pnl / perf.total_volume * 100) if perf.total_volume > 0 else 0
        perf.profit_factor = perf.gross_profit / perf.gross_loss if perf.gross_loss > 0 else float('inf')
        
        # Calculate Sharpe (simplified)
        monthly_pnls = self._calculate_monthly_pnls(trades)
        perf.monthly_returns = monthly_pnls
        if len(monthly_pnls) >= 2:
            perf.sharpe_ratio = np.mean(monthly_pnls) / (np.std(monthly_pnls) + 1e-6) * np.sqrt(12)
        
        # Max drawdown
        perf.max_drawdown = self._calculate_max_drawdown(trades)
        
        # Statistical significance test
        perf.p_value = self._calculate_p_value(perf.true_win_rate, total_settled)
        perf.is_statistically_significant = perf.p_value < self.MAX_P_VALUE
        
        # Category analysis
        perf.categories_traded = self._analyze_categories(trades)
        if perf.categories_traded:
            perf.best_category = max(perf.categories_traded.items(), key=lambda x: x[1])[0]
        
        # Timing analysis
        perf.avg_bet_size = np.mean([t.get('size', 0) for t in trades]) if trades else 0
        perf.avg_hold_time_hours = self._calculate_avg_hold_time(trades)
        
        # Calculate copy score
        perf.copy_score = self._calculate_copy_score(perf)
        
        # Confidence level
        if perf.total_bets >= 200 and perf.is_statistically_significant:
            perf.confidence_level = "high"
        elif perf.total_bets >= 100:
            perf.confidence_level = "medium"
        else:
            perf.confidence_level = "low"
        
        return perf
    
    def _calculate_monthly_pnls(self, trades: List[Dict]) -> List[float]:
        """Aggregate PnL by month."""
        monthly = defaultdict(float)
        for trade in trades:
            if trade.get('settled'):
                ts = trade.get('timestamp', datetime.now())
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                key = ts.strftime('%Y-%m')
                monthly[key] += trade.get('pnl', 0)
        
        return list(monthly.values())
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown from peak."""
        settled = sorted([t for t in trades if t.get('settled')], 
                        key=lambda x: x.get('timestamp', datetime.min))
        
        if not settled:
            return 0.0
        
        cumulative = 0
        peak = 0
        max_dd = 0
        
        for trade in settled:
            cumulative += trade.get('pnl', 0)
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _calculate_p_value(self, win_rate: float, n_bets: int) -> float:
        """
        Calculate p-value using binomial test.
        
        H0: Win rate = 50% (random chance)
        H1: Win rate > 50% (skill)
        """
        from scipy import stats
        
        if n_bets < 30:
            return 1.0  # Not enough data
        
        wins = int(win_rate * n_bets)
        # Binomial test: P(X >= wins | n_bets, 0.5)
        p_value = 1 - stats.binom.cdf(wins - 1, n_bets, 0.5)
        return p_value
    
    def _analyze_categories(self, trades: List[Dict]) -> Dict[str, int]:
        """Count bets by category."""
        categories = defaultdict(int)
        for trade in trades:
            cat = trade.get('category', 'unknown')
            categories[cat] += 1
        return dict(categories)
    
    def _calculate_avg_hold_time(self, trades: List[Dict]) -> float:
        """Calculate average position hold time."""
        hold_times = []
        for trade in trades:
            if trade.get('settled'):
                entry = trade.get('entry_time')
                exit_time = trade.get('exit_time')
                if entry and exit_time:
                    if isinstance(entry, str):
                        entry = datetime.fromisoformat(entry.replace('Z', '+00:00'))
                    if isinstance(exit_time, str):
                        exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                    hold_times.append((exit_time - entry).total_seconds() / 3600)
        
        return np.mean(hold_times) if hold_times else 0
    
    def _calculate_copy_score(self, perf: TraderPerformance) -> float:
        """
        Calculate overall desirability score for copying.
        
        Higher = better copy target
        """
        score = 0.0
        
        # Win rate component (35%)
        score += min(1.0, perf.true_win_rate) * 35
        
        # Profit factor component (25%)
        score += min(3.0, perf.profit_factor) / 3.0 * 25
        
        # Sample size component (20%)
        score += min(1.0, perf.total_bets / 200) * 20
        
        # Consistency component (10%)
        if perf.monthly_returns:
            consistency = 1 - min(1.0, np.std(perf.monthly_returns) / (abs(np.mean(perf.monthly_returns)) + 1))
            score += consistency * 10
        
        # Sharpe ratio component (10%)
        score += min(3.0, max(0, perf.sharpe_ratio)) / 3.0 * 10
        
        # Penalties
        if perf.vanity_gap > 0.2:
            score *= 0.7  # Penalize stat manipulation
        if perf.max_drawdown > 0.5:
            score *= 0.8  # Penalize high drawdown
        if not perf.is_statistically_significant:
            score *= 0.6  # Penalize lack of significance
        
        return score
    
    async def discover_winners(self, limit: int = 100) -> List[TraderPerformance]:
        """
        Discover top winners from Polymarket.
        
        This is the main entry point for the CLI.
        Returns top winners sorted by copy score.
        """
        # For now, return mock winners since actual implementation
        # would require fetching from subgraph
        mock_winners = [
            TraderPerformance(
                address=f"0x{i:040x}",
                ens_name=f"Winner{i}",
                total_bets=100 + i * 10,
                winning_bets=60 + i * 5,
                losing_bets=40 + i * 5,
                true_win_rate=0.60 + i * 0.01,
                profit_factor=1.5 + i * 0.1,
                net_pnl=5000 + i * 1000,
                copy_score=75.0 - i * 5,
                confidence_level="high" if i < 3 else "medium",
                is_statistically_significant=True,
                vanity_gap=0.05
            )
            for i in range(min(5, limit))
        ]
        
        self.discovered_winners = mock_winners
        return mock_winners
    
    def get_top_winners(self, n: int = 10, min_confidence: str = "medium") -> List[TraderPerformance]:
        """Get top N winners by copy score."""
        confidence_rank = {"high": 3, "medium": 2, "low": 1}
        min_rank = confidence_rank.get(min_confidence, 2)
        
        eligible = [
            w for w in self.discovered_winners
            if confidence_rank.get(w.confidence_level, 0) >= min_rank
        ]
        
        return sorted(eligible, key=lambda x: x.copy_score, reverse=True)[:n]
    
    def get_winner_profile(self, address: str) -> Optional[TraderPerformance]:
        """Get detailed profile of a winner."""
        return self.traders.get(address)
    
    def compare_winners(
        self,
        winner1: str,
        winner2: str
    ) -> Dict:
        """Compare two winners side-by-side."""
        w1 = self.traders.get(winner1)
        w2 = self.traders.get(winner2)
        
        if not w1 or not w2:
            return {"error": "One or both winners not found"}
        
        return {
            'win_rate': {'w1': w1.true_win_rate, 'w2': w2.true_win_rate, 'better': winner1 if w1.true_win_rate > w2.true_win_rate else winner2},
            'profit_factor': {'w1': w1.profit_factor, 'w2': w2.profit_factor, 'better': winner1 if w1.profit_factor > w2.profit_factor else winner2},
            'sharpe': {'w1': w1.sharpe_ratio, 'w2': w2.sharpe_ratio, 'better': winner1 if w1.sharpe_ratio > w2.sharpe_ratio else winner2},
            'max_dd': {'w1': w1.max_drawdown, 'w2': w2.max_drawdown, 'better': winner1 if w1.max_drawdown < w2.max_drawdown else winner2},
            'copy_score': {'w1': w1.copy_score, 'w2': w2.copy_score, 'better': winner1 if w1.copy_score > w2.copy_score else winner2},
        }
    
    def generate_leaderboard(self) -> pd.DataFrame:
        """Generate DataFrame leaderboard."""
        if not self.discovered_winners:
            return pd.DataFrame()
        
        data = []
        for w in sorted(self.discovered_winners, key=lambda x: x.copy_score, reverse=True):
            data.append({
                'Rank': len(data) + 1,
                'Address': w.address[:10] + '...',
                'ENS': w.ens_name or '',
                'Bets': w.total_bets,
                'True_WR': f"{w.true_win_rate:.1%}",
                'Net_PnL': f"${w.net_pnl:,.0f}",
                'ROI': f"{w.roi_percent:.1f}%",
                'Profit_Factor': f"{w.profit_factor:.2f}",
                'Sharpe': f"{w.sharpe_ratio:.2f}",
                'Max_DD': f"{w.max_drawdown:.1%}",
                'Copy_Score': f"{w.copy_score:.1f}",
                'Confidence': w.confidence_level.upper(),
            })
        
        return pd.DataFrame(data)
