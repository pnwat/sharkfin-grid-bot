import re

# ログから約定履歴を抽出
with open('sharkfin.log', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fills = []
for line in lines:
    if 'FILLED' in line:
        # FILLED buy @ $66975 -> sell @ $66995
        match = re.search(r'FILLED (buy|sell) @ \$(\d+) -> (buy|sell) @ \$(\d+)', line)
        if match:
            entry_side = match.group(1)
            entry_price = int(match.group(2))
            exit_side = match.group(3)
            exit_price = int(match.group(4))
            fills.append({
                'entry_side': entry_side,
                'entry_price': entry_price,
                'exit_side': exit_side,
                'exit_price': exit_price,
                'spread': exit_price - entry_price if exit_side == 'sell' else entry_price - exit_price
            })

print(f'=== 取引分析 ===')
print(f'総取引数: {len(fills)}回')

if fills:
    total_spread = sum(f['spread'] for f in fills)
    print(f'総スプレッド: ${total_spread}')
    
    # 1取引あたりのサイズ（概算）
    size_btc = 150 / 67000  # $150 / BTC価格
    total_pnl = total_spread * size_btc
    print(f'推定損益: ${total_pnl:.2f}')
    
    # 買い→売り vs 売り→買い
    buy_to_sell = [f for f in fills if f['entry_side'] == 'buy']
    sell_to_buy = [f for f in fills if f['entry_side'] == 'sell']
    
    print(f'\n買い→売り: {len(buy_to_sell)}回')
    print(f'売り→買い: {len(sell_to_buy)}回')
    
    # 平均スプレッド
    avg_spread = total_spread / len(fills)
    print(f'\n平均スプレッド: ${avg_spread:.2f}')
