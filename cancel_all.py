import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv

async def cancel_all():
    client = GrvtCcxt(env=GrvtEnv.PROD, parameters={
        'api_key': os.getenv('GRVT_API_KEY'),
        'private_key': os.getenv('GRVT_API_SECRET'),
        'trading_account_id': os.getenv('GRVT_TRADING_ACCOUNT_ID'),
    })
    
    orders = client.fetch_open_orders()
    btc_orders = [o for o in orders if 'BTC' in str(o.get('legs', [{}])[0].get('instrument', ''))]
    
    print(f'Cancelling {len(btc_orders)} BTC orders...')
    
    for o in btc_orders:
        try:
            client.cancel_order(o.get('order_id'), 'BTC_USDT_Perp')
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f'Error: {e}')
    
    print('Done')

asyncio.run(cancel_all())
