# -*- coding: utf-8 -*-
"""シャークフィン改善策シミュレーション（軽量版）"""
import numpy as np

def simulate_baseline(prices, spacing=0.03, levels=40):
    """ベースライン（固定レンジ）"""
    center = prices[0]
    pnl = 0
    trades = 0
    position = 0
    
    # グリッド生成
    grid = []
    for i in range(levels):
        if i < levels // 2:
            price = center * (1 - 0.005 * (i + 1) / (levels // 2) * levels)
        else:
            price = center * (1 + 0.005 * ((i - levels // 2) + 1) / (levels // 2) * levels)
        grid.append({'price': price, 'side': 'buy' if i < levels // 2 else 'sell', 'filled': False})
    
    for price in prices:
        for g in grid:
            if g['filled']:
                continue
            if g['side'] == 'buy' and price <= g['price']:
                pnl -= g['price'] * 0.002  # 手数料込み
                position += 1
                g['filled'] = True
                trades += 1
            elif g['side'] == 'sell' and price >= g['price'] and position > 0:
                pnl += g['price'] * 0.002 * (1 + spacing/100)
                position -= 1
                g['filled'] = True
                trades += 1
    
    return pnl, trades

def simulate_range_follow(prices, spacing=0.03, levels=40):
    """レンジ追従"""
    pnl = 0
    trades = 0
    position = 0
    center = prices[0]
    
    for i, price in enumerate(prices):
        # レンジ追従（価格が中心から離れたら移動）
        if abs(price - center) > center * 0.003:
            # ポジション決済
            if position > 0:
                pnl += position * price * 0.002 * spacing / 100
                trades += 1
                position = 0
            center = price
        
        # グリッド約定（簡略化）
        if price < center * 0.997:  # 買い
            pnl -= price * 0.002
            position += 1
            trades += 1
        elif price > center * 1.003 and position > 0:  # 売り
            pnl += price * 0.002 * (1 + spacing/100)
            position -= 1
            trades += 1
    
    return pnl, trades

def simulate_dynamic_spacing(prices, base_spacing=0.03, levels=40):
    """動的グリッド間隔"""
    pnl = 0
    trades = 0
    position = 0
    center = prices[0]
    
    for i, price in enumerate(prices):
        # ボラティリティ計算
        if i > 10:
            recent = prices[max(0, i-10):i]
            vol = np.std([p/recent[0] for p in recent])
        else:
            vol = 0.001
        
        # 動的間隔
        spacing = base_spacing * (1 + vol * 100)
        spacing = max(0.02, min(0.10, spacing))
        
        # グリッド約定
        threshold = spacing / 100 * center
        if price < center - threshold:
            pnl -= price * 0.002
            position += 1
            trades += 1
            center = price + threshold
        elif price > center + threshold and position > 0:
            pnl += price * 0.002 * (1 + spacing/100)
            position -= 1
            trades += 1
            center = price - threshold
    
    return pnl, trades

def main():
    print("=== 改善策シミュレーション ===\n")
    
    np.random.seed(42)
    
    scenarios = [
        ("低ボラ横ばい", 0.0005, 0.0),
        ("通常ボラ", 0.001, 0.0),
        ("高ボラ", 0.002, 0.0),
        ("上昇トレンド", 0.001, 0.001),
        ("下降トレンド", 0.001, -0.001),
    ]
    
    results = []
    
    for name, vol, trend in scenarios:
        # 価格生成
        ticks = 1000
        returns = np.random.randn(ticks) * vol + trend / ticks
        prices = list(67000 * np.cumprod(1 + returns))
        
        print(f"【{name}】")
        
        b_pnl, b_trades = simulate_baseline(prices)
        print(f"  ベースライン: PnL ${b_pnl:.2f}, {b_trades}回")
        
        r_pnl, r_trades = simulate_range_follow(prices)
        print(f"  レンジ追従:   PnL ${r_pnl:.2f}, {r_trades}回")
        
        d_pnl, d_trades = simulate_dynamic_spacing(prices)
        print(f"  動的間隔:     PnL ${d_pnl:.2f}, {d_trades}回")
        
        best = max([('ベースライン', b_pnl), ('レンジ追従', r_pnl), ('動的間隔', d_pnl)], key=lambda x: x[1])
        print(f"  → 最優秀: {best[0]}\n")
        
        results.append((name, best[0], best[1]))
    
    print("=" * 50)
    print("【総合結果】")
    
    wins = {}
    for _, best_name, _ in results:
        wins[best_name] = wins.get(best_name, 0) + 1
    
    for strategy, count in sorted(wins.items(), key=lambda x: -x[1]):
        print(f"{strategy}: {count}/5シナリオで最優秀")

if __name__ == "__main__":
    main()
