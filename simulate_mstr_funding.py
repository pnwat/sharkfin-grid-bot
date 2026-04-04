# -*- coding: utf-8 -*-
"""MSTRファンディング裁定シミュレーション"""
import numpy as np

def simulate_funding_arb(hours=24, funding_rate=0.0418, position_usd=1000, volatility=0.03):
    """
    ファンディング裁定シミュレーション
    
    Args:
        hours: 期間（時間）
        funding_rate: ファンディングレート（8時間ごと）
        position_usd: ポジションサイズ（USD）
        volatility: 価格ボラティリティ（日次）
    """
    np.random.seed(42)
    
    # ファンディング収益（8時間ごと）
    funding_periods = hours / 8
    funding_pnl = position_usd * funding_rate * funding_periods
    
    # 価格変動リスク（正規分布）
    price_changes = np.random.randn(1000) * volatility * (hours / 24)
    price_pnl = position_usd * price_changes
    
    # 総PnL
    total_pnl = funding_pnl + price_pnl
    
    return {
        'funding_pnl': funding_pnl,
        'avg_total_pnl': np.mean(total_pnl),
        'min_pnl': np.percentile(total_pnl, 5),  # 下位5%
        'max_pnl': np.percentile(total_pnl, 95),  # 上位5%
        'win_rate': np.mean(total_pnl > 0) * 100,
    }

def simulate_hedged_arb(hours=24, funding_rate=0.0418, position_usd=1000, 
                        btc_correlation=0.7, btc_funding=-0.0078):
    """
    MSTR/BTCヘッジ裁定シミュレーション
    
    MSTRロング + BTCショートで価格リスクをヘッジ
    """
    np.random.seed(42)
    
    # MSTRファンディング収益
    mstr_funding = position_usd * funding_rate * (hours / 8)
    
    # BTCファンディング収益（ショートなので正）
    btc_funding_pnl = position_usd * abs(btc_funding) * (hours / 8)
    
    # 総ファンディング収益
    total_funding = mstr_funding + btc_funding_pnl
    
    # ヘッジ効率（相関70%）
    hedge_efficiency = btc_correlation
    
    # 残リスク（30%の価格変動が残る）
    residual_risk = position_usd * 0.03 * (1 - hedge_efficiency) * (hours / 24)
    price_risk = np.random.randn(1000) * residual_risk
    
    total_pnl = total_funding + price_risk
    
    return {
        'funding_pnl': total_funding,
        'avg_total_pnl': np.mean(total_pnl),
        'min_pnl': np.percentile(total_pnl, 5),
        'max_pnl': np.percentile(total_pnl, 95),
        'win_rate': np.mean(total_pnl > 0) * 100,
    }

def main():
    print("=== MSTR ファンディング裁定シミュレーション ===\n")
    
    # シナリオ1: 単純ロング
    print("【シナリオ1】MSTR単純ロング（$1,000）")
    print("-" * 50)
    
    for hours in [24, 72, 168]:
        result = simulate_funding_arb(hours=hours, funding_rate=0.0418, position_usd=1000)
        print(f"{hours}時間:")
        print(f"  ファンディング収益: ${result['funding_pnl']:.2f}")
        print(f"  平均PnL: ${result['avg_total_pnl']:.2f}")
        print(f"  95%信頼区間: ${result['min_pnl']:.2f} ~ ${result['max_pnl']:.2f}")
        print(f"  勝率: {result['win_rate']:.1f}%")
        print()
    
    # シナリオ2: MSTR/BTCヘッジ
    print("【シナリオ2】MSTRロング + BTCショート（各$1,000）")
    print("-" * 50)
    
    for hours in [24, 72, 168]:
        result = simulate_hedged_arb(hours=hours, funding_rate=0.0418, position_usd=1000)
        print(f"{hours}時間:")
        print(f"  ファンディング収益: ${result['funding_pnl']:.2f}")
        print(f"  平均PnL: ${result['avg_total_pnl']:.2f}")
        print(f"  95%信頼区間: ${result['min_pnl']:.2f} ~ ${result['max_pnl']:.2f}")
        print(f"  勝率: {result['win_rate']:.1f}%")
        print()
    
    # 推奨
    print("=" * 50)
    print("【推奨】")
    
    unhedged = simulate_funding_arb(hours=168)
    hedged = simulate_hedged_arb(hours=168)
    
    print(f"単純ロング: 週${unhedged['avg_total_pnl']:.2f}（勝率{unhedged['win_rate']:.1f}%）")
    print(f"ヘッジ済み: 週${hedged['avg_total_pnl']:.2f}（勝率{hedged['win_rate']:.1f}%）")
    
    if hedged['win_rate'] > 80:
        print("\n→ ヘッジ済み戦略が推奨（勝率80%超、低リスク）")
    elif unhedged['win_rate'] > 60:
        print("\n→ 単純ロングで高収益狙い（勝率60%超）")
    else:
        print("\n→ リスク高、要検討")

if __name__ == "__main__":
    main()
