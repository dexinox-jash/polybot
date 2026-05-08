#!/usr/bin/env python3
"""
Verify API setup and test connections.
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("POLYBOT API SETUP VERIFICATION")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Check environment variables
print("[1/6] CHECKING ENVIRONMENT VARIABLES")
print("-" * 80)

required_vars = {
    'THEGRAPH_API_KEY': 'The Graph API (Required)',
    'POLYGON_RPC_URL': 'Polygon HTTP RPC (Required)',
    'POLYGON_WS_URL': 'Polygon WebSocket (Required for real-time)',
    'POLYMARKET_API_KEY': 'Polymarket API (Optional)',
    'ALCHEMY_API_KEY': 'Alchemy API (Recommended)',
}

configured = []
missing = []

for var, description in required_vars.items():
    value = os.getenv(var)
    if value and value not in ['your_key_here', 'your_telegram_bot_token', '']:
        masked = value[:10] + "..." if len(value) > 10 else value
        print(f"  [OK] {var}: {masked}")
        configured.append(var)
    else:
        print(f"  [MISSING] {var}: {description}")
        missing.append(var)

print()
print(f"Configured: {len(configured)}/{len(required_vars)}")
print(f"Missing: {len(missing)}")
print()

# Test The Graph API
print("[2/6] TESTING THE GRAPH API")
print("-" * 80)

try:
    import requests
    
    api_key = os.getenv('THEGRAPH_API_KEY')
    if api_key:
        # Test query to Polymarket subgraph
        url = f"https://gateway.thegraph.com/api/{api_key}/subgraphs/id/Bx1W4S7kDVxs9gC3s2G6DS8kdNBJNVhMviCtin2DiBp"
        
        query = {
            "query": "{ markets(first: 1) { id question } }"
        }
        
        response = requests.post(url, json=query, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and 'markets' in data['data']:
                print(f"  [OK] The Graph API is working!")
                print(f"       Found {len(data['data']['markets'])} markets")
            else:
                print(f"  [WARN] API responded but unexpected format")
                print(f"         Response: {data.keys()}")
        else:
            print(f"  [FAIL] HTTP {response.status_code}")
            print(f"         {response.text[:100]}")
    else:
        print("  [SKIP] No API key configured")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")

print()

# Test Polygon RPC
print("[3/6] TESTING POLYGON RPC")
print("-" * 80)

try:
    import requests
    
    rpc_url = os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com')
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 1
    }
    
    response = requests.post(rpc_url, json=payload, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        if 'result' in data:
            block_number = int(data['result'], 16)
            print(f"  [OK] Polygon RPC is working!")
            print(f"       Current block: {block_number:,}")
        else:
            print(f"  [WARN] RPC responded but no block number")
            print(f"         Response: {data}")
    else:
        print(f"  [FAIL] HTTP {response.status_code}")
except Exception as e:
    print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")

print()

# Test WebSocket (if configured)
print("[4/6] TESTING POLYGON WEBSOCKET")
print("-" * 80)

ws_url = os.getenv('POLYGON_WS_URL')
if ws_url:
    print(f"  WebSocket URL: {ws_url[:50]}...")
    print("  Testing connection...")
    
    try:
        import websocket
        import ssl
        
        ws = websocket.create_connection(
            ws_url,
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=5
        )
        
        # Send eth_blockNumber request
        ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "eth_blockNumber",
            "params": [],
            "id": 1
        }))
        
        result = ws.recv()
        data = json.loads(result)
        
        if 'result' in data:
            block_number = int(data['result'], 16)
            print(f"  [OK] WebSocket connection successful!")
            print(f"       Current block: {block_number:,}")
        else:
            print(f"  [WARN] Connected but unexpected response")
            
        ws.close()
        
    except Exception as e:
        print(f"  [FAIL] Could not connect to WebSocket")
        print(f"         Error: {str(e)[:100]}")
else:
    print("  [MISSING] POLYGON_WS_URL not configured")
    print("            This is REQUIRED for real-time whale detection")
    print()
    print("  To fix, add one of these to .env:")
    print("    Option 1 (Alchemy - Recommended):")
    print("      ALCHEMY_API_KEY=your_alchemy_key")
    print("      POLYGON_WS_URL=wss://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY")
    print()
    print("    Option 2 (Public - Less reliable):")
    print("      POLYGON_WS_URL=wss://polygon-mainnet.public.blastapi.io")

print()

# Test Polymarket API
print("[5/6] TESTING POLYMARKET API")
print("-" * 80)

poly_key = os.getenv('POLYMARKET_API_KEY')
if poly_key:
    try:
        import requests
        
        headers = {"POLYMARKET_API_KEY": poly_key}
        response = requests.get(
            "https://api.polymarket.com/markets",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            markets = response.json()
            if isinstance(markets, list):
                print(f"  [OK] Polymarket API is working!")
                print(f"       Found {len(markets)} markets")
            else:
                print(f"  [WARN] API responded but unexpected format")
        else:
            print(f"  [FAIL] HTTP {response.status_code}")
            print(f"         May need API secret, not just key")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)[:100]}")
else:
    print("  [SKIP] No Polymarket API key configured")
    print("         (Optional - only needed for live trading)")

print()

# Summary
print("[6/6] SUMMARY")
print("=" * 80)

if 'POLYGON_WS_URL' in missing:
    print("[CRITICAL] Missing POLYGON_WS_URL")
    print()
    print("To get real-time whale data, you NEED a WebSocket connection.")
    print()
    print("Quick Fix Options:")
    print()
    print("Option 1: Alchemy (Recommended - Most Reliable)")
    print("  1. Sign up at https://www.alchemy.com/")
    print("  2. Create a new app (Chain: Polygon, Network: Mainnet)")
    print("  3. Copy your API key")
    print("  4. Add to .env:")
    print("     ALCHEMY_API_KEY=your_key_here")
    print("     POLYGON_WS_URL=wss://polygon-mainnet.g.alchemy.com/v2/your_key_here")
    print()
    print("Option 2: Public Endpoint (Free but unreliable)")
    print("  Add to .env:")
    print("     POLYGON_WS_URL=wss://polygon-mainnet.public.blastapi.io")
    print()
    print("Option 3: BlastAPI (Free tier)")
    print("  1. Sign up at https://blastapi.io/")
    print("  2. Create Polygon Mainnet endpoint")
    print("  3. Copy WebSocket URL to .env")
    print()
    sys.exit(1)
else:
    print("[OK] All required connections configured!")
    print()
    print("You can now run a real trading session:")
    print("  python paper_trading_session.py")
    print()
    print("The bot will use REAL Polymarket data for whale detection.")
