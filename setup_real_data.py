#!/usr/bin/env python3
"""
PolyBot Real-Time Data Setup Script
====================================

This script guides you through setting up real-time Polymarket data connections.
It checks your current configuration, tests connections, and provides setup instructions.

Usage:
    python setup_real_data.py

Requirements:
    - Python 3.8+
    - requests library
    - websocket-client library (for WebSocket tests)
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

# Try to import optional dependencies
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[!] 'requests' library not found. Install with: pip install requests")

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("[!] 'websocket-client' library not found. Install with: pip install websocket-client")


class Colors:
    """Terminal colors for better output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}[OK] {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}[ERR] {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}[WARN] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}[INFO] {text}{Colors.ENDC}")


def print_step(step_num: int, total: int, text: str):
    """Print a step indicator"""
    print(f"\n{Colors.BOLD}[{step_num}/{total}] {text}{Colors.ENDC}")


class ConfigChecker:
    """Checks and validates configuration"""
    
    REQUIRED_VARS = [
        'THEGRAPH_API_KEY',
        'POLYGON_RPC_URL',
        'POLYGON_WS_URL',
        'POLYMARKET_API_KEY',
    ]
    
    OPTIONAL_VARS = [
        'ALCHEMY_API_KEY',
        'INFURA_API_KEY',
        'POLYMARKET_API_SECRET',
        'DISCORD_WEBHOOK_URL',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID',
    ]
    
    def __init__(self, env_path: str = '.env'):
        self.env_path = Path(env_path)
        self.config: Dict[str, str] = {}
        self.load_config()
    
    def load_config(self):
        """Load configuration from .env file"""
        if self.env_path.exists():
            with open(self.env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        self.config[key] = value
    
    def check_env_exists(self) -> bool:
        """Check if .env file exists"""
        return self.env_path.exists()
    
    def get_missing_required(self) -> List[str]:
        """Get list of missing required variables"""
        missing = []
        for var in self.REQUIRED_VARS:
            value = self.config.get(var, '')
            if not value or value.startswith('your_') or value == 'xxx':
                missing.append(var)
        return missing
    
    def get_configured_vars(self) -> Dict[str, str]:
        """Get all configured variables"""
        return {k: v for k, v in self.config.items() 
                if v and not v.startswith('your_') and v != 'xxx'}


class ConnectionTester:
    """Tests various API connections"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.results: Dict[str, Dict] = {}
    
    def test_thegraph(self) -> Dict:
        """Test The Graph API connection"""
        print_info("Testing The Graph API...")
        
        api_key = self.config.get('THEGRAPH_API_KEY', '')
        if not api_key or api_key == 'your_graph_api_key_here':
            return {
                'success': False,
                'error': 'API key not configured',
                'latency_ms': None
            }
        
        try:
            # Polymarket subgraph endpoint
            url = f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/6DZ6qE9jNJbT6Tg5xNYqDzUJwGf5fCbGWjFPbFxSyg8Z"
            
            query = {
                "query": "{ _meta { block { number } } }"
            }
            
            start = time.time()
            response = requests.post(
                url,
                json=query,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and '_meta' in data['data']:
                    block_number = data['data']['_meta']['block']['number']
                    return {
                        'success': True,
                        'error': None,
                        'latency_ms': round(latency, 2),
                        'block_number': block_number
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Invalid response format',
                        'latency_ms': round(latency, 2)
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text[:100]}',
                    'latency_ms': round(latency, 2)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency_ms': None
            }
    
    def test_polygon_rpc(self) -> Dict:
        """Test Polygon RPC connection"""
        print_info("Testing Polygon RPC...")
        
        rpc_url = self.config.get('POLYGON_RPC_URL', 'https://polygon-rpc.com')
        
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            
            start = time.time()
            response = requests.post(
                rpc_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    block_number = int(data['result'], 16)
                    return {
                        'success': True,
                        'error': None,
                        'latency_ms': round(latency, 2),
                        'block_number': block_number
                    }
                else:
                    return {
                        'success': False,
                        'error': f'RPC error: {data.get("error", {})}',
                        'latency_ms': round(latency, 2)
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'latency_ms': round(latency, 2)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency_ms': None
            }
    
    def test_polygon_websocket(self) -> Dict:
        """Test Polygon WebSocket connection"""
        print_info("Testing Polygon WebSocket...")
        
        ws_url = self.config.get('POLYGON_WS_URL', '')
        
        if not ws_url:
            return {
                'success': False,
                'error': 'WebSocket URL not configured',
                'latency_ms': None
            }
        
        if not WEBSOCKET_AVAILABLE:
            return {
                'success': False,
                'error': 'websocket-client library not installed',
                'latency_ms': None
            }
        
        try:
            start = time.time()
            ws = websocket.create_connection(ws_url, timeout=5)
            
            # Send a simple ping
            ws.send(json.dumps({"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}))
            response = ws.recv()
            latency = (time.time() - start) * 1000
            ws.close()
            
            data = json.loads(response)
            if 'result' in data:
                block_number = int(data['result'], 16)
                return {
                    'success': True,
                    'error': None,
                    'latency_ms': round(latency, 2),
                    'block_number': block_number
                }
            else:
                return {
                    'success': False,
                    'error': 'Invalid WebSocket response',
                    'latency_ms': round(latency, 2)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency_ms': None
            }
    
    def test_polymarket_api(self) -> Dict:
        """Test Polymarket API connection"""
        print_info("Testing Polymarket API...")
        
        api_key = self.config.get('POLYMARKET_API_KEY', '')
        
        if not api_key or api_key == 'your_polymarket_api_key':
            return {
                'success': False,
                'error': 'API key not configured',
                'latency_ms': None
            }
        
        try:
            # Try to get markets from Polymarket
            url = "https://clob.polymarket.com/markets"
            headers = {
                'POLYMARKET_API_KEY': api_key,
                'Accept': 'application/json'
            }
            
            start = time.time()
            response = requests.get(url, headers=headers, timeout=10)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                market_count = len(data) if isinstance(data, list) else 'N/A'
                return {
                    'success': True,
                    'error': None,
                    'latency_ms': round(latency, 2),
                    'market_count': market_count
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text[:100]}',
                    'latency_ms': round(latency, 2)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency_ms': None
            }
    
    def test_alchemy(self) -> Dict:
        """Test Alchemy connection if configured"""
        alchemy_key = self.config.get('ALCHEMY_API_KEY', '')
        
        if not alchemy_key or alchemy_key == 'your_alchemy_api_key':
            return {
                'success': False,
                'error': 'Not configured (optional)',
                'latency_ms': None,
                'optional': True
            }
        
        print_info("Testing Alchemy API...")
        
        try:
            url = f"https://polygon-mainnet.g.alchemy.com/v2/{alchemy_key}"
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            
            start = time.time()
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    block_number = int(data['result'], 16)
                    return {
                        'success': True,
                        'error': None,
                        'latency_ms': round(latency, 2),
                        'block_number': block_number
                    }
                else:
                    return {
                        'success': False,
                        'error': f'RPC error: {data.get("error", {})}',
                        'latency_ms': round(latency, 2)
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'latency_ms': round(latency, 2)
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency_ms': None
            }
    
    def run_all_tests(self) -> Dict[str, Dict]:
        """Run all connection tests"""
        print_header("Running Connection Tests")
        
        self.results['thegraph'] = self.test_thegraph()
        self.results['polygon_rpc'] = self.test_polygon_rpc()
        self.results['polygon_ws'] = self.test_polygon_websocket()
        self.results['polymarket_api'] = self.test_polymarket_api()
        self.results['alchemy'] = self.test_alchemy()
        
        return self.results
    
    def print_results(self):
        """Print test results in a formatted table"""
        print(f"\n{Colors.BOLD}Connection Test Results:{Colors.ENDC}")
        print("-" * 70)
        print(f"{'Service':<20} {'Status':<10} {'Latency':<12} {'Details'}")
        print("-" * 70)
        
        for service, result in self.results.items():
            status = "[PASS]" if result['success'] else "[FAIL]"
            if result.get('optional') and not result['success']:
                status = "[SKIP]"
            
            latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "N/A"
            
            if result['success']:
                if 'block_number' in result:
                    details = f"Block: {result['block_number']}"
                elif 'market_count' in result:
                    details = f"Markets: {result['market_count']}"
                else:
                    details = "OK"
            else:
                details = result['error'][:35]
            
            service_name = service.replace('_', ' ').title()
            print(f"{service_name:<20} {status:<10} {latency:<12} {details}")
        
        print("-" * 70)


def show_setup_instructions():
    """Show detailed setup instructions"""
    print_header("Setup Instructions")
    
    print(f"{Colors.BOLD}1. The Graph API Key (Required){Colors.ENDC}")
    print("   The Graph provides indexed blockchain data for Polymarket.")
    print("   ")
    print("   Steps:")
    print("   a) Visit: https://thegraph.com/studio/apikeys/")
    print("   b) Sign up or log in")
    print("   c) Create a new API key")
    print("   d) Copy the key and add to .env:")
    print(f"      {Colors.CYAN}THEGRAPH_API_KEY=your_key_here{Colors.ENDC}")
    print()
    
    print(f"{Colors.BOLD}2. Alchemy API Key (Recommended){Colors.ENDC}")
    print("   Alchemy provides reliable Polygon RPC and WebSocket endpoints.")
    print("   ")
    print("   Steps:")
    print("   a) Visit: https://www.alchemy.com/")
    print("   b) Sign up for a free account")
    print("   c) Create a new app:")
    print("      - Name: PolyBot")
    print("      - Chain: Polygon")
    print("      - Network: Polygon Mainnet")
    print("   d) Copy the API key and HTTP URL")
    print("   e) Add to .env:")
    print(f"      {Colors.CYAN}ALCHEMY_API_KEY=your_key_here{Colors.ENDC}")
    print(f"      {Colors.CYAN}POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY{Colors.ENDC}")
    print(f"      {Colors.CYAN}POLYGON_WS_URL=wss://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY{Colors.ENDC}")
    print()
    
    print(f"{Colors.BOLD}3. Polymarket API Key (Optional){Colors.ENDC}")
    print("   Required for CLOB (orderbook) data and live trading.")
    print("   ")
    print("   Steps:")
    print("   a) Visit: https://polymarket.com/settings/api")
    print("   b) Generate API key")
    print("   c) Add to .env:")
    print(f"      {Colors.CYAN}POLYMARKET_API_KEY=your_key_here{Colors.ENDC}")
    print()
    
    print(f"{Colors.BOLD}4. Alternative: Free Polygon RPC (No Alchemy){Colors.ENDC}")
    print("   If you prefer not to use Alchemy, you can use public endpoints:")
    print(f"      {Colors.CYAN}POLYGON_RPC_URL=https://polygon-rpc.com{Colors.ENDC}")
    print(f"      {Colors.CYAN}POLYGON_WS_URL=wss://polygon-mainnet.public.blastapi.io{Colors.ENDC}")
    print("   Note: Public endpoints may have rate limits and lower reliability.")
    print()


def generate_env_template() -> str:
    """Generate a .env template with all real-time data variables"""
    return '''# PolyBot Real-Time Data Configuration
# Generated on {timestamp}
# =============================================================================

# =============================================================================
# REQUIRED: The Graph API (for Polymarket data indexing)
# =============================================================================
# Get from: https://thegraph.com/studio/apikeys/
# This is required for accessing historical and real-time Polymarket data
THEGRAPH_API_KEY=your_graph_api_key_here

# =============================================================================
# REQUIRED: Polygon Blockchain Connection
# =============================================================================
# Option A: Alchemy (Recommended - more reliable)
# Get from: https://www.alchemy.com/
ALCHEMY_API_KEY=your_alchemy_api_key_here
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/your_alchemy_api_key_here
POLYGON_WS_URL=wss://polygon-mainnet.g.alchemy.com/v2/your_alchemy_api_key_here

# Option B: Public RPC (Free but less reliable)
# Uncomment these if not using Alchemy:
# POLYGON_RPC_URL=https://polygon-rpc.com
# POLYGON_WS_URL=wss://polygon-mainnet.public.blastapi.io

# =============================================================================
# REQUIRED: Polymarket CLOB API (for orderbook data)
# =============================================================================
# Get from: https://polymarket.com/settings/api
POLYMARKET_API_KEY=your_polymarket_api_key
POLYMARKET_API_SECRET=your_polymarket_api_secret

# =============================================================================
# OPTIONAL: Backup RPC Providers
# =============================================================================
# Infura (alternative to Alchemy)
# Get from: https://www.infura.io/
INFURA_API_KEY=your_infura_api_key
# INFURA_POLYGON_RPC=https://polygon-mainnet.infura.io/v3/your_infura_api_key

# =============================================================================
# REAL-TIME DATA SETTINGS
# =============================================================================
# WebSocket reconnection settings
WS_RECONNECT_INTERVAL=5
WS_MAX_RECONNECT_ATTEMPTS=10

# RPC failover settings
RPC_FAILOVER_ENABLED=true
RPC_TIMEOUT_SECONDS=10

# Data refresh intervals (seconds)
MARKET_DATA_REFRESH_INTERVAL=5
ORDERBOOK_REFRESH_INTERVAL=1
TRADE_HISTORY_REFRESH_INTERVAL=2

# =============================================================================
# WHALE TRACKING (Real-Time)
# =============================================================================
# Whale addresses to track (comma-separated)
# These are example addresses - replace with actual whale addresses
WHALE_ADDRESSES=0x0000000000000000000000000000000000000000

# Minimum whale trade size to track (USD)
MIN_WHALE_USD=5000

# Real-time notification settings
REALTIME_ALERTS_ENABLED=true
ALERT_ON_LARGE_TRADES=true
ALERT_ON_WHALE_ACCUMULATION=true

# =============================================================================
# TRADING SETTINGS
# =============================================================================
# Enable live trading (WARNING: uses real money)
LIVE_TRADING_ENABLED=false

# Paper trading starting balance
PAPER_TRADE_BALANCE_USD=10000

# Risk management
MAX_RISK_PER_TRADE=0.02
MAX_POSITION_SIZE=500
MIN_POSITION_SIZE=50

# =============================================================================
# NOTIFICATIONS
# =============================================================================
# Discord webhook for alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Telegram bot for alerts
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# =============================================================================
# DATABASE
# =============================================================================
# SQLite database path
DATABASE_PATH=./data/polybot.db

# Cache settings
MARKET_CACHE_HOURS=1
REALTIME_CACHE_SECONDS=30

# =============================================================================
# DEBUG
# =============================================================================
DEBUG=false
LOG_LEVEL=INFO
LOG_FILE=./logs/polybot.log
'''.format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def show_example_whales():
    """Show example whale addresses to track"""
    print_header("Example Whale Addresses")
    
    print(f"{Colors.BOLD}Note:{Colors.ENDC} These are example address formats.")
    print("You should discover actual whale addresses through:")
    print("  - Polymarket leaderboards")
    print("  - On-chain analysis tools")
    print("  - Community tracking")
    print()
    
    examples = [
        {
            'name': 'Large Market Maker',
            'address': '0x1234567890123456789012345678901234567890',
            'description': 'Example format - replace with real address'
        },
        {
            'name': 'Whale Trader',
            'address': '0xabcdefabcdefabcdefabcdefabcdefabcdefabcd',
            'description': 'Example format - replace with real address'
        },
        {
            'name': 'Institutional Wallet',
            'address': '0x9876543210987654321098765432109876543210',
            'description': 'Example format - replace with real address'
        }
    ]
    
    print(f"{Colors.CYAN}Format for WHALE_ADDRESSES in .env:{Colors.ENDC}")
    print("WHALE_ADDRESSES=0xaddr1,0xaddr2,0xaddr3")
    print()
    
    for ex in examples:
        print(f"{Colors.BOLD}{ex['name']}{Colors.ENDC}")
        print(f"  Address: {ex['address']}")
        print(f"  Note: {ex['description']}")
        print()


def main():
    """Main setup wizard"""
    print_header("PolyBot Real-Time Data Setup Wizard")
    print("This script will help you configure real-time Polymarket data connections.\n")
    
    if not REQUESTS_AVAILABLE:
        print_error("The 'requests' library is required.")
        print("Install it with: pip install requests")
        sys.exit(1)
    
    # Step 1: Check current configuration
    print_step(1, 5, "Checking Current Configuration")
    
    checker = ConfigChecker()
    
    if checker.check_env_exists():
        print_success("Found .env file")
        configured = checker.get_configured_vars()
        print_info(f"Configured variables: {len(configured)}")
        
        missing = checker.get_missing_required()
        if missing:
            print_warning(f"Missing required variables: {', '.join(missing)}")
        else:
            print_success("All required variables are configured")
    else:
        print_error("No .env file found")
        print_info("Creating from .env.example...")
        if Path('.env.example').exists():
            print("   Run: cp .env.example .env")
        else:
            print("   The .env.example file is also missing!")
    
    # Step 2: Show setup instructions
    print_step(2, 5, "Setup Instructions")
    show_setup_instructions()
    
    input(f"\n{Colors.CYAN}Press Enter to continue to connection testing...{Colors.ENDC}")
    
    # Step 3: Test connections
    print_step(3, 5, "Testing Connections")
    
    tester = ConnectionTester(checker.config)
    tester.run_all_tests()
    tester.print_results()
    
    # Step 4: Generate configuration
    print_step(4, 5, "Configuration Template")
    
    print("Here's a complete .env template you can use:\n")
    print(f"{Colors.CYAN}{generate_env_template()}{Colors.ENDC}")
    
    # Save template to file
    template_path = Path('.env.realtime.template')
    with open(template_path, 'w') as f:
        f.write(generate_env_template())
    print_success(f"Configuration template saved to {template_path}")
    
    # Step 5: Show example whales
    print_step(5, 5, "Example Whale Addresses")
    show_example_whales()
    
    # Summary
    print_header("Setup Summary")
    
    passed = sum(1 for r in tester.results.values() if r['success'])
    total = len(tester.results)
    optional_failed = sum(1 for r in tester.results.values() 
                         if not r['success'] and r.get('optional'))
    
    print(f"Connection Tests: {passed}/{total - optional_failed} required passed")
    
    if passed >= 3:  # At least TheGraph, one RPC, and Polymarket API
        print_success("Your configuration looks good for real-time data!")
        print()
        print("Next steps:")
        print("  1. Ensure all required API keys are set in .env")
        print("  2. Run: python cli_bot.py --test-connection")
        print("  3. Start the bot: python cli_bot.py")
    else:
        print_warning("Some connections failed. Please:")
        print()
        print("  1. Follow the setup instructions above")
        print("  2. Add the missing API keys to your .env file")
        print("  3. Run this script again to verify")
    
    print()
    print(f"{Colors.BLUE}For help, see:{Colors.ENDC}")
    print("  - QUICKSTART.md for getting started")
    print("  - DEVELOPER.md for technical details")
    print("  - README.md for full documentation")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
