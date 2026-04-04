# -*- coding: utf-8 -*-
"""
BTC/USDT グリッド戦略シミュレーション
最適パラメータを検証
"""
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import json

class GridSimulation:
    """グリッド戦略シミュレーション"""
    
    def __init__(self, initial_balance=1000.0, maker_fee=0.0002):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.maker_fee = maker_fee
        self.position = 0.0
        self.position_avg_price = 0.0
        self.trades = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.total_fees = 0.0
    
    def simulate_grid(self, prices, grid_spacing_pct=0.1, levels=30, take_profit_pct=0.25):
        """
        グリッドシミュレーション
        
        Args:
            prices: 価格系列
            grid_spacing_pct: グリッド間隔（%）
            levels: グリッドレベル数
            take_profit_pct: 利確目標（%）
        """
        # グリッド設定
        center_price = prices[0]
        min_price = center_price * (1 - levels * grid_spacing_pct / 100 / 2)
        max_price = center_price * (1 + levels * grid_spacing_pct / 100 / 2)
        
        # グリッドレベル
        grid_prices = []
        for i in range(levels):
            price = min_price + (max_price - min_price) * i / (levels - 1)
            grid_prices.append(price)
        
        # 指値注文
        pending_orders = {}
        for price in grid_prices:
            pending_orders[price] = {'side': 'buy', 'size': 0.001}  # 固定サイズ
        
        # シミュレーション
        for i, price in enumerate(prices):
            for order_price, order in list(pending_orders.items()):
                # 買い約定
                if order['side'] == 'buy' and price <= order_price:
                    cost = order['size'] * order_price
                    fee = cost * self.maker_fee
                    
                    self.position += order['size']
                    self.position_avg_price = order_price
                    self.balance -= (cost + fee)
                    self.total_fees += fee
                    
                    # 売り指値を配置
                    sell_price = order_price * (1 + take_profit_pct / 100)
                    pending_orders[sell_price] = {'side': 'sell', 'size': order['size']}
                    
                    del pending_orders[order_price]
                    self.trades += 1
                
                # 売り約定
                elif order['side'] == 'sell' and price >= order_price:
                    revenue = order['size'] * order_price
                    fee = revenue * self.maker_fee
                    
                    self.position -= order['size']
                    self.balance += (revenue - fee)
                    self.total_fees += fee
                    
                    # 利益計算
                    pnl = (order_price - self.position_avg_price) * order['size'] - fee * 2
                    self.total_pnl += pnl
                    
                    if pnl > 0:
                        self.wins += 1
                    else:
                        self.losses += 1
                    
                    self.trades += 1
                    del pending_orders[order_price]
        
        # 最終ポジションクローズ
        if self.position > 0:
            self.balance += self.position * prices[-1] * (1 - self.maker_fee)
            self.position = 0
        
        return self.get_stats()
    
    def get_stats(self):
        return {
            'initial_balance': self.initial_balance,
            'final_balance': self.balance,
            'pnl': self.balance - self.initial_balance,
            'pnl_pct': (self.balance - self.initial_balance) / self.initial_balance * 100,
            'trades': self.trades,
            'wins': self.wins,
            'losses': self.losses,
            'win_rate': self.wins / self.trades * 100 if self.trades > 0 else 0,
            'total_fees': self.total_fees,
        }


def generate_price_data(duration_hours=24, volatility=0.001):
    """価格データ生成（ランダムウォーク）"""
    np.random.seed(42)
    ticks = int(duration_hours * 12)  # 5分足
    returns = np.random.randn(ticks) * volatility
    prices = 67000 * np.cumprod(1 + returns)  # BTC価格
    return prices


def run_parameter_comparison():
    """パラメータ比較"""
    print("=== BTC/USDT Grid Parameter Comparison ===\n")
    
    # 価格データ生成（24時間、ボラティリティ0.1%）
    prices = generate_price_data(duration_hours=24, volatility=0.001)
    
    # パラメータ組み合わせ
    configs = [
        {"name": "High Frequency", "spacing": 0.05, "levels": 40, "tp": 0.15},
        {"name": "Standard", "spacing": 0.1, "levels": 30, "tp": 0.25},
        {"name": "Conservative", "spacing": 0.2, "levels": 20, "tp": 0.3},
        {"name": "Wide Grid", "spacing": 0.5, "levels": 10, "tp": 0.5},
    ]
    
    results = []
    
    for config in configs:
        sim = GridSimulation(initial_balance=1000.0)
        stats = sim.simulate_grid(
            prices,
            grid_spacing_pct=config['spacing'],
            levels=config['levels'],
            take_profit_pct=config['tp']
        )
        
        result = {
            'name': config['name'],
            'spacing': f"{config['spacing']}%",
            'levels': config['levels'],
            'tp': f"{config['tp']}%",
            **stats
        }
        results.append(result)
        
        print(f"{config['name']}:")
        print(f"  Spacing: {config['spacing']}%, Levels: {config['levels']}, TP: {config['tp']}%")
        print(f"  PnL: ${stats['pnl']:.2f} ({stats['pnl_pct']:.2f}%)")
        print(f"  Trades: {stats['trades']}, Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Fees: ${stats['total_fees']:.2f}")
        print()
    
    # 最適パラメータ
    best = max(results, key=lambda x: x['pnl'])
    print(f"=== Best Config: {best['name']} ===")
    print(f"PnL: ${best['pnl']:.2f} ({best['pnl_pct']:.2f}%)")
    
    return results, best


def simulate_different_timeframes():
    """異なる時間軸でのシミュレーション"""
    print("\n=== Timeframe Comparison ===\n")
    
    timeframes = [
        {"name": "1min", "ticks": 1440, "volatility": 0.0005},
        {"name": "5min", "ticks": 288, "volatility": 0.001},
        {"name": "15min", "ticks": 96, "volatility": 0.002},
        {"name": "1hour", "ticks": 24, "volatility": 0.005},
    ]
    
    for tf in timeframes:
        prices = generate_price_data(duration_hours=24, volatility=tf['volatility'])
        
        sim = GridSimulation(initial_balance=1000.0)
        stats = sim.simulate_grid(
            prices,
            grid_spacing_pct=0.1,
            levels=30,
            take_profit_pct=0.25
        )
        
        print(f"{tf['name']}: PnL ${stats['pnl']:.2f} ({stats['pnl_pct']:.2f}%), Trades: {stats['trades']}")


if __name__ == "__main__":
    results, best = run_parameter_comparison()
    simulate_different_timeframes()
