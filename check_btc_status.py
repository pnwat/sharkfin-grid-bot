import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

async def check():
    client = GrvtCcxt(env=GrvtEnv.PROD, parameters={
        'api_key': os.getenv('GRVT_API_KEY'),
        'private_key': os.getenv('GRVT_API_SECRET'),
        'trading_account_id': os.getenv('GRVT_TRADING_ACCOUNT_ID'),
    })
    
    # BTCポジション確認
    positions = client.fetch_positions()
    btc_pos = [p for p in positions if 'BTC' in p.get('instrument', '')]
    print('=== BTC POSITIONS ===')
    for p in btc_pos:
        size = float(p.get('size', 0))
        if abs(size) > 0.0001:
            print(f"{p.get('instrument')}: {size:.6f}")
            print(f"  Entry: ${float(p.get('entry_price', 0)):.2f}")
            print(f"  PnL: ${float(p.get('unrealized_pnl', 0)):.2f}")
    
    if not btc_pos or all(abs(float(p.get('size', 0))) < 0.0001 for p in btc_pos):
        print("No BTC position")
    
    # BTC注文確認
    print()
    print('=== BTC ORDERS ===')
    orders = client.fetch_open_orders()
    btc_orders = [o for o in orders if 'BTC' in str(o.get('legs', [{}])[0].get('instrument', ''))]
    print(f'Count: {len(btc_orders)}')
    
    # 価格帯ごとに分類
    buys = []
    sells = []
    for o in btc_orders:
        leg = o.get('legs', [{}])[0]
        price = float(leg.get('limit_price', 0))
        if leg.get('is_buying_asset'):
            buys.append(price)
        else:
            sells.append(price)
    
    if buys:
        print(f'BUY orders: {len(buys)} (${min(buys):.0f} - ${max(buys):.0f})')
    if sells:
        print(f'SELL orders: {len(sells)} (${min(sells):.0f} - ${max(sells):.0f})')
    
    # 現在価格
    ticker = client.fetch_ticker('BTC_USDT_Perp')
    print(f"\nCurrent BTC price: ${float(ticker.get('last_price', 0)):.2f}")

asyncio.run(check())
