"""
Streaming Module for Real-Time Whale Tracking

Provides continuous monitoring of whale wallets with
sub-minute latency for speed-matched copy trading.
"""

from .whale_stream_monitor import WhaleStreamMonitor, WhaleSignal, TradeUrgency
from .crypto_filter import CryptoMarketFilter

__all__ = [
    'WhaleStreamMonitor',
    'WhaleSignal', 
    'TradeUrgency',
    'CryptoMarketFilter',
]
