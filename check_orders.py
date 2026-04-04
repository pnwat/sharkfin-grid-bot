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
    
    orders = client.fetch_open_orders()
    btc_orders = [o for o in orders if 'BTC' in str(o.get('legs', [{}])[0].get('instrument', ''))]
    
    print(f'BTC open orders: {len(btc_orders)}')
    for o in btc_orders[:10]:
        leg = o.get('legs', [{}])[0]
        print(f'  {leg.get("instrument")}: {"BUY" if leg.get("is_buying_asset") else "SELL"} @ ${float(leg.get("limit_price", 0)):.0f}')

asyncio.run(check())
