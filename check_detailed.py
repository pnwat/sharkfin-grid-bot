import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

async def check_detailed():
    client = GrvtCcxt(env=GrvtEnv.PROD, parameters={
        'api_key': os.getenv('GRVT_API_KEY'),
        'private_key': os.getenv('GRVT_API_SECRET'),
        'trading_account_id': os.getenv('GRVT_TRADING_ACCOUNT_ID'),
    })
    
    # 全オーダー詳細
    orders = client.fetch_open_orders()
    btc_orders = [o for o in orders if 'BTC' in str(o.get('legs', [{}])[0].get('instrument', ''))]
    
    print(f'=== BTC ORDERS ({len(btc_orders)}) ===')
    
    buys = []
    sells = []
    
    for o in btc_orders:
        leg = o.get('legs', [{}])[0]
        price = float(leg.get('limit_price', 0))
        is_buy = leg.get('is_buying_asset', False)
        if is_buy:
            buys.append(price)
        else:
            sells.append(price)
    
    print(f'BUY orders: {len(buys)}')
    if buys:
        print(f'  Range: ${min(buys):.0f} - ${max(buys):.0f}')
    
    print(f'SELL orders: {len(sells)}')
    if sells:
        print(f'  Range: ${min(sells):.0f} - ${max(sells):.0f}')
    
    # 現在価格
    ticker = client.fetch_ticker('BTC_USDT_Perp')
    print(f'\nCurrent price: ${float(ticker.get("last_price", 0)):.2f}')
    
    # ポジション
    positions = client.fetch_positions()
    for pos in positions:
        size = float(pos.get('size', 0))
        if abs(size) > 0.0001 and 'BTC' in pos.get('instrument', ''):
            print(f'\nPosition: {size:.6f} BTC')
            print(f'  Entry: ${float(pos.get("entry_price", 0)):.2f}')
            print(f'  PnL: ${float(pos.get("unrealized_pnl", 0)):.2f}')

asyncio.run(check_detailed())
