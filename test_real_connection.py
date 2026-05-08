#!/usr/bin/env python3
"""
Test real-time connection to Polymarket data.
"""

import os
import asyncio
import json
import websockets
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("POLYBOT REAL-TIME CONNECTION TEST")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Test 1: Environment variables
print("[TEST 1] Environment Variables")
print("-" * 80)

alchemy_key = os.getenv('ALCHEMY_API_KEY')
ws_url = os.getenv('POLYGON_WS_URL')

if alchemy_key and ws_url:
    print(f"[OK] Alchemy Key: {alchemy_key[:15]}...")
    print(f"[OK] WebSocket URL configured")
else:
    print("[FAIL] Missing configuration")
    exit(1)

print()

# Test 2: Polygon WebSocket
print("[TEST 2] Polygon WebSocket Connection")
print("-" * 80)

async def test_websocket():
    try:
        print(f"Connecting to: {ws_url[:50]}...")
        
        async with websockets.connect(ws_url) as websocket:
            # Subscribe to new blocks
            await websocket.send(json.dumps({
                "jsonrpc": "2.0",
                "method": "eth_subscribe",
                "params": ["newHeads"],
                "id": 1
            }))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(response)
            
            if 'result' in data:
                subscription_id = data['result']
                print(f"[OK] Subscribed to new blocks (ID: {subscription_id})")
                
                # Wait for one block
                print("Waiting for next block...")
                block_data = await asyncio.wait_for(websocket.recv(), timeout=30)
                block = json.loads(block_data)
                
                if 'params' in block and 'result' in block['params']:
                    block_num = int(block['params']['result']['number'], 16)
                    print(f"[OK] Received new block: {block_num:,}")
                    return True
            else:
                print(f"[WARN] Unexpected response: {data}")
                return False
                
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {str(e)[:100]}")
        return False

try:
    ws_working = asyncio.run(test_websocket())
except Exception as e:
    print(f"[ERROR] {e}")
    ws_working = False

print()

# Test 3: The Graph API (simpler query)
print("[TEST 3] The Graph API")
print("-" * 80)

try:
    api_key = os.getenv('THEGRAPH_API_KEY')
    
    # Alternative: Use Polymarket's public subgraph endpoint
    # Some subgraphs don't require API key
    url = "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets"
    
    query = {
        "query": "{ markets(first: 3, orderBy: volume, orderDirection: desc) { id question volume } }"
    }
    
    response = requests.post(url, json=query, timeout=15)
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'markets' in data['data']:
            markets = data['data']['markets']
            print(f"[OK] The Graph API working!")
            print(f"[OK] Found {len(markets)} active markets:")
            for m in markets:
                volume = float(m.get('volume', 0)) / 1e6  # Convert to millions
                print(f"       - {m['question'][:50]}... (Vol: ${volume:.1f}M)")
        else:
            print(f"[WARN] Unexpected format: {data.keys()}")
    else:
        print(f"[FAIL] HTTP {response.status_code}")
        
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {str(e)[:100]}")

print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)

if ws_working:
    print("[READY] All critical connections working!")
    print()
    print("You can now run:")
    print("  python paper_trading_session.py")
    print()
    print("The bot will use REAL blockchain data for whale detection!")
else:
    print("[ISSUES] Some connections failed.")
    print("Check the errors above and fix configuration.")
