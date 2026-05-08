"""
Whale Tracker - Core class for tracking and analyzing Polymarket whales.

This module implements the true win rate calculation, zombie order detection,
and whale behavior analysis as described in the research.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict

from .subgraph_client import SubgraphClient
from .gamma_client import GammaClient
from ..utils.config import Config
from ..utils.logger import setup_logging

logger = setup_logging()

# Known whale wallets (from research)
KNOWN_WHALES = {
    'seriouslysirius': '0x0000000000000000000000000000000000000000',  # Complex Quantitative Hedging
    'drpufferfish': '0x0000000000000000000000000000000000000000',     # Probability Transformation
    'gmanas': '0x0000000000000000000000000000000000000000',           # High-Frequency Automation
    'simonbanza': '0x0000000000000000000000000000000000000000',       # Swing Trading
    'swisstony': '0x0000000000000000000000000000000000000000',        # Micro-Arbitrage
    '0xafee': '0x0000000000000000000000000000000000000000',           # Specialized Information
}


@dataclass
class WhaleProfile:
    """Profile of a tracked whale."""
    address: str
    name: Optional[str] = None
    archetype: Optional[str] = None
    
    # Performance metrics
    displayed_win_rate: float = 0.0
    true_win_rate: float = 0.0
    vanity_gap: float = 0.0
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Trading metrics
    total_trades: int = 0
    settled_wins: int = 0
    settled_losses: int = 0
    zombie_orders: int = 0
    avg_trade_size: float = 0.0
    
    # Behavior metrics
    avg_hold_time: timedelta = timedelta(0)
    trades_per_day: float = 0.0
    hedge_ratio: float = 0.0  # Multi-directional bets / total bets
    category_concentration: Dict[str, float] = None
    
    # Timestamps
    first_trade: Optional[datetime] = None
    last_trade: Optional[datetime] = None
    
    def __post_init__(self):
        if self.category_concentration is None:
            self.category_concentration = {}


class WhaleTracker:
    """
    Tracker for Polymarket whale wallets.
    
    Implements:
    - True win rate calculation (accounting for zombie orders)
    - Strategy archetype classification
    - Position tracking and PnL analysis
    """
    
    # Constants for analysis
    ZOMBIE_ORDER_DAYS = 30  # Orders open > 30 days considered zombie
    ZOMBIE_PROFIT_THRESHOLD = 0  # Unrealized PnL <= 0 for zombie
    WHALE_MIN_POSITION = 1000  # Minimum position to qualify as whale
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the whale tracker.
        
        Args:
            config: Application configuration
        """
        self.config = config or Config.from_env()
        self.subgraph = SubgraphClient(self.config.thegraph_api_key)
        self.gamma = GammaClient()
        self.profiles: Dict[str, WhaleProfile] = {}
        
        logger.info("WhaleTracker initialized")
    
    def add_wallet(self, address: str, name: Optional[str] = None):
        """
        Add a wallet to track.
        
        Args:
            address: Ethereum address
            name: Optional display name
        """
        address = address.lower()
        self.profiles[address] = WhaleProfile(address=address, name=name)
        logger.info(f"Added wallet {name or address} to tracker")
    
    def add_known_whales(self):
        """Add known whale wallets from research."""
        for name, address in KNOWN_WHALES.items():
            if address != '0x0000000000000000000000000000000000000000':
                self.add_wallet(address, name)
    
    def fetch_wallet_data(self, address: str) -> Dict:
        """
        Fetch all relevant data for a wallet.
        
        Args:
            address: Wallet address
            
        Returns:
            Dictionary with trades, positions, and PnL
        """
        address = address.lower()
        
        logger.info(f"Fetching data for {address}")
        
        # Fetch all data types
        trades = self.subgraph.get_all_trades(address)
        positions = self.subgraph.get_all_positions(address)
        pnl = self.subgraph.get_pnl(address)
        
        return {
            'trades': trades,
            'positions': positions,
            'pnl': pnl,
        }
    
    def calculate_true_win_rate(
        self,
        trades: pd.DataFrame,
        positions: pd.DataFrame
    ) -> Tuple[float, float, int, int, int]:
        """
        Calculate true win rate accounting for zombie orders.
        
        The "vanity gap" is the difference between displayed win rate (which
        ignores open positions) and true win rate (which counts zombie orders
        as losses).
        
        Args:
            trades: DataFrame of trades
            positions: DataFrame of open positions
            
        Returns:
            Tuple of (displayed_win_rate, true_win_rate, wins, losses, zombies)
        """
        if trades.empty:
            return 0.0, 0.0, 0, 0, 0
        
        # Calculate settled trades
        settled_trades = trades[trades['pnl'].notna()]
        
        if settled_trades.empty:
            return 0.0, 0.0, 0, 0, 0
        
        # Count wins and losses
        wins = len(settled_trades[settled_trades['pnl'] > 0])
        losses = len(settled_trades[settled_trades['pnl'] <= 0])
        
        # Calculate displayed win rate (what the UI shows)
        total_settled = wins + losses
        displayed_win_rate = (wins / total_settled * 100) if total_settled > 0 else 0
        
        # Detect zombie orders (open positions that are likely abandoned)
        zombie_count = 0
        
        if not positions.empty:
            now = datetime.now()
            zombie_threshold = now - timedelta(days=self.ZOMBIE_ORDER_DAYS)
            
            # Check for old open positions that are likely losing
            for _, pos in positions.iterrows():
                created_at = pos.get('createdAt')
                if created_at and created_at < zombie_threshold:
                    # This is an old position - likely a zombie
                    # In a full implementation, we'd calculate unrealized PnL
                    # For now, count old positions as zombies
                    zombie_count += 1
        
        # Calculate true win rate (including zombies as losses)
        true_losses = losses + zombie_count
        true_win_rate = (wins / (wins + true_losses) * 100) if (wins + true_losses) > 0 else 0
        
        return displayed_win_rate, true_win_rate, wins, losses, zombie_count
    
    def calculate_behavior_metrics(
        self,
        trades: pd.DataFrame,
        positions: pd.DataFrame
    ) -> Dict:
        """
        Calculate trading behavior metrics.
        
        Args:
            trades: DataFrame of trades
            positions: DataFrame of positions
            
        Returns:
            Dictionary of behavior metrics
        """
        metrics = {
            'avg_hold_time': timedelta(0),
            'trades_per_day': 0.0,
            'hedge_ratio': 0.0,
            'avg_trade_size': 0.0,
            'category_concentration': {},
        }
        
        if trades.empty:
            return metrics
        
        # Calculate trades per day
        trades = trades.copy()
        trades = trades.sort_values('timestamp')
        
        if len(trades) > 1:
            date_range = (trades['timestamp'].max() - trades['timestamp'].min()).days
            if date_range > 0:
                metrics['trades_per_day'] = len(trades) / date_range
        
        # Calculate average trade size
        if 'size' in trades.columns:
            metrics['avg_trade_size'] = trades['size'].mean()
        
        # Calculate hedge ratio (multi-directional bets on same market)
        if not trades.empty and 'market' in trades.columns:
            market_sides = defaultdict(set)
            for _, trade in trades.iterrows():
                market_id = trade.get('market', {}).get('id', '') if isinstance(trade.get('market'), dict) else ''
                side = trade.get('side', '')
                if market_id and side:
                    market_sides[market_id].add(side)
            
            multi_directional = sum(1 for sides in market_sides.values() if len(sides) > 1)
            metrics['hedge_ratio'] = multi_directional / len(market_sides) if market_sides else 0
        
        return metrics
    
    def analyze_wallet(self, address: str) -> WhaleProfile:
        """
        Perform full analysis on a wallet.
        
        Args:
            address: Wallet address
            
        Returns:
            Updated WhaleProfile
        """
        address = address.lower()
        
        if address not in self.profiles:
            self.add_wallet(address)
        
        profile = self.profiles[address]
        
        # Fetch data
        data = self.fetch_wallet_data(address)
        trades = data['trades']
        positions = data['positions']
        pnl = data['pnl']
        
        # Calculate win rates
        displayed_wr, true_wr, wins, losses, zombies = self.calculate_true_win_rate(
            trades, positions
        )
        
        profile.displayed_win_rate = displayed_wr
        profile.true_win_rate = true_wr
        profile.vanity_gap = displayed_wr - true_wr
        profile.settled_wins = wins
        profile.settled_losses = losses
        profile.zombie_orders = zombies
        profile.total_trades = len(trades)
        
        # Extract PnL data
        if pnl:
            profile.total_pnl = float(pnl.get('totalPnL', 0) or 0)
            profile.realized_pnl = float(pnl.get('realizedPnL', 0) or 0)
            profile.unrealized_pnl = float(pnl.get('unrealizedPnL', 0) or 0)
        
        # Calculate behavior metrics
        behavior = self.calculate_behavior_metrics(trades, positions)
        profile.trades_per_day = behavior['trades_per_day']
        profile.hedge_ratio = behavior['hedge_ratio']
        profile.avg_trade_size = behavior['avg_trade_size']
        
        # Set timestamps
        if not trades.empty and 'timestamp' in trades.columns:
            profile.first_trade = trades['timestamp'].min()
            profile.last_trade = trades['timestamp'].max()
        
        logger.info(f"Analysis complete for {address}: True WR={true_wr:.1f}%, "
                   f"Vanity Gap={profile.vanity_gap:.1f}%")
        
        return profile
    
    def analyze_all_wallets(self) -> pd.DataFrame:
        """
        Analyze all tracked wallets.
        
        Returns:
            DataFrame with all whale profiles
        """
        profiles = []
        
        for address in self.profiles:
            profile = self.analyze_wallet(address)
            profiles.append({
                'address': profile.address,
                'name': profile.name,
                'archetype': profile.archetype,
                'displayed_win_rate': profile.displayed_win_rate,
                'true_win_rate': profile.true_win_rate,
                'vanity_gap': profile.vanity_gap,
                'total_pnl': profile.total_pnl,
                'total_trades': profile.total_trades,
                'zombie_orders': profile.zombie_orders,
                'trades_per_day': profile.trades_per_day,
                'hedge_ratio': profile.hedge_ratio,
            })
        
        df = pd.DataFrame(profiles)
        
        # Sort by true PnL
        df = df.sort_values('total_pnl', ascending=False)
        
        return df
    
    def get_leaderboard(self, min_trades: int = 10) -> pd.DataFrame:
        """
        Get whale leaderboard ranked by true win rate.
        
        Args:
            min_trades: Minimum trades to qualify
            
        Returns:
            DataFrame sorted by true win rate
        """
        df = self.analyze_all_wallets()
        
        # Filter by minimum trades
        df = df[df['total_trades'] >= min_trades]
        
        # Sort by true win rate (descending)
        df = df.sort_values('true_win_rate', ascending=False)
        
        return df
    
    def detect_arbitrage_opportunities(self) -> List[Dict]:
        """
        Detect markets where YES + NO < 1.0 (arbitrage opportunity).
        
        Returns:
            List of arbitrage opportunities
        """
        opportunities = []
        
        # Get active markets
        markets = self.subgraph.get_active_markets(first=100)
        
        if markets.empty:
            return opportunities
        
        for _, market in markets.iterrows():
            prices = market.get('outcomeTokenPrices', [])
            if len(prices) >= 2:
                sum_prices = sum(float(p) for p in prices if p)
                
                # If sum < 1.0, there's an arbitrage opportunity
                if sum_prices < 0.99:  # Allow small rounding errors
                    opportunities.append({
                        'market_id': market.get('id'),
                        'question': market.get('question'),
                        'sum_prices': sum_prices,
                        'potential_profit': 1.0 - sum_prices,
                        'prices': prices,
                    })
        
        return opportunities
    
    def get_market_whale_consensus(self, market_id: str) -> Dict:
        """
        Get whale consensus for a specific market.
        
        Args:
            market_id: Market condition ID
            
        Returns:
            Consensus data including whale positions and sentiment
        """
        # Get whale positions for this market
        positions = self.subgraph.get_market_whale_positions(
            market_id, 
            min_size=self.WHALE_MIN_POSITION
        )
        
        if positions.empty:
            return {
                'market_id': market_id,
                'total_whale_volume': 0,
                'consensus': None,
                'confidence': 0,
            }
        
        # Calculate consensus (weighted by position size)
        yes_volume = positions[positions['outcomeIndex'] == 0]['amount'].sum()
        no_volume = positions[positions['outcomeIndex'] == 1]['amount'].sum()
        total_volume = yes_volume + no_volume
        
        if total_volume == 0:
            consensus = None
            confidence = 0
        else:
            consensus = 'YES' if yes_volume > no_volume else 'NO'
            confidence = max(yes_volume, no_volume) / total_volume
        
        return {
            'market_id': market_id,
            'total_whale_volume': total_volume,
            'yes_volume': yes_volume,
            'no_volume': no_volume,
            'consensus': consensus,
            'confidence': confidence,
            'num_whales': positions['wallet'].nunique(),
            'positions': positions.to_dict('records'),
        }
