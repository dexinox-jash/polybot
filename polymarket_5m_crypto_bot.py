#!/usr/bin/env python3
"""
Polymarket 5-Minute Crypto Trading Bot

Focus: BTC, ETH, XRP, SOL 5-minute prediction markets
Strategy: High-frequency micro-structure trading
Data: Real-time from Polymarket CLOB API

When https://polymarket.com/crypto/5M markets are live, this bot will:
1. Monitor real-time price action
2. Detect micro-patterns (momentum, mean reversion)
3. Execute trades via Polymarket CLOB
4. Manage risk with tight stops
"""

import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"5m_crypto_bot_{session_id}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
WS_URL = "wss://clob.polymarket.com/ws"

CRYPTO_KEYWORDS = {
    'BTC': ['bitcoin', 'btc', '$btc'],
    'ETH': ['ethereum', 'eth', '$eth', 'ether'],
    'XRP': ['ripple', 'xrp', '$xrp'],
    'SOL': ['solana', 'sol', '$sol'],
}

FIVE_MIN_KEYWORDS = ['5m', '5-min', '5 minute', 'five minute', '5min']

# Strategy Config for 5M markets
STRATEGY = {
    'max_positions': 10,          # Max concurrent 5M positions
    'position_size': 10.0,        # $10 per trade
    'take_profit_pct': 0.05,      # 5% profit target
    'stop_loss_pct': 0.03,        # 3% stop loss
    'min_edge': 0.02,             # 2% minimum edge
    'max_hold_minutes': 5,        # Hold max 5 minutes
    'trade_cooldown_seconds': 30, # 30s between trades on same market
}


@dataclass
class Market5M:
    """5-minute crypto market data."""
    condition_id: str
    question: str
    crypto_type: str  # BTC, ETH, XRP, SOL
    yes_price: float
    no_price: float
    volume: float
    liquidity: float
    end_time: datetime
    accepting_orders: bool
    enable_order_book: bool
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class Position5M:
    """5-minute position tracking."""
    id: str
    condition_id: str
    crypto_type: str
    side: str  # YES or NO
    entry_price: float
    size: float
    entry_time: datetime
    take_profit: float
    stop_loss: float
    target_exit_time: datetime
    status: str = 'OPEN'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0


class Polymarket5MCryptoBot:
    """
    High-frequency trading bot for Polymarket 5-minute crypto markets.
    
    Monitors https://polymarket.com/crypto/5M for:
    - BTC 5-minute price predictions
    - ETH 5-minute price predictions  
    - XRP 5-minute price predictions
    - SOL 5-minute price predictions
    """
    
    def __init__(self, balance: float = 100.0):
        self.balance = balance
        self.initial_balance = balance
        self.positions: Dict[str, Position5M] = {}
        self.position_history: List[Position5M] = []
        self.markets: Dict[str, Market5M] = {}
        self.trade_count = 0
        self.win_count = 0
        self.loss_count = 0
        self.total_pnl = 0.0
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    def _is_5m_crypto_market(self, question: str) -> Tuple[bool, str]:
        """Check if market is a 5-minute crypto market."""
        q_lower = question.lower()
        
        # Check for 5-minute indicators
        is_5m = any(kw in q_lower for kw in FIVE_MIN_KEYWORDS)
        
        # Check for crypto type
        crypto_type = ''
        for ctype, keywords in CRYPTO_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                crypto_type = ctype
                break
        
        return is_5m and bool(crypto_type), crypto_type
    
    async def fetch_5m_crypto_markets(self) -> List[Market5M]:
        """
        Fetch active 5-minute crypto markets from Polymarket.
        
        This queries the APIs to find markets matching:
        - 5-minute duration
        - BTC, ETH, XRP, or SOL
        - Accepting orders (tradeable)
        """
        markets_5m = []
        
        try:
            # Try Gamma API first
            url = f"{GAMMA_API}/markets"
            params = {'active': 'true', 'limit': 500}
            
            async with self.session.get(url, params=params, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    for m in data if isinstance(data, list) else []:
                        question = m.get('question', '')
                        is_5m_crypto, crypto_type = self._is_5m_crypto_market(question)
                        
                        if is_5m_crypto:
                            # Parse prices
                            prices = m.get('outcomePrices', ['0.5', '0.5'])
                            yes_price = float(prices[0]) if isinstance(prices, list) else 0.5
                            no_price = float(prices[1]) if isinstance(prices, list) and len(prices) > 1 else 0.5
                            
                            market = Market5M(
                                condition_id=m.get('conditionId'),
                                question=question,
                                crypto_type=crypto_type,
                                yes_price=yes_price,
                                no_price=no_price,
                                volume=float(m.get('volume', 0) or 0),
                                liquidity=float(m.get('liquidity', 0) or 0),
                                end_time=datetime.fromisoformat(m.get('endDate', '').replace('Z', '+00:00')) if m.get('endDate') else datetime.now() + timedelta(minutes=5),
                                accepting_orders=m.get('accepting_orders', False),
                                enable_order_book=m.get('enable_order_book', False)
                            )
                            markets_5m.append(market)
                            self.markets[market.condition_id] = market
            
            # Also try CLOB API
            url = f"{CLOB_API}/markets"
            async with self.session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    clob_markets = data.get('data', [])
                    
                    for m in clob_markets:
                        question = m.get('question', '')
                        is_5m_crypto, crypto_type = self._is_5m_crypto_market(question)
                        
                        if is_5m_crypto and m.get('accepting_orders'):
                            # Get prices from CLOB
                            prices = m.get('outcomePrices')
                            if prices and isinstance(prices, list):
                                yes_price = float(prices[0])
                                no_price = float(prices[1])
                            else:
                                yes_price = no_price = 0.5
                            
                            condition_id = m.get('condition_id')
                            if condition_id not in self.markets:
                                market = Market5M(
                                    condition_id=condition_id,
                                    question=question,
                                    crypto_type=crypto_type,
                                    yes_price=yes_price,
                                    no_price=no_price,
                                    volume=float(m.get('volume', 0) or 0),
                                    liquidity=float(m.get('liquidity', 0) or 0),
                                    end_time=datetime.now() + timedelta(minutes=5),
                                    accepting_orders=True,
                                    enable_order_book=m.get('enable_order_book', False)
                                )
                                markets_5m.append(market)
                                self.markets[condition_id] = market
            
            return markets_5m
            
        except Exception as e:
            logger.error(f"Error fetching 5M markets: {e}")
            return []
    
    async def get_market_orderbook(self, condition_id: str) -> Dict:
        """Fetch real-time orderbook for a 5M market."""
        url = f"{CLOB_API}/book/{condition_id}"
        
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception as e:
            logger.error(f"Error fetching orderbook: {e}")
            return {}
    
    async def get_recent_trades(self, condition_id: str, limit: int = 50) -> List[Dict]:
        """Fetch recent trades for flow analysis."""
        url = f"{CLOB_API}/trades/{condition_id}?limit={limit}"
        
        try:
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('trades', [])
                return []
        except Exception as e:
            return []
    
    def analyze_micro_structure(self, market: Market5M, orderbook: Dict, trades: List[Dict]) -> Optional[Dict]:
        """
        Analyze micro-structure for 5-minute opportunities.
        
        Strategies:
        1. Spread scalping - tight spreads
        2. Flow following - recent trade direction
        3. Mean reversion - price deviations
        """
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])
        
        if not bids or not asks:
            return None
        
        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        
        # Calculate spread %
        spread_pct = spread / mid_price if mid_price > 0 else 1.0
        
        opportunities = []
        
        # Strategy 1: Tight spread scalping
        if spread_pct < 0.01:  # Less than 1% spread
            # Check if we can buy and sell for small profit
            if market.yes_price < 0.50:
                edge = 0.50 - market.yes_price
                if edge >= STRATEGY['min_edge']:
                    opportunities.append({
                        'type': 'SPREAD_SCALP',
                        'side': 'YES',
                        'entry': best_ask,
                        'target': mid_price + spread/2,
                        'edge': edge,
                        'confidence': 0.6
                    })
        
        # Strategy 2: Flow following
        if len(trades) >= 3:
            recent_sides = [t.get('side') for t in trades[-3:]]
            buy_pressure = recent_sides.count('BUY')
            sell_pressure = recent_sides.count('SELL')
            
            if buy_pressure >= 2 and market.yes_price < 0.60:
                opportunities.append({
                    'type': 'FLOW_FOLLOW',
                    'side': 'YES',
                    'entry': best_ask,
                    'target': min(best_ask * 1.03, 0.95),
                    'edge': 0.03,
                    'confidence': 0.55
                })
            elif sell_pressure >= 2 and market.no_price < 0.60:
                opportunities.append({
                    'type': 'FLOW_FOLLOW',
                    'side': 'NO',
                    'entry': best_ask if best_ask < 0.5 else best_bid,
                    'target': min(best_ask * 1.03, 0.95) if best_ask < 0.5 else min(best_bid * 1.03, 0.95),
                    'edge': 0.03,
                    'confidence': 0.55
                })
        
        # Strategy 3: Mean reversion near extremes
        if market.yes_price < 0.45 and market.yes_price > 0.35:
            opportunities.append({
                'type': 'MEAN_REVERT',
                'side': 'YES',
                'entry': best_ask,
                'target': 0.50,
                'edge': 0.50 - market.yes_price,
                'confidence': 0.50
            })
        elif market.no_price < 0.45 and market.no_price > 0.35:
            opportunities.append({
                'type': 'MEAN_REVERT',
                'side': 'NO',
                'entry': best_ask if best_ask < 0.5 else best_bid,
                'target': 0.50,
                'edge': 0.50 - market.no_price,
                'confidence': 0.50
            })
        
        # Return best opportunity
        if opportunities:
            return max(opportunities, key=lambda x: x['confidence'] * x['edge'])
        return None
    
    async def execute_trade(self, market: Market5M, signal: Dict) -> bool:
        """Execute a paper trade on a 5M market."""
        if len(self.positions) >= STRATEGY['max_positions']:
            logger.warning("Max positions reached")
            return False
        
        if self.balance < STRATEGY['position_size']:
            logger.warning("Insufficient balance")
            return False
        
        # Calculate position parameters
        side = signal['side']
        entry_price = signal['entry']
        
        if side == 'YES':
            take_profit = entry_price * (1 + STRATEGY['take_profit_pct'])
            stop_loss = entry_price * (1 - STRATEGY['stop_loss_pct'])
        else:
            take_profit = entry_price * (1 - STRATEGY['take_profit_pct'])
            stop_loss = entry_price * (1 + STRATEGY['stop_loss_pct'])
        
        # Create position
        position = Position5M(
            id=f"5m_{self.trade_count}_{session_id}",
            condition_id=market.condition_id,
            crypto_type=market.crypto_type,
            side=side,
            entry_price=entry_price,
            size=STRATEGY['position_size'],
            entry_time=datetime.now(),
            take_profit=take_profit,
            stop_loss=stop_loss,
            target_exit_time=datetime.now() + timedelta(minutes=STRATEGY['max_hold_minutes'])
        )
        
        self.positions[position.id] = position
        self.position_history.append(position)
        self.trade_count += 1
        
        # Deduct balance (with 2% fee)
        fee = STRATEGY['position_size'] * 0.02
        self.balance -= (STRATEGY['position_size'] + fee)
        
        logger.info("=" * 80)
        logger.info(f"[TRADE] 5M {market.crypto_type} POSITION OPENED")
        logger.info(f"[TRADE] Strategy: {signal['type']}")
        logger.info(f"[TRADE] Market: {market.question[:50]}...")
        logger.info(f"[TRADE] Side: {side} | Entry: {entry_price:.4f}")
        logger.info(f"[TRADE] Size: ${STRATEGY['position_size']:.2f}")
        logger.info(f"[TRADE] TP: {take_profit:.4f} | SL: {stop_loss:.4f}")
        logger.info(f"[TRADE] Hold until: {position.target_exit_time.strftime('%H:%M:%S')}")
        logger.info("=" * 80)
        
        return True
    
    async def monitor_positions(self):
        """Monitor and manage open positions."""
        while self.running:
            try:
                current_time = datetime.now()
                
                for pos_id, position in list(self.positions.items()):
                    if position.status != 'OPEN':
                        continue
                    
                    # Get current market data
                    market = self.markets.get(position.condition_id)
                    if not market:
                        continue
                    
                    # Get current price (would fetch from CLOB in real implementation)
                    # For now, simulate price movement based on strategy
                    await self._check_exit_conditions(position, market, current_time)
                
                await asyncio.sleep(1)  # Check every second for 5M markets
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(1)
    
    async def _check_exit_conditions(self, position: Position5M, market: Market5M, current_time: datetime):
        """Check if position should be closed."""
        # Get current market price
        # In real implementation, fetch from CLOB
        # For demo, use market's current price
        current_price = market.yes_price if position.side == 'YES' else market.no_price
        
        exit_reason = None
        exit_price = current_price
        
        # Check time exit
        if current_time >= position.target_exit_time:
            exit_reason = 'TIME_EXIT'
        
        # Check take profit
        elif position.side == 'YES' and current_price >= position.take_profit:
            exit_reason = 'TAKE_PROFIT'
        elif position.side == 'NO' and current_price <= position.take_profit:
            exit_reason = 'TAKE_PROFIT'
        
        # Check stop loss
        elif position.side == 'YES' and current_price <= position.stop_loss:
            exit_reason = 'STOP_LOSS'
        elif position.side == 'NO' and current_price >= position.stop_loss:
            exit_reason = 'STOP_LOSS'
        
        if exit_reason:
            await self.close_position(position, exit_price, exit_reason)
    
    async def close_position(self, position: Position5M, exit_price: float, reason: str):
        """Close a position and calculate P&L."""
        # Calculate P&L
        if position.side == 'YES':
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - exit_price) / position.entry_price
        
        gross_pnl = position.size * pnl_pct
        exit_fee = position.size * 0.02
        net_pnl = gross_pnl - exit_fee
        
        # Update position
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.pnl = net_pnl
        position.status = 'WON' if net_pnl > 0 else 'LOST'
        
        # Update stats
        self.balance += position.size + net_pnl
        self.total_pnl += net_pnl
        
        if net_pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        # Remove from open positions
        del self.positions[position.id]
        
        # Log
        hold_time = (position.exit_time - position.entry_time).total_seconds()
        logger.info("=" * 80)
        logger.info(f"[CLOSE] 5M POSITION CLOSED: {reason}")
        logger.info(f"[CLOSE] Crypto: {position.crypto_type}")
        logger.info(f"[CLOSE] Entry: {position.entry_price:.4f} | Exit: {exit_price:.4f}")
        logger.info(f"[CLOSE] Hold time: {hold_time:.0f}s")
        logger.info(f"[CLOSE] Gross P&L: ${gross_pnl:+.2f}")
        logger.info(f"[CLOSE] Net P&L: ${net_pnl:+.2f}")
        logger.info(f"[CLOSE] Balance: ${self.balance:.2f}")
        logger.info("=" * 80)
    
    async def scan_for_opportunities(self):
        """Main scanning loop for 5M crypto markets."""
        while self.running:
            try:
                # Fetch active 5M markets
                markets = await self.fetch_5m_crypto_markets()
                
                accepting_markets = [m for m in markets if m.accepting_orders]
                
                if accepting_markets:
                    logger.info(f"Found {len(accepting_markets)} active 5M crypto markets")
                    
                    for market in accepting_markets:
                        if not self.running:
                            break
                        
                        # Skip if at max positions
                        if len(self.positions) >= STRATEGY['max_positions']:
                            break
                        
                        # Get market data
                        orderbook = await self.get_market_orderbook(market.condition_id)
                        trades = await self.get_recent_trades(market.condition_id)
                        
                        # Analyze for opportunity
                        signal = self.analyze_micro_structure(market, orderbook, trades)
                        
                        if signal and signal['confidence'] >= 0.55:
                            await self.execute_trade(market, signal)
                else:
                    logger.info("No active 5M crypto markets found. Checking again in 30s...")
                
                await asyncio.sleep(30)  # Scan every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                await asyncio.sleep(30)
    
    async def heartbeat(self):
        """Log status updates."""
        while self.running:
            win_rate = self.win_count / (self.win_count + self.loss_count) if (self.win_count + self.loss_count) > 0 else 0
            
            logger.info(f"[STATUS] Balance: ${self.balance:.2f} | "
                       f"Open: {len(self.positions)} | "
                       f"Trades: {self.trade_count} | "
                       f"Win%: {win_rate:.1%} | "
                       f"PnL: ${self.total_pnl:+.2f}")
            
            await asyncio.sleep(60)
    
    async def generate_report(self):
        """Generate final session report."""
        # Close all open positions
        for pos in list(self.positions.values()):
            market = self.markets.get(pos.condition_id)
            if market:
                current_price = market.yes_price if pos.side == 'YES' else market.no_price
                await self.close_position(pos, current_price, 'SESSION_END')
        
        total_return = (self.balance - self.initial_balance) / self.initial_balance
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0
        
        report = f"""
{'=' * 80}
5-MINUTE CRYPTO TRADING SESSION REPORT
{'=' * 80}
Session ID: {session_id}
Duration: Session completed

FINANCIAL SUMMARY:
  Initial Balance: ${self.initial_balance:.2f}
  Final Balance:   ${self.balance:.2f}
  Total P&L:       ${self.total_pnl:+.2f} ({total_return:+.2%})

TRADING STATISTICS:
  Total Trades:    {self.trade_count}
  Wins:            {self.win_count}
  Losses:          {self.loss_count}
  Win Rate:        {win_rate:.1%}

Note: This was a paper trading session.
When 5M crypto markets are live on Polymarket, this bot will trade with real data.
{'=' * 80}
Log file: {log_file}
"""
        logger.info(report)
        print(report)
    
    async def run(self, duration_hours: float = 2.0):
        """Run the 5M crypto trading bot."""
        self.running = True
        
        print("\n" + "=" * 80)
        print("POLYMARKET 5-MINUTE CRYPTO TRADING BOT")
        print("=" * 80)
        print(f"Target: https://polymarket.com/crypto/5M")
        print(f"Focus: BTC, ETH, XRP, SOL 5-minute markets")
        print(f"Strategy: High-frequency micro-structure trading")
        print(f"Paper Balance: ${self.balance:.2f}")
        print("=" * 80)
        print()
        
        # Initial scan
        markets = await self.fetch_5m_crypto_markets()
        accepting = [m for m in markets if m.accepting_orders]
        
        if accepting:
            print(f"[OK] Found {len(accepting)} active 5M crypto markets!")
            for m in accepting[:5]:
                print(f"  - [{m.crypto_type}] {m.question[:50]}...")
        else:
            print("[!] No active 5M crypto markets currently available.")
            print("  The bot will continue scanning for new markets...")
        
        print()
        print("Starting trading loops...")
        print()
        
        # Start all tasks
        await asyncio.gather(
            self.scan_for_opportunities(),
            self.monitor_positions(),
            self.heartbeat(),
            self._session_timer(duration_hours)
        )
    
    async def _session_timer(self, duration_hours: float):
        """Session duration timer."""
        await asyncio.sleep(duration_hours * 3600)
        self.running = False
        await self.generate_report()


async def main():
    async with Polymarket5MCryptoBot(balance=100.0) as bot:
        await bot.run(duration_hours=2.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nBot stopped by user.")
