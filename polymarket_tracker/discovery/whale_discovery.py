"""
Real-time Whale Discovery Module

Discovers high-performing whales from TheGraph in real-time.
Provides comprehensive whale analysis, filtering, ranking, and monitoring.

Features:
- Active whale discovery from recent trading activity
- Performance-based discovery with statistical significance
- Pattern-based whale discovery
- Crypto-specialized whale discovery
- Deep performance analysis (win rate, profit factor, Sharpe ratio)
- Statistical filtering and copy score ranking
- Vanity gap detection for stat manipulation
- Real-time monitoring with notifications
"""

import asyncio
import logging
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable

import numpy as np
import pandas as pd
from gql import gql

from ..data.subgraph_client import SubgraphClient
from ..data.database import TradeDatabase, WhaleProfile as DBWhaleProfile
from ..streaming.crypto_filter import CryptoMarketFilter
from ..notifications.notification_manager import NotificationManager, NotificationType
from ..utils.logger import setup_logging

logger = setup_logging()


class PatternType(Enum):
    """Trading pattern types for whale discovery."""
    MOMENTUM_BURST = "momentum_burst"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    LIQUIDITY_GRAB = "liquidity_grab"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    SWING_TRADING = "swing_trading"
    SCALPING = "scalping"
    ARBITRAGE = "arbitrage"


@dataclass
class WhaleProfile:
    """
    Comprehensive whale profile for discovery and analysis.
    
    Attributes:
        address: Ethereum wallet address
        ens_name: ENS name if available
        labels: Known labels/tags for this whale
        total_bets: Total number of bets placed
        win_rate: True win rate (0-1)
        profit_factor: Gross profit / gross loss
        sharpe_ratio: Risk-adjusted return metric
        pnl: Total profit/loss in USD
        max_drawdown: Maximum peak-to-trough decline
        risk_of_ruin: Probability of losing entire bankroll
        behavioral_patterns: Detected trading patterns
        optimal_copy_window: Best time window for copying
        is_statistically_significant: Has enough data to be reliable
        vanity_gap: Difference between displayed and true win rate
        copy_score: Composite score for copy desirability (0-100)
        rank: Current rank among discovered whales
        first_seen: When this whale was first observed
        last_seen: When this whale was last active
        avg_trade_size: Average position size
        total_volume: Total trading volume
        crypto_specialization: Crypto market focus percentage
        reliability_tier: Bronze/Silver/Gold/Platinum classification
    """
    # Identity
    address: str
    ens_name: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    
    # Core Performance
    total_bets: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Risk Metrics
    pnl: float = 0.0
    max_drawdown: float = 0.0
    risk_of_ruin: float = 0.0
    
    # Behavioral Analysis
    behavioral_patterns: List[PatternType] = field(default_factory=list)
    optimal_copy_window: Optional[Tuple[int, int]] = None  # (start_hour, end_hour)
    
    # Quality Metrics
    is_statistically_significant: bool = False
    vanity_gap: float = 0.0
    
    # Copy Trading
    copy_score: float = 0.0
    rank: int = 0
    
    # Activity Tracking
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    avg_trade_size: float = 0.0
    total_volume: float = 0.0
    
    # Specialization
    crypto_specialization: float = 0.0  # 0-1 percentage
    reliability_tier: str = "unverified"
    
    # Additional Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.now)
    last_analyzed: Optional[datetime] = None


@dataclass
class DiscoveryConfig:
    """Configuration for whale discovery."""
    # Volume thresholds
    min_volume_usd: float = 10000.0
    min_trade_size: float = 1000.0
    
    # Performance thresholds
    min_win_rate: float = 0.52
    min_profit_factor: float = 1.2
    min_sharpe_ratio: float = 0.5
    
    # Statistical significance
    min_trades_for_significance: int = 30
    min_days_active: int = 7
    
    # Copy score weights
    win_rate_weight: float = 0.25
    profit_factor_weight: float = 0.25
    sharpe_weight: float = 0.20
    consistency_weight: float = 0.15
    sample_size_weight: float = 0.15
    
    # Discovery intervals
    active_discovery_interval: int = 300  # 5 minutes
    full_discovery_interval: int = 3600  # 1 hour
    
    # Notification settings
    notify_on_new_whale: bool = True
    notify_on_top_performer: bool = True
    min_copy_score_for_notification: float = 70.0


class WhaleDiscovery:
    """
    Real-time whale discovery and analysis system.
    
    Discovers high-performing traders from TheGraph subgraphs,
    analyzes their performance, and provides ranking/filtering
    for copy trading decisions.
    
    Example:
        discovery = WhaleDiscovery(api_key="your_api_key")
        
        # Discover active whales
        whales = await discovery.discover_active_whales(
            min_volume=50000,
            min_trades=20
        )
        
        # Start continuous monitoring
        await discovery.start_discovery_monitoring(interval=300)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[DiscoveryConfig] = None,
        database: Optional[TradeDatabase] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        """
        Initialize whale discovery system.
        
        Args:
            api_key: TheGraph API key (or from env)
            config: Discovery configuration
            database: TradeDatabase instance for persistence
            notification_manager: For sending notifications
        """
        self.config = config or DiscoveryConfig()
        self.subgraph = SubgraphClient(api_key) if api_key else None
        self.database = database
        self.crypto_filter = CryptoMarketFilter()
        self.notifications = notification_manager
        
        # Internal state
        self.discovered_whales: Dict[str, WhaleProfile] = {}
        self.monitored_whales: Set[str] = set()
        self.discovery_history: List[Dict] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = asyncio.Event()
        
        # Caches
        self._trades_cache: Dict[str, pd.DataFrame] = {}
        self._last_discovery_time: Optional[datetime] = None
        
        logger.info("WhaleDiscovery initialized")
    
    async def discover_active_whales(
        self,
        min_volume: Optional[float] = None,
        min_trades: int = 10,
        lookback_hours: int = 24
    ) -> List[WhaleProfile]:
        """
        Discover whales based on recent trading activity.
        
        Queries TheGraph for wallets with significant recent volume
        and returns their profiles.
        
        Args:
            min_volume: Minimum USD volume (uses config default if None)
            min_trades: Minimum number of recent trades
            lookback_hours: How far back to look for activity
            
        Returns:
            List of WhaleProfile for active whales
        """
        if not self.subgraph:
            logger.error("Subgraph client not initialized")
            return []
        
        min_volume = min_volume or self.config.min_volume_usd
        since_timestamp = int((datetime.now() - timedelta(hours=lookback_hours)).timestamp())
        
        logger.info(f"Discovering active whales since {since_timestamp}")
        
        try:
            # Query for recent high-volume traders
            query = gql("""
                query GetActiveTraders($since: Int!, $minSize: BigDecimal!) {
                    trades(
                        where: { timestamp_gt: $since, size_gt: $minSize }
                        first: 1000
                        orderBy: timestamp
                        orderDirection: desc
                    ) {
                        user { id }
                        market { id question category }
                        size
                        price
                        side
                        pnl
                        timestamp
                    }
                }
            """)
            
            result = await asyncio.to_thread(
                self.subgraph._execute,
                'positions',
                query,
                {'since': since_timestamp, 'minSize': str(min_volume / 10)}
            )
            
            trades = result.get('trades', [])
            
            # Aggregate by wallet
            wallet_stats = defaultdict(lambda: {
                'trades': [],
                'total_volume': 0.0,
                'markets': set(),
                'last_trade': 0
            })
            
            for trade in trades:
                user = trade.get('user', {})
                wallet = user.get('id', '').lower() if user else ''
                if not wallet:
                    continue
                
                size = float(trade.get('size', 0) or 0)
                pnl = float(trade.get('pnl', 0) or 0)
                timestamp = int(trade.get('timestamp', 0) or 0)
                
                wallet_stats[wallet]['trades'].append({
                    'size': size,
                    'pnl': pnl,
                    'price': float(trade.get('price', 0) or 0),
                    'side': trade.get('side', ''),
                    'market': trade.get('market', {}),
                    'timestamp': timestamp
                })
                wallet_stats[wallet]['total_volume'] += size
                wallet_stats[wallet]['markets'].add(trade.get('market', {}).get('id', ''))
                wallet_stats[wallet]['last_trade'] = max(wallet_stats[wallet]['last_trade'], timestamp)
            
            # Filter and create profiles
            profiles = []
            for wallet, stats in wallet_stats.items():
                if (len(stats['trades']) >= min_trades and 
                    stats['total_volume'] >= min_volume):
                    
                    profile = await self.analyze_whale_performance(
                        wallet,
                        days=lookback_hours // 24 + 1
                    )
                    
                    if profile and profile.total_bets >= min_trades:
                        profiles.append(profile)
                        self.discovered_whales[wallet] = profile
            
            logger.info(f"Discovered {len(profiles)} active whales")
            return profiles
            
        except Exception as e:
            logger.error(f"Error in discover_active_whales: {e}")
            return []
    
    async def discover_by_performance(
        self,
        days: int = 30,
        min_win_rate: Optional[float] = None,
        min_profit_factor: Optional[float] = None,
        top_n: int = 100
    ) -> List[WhaleProfile]:
        """
        Discover whales by historical performance metrics.
        
        Args:
            days: Number of days to analyze
            min_win_rate: Minimum win rate (0-1)
            min_profit_factor: Minimum profit factor
            top_n: Maximum number of whales to return
            
        Returns:
            List of high-performing whale profiles
        """
        min_win_rate = min_win_rate or self.config.min_win_rate
        min_profit_factor = min_profit_factor or self.config.min_profit_factor
        
        logger.info(f"Discovering whales by performance (last {days} days)")
        
        try:
            # Get all users with significant volume in period
            since_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
            
            # Query for high-volume traders
            query = gql("""
                query GetPerformanceTraders($since: Int!) {
                    users(
                        where: { totalVolume_gt: "10000", lastTradeTimestamp_gt: $since }
                        first: 500
                        orderBy: totalVolume
                        orderDirection: desc
                    ) {
                        id
                        totalVolume
                        totalPnL
                        totalTrades
                        winningTrades
                        losingTrades
                        lastTradeTimestamp
                    }
                }
            """)
            
            result = await asyncio.to_thread(
                self.subgraph._execute,
                'pnl',
                query,
                {'since': since_timestamp}
            )
            
            users = result.get('users', [])
            profiles = []
            
            for user in users:
                address = user.get('id', '').lower()
                if not address:
                    continue
                
                total_trades = int(user.get('totalTrades', 0) or 0)
                winning_trades = int(user.get('winningTrades', 0) or 0)
                losing_trades = int(user.get('losingTrades', 0) or 0)
                
                if total_trades < self.config.min_trades_for_significance:
                    continue
                
                # Calculate metrics
                win_rate = winning_trades / (winning_trades + losing_trades) if (winning_trades + losing_trades) > 0 else 0
                
                # Get detailed analysis for qualifying traders
                if win_rate >= min_win_rate:
                    profile = await self.analyze_whale_performance(address, days=days)
                    
                    if (profile and 
                        profile.win_rate >= min_win_rate and 
                        profile.profit_factor >= min_profit_factor):
                        profiles.append(profile)
                        self.discovered_whales[address] = profile
            
            # Sort by copy score and limit
            profiles.sort(key=lambda p: p.copy_score, reverse=True)
            
            logger.info(f"Discovered {len(profiles)} high-performance whales")
            return profiles[:top_n]
            
        except Exception as e:
            logger.error(f"Error in discover_by_performance: {e}")
            return []
    
    async def discover_pattern_whales(
        self,
        pattern_type: PatternType,
        days: int = 30,
        min_examples: int = 5
    ) -> List[WhaleProfile]:
        """
        Discover whales exhibiting specific trading patterns.
        
        Args:
            pattern_type: Type of pattern to detect
            days: Analysis period
            min_examples: Minimum pattern examples required
            
        Returns:
            List of whales showing the specified pattern
        """
        logger.info(f"Discovering whales with pattern: {pattern_type.value}")
        
        try:
            # First get candidate whales
            candidates = await self.discover_by_performance(days=days, top_n=200)
            
            pattern_whales = []
            
            for whale in candidates:
                trades = await self._get_whale_trades(whale.address, days)
                
                if self._detect_pattern(trades, pattern_type, min_examples):
                    whale.behavioral_patterns.append(pattern_type)
                    pattern_whales.append(whale)
            
            logger.info(f"Found {len(pattern_whales)} whales with pattern {pattern_type.value}")
            return pattern_whales
            
        except Exception as e:
            logger.error(f"Error in discover_pattern_whales: {e}")
            return []
    
    async def discover_crypto_whales(
        self,
        min_crypto_percentage: float = 0.4,
        days: int = 30
    ) -> List[WhaleProfile]:
        """
        Discover whales specializing in crypto markets.
        
        Args:
            min_crypto_percentage: Minimum ratio of crypto trades (0-1)
            days: Analysis period
            
        Returns:
            List of crypto-specialized whale profiles
        """
        logger.info("Discovering crypto-specialized whales")
        
        try:
            # Get candidate whales
            candidates = await self.discover_by_performance(days=days, top_n=200)
            
            crypto_whales = []
            
            for whale in candidates:
                trades = await self._get_whale_trades(whale.address, days)
                
                # Analyze market categories
                crypto_trades = 0
                total_trades = len(trades)
                
                for _, trade in trades.iterrows():
                    market = trade.get('market', {})
                    question = market.get('question', '')
                    
                    if self.crypto_filter.classify_market(question).is_crypto:
                        crypto_trades += 1
                
                crypto_pct = crypto_trades / total_trades if total_trades > 0 else 0
                
                if crypto_pct >= min_crypto_percentage:
                    whale.crypto_specialization = crypto_pct
                    crypto_whales.append(whale)
            
            # Sort by crypto specialization
            crypto_whales.sort(key=lambda w: w.crypto_specialization, reverse=True)
            
            logger.info(f"Discovered {len(crypto_whales)} crypto-specialized whales")
            return crypto_whales
            
        except Exception as e:
            logger.error(f"Error in discover_crypto_whales: {e}")
            return []
    
    async def analyze_whale_performance(
        self,
        address: str,
        days: int = 30
    ) -> Optional[WhaleProfile]:
        """
        Perform deep performance analysis of a whale.
        
        Args:
            address: Whale wallet address
            days: Analysis period
            
        Returns:
            WhaleProfile with complete analysis or None if insufficient data
        """
        address = address.lower()
        
        try:
            # Get all trades
            trades = await self._get_whale_trades(address, days)
            
            if len(trades) < self.config.min_trades_for_significance:
                logger.debug(f"Insufficient trades for {address}: {len(trades)}")
                return None
            
            # Calculate core metrics
            win_rate = self.calculate_win_rate(trades)
            profit_factor = self.calculate_profit_factor(trades)
            
            # Calculate returns for Sharpe
            returns = trades['pnl'] / trades['size'] if 'size' in trades.columns else trades['pnl']
            sharpe_ratio = self.calculate_sharpe_ratio(returns)
            
            # Calculate PnL and drawdown
            pnl = trades['pnl'].sum()
            max_drawdown = self._calculate_max_drawdown(trades)
            
            # Calculate vanity gap
            displayed_wr = trades[trades['pnl'].notna()]['pnl'].gt(0).mean()
            true_wr = win_rate
            vanity_gap = max(0, displayed_wr - true_wr)
            
            # Calculate copy score
            copy_score = self._calculate_copy_score(
                win_rate, profit_factor, sharpe_ratio, len(trades), trades
            )
            
            # Determine tier
            tier = self._determine_tier(win_rate, profit_factor, len(trades))
            
            # Check statistical significance
            is_significant = (
                len(trades) >= self.config.min_trades_for_significance and
                win_rate > self.config.min_win_rate and
                profit_factor > self.config.min_profit_factor
            )
            
            # Find optimal copy window
            optimal_window = self._find_optimal_copy_window(trades)
            
            # Detect patterns
            patterns = self._detect_all_patterns(trades)
            
            # Calculate risk of ruin
            risk_of_ruin = self._calculate_risk_of_ruin(trades, win_rate)
            
            # Build profile
            profile = WhaleProfile(
                address=address,
                total_bets=len(trades),
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                pnl=pnl,
                max_drawdown=max_drawdown,
                risk_of_ruin=risk_of_ruin,
                behavioral_patterns=patterns,
                optimal_copy_window=optimal_window,
                is_statistically_significant=is_significant,
                vanity_gap=vanity_gap,
                copy_score=copy_score,
                first_seen=trades['timestamp'].min() if 'timestamp' in trades.columns else None,
                last_seen=trades['timestamp'].max() if 'timestamp' in trades.columns else None,
                avg_trade_size=trades['size'].mean() if 'size' in trades.columns else 0,
                total_volume=trades['size'].sum() if 'size' in trades.columns else 0,
                reliability_tier=tier,
                last_analyzed=datetime.now()
            )
            
            # Save to database
            if self.database:
                await self._save_to_database(profile)
            
            return profile
            
        except Exception as e:
            logger.error(f"Error analyzing whale {address}: {e}")
            return None
    
    def calculate_win_rate(self, trades: pd.DataFrame) -> float:
        """
        Calculate true win rate from trades.
        
        Args:
            trades: DataFrame with trade data (must have 'pnl' column)
            
        Returns:
            Win rate as decimal (0-1)
        """
        if trades.empty or 'pnl' not in trades.columns:
            return 0.0
        
        settled = trades[trades['pnl'].notna()]
        if settled.empty:
            return 0.0
        
        wins = (settled['pnl'] > 0).sum()
        total = len(settled)
        
        return wins / total if total > 0 else 0.0
    
    def calculate_profit_factor(self, trades: pd.DataFrame) -> float:
        """
        Calculate profit factor (gross profit / gross loss).
        
        Args:
            trades: DataFrame with trade data
            
        Returns:
            Profit factor (> 1.0 is profitable)
        """
        if trades.empty or 'pnl' not in trades.columns:
            return 0.0
        
        gross_profit = trades[trades['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades[trades['pnl'] < 0]['pnl'].sum())
        
        return gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: float = 365
    ) -> float:
        """
        Calculate annualized Sharpe ratio.
        
        Args:
            returns: Series of trade returns
            risk_free_rate: Risk-free rate (default 0)
            periods_per_year: Number of trading periods per year
            
        Returns:
            Annualized Sharpe ratio
        """
        if returns.empty or returns.std() == 0:
            return 0.0
        
        excess_returns = returns - risk_free_rate
        sharpe = excess_returns.mean() / returns.std()
        
        # Annualize
        return sharpe * np.sqrt(periods_per_year)
    
    async def apply_statistical_filters(
        self,
        whales: List[WhaleProfile],
        min_confidence: float = 0.95
    ) -> List[WhaleProfile]:
        """
        Filter whales by statistical significance.
        
        Args:
            whales: List of whale profiles
            min_confidence: Minimum confidence level for inclusion
            
        Returns:
            Statistically significant whales
        """
        filtered = []
        
        for whale in whales:
            # Check sample size
            if whale.total_bets < self.config.min_trades_for_significance:
                continue
            
            # Calculate confidence interval for win rate
            n = whale.total_bets
            p = whale.win_rate
            
            # Wilson score interval
            z = 1.96 if min_confidence == 0.95 else 2.576  # 95% or 99%
            
            denominator = 1 + z**2 / n
            center = (p + z**2 / (2*n)) / denominator
            margin = z * math.sqrt((p * (1-p) + z**2 / (4*n)) / n) / denominator
            
            lower_bound = center - margin
            
            # Keep if lower bound of win rate is still positive
            if lower_bound > 0.5:  # Better than random
                filtered.append(whale)
        
        logger.info(f"Statistical filtering: {len(whales)} -> {len(filtered)}")
        return filtered
    
    async def rank_by_copy_score(
        self,
        whales: List[WhaleProfile],
        update_ranks: bool = True
    ) -> List[WhaleProfile]:
        """
        Rank whales by copy desirability score.
        
        Args:
            whales: List of whale profiles
            update_ranks: Whether to update rank field on profiles
            
        Returns:
            Whales sorted by copy score (descending)
        """
        # Sort by copy score
        sorted_whales = sorted(whales, key=lambda w: w.copy_score, reverse=True)
        
        if update_ranks:
            for i, whale in enumerate(sorted_whales, 1):
                whale.rank = i
        
        return sorted_whales
    
    def detect_vanity_gaps(self, whale: WhaleProfile) -> Dict[str, Any]:
        """
        Detect potential stat manipulation in whale profile.
        
        Args:
            whale: Whale profile to analyze
            
        Returns:
            Dictionary with vanity gap analysis
        """
        flags = []
        
        # Check vanity gap
        if whale.vanity_gap > 0.15:
            flags.append(f"High vanity gap: {whale.vanity_gap:.1%}")
        
        # Check for suspicious win rate
        if whale.win_rate > 0.8 and whale.total_bets < 50:
            flags.append("Very high win rate with small sample")
        
        # Check for unrealistically consistent returns
        if whale.sharpe_ratio > 3.0:
            flags.append("Suspiciously high Sharpe ratio")
        
        return {
            'has_vanity_gap': whale.vanity_gap > 0.1,
            'vanity_gap': whale.vanity_gap,
            'flags': flags,
            'risk_level': 'high' if len(flags) >= 2 else 'medium' if flags else 'low'
        }
    
    async def get_top_whales(
        self,
        n: int = 10,
        category: Optional[str] = None,
        min_copy_score: float = 50.0
    ) -> List[WhaleProfile]:
        """
        Get top N whales by category.
        
        Args:
            n: Number of whales to return
            category: Optional category filter ('crypto', 'swing', 'scalp', etc.)
            min_copy_score: Minimum copy score to include
            
        Returns:
            Top N whale profiles
        """
        whales = list(self.discovered_whales.values())
        
        # Filter by category if specified
        if category:
            if category == 'crypto':
                whales = [w for w in whales if w.crypto_specialization > 0.4]
            elif category == 'swing':
                whales = [w for w in whales if PatternType.SWING_TRADING in w.behavioral_patterns]
            elif category == 'scalp':
                whales = [w for w in whales if PatternType.SCALPING in w.behavioral_patterns]
        
        # Filter by copy score
        whales = [w for w in whales if w.copy_score >= min_copy_score]
        
        # Sort and limit
        whales = await self.rank_by_copy_score(whales)
        
        return whales[:n]
    
    async def start_discovery_monitoring(
        self,
        interval: Optional[int] = None,
        callback: Optional[Callable[[List[WhaleProfile]], None]] = None
    ) -> None:
        """
        Start continuous whale discovery monitoring.
        
        Args:
            interval: Discovery interval in seconds (default: 300)
            callback: Optional callback for new discoveries
        """
        interval = interval or self.config.active_discovery_interval
        self._stop_monitoring.clear()
        
        logger.info(f"Starting whale discovery monitoring (interval: {interval}s)")
        
        async def monitoring_loop():
            while not self._stop_monitoring.is_set():
                try:
                    # Discover new whales
                    new_whales = await self.get_new_whales_since(
                        self._last_discovery_time or datetime.now() - timedelta(hours=24)
                    )
                    
                    if new_whales:
                        logger.info(f"Monitoring found {len(new_whales)} new whales")
                        
                        # Notify for high-quality whales
                        if self.notifications:
                            for whale in new_whales:
                                if whale.copy_score >= self.config.min_copy_score_for_notification:
                                    await self.notifications.notify_whale_activity({
                                        'trader': whale.address,
                                        'type': 'new_high_quality_whale',
                                        'copy_score': whale.copy_score,
                                        'win_rate': whale.win_rate,
                                        'profit_factor': whale.profit_factor
                                    })
                        
                        # Call callback if provided
                        if callback:
                            callback(new_whales)
                    
                    self._last_discovery_time = datetime.now()
                    
                    # Wait for next iteration
                    try:
                        await asyncio.wait_for(
                            self._stop_monitoring.wait(),
                            timeout=interval
                        )
                    except asyncio.TimeoutError:
                        pass
                    
                except Exception as e:
                    logger.error(f"Error in discovery monitoring: {e}")
                    await asyncio.sleep(60)
        
        self._monitoring_task = asyncio.create_task(monitoring_loop())
    
    async def stop_discovery_monitoring(self) -> None:
        """Stop the discovery monitoring loop."""
        self._stop_monitoring.set()
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Whale discovery monitoring stopped")
    
    async def get_new_whales_since(
        self,
        timestamp: datetime
    ) -> List[WhaleProfile]:
        """
        Find whales that became active since a given timestamp.
        
        Args:
            timestamp: Starting timestamp
            
        Returns:
            List of newly active whales
        """
        hours_ago = (datetime.now() - timestamp).total_seconds() / 3600
        
        # Discover recent active whales
        recent_whales = await self.discover_active_whales(
            lookback_hours=max(1, int(hours_ago))
        )
        
        # Filter to new discoveries
        new_whales = [
            w for w in recent_whales
            if w.address not in self.discovered_whales
        ]
        
        return new_whales
    
    async def track_whale_activity(
        self,
        address: str,
        track_duration_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Track specific whale activity for a duration.
        
        Args:
            address: Whale address to track
            track_duration_hours: How long to track
            
        Returns:
            Activity summary dictionary
        """
        address = address.lower()
        self.monitored_whales.add(address)
        
        logger.info(f"Starting {track_duration_hours}h tracking for {address}")
        
        # Get baseline
        baseline = await self.analyze_whale_performance(address)
        
        start_time = datetime.now()
        trades_seen = []
        
        while (datetime.now() - start_time).total_seconds() < track_duration_hours * 3600:
            try:
                # Check for new trades
                new_trades = await self._get_recent_trades(address, minutes=5)
                
                for trade in new_trades:
                    trade_id = trade.get('id', '')
                    if trade_id not in [t.get('id') for t in trades_seen]:
                        trades_seen.append(trade)
                        
                        # Real-time notification for large trades
                        size = float(trade.get('size', 0) or 0)
                        if size > 10000 and self.notifications:
                            await self.notifications.notify_whale_activity({
                                'trader': address,
                                'market': trade.get('market', {}).get('question', 'Unknown'),
                                'side': trade.get('side', 'UNKNOWN'),
                                'size': size,
                                'price': float(trade.get('price', 0) or 0)
                            })
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error tracking {address}: {e}")
                await asyncio.sleep(60)
        
        self.monitored_whales.discard(address)
        
        # Final analysis
        final = await self.analyze_whale_performance(address)
        
        return {
            'address': address,
            'tracking_duration_hours': track_duration_hours,
            'trades_observed': len(trades_seen),
            'baseline_copy_score': baseline.copy_score if baseline else 0,
            'final_copy_score': final.copy_score if final else 0,
            'pnl_change': (final.pnl - baseline.pnl) if final and baseline else 0,
            'trades': trades_seen
        }
    
    # ==================== Helper Methods ====================
    
    async def _get_whale_trades(
        self,
        address: str,
        days: int
    ) -> pd.DataFrame:
        """Fetch and cache whale trades."""
        cache_key = f"{address}_{days}"
        
        if cache_key in self._trades_cache:
            cache_time, df = self._trades_cache[cache_key]
            if datetime.now() - cache_time < timedelta(minutes=5):
                return df
        
        if not self.subgraph:
            return pd.DataFrame()
        
        try:
            df = await asyncio.to_thread(
                self.subgraph.get_all_trades,
                address
            )
            
            if not df.empty and 'timestamp' in df.columns:
                # Filter to requested period
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            self._trades_cache[cache_key] = (datetime.now(), df)
            return df
            
        except Exception as e:
            logger.error(f"Error fetching trades for {address}: {e}")
            return pd.DataFrame()
    
    async def _get_recent_trades(
        self,
        address: str,
        minutes: int = 5
    ) -> List[Dict]:
        """Get recent trades for a whale."""
        if not self.subgraph:
            return []
        
        try:
            since = int((datetime.now() - timedelta(minutes=minutes)).timestamp())
            
            query = gql("""
                query GetRecentTrades($wallet: String!, $since: Int!) {
                    trades(
                        where: { user: $wallet, timestamp_gt: $since }
                        orderBy: timestamp
                        orderDirection: desc
                    ) {
                        id
                        market { id question }
                        side
                        price
                        size
                        pnl
                        timestamp
                    }
                }
            """)
            
            result = await asyncio.to_thread(
                self.subgraph._execute,
                'positions',
                query,
                {'wallet': address.lower(), 'since': since}
            )
            
            return result.get('trades', [])
            
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []
    
    def _detect_pattern(
        self,
        trades: pd.DataFrame,
        pattern_type: PatternType,
        min_examples: int
    ) -> bool:
        """Detect if trades exhibit a specific pattern."""
        if trades.empty:
            return False
        
        examples = 0
        
        if pattern_type == PatternType.MOMENTUM_BURST:
            # Rapid consecutive trades in same direction
            if 'timestamp' in trades.columns and 'side' in trades.columns:
                trades_sorted = trades.sort_values('timestamp')
                for i in range(len(trades_sorted) - 2):
                    window = trades_sorted.iloc[i:i+3]
                    time_span = (window['timestamp'].max() - window['timestamp'].min()).total_seconds()
                    if time_span < 300 and window['side'].nunique() == 1:  # 5 min, same side
                        examples += 1
        
        elif pattern_type == PatternType.SWING_TRADING:
            # Longer hold times, fewer trades
            if len(trades) >= 10:
                avg_time_between = trades['timestamp'].diff().mean().total_seconds() / 3600
                if avg_time_between > 6:  # > 6 hours between trades
                    examples = len(trades) // 3
        
        elif pattern_type == PatternType.SCALPING:
            # Many small trades
            if len(trades) > 20:
                avg_size = trades['size'].mean() if 'size' in trades.columns else 0
                if avg_size < 5000 and len(trades) > 30:
                    examples = len(trades) // 5
        
        elif pattern_type == PatternType.ARBITRAGE:
            # Both sides of same market
            if 'market' in trades.columns:
                market_sides = defaultdict(set)
                for _, trade in trades.iterrows():
                    market = trade.get('market', {}).get('id', '')
                    side = trade.get('side', '')
                    market_sides[market].add(side)
                
                examples = sum(1 for sides in market_sides.values() if len(sides) > 1)
        
        return examples >= min_examples
    
    def _detect_all_patterns(self, trades: pd.DataFrame) -> List[PatternType]:
        """Detect all patterns in trade history."""
        patterns = []
        
        for pattern_type in PatternType:
            if self._detect_pattern(trades, pattern_type, min_examples=3):
                patterns.append(pattern_type)
        
        return patterns
    
    def _calculate_max_drawdown(self, trades: pd.DataFrame) -> float:
        """Calculate maximum drawdown from trades."""
        if trades.empty or 'pnl' not in trades.columns:
            return 0.0
        
        # Sort by timestamp
        trades_sorted = trades.sort_values('timestamp') if 'timestamp' in trades.columns else trades
        
        # Calculate cumulative PnL
        cumulative = trades_sorted['pnl'].cumsum()
        rolling_max = cumulative.expanding().max()
        drawdown = cumulative - rolling_max
        
        return abs(drawdown.min()) if not drawdown.empty else 0.0
    
    def _calculate_risk_of_ruin(
        self,
        trades: pd.DataFrame,
        win_rate: float,
        ruin_threshold: float = 0.5
    ) -> float:
        """
        Calculate probability of losing ruin_threshold% of bankroll.
        
        Uses simplified Kelly-based risk of ruin formula.
        """
        if trades.empty or 'pnl' not in trades.columns:
            return 1.0
        
        wins = trades[trades['pnl'] > 0]['pnl']
        losses = trades[trades['pnl'] < 0]['pnl']
        
        if wins.empty or losses.empty:
            return 1.0
        
        avg_win = wins.mean()
        avg_loss = abs(losses.mean())
        
        # Edge calculation
        edge = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        if edge <= 0:
            return 1.0
        
        # Simplified risk of ruin (assumes optimal Kelly sizing)
        variance = trades['pnl'].var()
        if variance == 0:
            return 0.0
        
        # Risk of ruin ~ exp(-2 * edge * capital / variance)
        # With ruin_threshold as capital fraction
        risk = math.exp(-2 * edge * ruin_threshold / variance)
        
        return min(1.0, risk)
    
    def _calculate_copy_score(
        self,
        win_rate: float,
        profit_factor: float,
        sharpe_ratio: float,
        num_trades: int,
        trades: pd.DataFrame
    ) -> float:
        """
        Calculate comprehensive copy trading desirability score (0-100).
        """
        score = 0.0
        
        # Win rate component (25%)
        score += min(1.0, win_rate / 0.65) * 25 * self.config.win_rate_weight
        
        # Profit factor component (25%)
        score += min(1.0, profit_factor / 2.0) * 25 * self.config.profit_factor_weight
        
        # Sharpe ratio component (20%)
        sharpe_normalized = max(0, sharpe_ratio) / 2.0
        score += min(1.0, sharpe_normalized) * 20 * self.config.sharpe_weight
        
        # Consistency component (15%) - coefficient of variation of returns
        if 'pnl' in trades.columns and len(trades) > 1:
            returns = trades['pnl']
            if returns.mean() != 0:
                cv = returns.std() / abs(returns.mean())
                consistency = max(0, 1 - cv)
                score += consistency * 15 * self.config.consistency_weight
        
        # Sample size component (15%)
        sample_score = min(1.0, num_trades / 200)
        score += sample_score * 15 * self.config.sample_size_weight
        
        # Penalties
        max_dd = self._calculate_max_drawdown(trades)
        if max_dd > 0.5:
            score *= 0.7
        elif max_dd > 0.3:
            score *= 0.85
        
        return max(0, min(100, score))
    
    def _determine_tier(self, win_rate: float, profit_factor: float, num_trades: int) -> str:
        """Determine reliability tier based on performance."""
        if num_trades >= 200 and win_rate >= 0.60 and profit_factor >= 2.0:
            return "platinum"
        elif num_trades >= 100 and win_rate >= 0.55 and profit_factor >= 1.5:
            return "gold"
        elif num_trades >= 50 and win_rate >= 0.52 and profit_factor >= 1.3:
            return "silver"
        elif num_trades >= 20 and win_rate >= 0.50 and profit_factor >= 1.1:
            return "bronze"
        return "unverified"
    
    def _find_optimal_copy_window(
        self,
        trades: pd.DataFrame
    ) -> Optional[Tuple[int, int]]:
        """Find the best time window for copying this whale."""
        if trades.empty or 'timestamp' not in trades.columns:
            return None
        
        # Extract hours
        trades['hour'] = trades['timestamp'].dt.hour
        
        # Group by hour and calculate win rate
        hourly_performance = trades.groupby('hour')['pnl'].agg(['mean', 'count'])
        hourly_performance = hourly_performance[hourly_performance['count'] >= 3]
        
        if hourly_performance.empty:
            return None
        
        # Find best consecutive 4-hour window
        best_start = 0
        best_score = -float('inf')
        
        for start in range(24):
            hours = [(start + i) % 24 for i in range(4)]
            score = hourly_performance.loc[
                hourly_performance.index.isin(hours), 'mean'
            ].sum()
            
            if score > best_score:
                best_score = score
                best_start = start
        
        return (best_start, (best_start + 4) % 24)
    
    async def _save_to_database(self, profile: WhaleProfile) -> None:
        """Save whale profile to database."""
        if not self.database:
            return
        
        try:
            db_profile = DBWhaleProfile(
                address=profile.address,
                first_seen=profile.first_seen.isoformat() if profile.first_seen else None,
                last_seen=profile.last_seen.isoformat() if profile.last_seen else None,
                total_trades=profile.total_bets,
                winning_trades=int(profile.win_rate * profile.total_bets),
                losing_trades=profile.total_bets - int(profile.win_rate * profile.total_bets),
                total_pnl=profile.pnl,
                win_rate=profile.win_rate * 100,  # Convert to percentage
                profit_factor=profile.profit_factor,
                avg_trade_size=profile.avg_trade_size,
                confluence_score=profile.copy_score,
                reliability_tier=profile.reliability_tier,
                market_specialization='crypto' if profile.crypto_specialization > 0.4 else None,
                metadata={
                    'sharpe_ratio': profile.sharpe_ratio,
                    'max_drawdown': profile.max_drawdown,
                    'vanity_gap': profile.vanity_gap,
                    'patterns': [p.value for p in profile.behavioral_patterns]
                }
            )
            
            await asyncio.to_thread(self.database.save_whale_profile, db_profile)
            
        except Exception as e:
            logger.error(f"Error saving whale to database: {e}")
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get statistics about the discovery system."""
        whales = list(self.discovered_whales.values())
        
        return {
            'total_discovered': len(whales),
            'statistically_significant': sum(1 for w in whales if w.is_statistically_significant),
            'by_tier': {
                'platinum': sum(1 for w in whales if w.reliability_tier == 'platinum'),
                'gold': sum(1 for w in whales if w.reliability_tier == 'gold'),
                'silver': sum(1 for w in whales if w.reliability_tier == 'silver'),
                'bronze': sum(1 for w in whales if w.reliability_tier == 'bronze'),
                'unverified': sum(1 for w in whales if w.reliability_tier == 'unverified'),
            },
            'avg_copy_score': statistics.mean([w.copy_score for w in whales]) if whales else 0,
            'top_performer': max(whales, key=lambda w: w.copy_score).address if whales else None,
            'monitored_count': len(self.monitored_whales),
            'is_monitoring': self._monitoring_task is not None and not self._monitoring_task.done()
        }
