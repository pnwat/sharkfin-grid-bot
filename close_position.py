import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

async def close_position():
    client = GrvtCcxt(env=GrvtEnv.PROD, parameters={
        'api_key': os.getenv('GRVT_API_KEY'),
        'private_key': os.getenv('GRVT_API_SECRET'),
        'trading_account_id': os.getenv('GRVT_TRADING_ACCOUNT_ID'),
    })
    
    # ポジション確認
    positions = client.fetch_positions()
    for pos in positions:
        size = float(pos.get('size', 0))
        if abs(size) > 0.0001 and 'BTC' in pos.get('instrument', ''):
            print(f'Position: {size:.6f} BTC')
            
            # 成行決済
            side = 'buy' if size < 0 else 'sell'  # ショートなら買いで決済
            try:
                order = client.create_order(
                    symbol='BTC_USDT_Perp',
                    order_type='market',
                    side=side,
                    amount=abs(size)
                )
                print(f'Closed: {side} {abs(size):.6f} BTC')
            except Exception as e:
                print(f'Error: {e}')

asyncio.run(close_position())
