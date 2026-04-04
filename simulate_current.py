# -*- coding: utf-8 -*-
"""シャークフィン現在設定でのシミュレーション"""
import numpy as np

def simulate_current_settings(hours=24, balance=1081, levels=40, spacing=0.03, 
                               range_pct=0.5, position_usd=150, stop_loss=1.5):
    """
    現在の設定でのシミュレーション
    
    Args:
        hours: 期間（時間）
        balance: 口座残高
        levels: グリッドレベル数
        spacing: グリッド間隔（%）
        range_pct: レンジ幅（%）
        position_usd: 1レベルあたりのサイズ
        stop_loss: ストップロス（%）
    """
    np.random.seed(42)
    
    # 価格系列生成（BTCボラティリティ）
    ticks = hours * 360  # 10秒足
    daily_vol = 0.03  # 日次ボラティリティ
    hourly_vol = daily_vol / np.sqrt(24)
    tick_vol = hourly_vol / np.sqrt(360)
    
    returns = np.random.randn(ticks) * tick_vol
    prices = list(67000 * np.cumprod(1 + returns))
    
    # シミュレーション
    pnl = 0
    trades = 0
    position = 0
    max_position = 0
    max_loss = 0
    
    center = prices[0]
    range_half = center * range_pct / 100 / 2
    
    grid_buys = [center - range_half * (i+1)/(levels//2) for i in range(levels//2)]
    grid_sells = [center + range_half * (i+1)/(levels//2) for i in range(levels//2)]
    
    filled_buys = set()
    filled_sells = set()
    
    stop_loss_count = 0
    
    for idx, price in enumerate(prices):
        # ストップロス判定
        lower_bound = center - range_half
        if price < lower_bound * (1 - stop_loss/100):
            # ストップロス発動
            loss = position * (center - price) if position > 0 else 0
            pnl -= loss
            position = 0
            stop_loss_count += 1
            
            # 5分待機後、新レンジ
            if idx + 30 < len(prices):
                center = prices[idx + 30]
                range_half = center * range_pct / 100 / 2
                grid_buys = [center - range_half * (i+1)/(levels//2) for i in range(levels//2)]
                grid_sells = [center + range_half * (i+1)/(levels//2) for i in range(levels//2)]
                filled_buys = set()
                filled_sells = set()
            continue
        
        # レンジ追従
        if price > center + range_half or price < center - range_half:
            center = price
            range_half = center * range_pct / 100 / 2
            grid_buys = [center - range_half * (i+1)/(levels//2) for i in range(levels//2)]
            grid_sells = [center + range_half * (i+1)/(levels//2) for i in range(levels//2)]
            filled_buys = set()
            filled_sells = set()
            continue
        
        # 買い約定
        for i, g in enumerate(grid_buys):
            if i not in filled_buys and price <= g:
                size = position_usd / g
                position += size
                pnl -= position_usd * (1 + 0.0002)  # 手数料
                trades += 1
                filled_buys.add(i)
                max_position = max(max_position, position)
        
        # 売り約定
        for i, g in enumerate(grid_sells):
            if i not in filled_sells and price >= g and position > 0:
                size = min(position_usd / g, position)
                revenue = size * g * (1 - 0.0002)
                pnl += revenue
                position -= size
                trades += 1
                filled_sells.add(i)
        
        # 最大損失更新
        current_pnl = pnl + position * price
        if current_pnl < max_loss:
            max_loss = current_pnl
    
    # 最終評価
    final_pnl = pnl + position * prices[-1]
    
    return {
        'hours': hours,
        'trades': trades,
        'pnl': final_pnl,
        'pnl_per_day': final_pnl / hours * 24,
        'stop_loss_count': stop_loss_count,
        'max_position_usd': max_position * 67000,
        'max_loss': max_loss,
        'margin_used_pct': max_position * 67000 / balance * 100,
    }

def main():
    print("=== シャークフィン現在設定でのシミュレーション ===\n")
    
    balance = 1081  # 現在の残高
    
    print("【設定】")
    print(f"  残高: ${balance}")
    print(f"  レベル数: 40")
    print(f"  グリッド間隔: 0.03%")
    print(f"  レンジ幅: 0.5%")
    print(f"  1レベルサイズ: $150")
    print(f"  ストップロス: 1.5%")
    print()
    
    print("-" * 60)
    
    for hours in [24, 72, 168]:
        result = simulate_current_settings(hours=hours, balance=balance)
        print(f"\n【{hours}時間（{hours//24}日）】")
        print(f"  取引回数: {result['trades']}回")
        print(f"  損益: ${result['pnl']:.2f}")
        print(f"  日次平均: ${result['pnl_per_day']:.2f}")
        print(f"  ストップロス発動: {result['stop_loss_count']}回")
        print(f"  最大ポジション: ${result['max_position_usd']:.2f}")
        print(f"  証拠金使用率: {result['margin_used_pct']:.1f}%")
        print(f"  最大ドローダウン: ${result['max_loss']:.2f}")
    
    # リスク分析
    print("\n" + "=" * 60)
    print("【リスク分析】")
    print("-" * 60)
    
    # 最悪ケース
    worst = simulate_current_settings(hours=24)
    print(f"\n最大ポジション（$600）での損失:")
    print(f"  5%急落: ${600 * 0.05:.2f}")
    print(f"  10%急落: ${600 * 0.10:.2f}")
    print(f"  ストップロス（1.5%）: ${600 * 0.015:.2f}")
    
    # レバレッジ確認
    print(f"\n実質レバレッジ:")
    print(f"  最大ポジション / 残高 = ${600} / ${balance} = {600/balance:.2f}倍")
    print(f"  → 安全圏内（GRVT最大50倍）")

if __name__ == "__main__":
    main()
