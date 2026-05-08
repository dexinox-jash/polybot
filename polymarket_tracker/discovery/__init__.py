"""
PolyBot Whale Discovery Module

Real-time discovery and analysis of high-performing whales from TheGraph.

Example:
    from polymarket_tracker.discovery import WhaleDiscovery, WhaleProfile, PatternType
    
    discovery = WhaleDiscovery(api_key="your_api_key")
    
    # Discover active whales
    whales = await discovery.discover_active_whales(min_volume=50000, min_trades=20)
    
    # Get top performers
    top_whales = await discovery.get_top_whales(n=10, category='crypto')
    
    # Analyze a specific whale
    profile = await discovery.analyze_whale_performance(address, days=30)
"""

from .whale_discovery import (
    WhaleDiscovery,
    WhaleProfile,
    PatternType,
    DiscoveryConfig,
)

__all__ = [
    'WhaleDiscovery',
    'WhaleProfile',
    'PatternType',
    'DiscoveryConfig',
]
