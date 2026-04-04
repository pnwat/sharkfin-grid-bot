# -*- coding: utf-8 -*-
"""
シャークフィンボット 収益性シミュレーション
様々なパラメータをテスト
"""
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class SimResult:
    config_name: str
    spacing_pct: float
    levels: int
    range_pct: float
    pnl: float
    pnl_pct: float
    trades: int
    win_rate: float
    fees: float

class SharkfinSimulator:
    """シャークフィン戦略シミュレータ"""
    
    def __init__(self, initial_balance=1000.0, maker_fee=0.0002):
        self.initial_balance = initial_balance
        self.maker_fee = maker_fee
    
    def simulate(self, prices: List[float], spacing_pct: float, levels: int, range_pct: float) -> SimResult:
        """
        シミュレーション実行
        
        Args:
            prices: 価格系列
            spacing_pct: グリッド間隔（%）
            levels: レベル数
            range_pct: レンジ幅（%）
        
        Returns:
            シミュレーション結果
        """
        balance = self.initial_balance
        position = 0.0
        entry_price = 0.0
        trades = 0
        wins = 0
        total_fees = 0.0
        
        # レンジ設定
        center = prices[0]
        upper = center * (1 + range_pct / 100)
        lower = center * (1 - range_pct / 100)
        
        # グリッド注文
        grid_orders = {}
        for i in range(levels):
            # 買い
            buy_price = lower + (center - lower) * i / levels
            grid_orders[buy_price] = {'side': 'buy', 'size': 0.01}
            
            # 売り
            sell_price = center + (upper - center) * i / levels
            grid_orders[sell_price] = {'side': 'sell', 'size': 0.01}
        
        # シミュレーション
        for price in prices:
            for order_price in list(grid_orders.keys()):
                order = grid_orders[order_price]
                
                # 買い約定
                if order['side'] == 'buy' and price <= order_price:
                    cost = order['size'] * order_price
                    fee = cost * self.maker_fee
                    
                    position += order['size']
                    entry_price = order_price
                    balance -= (cost + fee)
                    total_fees += fee
                    trades += 1
                    
                    # 売り注文配置
                    sell_price = order_price * (1 + spacing_pct / 100)
                    grid_orders[sell_price] = {'side': 'sell', 'size': order['size']}
                    del grid_orders[order_price]
                
                # 売り約定
                elif order['side'] == 'sell' and price >= order_price:
                    revenue = order['size'] * order_price
                    fee = revenue * self.maker_fee
                    
                    position -= order['size']
                    balance += (revenue - fee)
                    total_fees += fee
                    
                    # 損益計算
                    pnl = (order_price - entry_price) * order['size'] - fee * 2
                    if pnl > 0:
                        wins += 1
                    
                    trades += 1
                    del grid_orders[order_price]
        
        # 最終決済
        if position > 0:
            balance += position * prices[-1] * (1 - self.maker_fee)
        
        pnl = balance - self.initial_balance
        pnl_pct = pnl / self.initial_balance * 100
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        return SimResult(
            config_name="",
            spacing_pct=spacing_pct,
            levels=levels,
            range_pct=range_pct,
            pnl=pnl,
            pnl_pct=pnl_pct,
            trades=trades,
            win_rate=win_rate,
            fees=total_fees
        )

def generate_market_data(hours: int, volatility: float) -> List[float]:
    """市場データ生成"""
    np.random.seed(42)
    ticks = hours * 12  # 5分足
    returns = np.random.randn(ticks) * volatility
    prices = 67000 * np.cumprod(1 + returns)
    return prices.tolist()

def run_comprehensive_simulation():
    """包括的シミュレーション"""
    print("=== Sharkfin Bot 収益性シミュレーション ===\n")
    
    sim = SharkfinSimulator()
    
    # シナリオ1: グリッド間隔比較
    print("【1】グリッド間隔比較（24時間、ボラ0.1%）")
    print("-" * 60)
    
    prices = generate_market_data(24, 0.001)
    
    spacings = [0.03, 0.05, 0.10, 0.15, 0.20]
    results = []
    
    for spacing in spacings:
        result = sim.simulate(prices, spacing_pct=spacing, levels=40, range_pct=1.0)
        result.config_name = f"spacing={spacing}%"
        results.append(result)
        
        print(f"間隔 {spacing:.2f}%: PnL ${result.pnl:.2f} ({result.pnl_pct:.2f}%), 取引{result.trades}回, 勝率{result.win_rate:.1f}%")
    
    best_spacing = max(results, key=lambda x: x.pnl)
    print(f"\n最適間隔: {best_spacing.spacing_pct:.2f}% (PnL ${best_spacing.pnl:.2f})")
    
    # シナリオ2: レベル数比較
    print("\n【2】レベル数比較（24時間、ボラ0.1%）")
    print("-" * 60)
    
    level_counts = [20, 30, 40, 50, 60]
    results2 = []
    
    for levels in level_counts:
        result = sim.simulate(prices, spacing_pct=0.05, levels=levels, range_pct=1.0)
        result.config_name = f"levels={levels}"
        results2.append(result)
        
        print(f"レベル {levels}: PnL ${result.pnl:.2f} ({result.pnl_pct:.2f}%), 取引{result.trades}回")
    
    best_levels = max(results2, key=lambda x: x.pnl)
    print(f"\n最適レベル数: {best_levels.levels} (PnL ${best_levels.pnl:.2f})")
    
    # シナリオ3: レンジ幅比較
    print("\n【3】レンジ幅比較（24時間、ボラ0.1%）")
    print("-" * 60)
    
    ranges = [0.5, 1.0, 1.5, 2.0, 3.0]
    results3 = []
    
    for range_pct in ranges:
        result = sim.simulate(prices, spacing_pct=0.05, levels=40, range_pct=range_pct)
        result.config_name = f"range={range_pct}%"
        results3.append(result)
        
        print(f"レンジ {range_pct:.1f}%: PnL ${result.pnl:.2f} ({result.pnl_pct:.2f}%), 取引{result.trades}回")
    
    best_range = max(results3, key=lambda x: x.pnl)
    print(f"\n最適レンジ: {best_range.range_pct:.1f}% (PnL ${best_range.pnl:.2f})")
    
    # シナリオ4: ボラティリティ影響
    print("\n【4】ボラティリティ影響（24時間）")
    print("-" * 60)
    
    volatilities = [
        ("低ボラ", 0.0005),
        ("通常", 0.001),
        ("高ボラ", 0.002),
        ("超高ボラ", 0.005),
    ]
    
    for name, vol in volatilities:
        prices_vol = generate_market_data(24, vol)
        result = sim.simulate(prices_vol, spacing_pct=0.05, levels=40, range_pct=1.0)
        print(f"{name} ({vol*100:.2f}%): PnL ${result.pnl:.2f} ({result.pnl_pct:.2f}%), 取引{result.trades}回")
    
    # シナリオ5: 最適パラメータ組み合わせ
    print("\n【5】最適パラメータ組み合わせ")
    print("-" * 60)
    
    optimal_configs = [
        {"name": "保守的", "spacing": 0.10, "levels": 20, "range": 2.0},
        {"name": "標準", "spacing": 0.05, "levels": 40, "range": 1.0},
        {"name": "積極的", "spacing": 0.03, "levels": 60, "range": 0.5},
    ]
    
    for config in optimal_configs:
        prices_opt = generate_market_data(24, 0.001)
        result = sim.simulate(
            prices_opt,
            spacing_pct=config['spacing'],
            levels=config['levels'],
            range_pct=config['range']
        )
        print(f"{config['name']}: 間隔{config['spacing']}%, レベル{config['levels']}, レンジ{config['range']}%")
        print(f"  → PnL ${result.pnl:.2f} ({result.pnl_pct:.2f}%), 手数料${result.fees:.2f}")
    
    # 期待収益サマリー
    print("\n" + "=" * 60)
    print("【期待収益サマリー】")
    print("-" * 60)
    
    # 1週間シミュレーション
    prices_week = generate_market_data(24 * 7, 0.001)
    result_week = sim.simulate(prices_week, spacing_pct=0.05, levels=40, range_pct=1.0)
    
    print(f"1週間: PnL ${result_week.pnl:.2f} ({result_week.pnl_pct:.2f}%)")
    print(f"1ヶ月（予測）: ${result_week.pnl * 4:.2f} ({result_week.pnl_pct * 4:.2f}%)")
    print(f"1年（予測）: ${result_week.pnl * 52:.2f} ({result_week.pnl_pct * 52:.2f}%)")

if __name__ == "__main__":
    run_comprehensive_simulation()
