"""
Crypto Market Filter

Filters markets and traders for crypto-specific content.
Identifies crypto markets by keywords and tracks crypto-specialized whales.
"""

import re
from typing import List, Dict, Set
from dataclasses import dataclass


# Crypto-related keywords for market filtering
CRYPTO_KEYWORDS = [
    # Core crypto
    'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
    'blockchain', 'digital asset', 'virtual currency',
    
    # Altcoins
    'solana', 'sol', 'cardano', 'ada', 'polkadot', 'dot',
    'avalanche', 'avax', 'chainlink', 'link', 'polygon', 'matic',
    'arbitrum', 'optimism', 'base', 'zksync',
    
    # DeFi
    'defi', 'decentralized finance', 'dex', 'amm', 'liquidity',
    'yield', 'staking', 'lending', 'borrowing', 'vault',
    'uniswap', 'aave', 'compound', 'curve', 'convex',
    'makerdao', 'dai', 'stablecoin', 'usdc', 'usdt',
    
    # NFT/Metaverse
    'nft', 'non-fungible', 'opensea', 'blur', 'metaverse',
    
    # L1/L2
    'layer 1', 'layer 2', 'l1', 'l2', 'rollup', 'sidechain',
    'cosmos', 'atom', 'near', 'ftm', 'fantom', 'bnb', 'binance',
    
    # Meme coins
    'meme', 'dogecoin', 'doge', 'shiba', 'shib', 'pepe', 'bonk',
    
    # Trading/Exchanges
    'etf', 'exchange', 'binance', 'coinbase', 'kraken', 'ftx',
    'blackrock', 'spot bitcoin', 'spot etf',
    
    # Technical
    'halving', 'merge', 'shanghai', 'dencun', 'eip',
    'hash rate', 'mining', 'validator', 'proof of stake',
    'proof of work', 'pos', 'pow', 'consensus',
    
    # Market terms
    'altcoin', 'alt season', 'bear market', 'bull market',
    'capitulation', 'accumulation', 'distribution'
]


@dataclass
class CryptoRelevance:
    """Crypto relevance score for a market."""
    is_crypto: bool
    confidence: float  # 0-1
    matched_keywords: List[str]
    primary_category: str


class CryptoMarketFilter:
    """
    Filter markets and traders for crypto-specific content.
    """
    
    def __init__(self, min_confidence: float = 0.3):
        """
        Initialize crypto filter.
        
        Args:
            min_confidence: Minimum confidence to classify as crypto
        """
        self.min_confidence = min_confidence
        self.keywords = [k.lower() for k in CRYPTO_KEYWORDS]
        self.keyword_weights = self._build_weights()
    
    def _build_weights(self) -> Dict[str, float]:
        """Build keyword weights (stronger terms = higher weight)."""
        weights = {}
        
        # High-weight core terms
        for term in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency']:
            weights[term] = 1.0
        
        # Medium-weight altcoins
        for term in ['solana', 'sol', 'cardano', 'ada', 'defi', 'blockchain']:
            weights[term] = 0.8
        
        # Lower-weight general terms
        for term in ['nft', 'metaverse', 'exchange', 'mining']:
            weights[term] = 0.5
        
        # Default weight
        for kw in self.keywords:
            if kw not in weights:
                weights[kw] = 0.6
        
        return weights
    
    def classify_market(self, question: str, description: str = "", 
                       tags: List[str] = None) -> CryptoRelevance:
        """
        Classify a market as crypto-related.
        
        Args:
            question: Market question/title
            description: Market description
            tags: Market tags
            
        Returns:
            CryptoRelevance with confidence score
        """
        text = f"{question} {description}".lower()
        tags_lower = [t.lower() for t in (tags or [])]
        
        matched_keywords = []
        total_weight = 0
        
        # Check for keyword matches
        for keyword in self.keywords:
            if keyword in text or keyword in ' '.join(tags_lower):
                matched_keywords.append(keyword)
                total_weight += self.keyword_weights.get(keyword, 0.6)
        
        # Calculate confidence (normalize by expected max weight)
        max_possible = 3.0  # Expect ~3 strong matches for clear crypto market
        confidence = min(1.0, total_weight / max_possible)
        
        # Determine primary category
        primary = self._determine_category(matched_keywords)
        
        return CryptoRelevance(
            is_crypto=confidence >= self.min_confidence,
            confidence=confidence,
            matched_keywords=matched_keywords[:5],  # Top 5
            primary_category=primary
        )
    
    def _determine_category(self, keywords: List[str]) -> str:
        """Determine primary crypto category from keywords."""
        keyword_set = set(keywords)
        
        if keyword_set & {'bitcoin', 'btc', 'spot bitcoin', 'etf'}:
            return "BITCOIN"
        elif keyword_set & {'ethereum', 'eth', 'merge', 'eip'}:
            return "ETHEREUM"
        elif keyword_set & {'defi', 'uniswap', 'aave', 'dex', 'yield'}:
            return "DEFI"
        elif keyword_set & {'nft', 'opensea', 'blur', 'non-fungible'}:
            return "NFT"
        elif keyword_set & {'solana', 'sol', 'cardano', 'ada'}:
            return "ALTCOIN"
        elif keyword_set & {'halving', 'mining', 'hash rate', 'validator'}:
            return "TECHNICAL"
        else:
            return "GENERAL_CRYPTO"
    
    def filter_markets(self, markets: List[Dict]) -> List[Dict]:
        """
        Filter a list of markets to only crypto-related ones.
        
        Args:
            markets: List of market dictionaries
            
        Returns:
            Filtered list with only crypto markets
        """
        crypto_markets = []
        
        for market in markets:
            relevance = self.classify_market(
                question=market.get('question', ''),
                description=market.get('description', ''),
                tags=market.get('tags', [])
            )
            
            if relevance.is_crypto:
                market['_crypto_relevance'] = relevance
                crypto_markets.append(market)
        
        # Sort by confidence
        crypto_markets.sort(
            key=lambda m: m['_crypto_relevance'].confidence,
            reverse=True
        )
        
        return crypto_markets
    
    def is_crypto_whale(self, trader_stats: Dict) -> bool:
        """
        Determine if a trader is crypto-specialized.
        
        Args:
            trader_stats: Dictionary with trader statistics
            
        Returns:
            True if trader specializes in crypto
        """
        # Check crypto trade percentage
        total_trades = trader_stats.get('total_trades', 0)
        crypto_trades = trader_stats.get('crypto_trades', 0)
        
        if total_trades < 20:  # Not enough data
            return False
        
        crypto_percentage = crypto_trades / total_trades
        
        # Check crypto volume
        total_volume = trader_stats.get('total_volume', 0)
        crypto_volume = trader_stats.get('crypto_volume', 0)
        
        volume_percentage = crypto_volume / total_volume if total_volume > 0 else 0
        
        # Criteria: >40% crypto trades OR >$100k crypto volume
        return crypto_percentage > 0.40 or crypto_volume > 100000
    
    def get_crypto_market_ids(self, markets: List[Dict]) -> Set[str]:
        """Get set of crypto market IDs."""
        return {m['id'] for m in self.filter_markets(markets)}
    
    def explain_classification(self, question: str) -> str:
        """Get human-readable explanation of classification."""
        relevance = self.classify_market(question)
        
        if not relevance.is_crypto:
            return f"Not classified as crypto (confidence: {relevance.confidence:.1%})"
        
        keywords_str = ', '.join(relevance.matched_keywords[:3])
        return (f"Crypto market ({relevance.primary_category}) - "
                f"confidence: {relevance.confidence:.1%}. "
                f"Matched: {keywords_str}")


# Pre-built filters
CRYPTO_ONLY_FILTER = CryptoMarketFilter(min_confidence=0.5)
BROADER_CRYPTO_FILTER = CryptoMarketFilter(min_confidence=0.3)
STRICT_CRYPTO_FILTER = CryptoMarketFilter(min_confidence=0.7)
