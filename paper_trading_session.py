#!/usr/bin/env python3
"""
PolyBot Paper Trading Session - 2 Hour Run
Starting Balance: $100
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import logging

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = log_dir / f"paper_trading_session_{session_id}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Trade frequency filter constants
MIN_WHALE_SIZE_USD = 10000        # Only whales >$10k
MIN_CONFIDENCE = 0.75             # Only high confidence >75%
MIN_EDGE_EXPECTED = 0.05          # Only if +5% expected profit
MAX_TRADES_PER_HOUR = 2           # Hard limit: 2 trades/hour
MAX_TRADES_PER_DAY = 5            # Hard limit: 5 trades/day
MIN_TIME_BETWEEN_TRADES = 1800    # 30 minutes between trades
COOLDOWN_AFTER_LOSS = 3600        # 1 hour cooldown after loss


class TradeFrequencyFilter:
    """Filters trades to reduce overtrading and improve quality."""
    
    def __init__(self):
        self.trades_today = 0
        self.trades_this_hour = 0
        self.last_trade_time = None
        self.last_loss_time = None
        self.hour_start_time = datetime.now()
        self.day_start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.filter_stats = {
            'rejected_total': 0,
            'rejected_by_whale_size': 0,
            'rejected_by_confidence': 0,
            'rejected_by_edge': 0,
            'rejected_by_hour_limit': 0,
            'rejected_by_day_limit': 0,
            'rejected_by_time_gap': 0,
            'rejected_by_loss_cooldown': 0,
            'accepted': 0,
        }
        
    def should_allow_trade(self, whale_size: float, confidence: float, expected_edge: float) -> tuple[bool, str]:
        """
        Check if a trade should be allowed based on all filters.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        now = datetime.now()
        
        # Reset counters if needed
        self._reset_counters_if_needed(now)
        
        # Check minimum whale size
        if whale_size < MIN_WHALE_SIZE_USD:
            self.filter_stats['rejected_total'] += 1
            self.filter_stats['rejected_by_whale_size'] += 1
            return False, f"Whale size ${whale_size:,.0f} below minimum ${MIN_WHALE_SIZE_USD:,.0f}"
        
        # Check minimum confidence
        if confidence < MIN_CONFIDENCE:
            self.filter_stats['rejected_total'] += 1
            self.filter_stats['rejected_by_confidence'] += 1
            return False, f"Confidence {confidence:.1%} below minimum {MIN_CONFIDENCE:.1%}"
        
        # Check minimum expected edge
        if expected_edge < MIN_EDGE_EXPECTED:
            self.filter_stats['rejected_total'] += 1
            self.filter_stats['rejected_by_edge'] += 1
            return False, f"Expected edge {expected_edge:.1%} below minimum {MIN_EDGE_EXPECTED:.1%}"
        
        # Check daily trade limit
        if self.trades_today >= MAX_TRADES_PER_DAY:
            self.filter_stats['rejected_total'] += 1
            self.filter_stats['rejected_by_day_limit'] += 1
            return False, f"Daily trade limit reached ({self.trades_today}/{MAX_TRADES_PER_DAY})"
        
        # Check hourly trade limit
        if self.trades_this_hour >= MAX_TRADES_PER_HOUR:
            self.filter_stats['rejected_total'] += 1
            self.filter_stats['rejected_by_hour_limit'] += 1
            return False, f"Hourly trade limit reached ({self.trades_this_hour}/{MAX_TRADES_PER_HOUR})"
        
        # Check minimum time between trades
        if self.last_trade_time is not None:
            seconds_since_last = (now - self.last_trade_time).total_seconds()
            if seconds_since_last < MIN_TIME_BETWEEN_TRADES:
                remaining = MIN_TIME_BETWEEN_TRADES - seconds_since_last
                self.filter_stats['rejected_total'] += 1
                self.filter_stats['rejected_by_time_gap'] += 1
                return False, f"Trade cooldown active ({remaining:.0f}s remaining)"
        
        # Check cooldown after loss
        if self.last_loss_time is not None:
            seconds_since_loss = (now - self.last_loss_time).total_seconds()
            if seconds_since_loss < COOLDOWN_AFTER_LOSS:
                remaining = COOLDOWN_AFTER_LOSS - seconds_since_loss
                self.filter_stats['rejected_total'] += 1
                self.filter_stats['rejected_by_loss_cooldown'] += 1
                return False, f"Loss cooldown active ({remaining//60:.0f}m remaining)"
        
        # All filters passed
        self.filter_stats['accepted'] += 1
        return True, "Trade accepted"
    
    def record_trade(self, result: str = None):
        """Record a trade execution and its result."""
        now = datetime.now()
        
        # Reset counters if needed before recording
        self._reset_counters_if_needed(now)
        
        self.trades_today += 1
        self.trades_this_hour += 1
        self.last_trade_time = now
        
        # Record loss time if trade was a loss
        if result and result.upper() == 'LOSS':
            self.last_loss_time = now
            logger.info(f"[FILTER] Loss recorded - cooldown activated for {COOLDOWN_AFTER_LOSS//3600} hour(s)")
    
    def _reset_counters_if_needed(self, now: datetime):
        """Reset daily/hourly counters if time periods have elapsed."""
        # Check if new hour started
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        if current_hour_start > self.hour_start_time:
            self.trades_this_hour = 0
            self.hour_start_time = current_hour_start
            logger.info(f"[FILTER] New hour started - hourly trade counter reset")
        
        # Check if new day started
        current_day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if current_day_start > self.day_start_time:
            self.trades_today = 0
            self.day_start_time = current_day_start
            self.last_loss_time = None  # Reset loss cooldown on new day
            logger.info(f"[FILTER] New day started - daily trade counter reset")
    
    def reset_daily(self):
        """Manually reset daily counters."""
        self.trades_today = 0
        self.last_loss_time = None
        logger.info("[FILTER] Daily counters manually reset")
    
    def get_status(self) -> dict:
        """Get current filter status."""
        now = datetime.now()
        
        return {
            'trades_today': self.trades_today,
            'trades_this_hour': self.trades_this_hour,
            'max_trades_per_day': MAX_TRADES_PER_DAY,
            'max_trades_per_hour': MAX_TRADES_PER_HOUR,
            'last_trade_time': self.last_trade_time.isoformat() if self.last_trade_time else None,
            'last_loss_time': self.last_loss_time.isoformat() if self.last_loss_time else None,
            'in_loss_cooldown': self.last_loss_time is not None and 
                               (now - self.last_loss_time).total_seconds() < COOLDOWN_AFTER_LOSS,
            'seconds_since_last_trade': (now - self.last_trade_time).total_seconds() if self.last_trade_time else None,
            'filter_stats': self.filter_stats,
        }


# Session configuration
SESSION_CONFIG = {
    "session_id": session_id,
    "start_time": datetime.now().isoformat(),
    "duration_hours": 2,
    "initial_balance": 100.0,
    "mode": "PAPER",
    "speed": "ULTRA",
    "tracked_whales": [
        "0x7a105f75dfb91a0f55e70e1479f149768b7786d4",  # Example whale
        "0x8ba40d96f3b1a0f45e5c0f668f5fcee2f5b66e5e",  # Example whale
    ]
}

class PaperTradingSession:
    """2-hour paper trading session manager."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=2)
        self.initial_balance = 100.0
        self.current_balance = 100.0
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.stats = {
            "trades_executed": 0,
            "trades_won": 0,
            "trades_lost": 0,
            "total_volume": 0.0,
            "total_pnl": 0.0,
            "whales_detected": 0,
            "signals_processed": 0,
            "signals_filtered": 0,
        }
        self.running = False
        self.trade_filter = TradeFrequencyFilter()
        
    async def start(self):
        """Start the 2-hour trading session."""
        logger.info("=" * 80)
        logger.info("POLYBOT PAPER TRADING SESSION STARTED")
        logger.info("=" * 80)
        logger.info(f"Session ID: {SESSION_CONFIG['session_id']}")
        logger.info(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"End Time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Initial Balance: ${self.initial_balance:.2f}")
        logger.info(f"Mode: PAPER TRADING (Simulated)")
        logger.info(f"Duration: 2 hours")
        logger.info("=" * 80)
        logger.info("")
        
        self.running = True
        
        # Log filter configuration
        logger.info("=" * 80)
        logger.info("TRADE FREQUENCY FILTERS CONFIGURED")
        logger.info("=" * 80)
        logger.info(f"Min Whale Size:        ${MIN_WHALE_SIZE_USD:>10,}")
        logger.info(f"Min Confidence:        {MIN_CONFIDENCE:>10.1%}")
        logger.info(f"Min Expected Edge:     {MIN_EDGE_EXPECTED:>10.1%}")
        logger.info(f"Max Trades/Hour:       {MAX_TRADES_PER_HOUR:>10}")
        logger.info(f"Max Trades/Day:        {MAX_TRADES_PER_DAY:>10}")
        logger.info(f"Min Time Between:      {MIN_TIME_BETWEEN_TRADES//60:>10} minutes")
        logger.info(f"Cooldown After Loss:   {COOLDOWN_AFTER_LOSS//3600:>10} hour(s)")
        logger.info("=" * 80)
        logger.info("")
        
        # Start all tasks
        tasks = [
            self.session_timer(),
            self.heartbeat_logger(),
            self.simulate_trading(),
            self.monitor_performance(),
            self.generate_reports(),
        ]
        
        await asyncio.gather(*tasks)
        
    async def session_timer(self):
        """Keep session running for exactly 2 hours."""
        while self.running and datetime.now() < self.end_time:
            remaining = self.end_time - datetime.now()
            if remaining.total_seconds() <= 0:
                break
            await asyncio.sleep(1)
        
        self.running = False
        logger.info("=" * 80)
        logger.info("SESSION COMPLETE - 2 HOURS ELAPSED")
        logger.info("=" * 80)
        await self.final_report()
        
    async def heartbeat_logger(self):
        """Log heartbeat every 30 seconds."""
        while self.running:
            remaining = self.end_time - datetime.now()
            elapsed = datetime.now() - self.start_time
            
            # Get filter status
            filter_status = self.trade_filter.get_status()
            
            logger.info(f"[HEARTBEAT] Elapsed: {elapsed.seconds//60}m {elapsed.seconds%60}s | "
                       f"Remaining: {remaining.seconds//60}m {remaining.seconds%60}s | "
                       f"Balance: ${self.current_balance:.2f} | "
                       f"Trades: {self.stats['trades_executed']} | "
                       f"Filtered: {self.stats['signals_filtered']}")
            
            await asyncio.sleep(30)
    
    async def simulate_trading(self):
        """Simulate real-time trading activity."""
        logger.info("[TRADING] Starting trading engine...")
        
        # Import and initialize components
        try:
            from polymarket_tracker.realtime.unified_trading_system import (
                UnifiedRealTimeTradingSystem, TradingMode, SpeedMode, RiskProfile
            )
            
            # Initialize in paper mode
            self.system = UnifiedRealTimeTradingSystem(
                mode=TradingMode.PAPER,
                speed=SpeedMode.ULTRA,
                risk=RiskProfile.MODERATE,
                custom_config={
                    'initial_bankroll': self.initial_balance,
                    'enable_auto_trading': True,
                    'enable_notifications': False,
                }
            )
            
            logger.info("[TRADING] Unified Trading System initialized")
            logger.info("[TRADING] Mode: PAPER | Speed: ULTRA | Risk: MODERATE")
            logger.info("[TRADING] Auto-trading: ENABLED")
            logger.info("")
            
            # Start the system
            await self.system.start()
            logger.info("[TRADING] System started successfully")
            logger.info("[TRADING] Monitoring for whale activity...")
            logger.info("")
            
            # Monitor for trades
            check_interval = 5  # Check every 5 seconds
            
            while self.running:
                try:
                    # Get current status
                    status = await self.system.get_status()
                    metrics = await self.system.get_metrics()
                    
                    # Log any new trades
                    if metrics:
                        trades_today = metrics.get('trades_today', 0)
                        if trades_today > self.stats['trades_executed']:
                            new_trades = trades_today - self.stats['trades_executed']
                            self.stats['trades_executed'] = trades_today
                            
                            # Record trade in filter (assume neutral result initially)
                            self.trade_filter.record_trade(result=None)
                            
                            # Get portfolio info
                            portfolio = await self.system.get_portfolio()
                            if portfolio:
                                self.current_balance = portfolio.get('total_value', self.current_balance)
                                pnl = portfolio.get('total_pnl', 0)
                                
                                logger.info(f"[TRADE] New trade executed! Total: {trades_today}")
                                logger.info(f"[PORTFOLIO] Balance: ${self.current_balance:.2f} | P&L: ${pnl:+.2f}")
                    
                    # Log component status periodically
                    if status:
                        components = status.get('components', {})
                        running = sum(1 for c in components.values() if c.get('running', False))
                        total = len(components)
                        
                        if total > 0 and datetime.now().second % 60 == 0:  # Log every minute
                            logger.info(f"[STATUS] Components: {running}/{total} running")
                    
                except Exception as e:
                    logger.error(f"[ERROR] Trading loop error: {e}")
                
                await asyncio.sleep(check_interval)
            
            # Stop the system
            await self.system.stop()
            logger.info("[TRADING] System stopped")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize trading system: {e}")
            logger.info("[TRADING] Falling back to simulation mode...")
            await self.simulate_fallback_trading()
    
    async def simulate_fallback_trading(self):
        """Fallback simulation if real system fails."""
        logger.info("[SIMULATION] Running in fallback simulation mode")
        logger.info("[SIMULATION] This demonstrates what the bot would do with real data")
        logger.info("")
        
        # Simulate some whale activity
        import random
        
        whale_addresses = SESSION_CONFIG['tracked_whales']
        markets = [
            "Will Bitcoin close above $100k in 2026?",
            "Will Trump win the 2024 election?",
            "Will Ethereum ETF be approved by June?",
            "Will Fed cut rates in March?",
        ]
        
        while self.running:
            # Random whale activity
            if random.random() < 0.1:  # 10% chance every loop
                whale = random.choice(whale_addresses)
                market = random.choice(markets)
                side = random.choice(["YES", "NO"])
                size = random.uniform(1000, 50000)
                price = random.uniform(0.3, 0.7)
                confidence = random.uniform(0.6, 0.95)  # Simulated confidence
                expected_edge = random.uniform(-0.02, 0.12)  # Simulated edge
                
                self.stats['signals_processed'] += 1
                
                logger.info(f"[SIGNAL] Whale activity detected - checking filters...")
                logger.info(f"[SIGNAL] Market: {market}")
                logger.info(f"[SIGNAL] Side: {side} | Size: ${size:,.0f} | Price: {price:.3f}")
                logger.info(f"[SIGNAL] Confidence: {confidence:.1%} | Expected Edge: {expected_edge:+.1%}")
                
                # Apply trade frequency filters
                allowed, reason = self.trade_filter.should_allow_trade(
                    whale_size=size,
                    confidence=confidence,
                    expected_edge=expected_edge
                )
                
                if not allowed:
                    self.stats['signals_filtered'] += 1
                    logger.info(f"[FILTERED] Signal rejected: {reason}")
                    logger.info("")
                    continue
                
                # Signal passed filters - execute trade
                logger.info(f"[FILTER] Signal passed all filters - executing trade")
                
                # Simulate copy trade
                await asyncio.sleep(0.1)  # 100ms execution delay
                
                trade_size = min(50, self.current_balance * 0.2)  # Max 20% of balance
                if trade_size > 10:  # Minimum trade
                    trade = {
                        "timestamp": datetime.now().isoformat(),
                        "whale": whale,
                        "market": market,
                        "side": side,
                        "entry_price": price,
                        "size": trade_size,
                        "confidence": confidence,
                        "expected_edge": expected_edge,
                        "status": "OPEN"
                    }
                    
                    self.trades.append(trade)
                    self.stats['trades_executed'] += 1
                    self.stats['whales_detected'] += 1
                    self.stats['total_volume'] += trade_size
                    
                    # Record trade in filter
                    self.trade_filter.record_trade(result=None)
                    
                    logger.info(f"[COPY] Executed paper trade!")
                    logger.info(f"[COPY] Size: ${trade_size:.2f} | Price: {price:.3f}")
                    
                    # Simulate outcome after random time
                    asyncio.create_task(self.simulate_trade_outcome(trade))
            
            await asyncio.sleep(5)  # Check every 5 seconds
    
    async def simulate_trade_outcome(self, trade):
        """Simulate the outcome of a trade."""
        import random
        
        # Hold for 5-30 minutes
        hold_time = random.uniform(300, 1800)
        await asyncio.sleep(hold_time)
        
        if not self.running:
            return
        
        # 55% win rate (realistic for good whale copying)
        win = random.random() < 0.55
        
        if win:
            pnl_pct = random.uniform(0.05, 0.25)  # 5-25% profit
            trade['status'] = 'WON'
            self.stats['trades_won'] += 1
        else:
            pnl_pct = random.uniform(-0.15, -0.05)  # 5-15% loss
            trade['status'] = 'LOST'
            self.stats['trades_lost'] += 1
            # Record loss in filter for cooldown
            self.trade_filter.record_trade(result='LOSS')
        
        pnl = trade['size'] * pnl_pct
        trade['pnl'] = pnl
        trade['exit_price'] = trade['entry_price'] * (1 + pnl_pct)
        trade['exit_time'] = datetime.now().isoformat()
        
        self.current_balance += pnl
        self.stats['total_pnl'] += pnl
        
        logger.info(f"[RESULT] Trade closed: {trade['status']}")
        logger.info(f"[RESULT] P&L: ${pnl:+.2f} ({pnl_pct*100:+.1f}%)")
        logger.info(f"[RESULT] New Balance: ${self.current_balance:.2f}")
        logger.info("")
    
    async def monitor_performance(self):
        """Monitor and log performance metrics."""
        while self.running:
            elapsed = datetime.now() - self.start_time
            
            # Calculate performance metrics
            if self.stats['trades_executed'] > 0:
                win_rate = self.stats['trades_won'] / self.stats['trades_executed']
                avg_pnl = self.stats['total_pnl'] / self.stats['trades_executed']
            else:
                win_rate = 0
                avg_pnl = 0
            
            # Save stats to file every minute
            if elapsed.seconds % 60 == 0:
                stats_file = log_dir / f"stats_{session_id}.json"
                filter_status = self.trade_filter.get_status()
                with open(stats_file, 'w') as f:
                    json.dump({
                        "session": SESSION_CONFIG,
                        "current_stats": self.stats,
                        "current_balance": self.current_balance,
                        "elapsed_minutes": elapsed.seconds // 60,
                        "win_rate": win_rate,
                        "avg_pnl_per_trade": avg_pnl,
                        "trade_filter_status": filter_status,
                    }, f, indent=2, default=str)
            
            await asyncio.sleep(1)
    
    async def generate_reports(self):
        """Generate periodic reports."""
        report_interval = 300  # Every 5 minutes
        
        while self.running:
            await asyncio.sleep(report_interval)
            
            if not self.running:
                break
            
            elapsed = datetime.now() - self.start_time
            
            logger.info("=" * 80)
            logger.info("PERIODIC REPORT")
            logger.info("=" * 80)
            logger.info(f"Elapsed: {elapsed.seconds // 60} minutes")
            logger.info(f"Current Balance: ${self.current_balance:.2f}")
            logger.info(f"Total P&L: ${self.stats['total_pnl']:+.2f}")
            logger.info(f"Trades: {self.stats['trades_executed']} "
                       f"(Won: {self.stats['trades_won']}, Lost: {self.stats['trades_lost']}, "
                       f"Filtered: {self.stats['signals_filtered']})")
            
            if self.stats['trades_executed'] > 0:
                win_rate = self.stats['trades_won'] / self.stats['trades_executed']
                logger.info(f"Win Rate: {win_rate:.1%}")
            
            logger.info(f"Whales Detected: {self.stats['whales_detected']}")
            logger.info("=" * 80)
            logger.info("")
    
    async def final_report(self):
        """Generate final session report."""
        elapsed = datetime.now() - self.start_time
        total_return = (self.current_balance - self.initial_balance) / self.initial_balance
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL SESSION REPORT")
        logger.info("=" * 80)
        logger.info(f"Session ID: {SESSION_CONFIG['session_id']}")
        logger.info(f"Duration: {elapsed.seconds // 3600}h {(elapsed.seconds % 3600) // 60}m {elapsed.seconds % 60}s")
        logger.info("")
        logger.info("BALANCE SUMMARY:")
        logger.info(f"  Initial Balance:    ${self.initial_balance:>10.2f}")
        logger.info(f"  Final Balance:      ${self.current_balance:>10.2f}")
        logger.info(f"  Total P&L:          ${self.stats['total_pnl']:>+10.2f}")
        logger.info(f"  Return:             {total_return:>+10.2%}")
        logger.info("")
        logger.info("TRADING STATISTICS:")
        logger.info(f"  Total Trades:       {self.stats['trades_executed']:>10}")
        logger.info(f"  Winning Trades:     {self.stats['trades_won']:>10}")
        logger.info(f"  Losing Trades:      {self.stats['trades_lost']:>10}")
        
        if self.stats['trades_executed'] > 0:
            win_rate = self.stats['trades_won'] / self.stats['trades_executed']
            profit_factor = abs(self.stats['total_pnl'] / (self.stats['trades_lost'] or 1))
            logger.info(f"  Win Rate:           {win_rate:>10.1%}")
            logger.info(f"  Profit Factor:      {profit_factor:>10.2f}")
        
        logger.info(f"  Total Volume:       ${self.stats['total_volume']:>10.2f}")
        logger.info(f"  Whales Detected:    {self.stats['whales_detected']:>10}")
        logger.info("")
        # Log filter statistics
        filter_stats = self.trade_filter.filter_stats
        logger.info("FILTER STATISTICS:")
        logger.info(f"  Signals Accepted:    {filter_stats['accepted']:>10}")
        logger.info(f"  Signals Rejected:    {filter_stats['rejected_total']:>10}")
        if filter_stats['rejected_total'] > 0:
            logger.info("  Rejection Reasons:")
            logger.info(f"    - Whale size:      {filter_stats['rejected_by_whale_size']:>10}")
            logger.info(f"    - Confidence:      {filter_stats['rejected_by_confidence']:>10}")
            logger.info(f"    - Expected edge:   {filter_stats['rejected_by_edge']:>10}")
            logger.info(f"    - Hour limit:      {filter_stats['rejected_by_hour_limit']:>10}")
            logger.info(f"    - Day limit:       {filter_stats['rejected_by_day_limit']:>10}")
            logger.info(f"    - Time gap:        {filter_stats['rejected_by_time_gap']:>10}")
            logger.info(f"    - Loss cooldown:   {filter_stats['rejected_by_loss_cooldown']:>10}")
        logger.info("")
        logger.info("PERFORMANCE RATING:")
        
        if total_return > 0.1:
            rating = "EXCELLENT [DONE]"
        elif total_return > 0.05:
            rating = "GOOD [OK]"
        elif total_return > 0:
            rating = "POSITIVE [OK]"
        elif total_return > -0.05:
            rating = "ACCEPTABLE [INFO]"
        else:
            rating = "NEEDS IMPROVEMENT [WARN]"
        
        logger.info(f"  {rating}")
        logger.info("=" * 80)
        
        # Save final report
        report_file = log_dir / f"final_report_{session_id}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "session_config": SESSION_CONFIG,
                "final_stats": self.stats,
                "final_balance": self.current_balance,
                "total_return": total_return,
                "elapsed_seconds": elapsed.seconds,
                "all_trades": self.trades,
                "trade_filter_stats": self.trade_filter.filter_stats,
            }, f, indent=2, default=str)
        
        logger.info(f"Full report saved to: {report_file}")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 80)

async def main():
    """Main entry point."""
    print("=" * 80)
    print("POLYBOT PAPER TRADING SESSION")
    print("=" * 80)
    print(f"Session ID: {session_id}")
    print(f"Starting Balance: $100.00")
    print(f"Duration: 2 hours")
    print(f"Mode: PAPER TRADING")
    print("=" * 80)
    print("")
    print("Starting in 5 seconds...")
    print("Press Ctrl+C to stop early")
    print("")
    
    await asyncio.sleep(5)
    
    session = PaperTradingSession()
    
    try:
        await session.start()
    except KeyboardInterrupt:
        print("\n\n[INTERRUPT] Session stopped by user")
        session.running = False
        await session.final_report()
    except Exception as e:
        logger.error(f"[FATAL] Session error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
