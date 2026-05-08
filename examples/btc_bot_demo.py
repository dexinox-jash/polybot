"""
BTC 5-Minute Bot - Demo Mode

This runs the bot in demonstration mode with simulated data
to show how the system works without requiring API keys.

For educational purposes only.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import deque

from polymarket_tracker import (
    PatternEngine,
    SignalGenerator,
    PositionManager,
    RiskParameters,
    RiskLevel
)
from polymarket_tracker.analysis.pattern_engine import (
    PatternSignal, SignalType, PatternConfidence
)
from polymarket_tracker.analysis.signal_generator import (
    TradeSignal, TradeDirection, SignalStatus
)
from polymarket_tracker.utils.logger import setup_logging

logger = setup_logging(debug=True)


class SimulatedBTCMarket:
    """Simulates a BTC 5-minute prediction market for demo."""
    
    def __init__(self, market_id: str, question: str):
        self.market_id = market_id
        self.question = question
        self.price = 0.50
        self.created_at = datetime.now()
        self.expires_at = datetime.now() + timedelta(minutes=5)
        self.price_history = deque(maxlen=300)
        self.whale_activity = {'yes': 0, 'no': 0}
        
    def generate_tick(self):
        """Generate a simulated price tick."""
        # Random walk with slight momentum
        change = random.gauss(0, 0.005)
        
        # Occasionally inject momentum (trend)
        if random.random() < 0.1:
            change += random.choice([-0.02, 0.02])
        
        # Occasionally inject mean reversion
        if self.price > 0.65:
            change -= 0.005
        elif self.price < 0.35:
            change += 0.005
        
        self.price = max(0.01, min(0.99, self.price + change))
        
        tick = {
            'timestamp': datetime.now(),
            'price': self.price,
            'size': random.uniform(100, 2000),
            'side': random.choice(['buy', 'sell']),
            'is_whale': random.random() < 0.15,  # 15% whale trades
        }
        
        self.price_history.append(tick)
        
        # Simulate whale activity
        if tick['is_whale']:
            if tick['side'] == 'buy':
                if self.price > 0.5:
                    self.whale_activity['yes'] += tick['size']
                else:
                    self.whale_activity['no'] += tick['size']
        
        return tick
    
    def get_dataframe(self):
        """Convert price history to DataFrame."""
        return pd.DataFrame(list(self.price_history))
    
    @property
    def time_remaining(self):
        return (self.expires_at - datetime.now()).total_seconds()


class DemoWhaleTracker:
    """Simulated whale tracker for demo."""
    
    def __init__(self):
        self.traders = {
            '0xWhale1': {
                'name': 'CryptoKing',
                'win_rate': 0.68,
                'profit_factor': 2.1,
                'is_hot': True,
                'is_dangerous': True,
            },
            '0xWhale2': {
                'name': 'BTCMaster',
                'win_rate': 0.62,
                'profit_factor': 1.8,
                'is_hot': True,
                'is_dangerous': False,
            },
            '0xWhale3': {
                'name': 'QuickTrader',
                'win_rate': 0.58,
                'profit_factor': 1.5,
                'is_hot': False,
                'is_dangerous': True,
            },
        }
    
    def get_top_performers(self, min_sessions=5):
        data = []
        for addr, trader in self.traders.items():
            data.append({
                'address': addr,
                'name': trader['name'],
                'win_rate': trader['win_rate'],
                'profit_factor': trader['profit_factor'],
                'recent_pnl': random.uniform(5000, 15000),
                'is_hot': trader['is_hot'],
                'is_dangerous': trader['is_dangerous'],
                'score': trader['win_rate'] * trader['profit_factor'] / 2,
            })
        return pd.DataFrame(data).sort_values('score', ascending=False)


class BTCFiveMinuteBotDemo:
    """Demo version of the BTC 5-Minute Bot."""
    
    def __init__(self, bankroll: float = 10000):
        self.bankroll = bankroll
        
        # Initialize components
        self.pattern_engine = PatternEngine()
        self.signal_generator = SignalGenerator(self.pattern_engine)
        
        risk_params = RiskParameters.from_risk_level(RiskLevel.MODERATE)
        self.position_manager = PositionManager(bankroll, risk_params)
        
        self.whale_tracker = DemoWhaleTracker()
        
        # Simulated markets
        self.markets = [
            SimulatedBTCMarket("0xBTC1", "Will BTC be above $95K in 5 mins?"),
            SimulatedBTCMarket("0xBTC2", "Will BTC be below $94K in 5 mins?"),
            SimulatedBTCMarket("0xBTC3", "Will BTC volatility spike in 5 mins?"),
        ]
        
        self.running = False
        self.iteration = 0
        
        # Statistics
        self.signals_generated = 0
        self.signals_executed = 0
        self.patterns_detected = {pt: 0 for pt in SignalType}
        
        print("=" * 70)
        print("🤖 BTC 5-MINUTE BOT - DEMO MODE")
        print("=" * 70)
        print("⚠️  This is a SIMULATION with synthetic market data")
        print("⚠️  No real trades are being executed")
        print("⚠️  For educational purposes only\n")
        
    async def run_simulation(self, duration_seconds: int = 120):
        """Run the demo simulation."""
        self.running = True
        start_time = datetime.now()
        
        print(f"🚀 Starting simulation with ${self.bankroll:,.0f} bankroll")
        print(f"⏱️  Running for {duration_seconds} seconds...\n")
        
        try:
            while self.running and (datetime.now() - start_time).seconds < duration_seconds:
                self.iteration += 1
                
                print(f"\n{'='*70}")
                print(f"📊 ITERATION {self.iteration} | {datetime.now().strftime('%H:%M:%S')}")
                print('='*70)
                
                # Generate ticks for all markets
                for market in self.markets:
                    market.generate_tick()
                
                # Analyze each market
                for market in self.markets:
                    await self.analyze_market(market)
                
                # Update positions
                self.update_positions()
                
                # Display status every 5 iterations
                if self.iteration % 5 == 0:
                    self.display_status()
                
                # Simulate 1-second delay
                await asyncio.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user")
        finally:
            self.running = False
            self.final_report()
    
    async def analyze_market(self, market: SimulatedBTCMarket):
        """Analyze a simulated market."""
        tick_data = market.get_dataframe()
        
        if len(tick_data) < 20:
            return
        
        # Create market data dict
        market_data = {
            'market_id': market.market_id,
            'question': market.question,
            'expires_at': market.expires_at,
            'regime': 'simulated',
        }
        
        # Calculate whale confluence
        total_whale = market.whale_activity['yes'] + market.whale_activity['no']
        whale_imbalance = 0.5
        if total_whale > 0:
            whale_imbalance = market.whale_activity['yes'] / total_whale
        
        whale_data = {
            'positions': [],
            'whale_imbalance': whale_imbalance,
        }
        
        trader_confluence = {
            'agreement_ratio': 0.5 + (whale_imbalance - 0.5) * 0.4,
            'hot_traders': sum(1 for t in self.whale_tracker.traders.values() if t['is_hot']),
        }
        
        # Generate signal
        signal = self.signal_generator.generate_signal(
            market_data, tick_data, whale_data, trader_confluence
        )
        
        if signal:
            self.signals_generated += 1
            self.patterns_detected[signal.primary_pattern] += 1
            
            print(f"\n🎯 SIGNAL DETECTED!")
            print(f"   Market: {market.question[:50]}...")
            print(f"   Pattern: {signal.primary_pattern.value}")
            print(f"   Direction: {signal.direction.value.upper()}")
            print(f"   Confidence: {signal.confidence_score:.1%}")
            print(f"   Risk/Reward: {signal.risk_reward:.2f}")
            print(f"   Whale Confluence: {trader_confluence['agreement_ratio']:.1%}")
            
            # Simulate execution decision
            if signal.confidence_score >= 0.65:
                self.simulate_trade(signal, market)
    
    def simulate_trade(self, signal: TradeSignal, market: SimulatedBTCMarket):
        """Simulate executing a trade."""
        can_trade, reason = self.position_manager.can_take_signal(signal)
        
        if can_trade:
            # Simulate fill price (slippage)
            slippage = random.uniform(-0.002, 0.002)
            fill_price = signal.entry_price + slippage
            
            # Open position (simulated)
            position_size = self.position_manager.calculate_position_size(signal, fill_price)
            
            print(f"\n   ✅ TRADE EXECUTED (Simulated)")
            print(f"      Size: ${position_size:.0f}")
            print(f"      Fill Price: ${fill_price:.4f}")
            print(f"      Target: ${signal.target_price:.4f}")
            print(f"      Stop: ${signal.stop_loss:.4f}")
            
            self.signals_executed += 1
            
            # Simulate outcome after random delay
            asyncio.create_task(self.simulate_outcome(signal, market))
        else:
            print(f"\n   ❌ Trade rejected: {reason}")
    
    async def simulate_outcome(self, signal: TradeSignal, market: SimulatedBTCMarket):
        """Simulate trade outcome."""
        # Wait a bit
        await asyncio.sleep(1)
        
        # Random outcome based on confidence
        win_prob = signal.win_probability
        is_win = random.random() < win_prob
        
        if is_win:
            pnl = signal.suggested_size * signal.expected_return
            result = "✅ WIN"
        else:
            pnl = -signal.suggested_size * abs(signal.entry_price - signal.stop_loss) / signal.entry_price
            result = "❌ LOSS"
        
        print(f"\n   {result} | P&L: ${pnl:+.2f}")
        
        # Update portfolio
        self.position_manager.portfolio.bankroll += pnl
        self.position_manager.portfolio.total_pnl += pnl
    
    def update_positions(self):
        """Update open positions (simulated)."""
        # In real bot, this would check stops/targets
        pass
    
    def display_status(self):
        """Display current status."""
        print("\n" + "-" * 70)
        print("📊 STATUS REPORT")
        print("-" * 70)
        
        portfolio = self.position_manager.get_portfolio_summary()
        print(f"Bankroll: ${portfolio['bankroll']:,.2f}")
        print(f"Total P&L: ${portfolio['total_pnl']:+,.2f}")
        print(f"Signals Generated: {self.signals_generated}")
        print(f"Signals Executed: {self.signals_executed}")
        
        # Pattern breakdown
        print("\nPatterns Detected:")
        for pattern, count in self.patterns_detected.items():
            if count > 0:
                print(f"  - {pattern.value}: {count}")
    
    def final_report(self):
        """Display final report."""
        print("\n" + "=" * 70)
        print("📈 FINAL REPORT")
        print("=" * 70)
        
        portfolio = self.position_manager.get_portfolio_summary()
        
        print(f"\n💼 Portfolio Summary:")
        print(f"  Starting Bankroll: ${self.bankroll:,.2f}")
        print(f"  Final Bankroll: ${portfolio['bankroll']:,.2f}")
        print(f"  Total P&L: ${portfolio['total_pnl']:+,.2f}")
        print(f"  Return: {(portfolio['total_pnl'] / self.bankroll) * 100:+.2f}%")
        
        print(f"\n📊 Signal Statistics:")
        print(f"  Total Signals Generated: {self.signals_generated}")
        print(f"  Signals Executed: {self.signals_executed}")
        print(f"  Execution Rate: {(self.signals_executed/max(1,self.signals_generated))*100:.1f}%")
        
        print(f"\n🔍 Pattern Distribution:")
        for pattern, count in self.patterns_detected.items():
            if count > 0:
                pct = (count / max(1, self.signals_generated)) * 100
                print(f"  - {pattern.value}: {count} ({pct:.1f}%)")
        
        print("\n" + "=" * 70)
        print("✅ Demo completed!")
        print("=" * 70)


def main():
    """Run the demo."""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║              ₿ BTC 5-MINUTE BOT - DEMO MODE ₿                    ║
    ║                                                                  ║
    ║  This is a SIMULATION with synthetic market data                ║
    ║  No real money is at risk                                       ║
    ║  For educational purposes only                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Get configuration
    try:
        bankroll = float(input("\nEnter simulated bankroll ($) [default 10000]: ") or 10000)
    except ValueError:
        bankroll = 10000
    
    print("\nRisk Level:")
    print("1. Conservative (1% risk/trade)")
    print("2. Moderate (2% risk/trade)")
    print("3. Aggressive (3% risk/trade)")
    
    risk_choice = input("Select [1-3, default 2]: ") or "2"
    
    duration = input("\nSimulation duration in seconds [default 60]: ") or "60"
    try:
        duration = int(duration)
    except ValueError:
        duration = 60
    
    print("\n" + "=" * 70)
    print("🚀 Starting simulation...")
    print("Press Ctrl+C to stop early")
    print("=" * 70 + "\n")
    
    # Create and run bot
    bot = BTCFiveMinuteBotDemo(bankroll=bankroll)
    
    try:
        asyncio.run(bot.run_simulation(duration_seconds=duration))
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
