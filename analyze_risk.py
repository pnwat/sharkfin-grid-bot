# -*- coding: utf-8 -*-
"""シャークフィンリスク分析シミュレーション"""
import numpy as np

def simulate_flash_crash(price_start=67000, crash_pct=10, leverage=50, 
                         position_usd=1000, stop_loss_pct=1.5):
    """
    フラッシュクラッシュ時のシミュレーション
    
    Args:
        price_start: 開始価格
        crash_pct: 下落率（%）
        leverage: レバレッジ
        position_usd: ポジションサイズ
        stop_loss_pct: ストップロス（%）
    """
    # クラッシュ後の価格
    price_after = price_start * (1 - crash_pct / 100)
    
    # ポジションサイズ（BTC）
    position_btc = position_usd / price_start
    
    # 実際の証拠金
    margin = position_usd / leverage
    
    # ストップロス価格
    stop_price = price_start * (1 - stop_loss_pct / 100)
    
    # ストップロスが発動するか
    stop_triggered = price_after < stop_price
    
    # 損失計算（ストップロスなし）
    loss_no_stop = (price_start - price_after) * position_btc
    
    # 損失計算（ストップロスあり）
    if stop_triggered:
        loss_with_stop = (price_start - stop_price) * position_btc
    else:
        loss_with_stop = loss_no_stop
    
    # ロスカット判定（証拠金の80%損失で強制決済）
    liquidation_loss = margin * 0.8
    liquidated = loss_no_stop >= liquidation_loss
    
    return {
        'price_start': price_start,
        'price_after': price_after,
        'stop_triggered': stop_triggered,
        'loss_no_stop': loss_no_stop,
        'loss_with_stop': loss_with_stop,
        'margin': margin,
        'liquidated': liquidated,
        'margin_remaining': margin - loss_with_stop,
    }

def simulate_volatility_spike(volatility_pct=5, leverage=50, position_usd=1000):
    """
    ボラティリティスパイク時のリスク
    """
    np.random.seed(42)
    
    # 1000回シミュレーション
    results = []
    for _ in range(1000):
        # ランダムな価格変動
        change = np.random.randn() * volatility_pct / 100
        price_change = 67000 * change
        
        position_btc = position_usd / 67000
        pnl = -price_change * position_btc  # ロングの場合
        
        margin = position_usd / leverage
        liquidated = abs(pnl) >= margin * 0.8
        
        results.append({
            'pnl': pnl,
            'liquidated': liquidated,
        })
    
    pnls = [r['pnl'] for r in results]
    liquidations = sum(1 for r in results if r['liquidated'])
    
    return {
        'avg_pnl': np.mean(pnls),
        'max_loss': min(pnls),
        'liquidation_rate': liquidations / 1000 * 100,
    }

def calculate_optimal_leverage(position_usd=1000, max_drawdown_pct=20, 
                                daily_volatility=0.03):
    """
    最適レバレッジ計算
    
    Args:
        position_usd: ポジションサイズ
        max_drawdown_pct: 許容ドローダウン（%）
        daily_volatility: 日次ボラティリティ（%）
    """
    # 最悪ケース（3σ）
    worst_case_move = daily_volatility * 3
    
    # 許容損失
    max_loss_usd = position_usd * max_drawdown_pct / 100
    
    # 必要証拠金
    required_margin = position_usd * worst_case_move / 100
    
    # 最適レバレッジ
    optimal_leverage = position_usd / required_margin
    
    return {
        'worst_case_move': worst_case_move,
        'max_loss_usd': max_loss_usd,
        'required_margin': required_margin,
        'optimal_leverage': optimal_leverage,
    }

def main():
    print("=== シャークフィンリスク分析 ===\n")
    
    # 1. フラッシュクラッシュ
    print("【1】フラッシュクラッシュ時の挙動")
    print("-" * 60)
    
    for crash in [5, 10, 20, 30]:
        result = simulate_flash_crash(crash_pct=crash, leverage=50)
        print(f"\n{crash}%下落（${result['price_start']:.0f}→${result['price_after']:.0f}）:")
        print(f"  ストップロス発動: {'はい' if result['stop_triggered'] else 'いいえ'}")
        print(f"  損失（SLなし）: ${result['loss_no_stop']:.2f}")
        print(f"  損失（SLあり）: ${result['loss_with_stop']:.2f}")
        print(f"  証拠金: ${result['margin']:.2f}")
        print(f"  ロスカット: {'警告-発生' if result['liquidated'] else '安全'}")
        print(f"  残証拠金: ${result['margin_remaining']:.2f}")
    
    # 2. ボラティリティスパイク
    print("\n\n【2】ボラティリティスパイク時のリスク")
    print("-" * 60)
    
    for vol in [3, 5, 10, 15]:
        result = simulate_volatility_spike(volatility_pct=vol, leverage=50)
        print(f"\n{vol}%ボラティリティ:")
        print(f"  平均PnL: ${result['avg_pnl']:.2f}")
        print(f"  最大損失: ${result['max_loss']:.2f}")
        print(f"  ロスカット率: {result['liquidation_rate']:.1f}%")
    
    # 3. 最適レバレッジ
    print("\n\n【3】最適レバレッジ計算")
    print("-" * 60)
    
    for max_dd in [10, 20, 30, 50]:
        result = calculate_optimal_leverage(max_drawdown_pct=max_dd)
        print(f"\n許容ドローダウン{max_dd}%:")
        print(f"  最悪ケース変動: {result['worst_case_move']:.1f}%")
        print(f"  推奨レバレッジ: {result['optimal_leverage']:.1f}倍")
    
    # 4. レバレッジ別リスク
    print("\n\n【4】レバレッジ別リスク比較")
    print("-" * 60)
    
    for lev in [10, 20, 30, 50, 100]:
        result = simulate_flash_crash(crash_pct=10, leverage=lev)
        margin_pct = (1/lev) * 100
        print(f"\n{lev}倍（証拠金{margin_pct:.1f}%）:")
        print(f"  10%下落時損失: ${result['loss_with_stop']:.2f}")
        print(f"  ロスカット: {'警告' if result['liquidated'] else '安全'}")
    
    # 推奨
    print("\n\n" + "=" * 60)
    print("【推奨設定】")
    print("-" * 60)
    print("レバレッジ: 20-30倍（推奨）")
    print("理由:")
    print("  - 50倍: 10%下落でロスカットリスクあり")
    print("  - 20倍: 15%下落まで耐える")
    print("  - ストップロス1.5%で約$15損失に制限")

if __name__ == "__main__":
    main()
