"""
BTC 5-Minute Bot - Simple Demo (No Dependencies)

This demonstrates the bot's logic with pure Python - no external packages needed.
"""

import random
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict
from enum import Enum


class SignalType(Enum):
    MOMENTUM_LONG = "momentum_long"
    MOMENTUM_SHORT = "momentum_short"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    WHALE_ACCUMULATION = "whale_accumulation"
    NO_SIGNAL = "no_signal"


@dataclass
class Market:
    """Simulated BTC 5-min market."""
    id: str
    question: str
    price: float = 0.50
    volume: float = 0.0
    whale_imbalance: float = 0.0
    
    def update(self):
        """Update market price."""
        # Random walk
        change = random.gauss(0, 0.01)
        
        # Add momentum occasionally
        if random.random() < 0.1:
            change += random.choice([-0.03, 0.03])
        
        self.price = max(0.01, min(0.99, self.price + change))
        self.volume += random.uniform(1000, 5000)
        
        # Simulate whale activity
        if random.random() < 0.2:
            self.whale_imbalance = random.uniform(-0.8, 0.8)


@dataclass
class Signal:
    """Trading signal."""
    market: str
    pattern: SignalType
    direction: str
    confidence: float
    entry: float
    target: float
    stop: float
    risk_reward: float
    reasoning: List[str]


class PatternEngine:
    """Detect patterns in price action."""
    
    def analyze(self, market: Market, price_history: List[float]) -> List[Signal]:
        """Analyze market for patterns."""
        signals = []
        
        if len(price_history) < 5:
            return signals
        
        # Calculate momentum
        momentum = (price_history[-1] - price_history[-5]) / price_history[-5]
        
        # Momentum Long
        if momentum > 0.02 and market.price > 0.5:
            signals.append(Signal(
                market=market.id,
                pattern=SignalType.MOMENTUM_LONG,
                direction="LONG",
                confidence=random.uniform(0.65, 0.85),
                entry=market.price,
                target=min(0.99, market.price * 1.03),
                stop=market.price * 0.985,
                risk_reward=2.0,
                reasoning=[
                    f"Strong momentum: {momentum:.2%}",
                    "Price above 0.5 midpoint",
                    f"Volume: ${market.volume:,.0f}"
                ]
            ))
        
        # Momentum Short
        elif momentum < -0.02 and market.price < 0.5:
            signals.append(Signal(
                market=market.id,
                pattern=SignalType.MOMENTUM_SHORT,
                direction="SHORT",
                confidence=random.uniform(0.65, 0.85),
                entry=market.price,
                target=max(0.01, market.price * 0.97),
                stop=market.price * 1.015,
                risk_reward=2.0,
                reasoning=[
                    f"Negative momentum: {momentum:.2%}",
                    "Price below 0.5 midpoint",
                    f"Volume: ${market.volume:,.0f}"
                ]
            ))
        
        # Whale Accumulation
        if abs(market.whale_imbalance) > 0.6:
            direction = "LONG" if market.whale_imbalance > 0 else "SHORT"
            signals.append(Signal(
                market=market.id,
                pattern=SignalType.WHALE_ACCUMULATION,
                direction=direction,
                confidence=abs(market.whale_imbalance),
                entry=market.price,
                target=market.price * (1.02 if direction == "LONG" else 0.98),
                stop=market.price * (0.98 if direction == "LONG" else 1.02),
                risk_reward=1.0,
                reasoning=[
                    f"Whale imbalance: {market.whale_imbalance:.1%}",
                    "Smart money flow detected"
                ]
            ))
        
        return signals


class PositionManager:
    """Manage positions and risk."""
    
    def __init__(self, bankroll: float):
        self.bankroll = bankroll
        self.initial_bankroll = bankroll
        self.positions = []
        self.trade_history = []
    
    def can_trade(self, signal: Signal) -> bool:
        """Check if we can take this signal."""
        return signal.confidence >= 0.65 and signal.risk_reward >= 1.5
    
    def calculate_size(self, signal: Signal) -> float:
        """Calculate position size using Kelly Criterion."""
        # Kelly: f = (bp - q) / b
        p = signal.confidence
        q = 1 - p
        b = signal.risk_reward
        
        if b > 0:
            kelly = (b * p - q) / b
        else:
            kelly = 0
        
        # Half-Kelly for safety
        kelly = max(0, kelly * 0.5)
        
        # Limit to 2% risk
        size = self.bankroll * min(kelly, 0.02)
        
        return min(size, 5000)  # Max $5k per position
    
    def execute_trade(self, signal: Signal) -> Dict:
        """Execute a simulated trade."""
        size = self.calculate_size(signal)
        
        # Simulate outcome based on confidence
        win = random.random() < signal.confidence
        
        if win:
            pnl = size * signal.risk_reward * 0.02  # Simplified P&L
            result = "WIN"
        else:
            pnl = -size * 0.02
            result = "LOSS"
        
        self.bankroll += pnl
        
        trade = {
            'market': signal.market,
            'direction': signal.direction,
            'pattern': signal.pattern.value,
            'confidence': signal.confidence,
            'size': size,
            'pnl': pnl,
            'result': result,
        }
        
        self.trade_history.append(trade)
        return trade


def print_header():
    """Print bot header."""
    print("""
======================================================================
              BTC 5-MINUTE INTELLIGENCE BOT - DEMO

     *** SIMULATION MODE - Synthetic Data - Educational Only ***
======================================================================
    """)


def run_demo():
    """Run the demo."""
    print_header()
    
    # Initialize
    bankroll = 10000
    markets = [
        Market("BTC-1", "Will BTC be > $95K in 5 mins?"),
        Market("BTC-2", "Will BTC be < $94K in 5 mins?"),
        Market("BTC-3", "Will BTC volatility spike?"),
    ]
    pattern_engine = PatternEngine()
    position_manager = PositionManager(bankroll)
    
    price_history = {m.id: [] for m in markets}
    
    print(f"[BANK] Starting Bankroll: ${bankroll:,.2f}")
    print(f"[TIME] Running 30-second simulation...\n")
    
    # Run simulation
    iterations = 10
    for i in range(1, iterations + 1):
        print(f"{'='*70}")
        print(f"[ITERATION {i}/{iterations}] | {datetime.now().strftime('%H:%M:%S')}")
        print('='*70)
        
        # Update markets
        for market in markets:
            market.update()
            price_history[market.id].append(market.price)
            
            print(f"\n[MARKET] {market.question}")
            print(f"   Price: ${market.price:.4f} | Volume: ${market.volume:,.0f}")
            
            if abs(market.whale_imbalance) > 0.5:
                direction = "BULLISH" if market.whale_imbalance > 0 else "BEARISH"
                print(f"   [WHALE] {direction} Imbalance: {market.whale_imbalance:+.1%}")
        
        # Analyze for signals
        all_signals = []
        for market in markets:
            signals = pattern_engine.analyze(market, price_history[market.id])
            all_signals.extend(signals)
        
        # Display signals
        if all_signals:
            # Take best signal
            best_signal = max(all_signals, key=lambda s: s.confidence)
            
            print(f"\n[SIGNAL] BEST SIGNAL DETECTED!")
            print(f"   Market: {best_signal.market}")
            print(f"   Pattern: {best_signal.pattern.value.upper()}")
            print(f"   Direction: {best_signal.direction}")
            print(f"   Confidence: {best_signal.confidence:.1%}")
            print(f"   Risk/Reward: {best_signal.risk_reward:.2f}")
            print(f"   Entry: ${best_signal.entry:.4f}")
            print(f"   Target: ${best_signal.target:.4f}")
            print(f"   Stop: ${best_signal.stop:.4f}")
            
            print(f"\n   [REASONING]:")
            for reason in best_signal.reasoning:
                print(f"      • {reason}")
            
            # Execute if meets criteria
            if position_manager.can_trade(best_signal):
                size = position_manager.calculate_size(best_signal)
                print(f"\n   [POSITION] Calculated Size: ${size:.0f}")
                print(f"   [EXECUTING] TRADE...")
                
                trade = position_manager.execute_trade(best_signal)
                
                status = "[WIN]" if trade['result'] == "WIN" else "[LOSS]"
                print(f"   {status} Result: {trade['result']} | P&L: ${trade['pnl']:+.2f}")
            else:
                print(f"\n   [REJECTED] Signal (confidence < 65% or R:R < 1.5)")
        else:
            print(f"\n[WAITING] No signals this iteration")
        
        print(f"\n[PORTFOLIO] Current Bankroll: ${position_manager.bankroll:,.2f}")
        print(f"[P&L] ${position_manager.bankroll - bankroll:+.2f}")
        
        time.sleep(0.5)  # Brief pause between iterations
    
    # Final report
    print("\n" + "="*70)
    print("[FINAL REPORT]")
    print("="*70)
    
    print(f"\n[PORTFOLIO SUMMARY]:")
    print(f"   Starting: ${bankroll:,.2f}")
    print(f"   Final: ${position_manager.bankroll:,.2f}")
    print(f"   P&L: ${position_manager.bankroll - bankroll:+.2f}")
    print(f"   Return: {((position_manager.bankroll / bankroll) - 1) * 100:+.2f}%")
    
    trades = position_manager.trade_history
    if trades:
        wins = sum(1 for t in trades if t['result'] == 'WIN')
        win_rate = wins / len(trades)
        total_pnl = sum(t['pnl'] for t in trades)
        
        print(f"\n[TRADING STATISTICS]:")
        print(f"   Total Trades: {len(trades)}")
        print(f"   Wins: {wins} | Losses: {len(trades) - wins}")
        print(f"   Win Rate: {win_rate:.1%}")
        print(f"   Total P&L: ${total_pnl:+.2f}")
        
        print(f"\n[TRADE HISTORY]:")
        for i, trade in enumerate(trades, 1):
            status = "[WIN]" if trade['result'] == "WIN" else "[LOSS]"
            print(f"   {i}. {status} {trade['direction']} {trade['pattern']} | "
                  f"${trade['pnl']:+.2f} ({trade['confidence']:.0%} conf)")
    else:
        print(f"\n[INFO] No trades executed during simulation")
    
    print("\n" + "="*70)
    print("[DEMO COMPLETED]")
    print("="*70)
    print("\n[WARNING] Remember: This was a simulation with random outcomes.")
    print("   Real trading involves significant risk of loss.")
    print("   Always do your own research and trade responsibly.\n")


if __name__ == "__main__":
    run_demo()
