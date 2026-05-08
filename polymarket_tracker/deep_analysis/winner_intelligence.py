"""
Winner Intelligence - Deep Profile Analysis

Comprehensive analysis of top betters including:
- Complete trade history analysis
- Behavioral pattern recognition
- Edge decomposition (where do they win?)
- Risk profile analysis
- Temporal patterns (time of day, day of week)
- Market condition preferences
- Psychological profiling
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json


@dataclass
class DeepWinnerProfile:
    """Comprehensive intelligence profile of a winning trader."""
    
    # Identity
    address: str
    ens_name: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    
    # Core Performance Metrics
    total_bets: int = 0
    winning_bets: int = 0
    losing_bets: int = 0
    push_bets: int = 0
    
    # Win Rate Analysis
    overall_win_rate: float = 0.0
    win_rate_by_category: Dict[str, float] = field(default_factory=dict)
    win_rate_by_market_type: Dict[str, float] = field(default_factory=dict)
    win_rate_by_price_range: Dict[str, float] = field(default_factory=dict)
    win_rate_by_time: Dict[str, float] = field(default_factory=dict)
    
    # Profitability Deep Dive
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    adjusted_pnl: float = 0.0  # After fees, slippage, opportunity cost
    
    profit_factor: float = 0.0
    risk_adjusted_return: float = 0.0
    expectancy_per_trade: float = 0.0
    
    # Return Distribution
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    win_loss_ratio: float = 0.0
    
    # Risk Metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    recovery_factor: float = 0.0
    
    # Volatility Analysis
    daily_volatility: float = 0.0
    monthly_volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk
    cvar_95: float = 0.0  # Conditional VaR
    
    # Behavioral Patterns
    avg_bet_size: float = 0.0
    median_bet_size: float = 0.0
    max_bet_size: float = 0.0
    bet_size_volatility: float = 0.0
    
    position_sizing_strategy: str = "unknown"  # kelly, fixed, martingale, etc.
    staking_pattern: str = "unknown"  # consistent, increasing, decreasing
    
    # Timing Patterns
    avg_hold_time: timedelta = field(default_factory=lambda: timedelta(0))
    hold_time_distribution: Dict[str, float] = field(default_factory=dict)
    
    preferred_hours: List[int] = field(default_factory=list)
    preferred_days: List[str] = field(default_factory=list)
    preferred_months: List[int] = field(default_factory=list)
    
    entry_timing_quality: float = 0.0  # How well do they time entries?
    exit_timing_quality: float = 0.0
    
    # Market Selection
    categories_traded: Dict[str, int] = field(default_factory=dict)
    best_category: Optional[str] = None
    worst_category: Optional[str] = None
    category_specialization_score: float = 0.0
    
    market_types: Dict[str, int] = field(default_factory=dict)
    preferred_odds_range: Tuple[float, float] = (0.0, 1.0)
    
    # Edge Decomposition
    edge_by_category: Dict[str, float] = field(default_factory=dict)
    edge_by_time: Dict[str, float] = field(default_factory=dict)
    edge_by_market_size: Dict[str, float] = field(default_factory=dict)
    edge_by_liquidity: Dict[str, float] = field(default_factory=dict)
    
    information_advantage_score: float = 0.0
    speed_advantage_score: float = 0.0
    analytical_advantage_score: float = 0.0
    
    # Streak Analysis
    current_streak: int = 0
    longest_win_streak: int = 0
    longest_loss_streak: int = 0
    streak_sensitivity: float = 0.0  # How do they perform after streaks?
    
    # Market Conditions
    performance_in_volatile_markets: float = 0.0
    performance_in_trending_markets: float = 0.0
    performance_in_ranging_markets: float = 0.0
    
    adaptability_score: float = 0.0
    regime_detection_ability: float = 0.0
    
    # Quality Metrics
    trade_quality_score: float = 0.0
    consistency_score: float = 0.0
    improvement_trajectory: str = "stable"  # improving, declining, stable
    
    # Copy Trading Suitability
    copy_score: float = 0.0
    copy_confidence: str = "low"
    optimal_copy_delay: int = 0  # seconds to wait before copying
    replication_quality_estimate: float = 0.0
    
    # Risk Flags
    red_flags: List[str] = field(default_factory=list)
    yellow_flags: List[str] = field(default_factory=list)
    green_flags: List[str] = field(default_factory=list)
    
    # Raw Data
    trade_history: List[Dict] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Metadata
    first_trade_date: Optional[datetime] = None
    last_trade_date: Optional[datetime] = None
    analysis_date: datetime = field(default_factory=datetime.now)
    data_quality_score: float = 0.0


class WinnerIntelligence:
    """
    Deep intelligence analysis of winning traders.
    
    Analyzes everything: performance, behavior, timing, edge sources.
    """
    
    def __init__(self, subgraph_client=None):
        self.subgraph = subgraph_client
        self.profiles: Dict[str, DeepWinnerProfile] = {}
        self.analysis_cache: Dict[str, Dict] = {}
        
    def analyze_winner(self, address: str, trade_history: List[Dict]) -> DeepWinnerProfile:
        """
        Perform comprehensive analysis of a trader.
        
        Args:
            address: Wallet address
            trade_history: Complete list of trades
            
        Returns:
            DeepWinnerProfile with full analysis
        """
        print(f"  [Analysis] Deep profiling {address[:12]}...")
        
        profile = DeepWinnerProfile(address=address)
        
        if not trade_history:
            return profile
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(trade_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Basic counts
        profile.total_bets = len(df)
        profile.winning_bets = len(df[df['pnl'] > 0])
        profile.losing_bets = len(df[df['pnl'] < 0])
        profile.push_bets = len(df[df['pnl'] == 0])
        
        # Win rates
        profile.overall_win_rate = profile.winning_bets / (profile.winning_bets + profile.losing_bets) if (profile.winning_bets + profile.losing_bets) > 0 else 0
        
        # Win rate by category
        if 'category' in df.columns:
            for cat in df['category'].unique():
                cat_df = df[df['category'] == cat]
                wins = len(cat_df[cat_df['pnl'] > 0])
                losses = len(cat_df[cat_df['pnl'] < 0])
                if wins + losses > 0:
                    profile.win_rate_by_category[cat] = wins / (wins + losses)
                    profile.edge_by_category[cat] = cat_df['pnl'].sum() / len(cat_df)
        
        # Win rate by price range
        if 'price' in df.columns:
            df['price_range'] = pd.cut(df['price'], bins=[0, 0.3, 0.5, 0.7, 1.0], labels=['0-30%', '30-50%', '50-70%', '70-100%'])
            for range_label in df['price_range'].unique():
                if pd.isna(range_label):
                    continue
                range_df = df[df['price_range'] == range_label]
                wins = len(range_df[range_df['pnl'] > 0])
                losses = len(range_df[range_df['pnl'] < 0])
                if wins + losses > 0:
                    profile.win_rate_by_price_range[str(range_label)] = wins / (wins + losses)
        
        # Win rate by time
        df['hour'] = df['timestamp'].dt.hour
        df['day'] = df['timestamp'].dt.day_name()
        
        for hour in range(24):
            hour_df = df[df['hour'] == hour]
            if len(hour_df) > 5:  # Minimum sample size
                wins = len(hour_df[hour_df['pnl'] > 0])
                losses = len(hour_df[hour_df['pnl'] < 0])
                if wins + losses > 0:
                    profile.win_rate_by_time[f"{hour:02d}:00"] = wins / (wins + losses)
        
        # Profitability
        profile.gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        profile.gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        profile.net_pnl = df['pnl'].sum()
        profile.profit_factor = profile.gross_profit / profile.gross_loss if profile.gross_loss > 0 else float('inf')
        
        # Return distribution
        wins = df[df['pnl'] > 0]['pnl']
        losses = df[df['pnl'] < 0]['pnl']
        
        profile.avg_win = wins.mean() if len(wins) > 0 else 0
        profile.avg_loss = losses.mean() if len(losses) > 0 else 0
        profile.largest_win = wins.max() if len(wins) > 0 else 0
        profile.largest_loss = losses.min() if len(losses) > 0 else 0
        profile.win_loss_ratio = abs(profile.avg_win / profile.avg_loss) if profile.avg_loss != 0 else 0
        
        # Expectancy
        profile.expectancy_per_trade = (
            profile.overall_win_rate * profile.avg_win - 
            (1 - profile.overall_win_rate) * abs(profile.avg_loss)
        )
        
        # Calculate equity curve and risk metrics
        df['cumulative_pnl'] = df['pnl'].cumsum()
        profile.equity_curve = list(zip(df['timestamp'], df['cumulative_pnl']))
        
        # Max drawdown
        rolling_max = df['cumulative_pnl'].expanding().max()
        drawdown = df['cumulative_pnl'] - rolling_max
        profile.max_drawdown = abs(drawdown.min())
        
        # Sharpe ratio (simplified)
        returns = df['pnl'] / df['size'] if 'size' in df.columns else df['pnl']
        if len(returns) > 1 and returns.std() > 0:
            profile.sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
        
        # Sortino (downside deviation only)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            profile.sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(252)
        
        # Bet sizing
        if 'size' in df.columns:
            profile.avg_bet_size = df['size'].mean()
            profile.median_bet_size = df['size'].median()
            profile.max_bet_size = df['size'].max()
            profile.bet_size_volatility = df['size'].std() / df['size'].mean() if df['size'].mean() > 0 else 0
            
            # Determine sizing strategy
            if profile.bet_size_volatility < 0.2:
                profile.position_sizing_strategy = "fixed"
            elif df['size'].corr(df['cumulative_pnl']) > 0.3:
                profile.position_sizing_strategy = "kelly_progressive"
            else:
                profile.position_sizing_strategy = "variable"
        
        # Hold time analysis
        if 'exit_time' in df.columns:
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df['hold_time'] = (df['exit_time'] - df['timestamp']).dt.total_seconds() / 3600
            profile.avg_hold_time = timedelta(hours=df['hold_time'].mean())
            
            # Hold time distribution
            profile.hold_time_distribution = {
                '< 1 hour': len(df[df['hold_time'] < 1]) / len(df),
                '1-6 hours': len(df[(df['hold_time'] >= 1) & (df['hold_time'] < 6)]) / len(df),
                '6-24 hours': len(df[(df['hold_time'] >= 6) & (df['hold_time'] < 24)]) / len(df),
                '1-7 days': len(df[(df['hold_time'] >= 24) & (df['hold_time'] < 168)]) / len(df),
                '> 7 days': len(df[df['hold_time'] >= 168]) / len(df)
            }
        
        # Preferred hours (top 3)
        hourly_performance = df.groupby('hour')['pnl'].mean()
        profile.preferred_hours = hourly_performance.nlargest(3).index.tolist()
        
        # Preferred days
        daily_performance = df.groupby('day')['pnl'].mean()
        profile.preferred_days = daily_performance.nlargest(3).index.tolist()
        
        # Streak analysis
        df['streak'] = (df['pnl'] > 0).astype(int)
        df['streak_group'] = (df['streak'] != df['streak'].shift()).cumsum()
        streaks = df.groupby('streak_group')['streak'].sum()
        
        win_streaks = streaks[streaks > 0]
        loss_streaks = streaks[streaks == 0]
        
        profile.longest_win_streak = win_streaks.max() if len(win_streaks) > 0 else 0
        profile.longest_loss_streak = len(loss_streaks) if len(loss_streaks) > 0 else 0
        profile.current_streak = df['streak'].iloc[-5:].sum() if len(df) >= 5 else 0
        
        # Best/worst category
        if profile.win_rate_by_category:
            profile.best_category = max(profile.win_rate_by_category.items(), key=lambda x: x[1])[0]
            profile.worst_category = min(profile.win_rate_by_category.items(), key=lambda x: x[1])[0]
        
        # Information advantage score
        # If they consistently beat the closing line, they have info advantage
        if 'closing_price' in df.columns and 'entry_price' in df.columns:
            line_beats = len(df[abs(df['closing_price'] - df['entry_price']) > 0.02])
            profile.information_advantage_score = line_beats / len(df)
        
        # Timing quality
        if 'market_open_time' in df.columns:
            df['time_from_open'] = (df['timestamp'] - df['market_open_time']).dt.total_seconds()
            early_entries = len(df[df['time_from_open'] < 3600])  # Within 1 hour
            profile.entry_timing_quality = early_entries / len(df)
        
        # Copy score calculation
        profile.copy_score = self._calculate_copy_score(profile)
        
        # Determine copy confidence
        if profile.total_bets >= 200 and profile.sharpe_ratio > 1.5:
            profile.copy_confidence = "very_high"
        elif profile.total_bets >= 100 and profile.sharpe_ratio > 1.0:
            profile.copy_confidence = "high"
        elif profile.total_bets >= 50 and profile.profit_factor > 1.5:
            profile.copy_confidence = "medium"
        else:
            profile.copy_confidence = "low"
        
        # Flags
        if profile.vanity_gap > 0.2:
            profile.red_flags.append("High vanity gap - may be manipulating stats")
        
        if profile.max_drawdown > 0.5:
            profile.red_flags.append("Severe drawdown history")
        
        if profile.sharpe_ratio > 2.0 and profile.profit_factor > 2.0:
            profile.green_flags.append("Exceptional risk-adjusted returns")
        
        if profile.information_advantage_score > 0.7:
            profile.green_flags.append("Consistently beats closing line")
        
        # Store
        self.profiles[address] = profile
        
        print(f"    ✓ Analysis complete: {profile.copy_confidence.upper()} confidence (Score: {profile.copy_score:.1f})")
        
        return profile
    
    def _calculate_copy_score(self, profile: DeepWinnerProfile) -> float:
        """Calculate comprehensive copy trading score."""
        score = 0.0
        
        # Win rate quality (20%)
        score += min(1.0, profile.overall_win_rate / 0.65) * 20
        
        # Profit factor (20%)
        score += min(1.0, profile.profit_factor / 2.0) * 20
        
        # Sharpe ratio (15%)
        score += min(1.0, max(0, profile.sharpe_ratio) / 2.0) * 15
        
        # Sample size (15%)
        score += min(1.0, profile.total_bets / 200) * 15
        
        # Consistency (10%)
        if profile.monthly_returns:
            consistency = 1 - min(1.0, np.std(profile.monthly_returns) / (abs(np.mean(profile.monthly_returns)) + 0.01))
            score += consistency * 10
        
        # Expectancy (10%)
        expectancy_score = min(1.0, max(0, profile.expectancy_per_trade) / 100)
        score += expectancy_score * 10
        
        # Information advantage (10%)
        score += profile.information_advantage_score * 10
        
        # Penalties
        if profile.max_drawdown > 0.4:
            score *= 0.8
        
        if profile.vanity_gap > 0.15:
            score *= 0.9
        
        return score
    
    def compare_winners(self, address1: str, address2: str) -> Dict:
        """Detailed comparison of two winners."""
        p1 = self.profiles.get(address1)
        p2 = self.profiles.get(address2)
        
        if not p1 or not p2:
            return {"error": "One or both profiles not found"}
        
        return {
            "win_rate": {"p1": p1.overall_win_rate, "p2": p2.overall_win_rate, "better": address1 if p1.overall_win_rate > p2.overall_win_rate else address2},
            "sharpe": {"p1": p1.sharpe_ratio, "p2": p2.sharpe_ratio, "better": address1 if p1.sharpe_ratio > p2.sharpe_ratio else address2},
            "profit_factor": {"p1": p1.profit_factor, "p2": p2.profit_factor, "better": address1 if p1.profit_factor > p2.profit_factor else address2},
            "max_dd": {"p1": p1.max_drawdown, "p2": p2.max_drawdown, "better": address1 if p1.max_drawdown < p2.max_drawdown else address2},
            "expectancy": {"p1": p1.expectancy_per_trade, "p2": p2.expectancy_per_trade, "better": address1 if p1.expectancy_per_trade > p2.expectancy_per_trade else address2},
            "copy_score": {"p1": p1.copy_score, "p2": p2.copy_score, "better": address1 if p1.copy_score > p2.copy_score else address2},
        }
    
    def generate_report(self, address: str) -> str:
        """Generate human-readable analysis report."""
        profile = self.profiles.get(address)
        if not profile:
            return "Profile not found"
        
        lines = []
        lines.append("=" * 80)
        lines.append(f"DEEP INTELLIGENCE REPORT: {profile.ens_name or address[:16]}...")
        lines.append("=" * 80)
        
        lines.append(f"\n[PERFORMANCE SUMMARY]")
        lines.append(f"  Total Bets: {profile.total_bets}")
        lines.append(f"  Win Rate: {profile.overall_win_rate:.1%} ({profile.winning_bets}W/{profile.losing_bets}L)")
        lines.append(f"  Net P&L: ${profile.net_pnl:,.2f}")
        lines.append(f"  Profit Factor: {profile.profit_factor:.2f}")
        lines.append(f"  Sharpe Ratio: {profile.sharpe_ratio:.2f}")
        lines.append(f"  Max Drawdown: {profile.max_drawdown:.1%}")
        
        lines.append(f"\n[COPY TRADING SUITABILITY]")
        lines.append(f"  Copy Score: {profile.copy_score:.1f}/100")
        lines.append(f"  Confidence: {profile.copy_confidence.upper()}")
        lines.append(f"  Expectancy per Trade: ${profile.expectancy_per_trade:.2f}")
        
        if profile.best_category:
            lines.append(f"\n[EDGE ANALYSIS]")
            lines.append(f"  Best Category: {profile.best_category} ({profile.win_rate_by_category.get(profile.best_category, 0):.1%} WR)")
            lines.append(f"  Preferred Hours: {', '.join(map(str, profile.preferred_hours))}")
            lines.append(f"  Avg Hold Time: {profile.avg_hold_time}")
            lines.append(f"  Information Advantage: {profile.information_advantage_score:.1%}")
        
        if profile.green_flags:
            lines.append(f"\n[GREEN FLAGS]")
            for flag in profile.green_flags:
                lines.append(f"  ✓ {flag}")
        
        if profile.red_flags:
            lines.append(f"\n[RED FLAGS]")
            for flag in profile.red_flags:
                lines.append(f"  ✗ {flag}")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
