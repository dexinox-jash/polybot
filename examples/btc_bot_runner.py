"""
BTC 5-Minute Bot Runner

Complete example of running the BTC 5-minute trading intelligence bot.
This demonstrates the full workflow from market scanning to signal generation
to position management.

DISCLAIMER: This is for educational purposes only. Do not use with real funds
without extensive testing and understanding of the risks involved.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pandas as pd
from datetime import datetime, timedelta

from polymarket_tracker import (
    BTCMarketScanner,
    MicroWhaleTracker,
    PatternEngine,
    SignalGenerator,
    PositionManager,
    RiskParameters,
    RiskLevel
)
from polymarket_tracker.utils.config import Config
from polymarket_tracker.utils.logger import setup_logging

logger = setup_logging(debug=True)


class BTCFiveMinuteBot:
    """
    Complete BTC 5-Minute Trading Intelligence Bot.
    
    This bot combines:
    1. Real-time market scanning for BTC 5-min markets
    2. Micro-whale tracking (who wins in this niche)
    3. Pattern recognition (momentum, mean reversion, breakouts)
    4. Signal generation with confidence scoring
    5. Risk-managed position sizing
    """
    
    def __init__(self, bankroll: float = 10000, risk_level: RiskLevel = RiskLevel.MODERATE):
        """Initialize the bot."""
        self.config = Config.from_env()
        
        # Initialize components
        self.scanner = BTCMarketScanner(self.config)
        self.whale_tracker = MicroWhaleTracker(self.config)
        self.pattern_engine = PatternEngine()
        self.signal_generator = SignalGenerator(self.pattern_engine)
        
        # Risk management
        risk_params = RiskParameters.from_risk_level(risk_level)
        self.position_manager = PositionManager(bankroll, risk_params)
        
        # State
        self.running = False
        self.scanned_markets: dict = {}
        self.active_signals: list = []
        
        logger.info(f"🤖 BTC 5-Min Bot initialized with ${bankroll:,.0f} bankroll")
    
    async def scan_and_analyze(self):
        """Scan markets and generate signals."""
        logger.info("🔍 Scanning BTC 5-minute markets...")
        
        # Scan for active markets
        markets = await self.scanner.scan_markets()
        
        if not markets:
            logger.info("No active BTC 5-min markets found")
            return
        
        logger.info(f"Found {len(markets)} active markets")
        
        for market in markets:
            await self.analyze_market(market)
    
    async def analyze_market(self, market):
        """Analyze a single market for trading opportunities."""
        market_id = market.market_id
        
        # Get price history from scanner
        metrics = self.scanner.calculate_micro_metrics(market_id)
        
        if not metrics:
            return
        
        # Create tick DataFrame
        if market_id in self.scanner.price_buffers:
            buffer = self.scanner.price_buffers[market_id]
            tick_data = pd.DataFrame([
                {
                    'timestamp': t.timestamp,
                    'price': t.price,
                    'size': t.size,
                    'side': t.side,
                    'is_whale': t.is_whale
                }
                for t in buffer
            ])
        else:
            return
        
        # Get whale data
        whale_data = {
            'positions': [],  # Would come from get_market_whale_positions
            'aligned_whales': [],
            'opposed_whales': []
        }
        
        # Get trader confluence
        trader_confluence = self._get_trader_confluence(market)
        
        # Generate signal
        signal = self.signal_generator.generate_signal(
            market_data={
                'market_id': market_id,
                'question': market.question,
                'expires_at': market.expires_at,
                'regime': market.regime.value,
            },
            tick_data=tick_data,
            whale_data=whale_data,
            trader_confluence=trader_confluence
        )
        
        if signal:
            logger.info(f"🎯 SIGNAL: {signal.direction.value.upper()} "
                       f"{signal.primary_pattern.value} "
                       f"(confidence: {signal.confidence_score:.1%})")
            
            # Check if we can take this signal
            can_trade, reason = self.position_manager.can_take_signal(signal)
            
            if can_trade:
                logger.info(f"✅ Signal approved for execution")
                # In live trading, this would execute the trade
                # For demo, we just log it
            else:
                logger.info(f"⛔ Signal rejected: {reason}")
    
    def _get_trader_confluence(self, market) -> dict:
        """Get confluence from top traders."""
        # Get top performers
        top_traders = self.whale_tracker.get_top_performers(min_sessions=5)
        
        if top_traders.empty:
            return {'agreement_ratio': 0.5}
        
        # Check if hot traders are aligned
        hot_traders = top_traders[top_traders['is_hot'] == True]
        
        # Calculate agreement (simplified)
        if len(hot_traders) > 0:
            # Assume they agree with whale imbalance
            agreement = 0.6 + (market.whale_imbalance * 0.2)
        else:
            agreement = 0.5
        
        return {
            'agreement_ratio': agreement,
            'hot_traders': len(hot_traders),
            'total_traders': len(top_traders)
        }
    
    async def update_positions(self):
        """Update open positions and check for exits."""
        # Get current prices for all open positions
        market_prices = {}
        
        for pos in self.position_manager.portfolio.open_positions.values():
            if pos.market_id in self.scanned_markets:
                market = self.scanned_markets[pos.market_id]
                market_prices[pos.market_id] = market.yes_price
        
        # Update positions
        actions = self.position_manager.update_positions(market_prices)
        
        for action in actions:
            pos = action['position']
            reason = action['reason']
            exit_price = action['exit_price']
            
            logger.info(f"🔔 EXIT TRIGGERED: {pos.direction} position "
                       f"via {reason} at ${exit_price:.4f}")
            
            # Close position (demo only)
            # trade_record = self.position_manager.close_position(
            #     pos.position_id, exit_price, reason
            # )
    
    def display_status(self):
        """Display current bot status."""
        print("\n" + "=" * 70)
        print("🤖 BTC 5-MINUTE BOT STATUS")
        print("=" * 70)
        
        # Portfolio
        portfolio = self.position_manager.get_portfolio_summary()
        print(f"\n💼 PORTFOLIO")
        print(f"  Bankroll: ${portfolio['bankroll']:,.2f}")
        print(f"  Available: ${portfolio['available_balance']:,.2f}")
        print(f"  Exposure: ${portfolio['total_exposure']:,.2f} ({portfolio['exposure_pct']:.1%})")
        print(f"  Daily P&L: ${portfolio['daily_pnl']:+.2f}")
        print(f"  Total P&L: ${portfolio['total_pnl']:+.2f}")
        print(f"  Drawdown: {portfolio['current_drawdown']:.2%}")
        
        # Open positions
        print(f"\n📊 OPEN POSITIONS ({portfolio['open_positions']})")
        positions_df = self.position_manager.get_position_report()
        if not positions_df.empty:
            print(positions_df.to_string(index=False))
        else:
            print("  No open positions")
        
        # Active signals
        print(f"\n🎯 ACTIVE SIGNALS")
        signals = self.signal_generator.get_active_signals()
        if signals:
            for sig in signals[:3]:  # Show top 3
                print(f"  {sig.direction.value.upper()} | {sig.primary_pattern.value} | "
                      f"Confidence: {sig.confidence_score:.1%} | "
                      f"R:R: {sig.risk_reward:.2f}")
        else:
            print("  No active signals")
        
        # Trade statistics
        print(f"\n📈 TRADE STATISTICS")
        stats = self.position_manager.get_trade_statistics()
        if 'message' not in stats:
            print(f"  Total Trades: {stats['total_trades']}")
            print(f"  Win Rate: {stats['win_rate']:.1%}")
            print(f"  Profit Factor: {stats['profit_factor']:.2f}")
            print(f"  Avg R-Multiple: {stats['avg_r_multiple']:.2f}")
        else:
            print(f"  {stats['message']}")
        
        print("\n" + "=" * 70)
    
    async def run(self, duration_minutes: int = 30):
        """Run the bot for specified duration."""
        self.running = True
        start_time = datetime.now()
        
        logger.info(f"🚀 Bot started. Running for {duration_minutes} minutes...")
        
        try:
            while self.running and (datetime.now() - start_time).seconds < duration_minutes * 60:
                # Scan and analyze
                await self.scan_and_analyze()
                
                # Update positions
                await self.update_positions()
                
                # Display status
                self.display_status()
                
                # Wait before next iteration
                await asyncio.sleep(10)  # 10-second scan interval
                
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("🏁 Bot shutdown complete")
            self.display_status()


def main():
    """Main entry point."""
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║           ₿ BTC 5-MINUTE TRADING INTELLIGENCE BOT ₿              ║
    ║                                                                  ║
    ║  Highly specialized analytical engine for BTC 5-min markets     ║
    ║  Features:                                                       ║
    ║  • Real-time micro-pattern recognition                          ║
    ║  • Whale confluence analysis                                     ║
    ║  • Kelly Criterion position sizing                               ║
    ║  • Risk-managed portfolio heat                                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Configuration
    bankroll = float(input("Enter bankroll ($) [default 10000]: ") or 10000)
    
    print("\nRisk Level:")
    print("1. Conservative (1% risk/trade)")
    print("2. Moderate (2% risk/trade)")
    print("3. Aggressive (3% risk/trade)")
    
    risk_choice = input("Select [1-3, default 2]: ") or "2"
    risk_levels = {
        "1": RiskLevel.CONSERVATIVE,
        "2": RiskLevel.MODERATE,
        "3": RiskLevel.AGGRESSIVE
    }
    risk_level = risk_levels.get(risk_choice, RiskLevel.MODERATE)
    
    # Initialize and run bot
    bot = BTCFiveMinuteBot(bankroll=bankroll, risk_level=risk_level)
    
    print("\n⚠️  DISCLAIMER:")
    print("This bot is for EDUCATIONAL PURPOSES ONLY.")
    print("Do not use with real funds without extensive testing.")
    print("Crypto trading involves substantial risk of loss.\n")
    
    input("Press Enter to start (Ctrl+C to stop)...")
    
    # Run the bot
    try:
        asyncio.run(bot.run(duration_minutes=60))
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
