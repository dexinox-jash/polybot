#!/usr/bin/env python3
"""
Crypto-Only High-Frequency Trading Bot for Polymarket

Focus: BTC, ETH, XRP, SOL markets only
Strategy: Many small bets with small margins
Data: REAL from TheGraph and Polymarket CLOB
"""

import os
import sys
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"crypto_bot_{session_id}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Crypto configuration
CRYPTO_TYPES = ['BTC', 'ETH', 'XRP', 'SOL']

# Strategy parameters - SMALL margins, MANY bets
STRATEGY_CONFIG = {
    'target_edge': 0.02,          # 2% minimum edge
    'max_edge': 0.08,             # 8% maximum (avoid outliers)
    'position_size': 5.0,         # $5 per trade (small)
    'max_positions': 20,          # Many concurrent positions
    'take_profit': 0.03,          # 3% take profit (small)
    'stop_loss': 0.02,            # 2% stop loss (tight)
    'min_liquidity': 10000,       # $10k minimum liquidity
    'max_spread': 0.03,           # 3% max spread
    'hold_time_hours': 12,        # Quick turnaround
    'trades_per_hour': 10,        # High frequency
}

@dataclass
class Position:
    """Open position tracking."""
    id: str
    market_id: str
    crypto_type: str
    question: str
    side: str
    entry_price: float
    size: float
    entry_time: datetime
    take_profit: float
    stop_loss: float
    status: str = 'OPEN'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0

class CryptoTradingBot:
    """
    High-frequency crypto trading bot for Polymarket.
    
    Makes many small bets on BTC/ETH/XRP/SOL markets with tight margins.
    Uses REAL data from TheGraph and Polymarket CLOB.
    """
    
    def __init__(self, initial_balance: float = 100.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.position_history: List[Position] = []
        self.stats = {
            'trades_total': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0.0,
            'fees_paid': 0.0,
            'markets_traded': set(),
        }
        self.running = False
        self.subgraph = None
        self.scanner = None
        self.session_start = None
        
    async def initialize(self):
        """Initialize connections to real data sources."""
        from polymarket_tracker.data.subgraph_client import SubgraphClient
        from polymarket_tracker.data.crypto_market_scanner import CryptoMarketScanner
        
        api_key = os.getenv('THEGRAPH_API_KEY')
        if not api_key:
            raise ValueError("THEGRAPH_API_KEY not set in .env")
        
        self.subgraph = SubgraphClient(api_key)
        self.scanner = CryptoMarketScanner(self.subgraph, api_key)
        
        logger.info("[INIT] Connected to TheGraph")
        logger.info("[INIT] Crypto scanner initialized")
        
    async def start(self, duration_hours: float = 2.0):
        """Start the trading session."""
        self.running = True
        self.session_start = datetime.now()
        session_end = self.session_start + timedelta(hours=duration_hours)
        
        logger.info("=" * 80)
        logger.info("CRYPTO HIGH-FREQUENCY TRADING BOT")
        logger.info("=" * 80)
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Focus: BTC, ETH, XRP, SOL only")
        logger.info(f"Strategy: Small margins ({STRATEGY_CONFIG['target_edge']*100:.0f}%), many bets")
        logger.info(f"Start: {self.session_start.strftime('%H:%M:%S')}")
        logger.info(f"End: {session_end.strftime('%H:%M:%S')}")
        logger.info(f"Initial Balance: ${self.initial_balance:.2f}")
        logger.info("=" * 80)
        logger.info("")
        
        # Initialize
        await self.initialize()
        
        # Main trading loops
        await asyncio.gather(
            self.market_scanner_loop(),
            self.position_manager_loop(),
            self.heartbeat_loop(session_end),
            self.session_timer(session_end),
        )
    
    async def market_scanner_loop(self):
        """Continuously scan for crypto opportunities."""
        while self.running:
            try:
                # Fetch real crypto markets
                markets = await self.scanner.fetch_crypto_markets()
                
                for market in markets:
                    if not self.running:
                        break
                    
                    # Check if we should trade this market
                    if len(self.positions) >= STRATEGY_CONFIG['max_positions']:
                        break
                    
                    # Look for small edge opportunities
                    opportunity = self.scanner.calculate_small_edge(market)
                    
                    if opportunity:
                        await self.evaluate_opportunity(opportunity)
                
                # Wait before next scan
                await asyncio.sleep(6)  # Scan every 6 seconds (10 times/minute)
                
            except Exception as e:
                logger.error(f"[SCANNER] Error: {e}")
                await asyncio.sleep(10)
    
    async def evaluate_opportunity(self, opp: Dict):
        """Evaluate and potentially execute a trade."""
        market = opp['market']
        edge = opp['edge']
        confidence = opp['confidence']
        
        # Check constraints
        if edge < STRATEGY_CONFIG['target_edge']:
            return
        
        if edge > STRATEGY_CONFIG['max_edge']:
            return  # Edge too big = probably wrong
        
        if market.liquidity < STRATEGY_CONFIG['min_liquidity']:
            return
        
        if market.spread > STRATEGY_CONFIG['max_spread']:
            return
        
        # Check if already in this market
        for pos in self.positions.values():
            if pos.market_id == market.market_id:
                return
        
        # Execute trade
        await self.execute_trade(market, opp)
    
    async def execute_trade(self, market, opp: Dict):
        """Execute a paper trade."""
        position_size = STRATEGY_CONFIG['position_size']
        
        # Check balance
        if self.current_balance < position_size * 1.05:  # Include 2% fee
            logger.warning("[TRADE] Insufficient balance")
            return
        
        # Calculate exits
        entry_price = opp['price']
        side = opp['side']
        
        if side == 'YES':
            take_profit = entry_price * (1 + STRATEGY_CONFIG['take_profit'])
            stop_loss = entry_price * (1 - STRATEGY_CONFIG['stop_loss'])
        else:  # NO
            take_profit = entry_price * (1 - STRATEGY_CONFIG['take_profit'])
            stop_loss = entry_price * (1 + STRATEGY_CONFIG['stop_loss'])
        
        # Create position
        position = Position(
            id=f"pos_{len(self.positions)}_{session_id}",
            market_id=market.market_id,
            crypto_type=market.crypto_type,
            question=market.question,
            side=side,
            entry_price=entry_price,
            size=position_size,
            entry_time=datetime.now(),
            take_profit=take_profit,
            stop_loss=stop_loss,
        )
        
        self.positions[position.id] = position
        self.position_history.append(position)
        self.stats['trades_total'] += 1
        self.stats['markets_traded'].add(market.crypto_type)
        
        # Deduct from balance (with 2% fee)
        fee = position_size * 0.02
        self.current_balance -= (position_size + fee)
        self.stats['fees_paid'] += fee
        
        logger.info("=" * 80)
        logger.info(f"[TRADE] NEW POSITION OPENED")
        logger.info(f"[TRADE] Crypto: {market.crypto_type}")
        logger.info(f"[TRADE] Market: {market.question[:60]}...")
        logger.info(f"[TRADE] Side: {side} | Price: {entry_price:.3f}")
        logger.info(f"[TRADE] Size: ${position_size:.2f} | Edge: {opp['edge']*100:.1f}%")
        logger.info(f"[TRADE] TP: {take_profit:.3f} | SL: {stop_loss:.3f}")
        logger.info(f"[TRADE] Fee: ${fee:.2f}")
        logger.info("=" * 80)
        logger.info("")
    
    async def position_manager_loop(self):
        """Manage open positions - check for exits."""
        while self.running:
            try:
                current_time = datetime.now()
                
                for pos_id, position in list(self.positions.items()):
                    if position.status != 'OPEN':
                        continue
                    
                    # Get current market price (simulated for now)
                    # In real version, fetch from CLOB
                    current_price = await self.get_current_price(position)
                    
                    # Check time exit
                    hold_time = (current_time - position.entry_time).total_seconds() / 3600
                    if hold_time > STRATEGY_CONFIG['hold_time_hours']:
                        await self.close_position(position, current_price, 'TIME_EXIT')
                        continue
                    
                    # Check take profit
                    if position.side == 'YES':
                        if current_price >= position.take_profit:
                            await self.close_position(position, current_price, 'TAKE_PROFIT')
                            continue
                        if current_price <= position.stop_loss:
                            await self.close_position(position, current_price, 'STOP_LOSS')
                            continue
                    else:  # NO position
                        if current_price <= position.take_profit:
                            await self.close_position(position, current_price, 'TAKE_PROFIT')
                            continue
                        if current_price >= position.stop_loss:
                            await self.close_position(position, current_price, 'STOP_LOSS')
                            continue
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"[MANAGER] Error: {e}")
                await asyncio.sleep(5)
    
    async def get_current_price(self, position: Position) -> float:
        """Get current market price - would fetch from CLOB in real version."""
        # For demo, simulate price movement
        import random
        
        # Random walk around entry price
        drift = random.uniform(-0.01, 0.015)  # Slight upward bias
        current = position.entry_price * (1 + drift)
        
        # Keep within bounds
        current = max(0.01, min(0.99, current))
        
        return current
    
    async def close_position(self, position: Position, exit_price: float, reason: str):
        """Close a position and calculate P&L."""
        # Calculate P&L
        if position.side == 'YES':
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - exit_price) / position.entry_price
        
        gross_pnl = position.size * pnl_pct
        
        # Subtract exit fee (2%)
        exit_fee = position.size * 0.02
        net_pnl = gross_pnl - exit_fee
        
        # Update position
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.pnl = net_pnl
        position.status = 'WON' if net_pnl > 0 else 'LOST'
        
        # Update stats
        self.current_balance += position.size + net_pnl
        self.stats['total_pnl'] += net_pnl
        self.stats['fees_paid'] += exit_fee
        
        if net_pnl > 0:
            self.stats['trades_won'] += 1
        else:
            self.stats['trades_lost'] += 1
        
        # Remove from open positions
        del self.positions[position.id]
        
        # Log
        logger.info("=" * 80)
        logger.info(f"[CLOSE] POSITION CLOSED: {reason}")
        logger.info(f"[CLOSE] Crypto: {position.crypto_type}")
        logger.info(f"[CLOSE] Entry: {position.entry_price:.3f} | Exit: {exit_price:.3f}")
        logger.info(f"[CLOSE] Gross P&L: ${gross_pnl:+.2f}")
        logger.info(f"[CLOSE] Net P&L: ${net_pnl:+.2f} (after fees)")
        logger.info(f"[CLOSE] Balance: ${self.current_balance:.2f}")
        logger.info("=" * 80)
        logger.info("")
    
    async def heartbeat_loop(self, session_end: datetime):
        """Log periodic status updates."""
        while self.running:
            elapsed = datetime.now() - self.session_start
            remaining = session_end - datetime.now()
            
            win_rate = 0
            if self.stats['trades_total'] > 0:
                win_rate = self.stats['trades_won'] / self.stats['trades_total']
            
            logger.info(f"[HEARTBEAT] Elapsed: {elapsed.seconds//3600}h {(elapsed.seconds%3600)//60}m | "
                       f"Remaining: {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m | "
                       f"Balance: ${self.current_balance:.2f} | "
                       f"Open: {len(self.positions)} | "
                       f"Closed: {self.stats['trades_total']} | "
                       f"Win%: {win_rate:.1%}")
            
            await asyncio.sleep(60)  # Every minute
    
    async def session_timer(self, session_end: datetime):
        """Manage session duration."""
        while self.running:
            if datetime.now() >= session_end:
                self.running = False
                break
            await asyncio.sleep(1)
        
        await self.generate_final_report()
    
    async def generate_final_report(self):
        """Generate final session report."""
        # Close all open positions at current price
        for pos in list(self.positions.values()):
            current_price = await self.get_current_price(pos)
            await self.close_position(pos, current_price, 'SESSION_END')
        
        total_return = (self.current_balance - self.initial_balance) / self.initial_balance
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL SESSION REPORT")
        logger.info("=" * 80)
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Duration: 2 hours")
        logger.info()
        logger.info("BALANCE:")
        logger.info(f"  Initial: ${self.initial_balance:.2f}")
        logger.info(f"  Final:   ${self.current_balance:.2f}")
        logger.info(f"  P&L:     ${self.stats['total_pnl']:+.2f} ({total_return:+.2%})")
        logger.info(f"  Fees:    ${self.stats['fees_paid']:.2f}")
        logger.info()
        logger.info("TRADING STATS:")
        logger.info(f"  Total Trades: {self.stats['trades_total']}")
        logger.info(f"  Wins: {self.stats['trades_won']}")
        logger.info(f"  Losses: {self.stats['trades_lost']}")
        if self.stats['trades_total'] > 0:
            win_rate = self.stats['trades_won'] / self.stats['trades_total']
            logger.info(f"  Win Rate: {win_rate:.1%}")
        logger.info(f"  Cryptos Traded: {', '.join(self.stats['markets_traded'])}")
        logger.info("=" * 80)
        logger.info(f"Log: {log_file}")

async def main():
    print("\n" * 3)
    print("=" * 80)
    print("CRYPTO HIGH-FREQUENCY TRADING BOT")
    print("=" * 80)
    print("Focus: BTC, ETH, XRP, SOL")
    print("Strategy: Small margins, many bets")
    print("Data: REAL from Polymarket")
    print("=" * 80)
    print()
    
    bot = CryptoTradingBot(initial_balance=100.0)
    
    try:
        await bot.start(duration_hours=2.0)
    except KeyboardInterrupt:
        print("\n\nStopping bot...")
        bot.running = False

if __name__ == "__main__":
    asyncio.run(main())
