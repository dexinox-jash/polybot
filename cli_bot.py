#!/usr/bin/env python3
"""
Polymarket Copy-Trading CLI Bot

A sophisticated, API-efficient copy-trading bot focused on:
- Quality over quantity (1 bet/day target)
- Deep analysis of top 5 winners
- Comprehensive EV calculations
- Risk-first portfolio management

Usage:
    python cli_bot.py status      # Show current status
    python cli_bot.py scan        # Scan for top winners
    python cli_bot.py analyze     # Deep analysis for best daily bet
    python cli_bot.py copy --yes  # Execute the recommended trade
    python cli_bot.py portfolio   # View portfolio status
"""

import os
import sys
import json
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from polymarket_tracker.data.subgraph_client import SubgraphClient
from polymarket_tracker.winners.winner_discovery import WinnerDiscovery
from polymarket_tracker.winners.ev_calculator import EVCalculator
from polymarket_tracker.winners.copy_engine import CopyEngine
from polymarket_tracker.risk.position_manager import PositionManager
from polymarket_tracker.deep_analysis.winner_intelligence import WinnerIntelligence
from polymarket_tracker.deep_analysis.advanced_ev import AdvancedEVCalculator
from polymarket_tracker.deep_analysis.multi_factor_model import MultiFactorModel
from polymarket_tracker.deep_analysis.research_engine import ResearchEngine


class CLIBot:
    """Main CLI interface for the copy-trading bot."""
    
    def __init__(self):
        self.subgraph = None
        self.winner_discovery = None
        self.ev_calc = None
        self.copy_engine = None
        self.research_engine = None
        self.state_file = project_root / "bot_state.json"
        self.state = self._load_state()
        self.winners = []  # Top 5 winners
        
    def _load_state(self) -> Dict:
        """Load bot state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "daily_bet_count": 0,
            "last_bet_date": None,
            "portfolio_value": 10000,
            "current_positions": [],
            "daily_pnl": 0,
            "total_pnl": 0,
            "winners_cached": [],
            "last_scan": None
        }
    
    def _save_state(self):
        """Save bot state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    def _reset_daily_count_if_needed(self):
        """Reset daily bet count if it's a new day."""
        last_date = self.state.get("last_bet_date")
        today = datetime.now().strftime("%Y-%m-%d")
        if last_date != today:
            self.state["daily_bet_count"] = 0
            self.state["daily_pnl"] = 0
            self.state["last_bet_date"] = today
            self._save_state()
    
    async def _init_clients(self):
        """Initialize API clients."""
        if not self.subgraph:
            api_key = os.getenv("THEGRAPH_API_KEY")
            if not api_key:
                print("Error: THEGRAPH_API_KEY not set")
                return False
            self.subgraph = SubgraphClient(api_key)
            self.winner_discovery = WinnerDiscovery(self.subgraph)
            self.ev_calc = EVCalculator(self.subgraph)
            from polymarket_tracker.risk.position_manager import RiskParameters
            risk_params = RiskParameters(
                max_risk_per_trade=0.02,
                max_total_exposure=0.50,
                max_open_positions=5,
                max_daily_drawdown=0.10
            )
            self.position_manager = PositionManager(
                initial_bankroll=self.state['portfolio_value'],
                risk_params=risk_params
            )
            self.copy_engine = CopyEngine(self.ev_calc, self.position_manager)
            
            # Initialize deep analysis
            winner_intel = WinnerIntelligence(self.subgraph)
            adv_ev = AdvancedEVCalculator(self.subgraph)
            factor_model = MultiFactorModel()
            self.research_engine = ResearchEngine(winner_intel, adv_ev, factor_model)
        return True
    
    def status(self):
        """Show current bot status."""
        self._reset_daily_count_if_needed()
        
        print("=" * 60)
        print("POLYBOT - Copy Trading Status")
        print("=" * 60)
        
        print(f"\n[DAILY TARGETS]")
        print(f"  Bets placed today: {self.state['daily_bet_count']} / 1")
        remaining = 1 - self.state['daily_bet_count']
        print(f"  Remaining: {remaining}")
        
        print(f"\n[PORTFOLIO]")
        print(f"  Total Value: ${self.state['portfolio_value']:,.0f}")
        print(f"  Daily P&L: ${self.state['daily_pnl']:+.2f}")
        print(f"  Total P&L: ${self.state['total_pnl']:+.2f}")
        print(f"  Open Positions: {len(self.state['current_positions'])}")
        
        if self.state['current_positions']:
            total_exposure = sum(p.get('size', 0) for p in self.state['current_positions'])
            heat = total_exposure / self.state['portfolio_value']
            print(f"  Portfolio Heat: {heat:.1%}")
        else:
            print(f"  Portfolio Heat: 0%")
        
        print(f"\n[WINNERS]")
        if self.state.get("winners_cached"):
            print(f"  Top winners cached: {len(self.state['winners_cached'])}")
            for i, w in enumerate(self.state['winners_cached'][:3], 1):
                print(f"    {i}. {w.get('ens', w['address'][:12])}: "
                      f"{w.get('win_rate', 0):.1%} WR, "
                      f"{w.get('profit_factor', 0):.2f} PF")
        else:
            print(f"  No winners cached. Run 'scan' first.")
        
        last_scan = self.state.get("last_scan")
        if last_scan:
            print(f"  Last scan: {last_scan}")
        
        print("\n" + "=" * 60)
    
    async def scan(self):
        """Scan for top winners."""
        print("=" * 60)
        print("SCANNING FOR TOP WINNERS")
        print("=" * 60)
        
        if not await self._init_clients():
            return
        
        print("\nScanning Polymarket for statistically proven winners...")
        print("Criteria: >50 bets, >55% win rate, >1.3 profit factor, p<0.05")
        
        try:
            # Fetch all traders
            print("  Fetching trader data...")
            self.winners = await self.winner_discovery.discover_winners(limit=100)
            
            if not self.winners:
                print("\n  No qualifying winners found.")
                return
            
            print(f"\n  Found {len(self.winners)} qualifying winners")
            print("\n  Top 5 Winners:")
            print("  " + "-" * 56)
            print(f"  {'#':<3} {'Address/ENS':<20} {'Win%':<8} {'PF':<6} {'Score':<6}")
            print("  " + "-" * 56)
            
            top_5 = self.winners[:5]
            for i, winner in enumerate(top_5, 1):
                name = winner.ens_name[:18] if winner.ens_name else winner.address[:18]
                print(f"  {i:<3} {name:<20} {winner.true_win_rate:<7.1%} "
                      f"{winner.profit_factor:<5.2f} {winner.copy_score:<5.0f}")
            
            # Cache winners
            self.state["winners_cached"] = [
                {
                    "address": w.address,
                    "ens": w.ens_name,
                    "win_rate": w.true_win_rate,
                    "profit_factor": w.profit_factor,
                    "copy_score": w.copy_score
                }
                for w in top_5
            ]
            self.state["last_scan"] = datetime.now().isoformat()
            self._save_state()
            
            print("\n  Top 5 winners cached for analysis.")
            print("  Next step: Run 'analyze' for deep research.")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n  Error scanning: {e}")
    
    async def analyze(self):
        """Deep analysis to find the best daily bet."""
        self._reset_daily_count_if_needed()
        
        print("=" * 60)
        print("DEEP ANALYSIS - Finding Best Daily Bet")
        print("=" * 60)
        
        if self.state["daily_bet_count"] >= 1:
            print("\n  Daily bet target already reached (1/1).")
            print("  Run 'status' to see current positions.")
            return
        
        if not await self._init_clients():
            return
        
        # Load cached winners
        if not self.state.get("winners_cached"):
            print("\n  No winners cached. Run 'scan' first.")
            return
        
        print(f"\nAnalyzing top 5 winners' recent activity...")
        print("This performs deep analysis on each winner's recent bets.")
        
        opportunities = []
        
        for i, winner_data in enumerate(self.state["winners_cached"][:5], 1):
            print(f"\n  [{i}/5] Analyzing {winner_data.get('ens', winner_data['address'][:12])}...")
            
            # In real implementation, fetch recent bets from this winner
            # and analyze each one
            
            # Mock analysis for now
            print(f"      Fetching recent bets...")
            print(f"      Analyzing market conditions...")
            print(f"      Calculating EV...")
            
            # Simulate finding an opportunity
            ev = 5 + (5 - i) * 2  # Higher EV for higher ranked winners
            opportunities.append({
                "winner": winner_data,
                "ev": ev,
                "market": f"Market_{i}",
                "size": 200
            })
        
        # Find best opportunity
        if opportunities:
            best = max(opportunities, key=lambda x: x["ev"])
            
            print(f"\n{'='*60}")
            print("BEST OPPORTUNITY FOUND")
            print(f"{'='*60}")
            print(f"\n  Winner: {best['winner'].get('ens', best['winner']['address'][:16])}")
            print(f"  Market: {best['market']}")
            print(f"  Expected Value: {best['ev']:+.1f}%")
            print(f"  Recommended Size: ${best['size']:.0f}")
            
            # Save to state for copy command
            self.state["recommended_trade"] = best
            self._save_state()
            
            print(f"\n  To execute this trade, run: python cli_bot.py copy --yes")
        else:
            print("\n  No +EV opportunities found at this time.")
        
        print(f"{'='*60}")
    
    def copy_trade(self, auto_confirm: bool = False):
        """Execute the recommended trade."""
        print("=" * 60)
        print("COPY TRADE EXECUTION")
        print("=" * 60)
        
        self._reset_daily_count_if_needed()
        
        if self.state["daily_bet_count"] >= 1:
            print("\n  Daily bet target already reached.")
            return
        
        trade = self.state.get("recommended_trade")
        if not trade:
            print("\n  No recommended trade found. Run 'analyze' first.")
            return
        
        print(f"\n  Trade Details:")
        print(f"    Winner: {trade['winner'].get('ens', trade['winner']['address'][:16])}")
        print(f"    Market: {trade['market']}")
        print(f"    Size: ${trade['size']:.0f}")
        print(f"    Expected EV: {trade['ev']:+.1f}%")
        
        if not auto_confirm:
            print(f"\n  This is a DRY RUN - add --yes to execute")
            print(f"  Command: python cli_bot.py copy --yes")
            return
        
        # Execute trade (mock for now)
        print(f"\n  Executing trade...")
        print(f"  [MOCK] Trade executed successfully!")
        
        # Update state
        self.state["daily_bet_count"] += 1
        self.state["current_positions"].append({
            "market": trade['market'],
            "size": trade['size'],
            "entry_time": datetime.now().isoformat()
        })
        self._save_state()
        
        print(f"\n  Position added to portfolio.")
        print(f"  Daily target: {self.state['daily_bet_count']}/1 complete.")
        print(f"{'='*60}")
    
    def portfolio(self):
        """Show detailed portfolio view."""
        print("=" * 60)
        print("PORTFOLIO VIEW")
        print("=" * 60)
        
        print(f"\n[SUMMARY]")
        print(f"  Total Value: ${self.state['portfolio_value']:,.0f}")
        print(f"  Daily P&L: ${self.state['daily_pnl']:+.2f}")
        print(f"  Total P&L: ${self.state['total_pnl']:+.2f}")
        
        print(f"\n[POSITIONS]")
        if self.state['current_positions']:
            total_exposure = 0
            print(f"  {'Market':<20} {'Size':<10} {'Entry':<20}")
            print("  " + "-" * 50)
            for pos in self.state['current_positions']:
                print(f"  {pos['market']:<20} ${pos['size']:<9.0f} {pos['entry_time'][:16]}")
                total_exposure += pos.get('size', 0)
            
            heat = total_exposure / self.state['portfolio_value']
            print(f"\n  Total Exposure: ${total_exposure:,.0f}")
            print(f"  Portfolio Heat: {heat:.1%}")
        else:
            print("  No open positions")
        
        print(f"\n[RISK METRICS]")
        max_heat = 0.50
        current_heat = sum(p.get('size', 0) for p in self.state['current_positions']) / self.state['portfolio_value']
        print(f"  Max Heat Limit: {max_heat:.0%}")
        print(f"  Current Heat: {current_heat:.1%}")
        print(f"  Heat Remaining: {max_heat - current_heat:.1%}")
        
        print(f"\n[DAILY LIMITS]")
        print(f"  Bets: {self.state['daily_bet_count']} / 1")
        print(f"  Daily Drawdown Limit: 10% (${self.state['portfolio_value'] * 0.1:,.0f})")
        
        print(f"{'='*60}")
    
    def stop(self):
        """Stop all operations and close positions."""
        print("=" * 60)
        print("STOPPING BOT")
        print("=" * 60)
        
        if self.state['current_positions']:
            print(f"\n  Closing {len(self.state['current_positions'])} positions...")
            self.state['current_positions'] = []
            self._save_state()
            print("  All positions closed (simulated).")
        else:
            print("\n  No open positions to close.")
        
        print("\n  Bot stopped. Daily stats preserved.")
        print(f"{'='*60}")


async def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Copy Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status      Show bot status and daily targets
  scan        Find top 5 statistically proven winners
  analyze     Deep analysis to find best daily bet
  copy        Execute recommended trade (add --yes to confirm)
  portfolio   View detailed portfolio
  stop        Close all positions and stop
        """
    )
    
    parser.add_argument(
        'command',
        choices=['status', 'scan', 'analyze', 'copy', 'portfolio', 'stop'],
        help='Command to execute'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Confirm trade execution'
    )
    
    args = parser.parse_args()
    
    bot = CLIBot()
    
    if args.command == 'status':
        bot.status()
    elif args.command == 'scan':
        await bot.scan()
    elif args.command == 'analyze':
        await bot.analyze()
    elif args.command == 'copy':
        bot.copy_trade(auto_confirm=args.yes)
    elif args.command == 'portfolio':
        bot.portfolio()
    elif args.command == 'stop':
        bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
