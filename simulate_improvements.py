# -*- coding: utf-8 -*-
"""
シャークフィン改善策シミュレーション比較
"""
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class SimResult:
    name: str
    pnl: float
    trades: int
    win_rate: float
    max_drawdown: float

class SharkfinSimulator:
    def __init__(self, initial_balance=1000.0, maker_fee=0.0002):
        self.initial_balance = initial_balance
        self.maker_fee = maker_fee
    
    def generate_price_series(self, hours: int, volatility: float, trend: float = 0.0) -> List[float]:
        """価格系列生成（トレンド付き）"""
        np.random.seed(42)
        ticks = hours * 360  # 10秒足
        returns = np.random.randn(ticks) * volatility + trend / ticks
        prices = 67000 * np.cumprod(1 + returns)
        return prices.tolist()
    
    def simulate_baseline(self, prices: List[float], spacing_pct: float = 0.03, 
                          levels: int = 40, range_pct: float = 0.5) -> SimResult:
        """ベースライン（固定レンジ）"""
        balance = self.initial_balance
        trades = 0
        wins = 0
        max_balance = balance
        max_drawdown = 0
        
        center = prices[0]
        upper = center * (1 + range_pct / 100 / 2)
        lower = center * (1 - range_pct / 100 / 2)
        
        position = 0.0
        entry_price = 0.0
        
        # グリッド注文（簡略化）
        grid_buys = [lower + (center - lower) * i / (levels // 2) for i in range(levels // 2)]
        grid_sells = [center + (upper - center) * i / (levels // 2) for i in range(levels // 2)]
        
        filled_buys = []
        filled_sells = []
        
        for price in prices:
            # 買い約定チェック
            for i, grid_price in enumerate(grid_buys):
                if price <= grid_price and i not in filled_buys:
                    size = 150 / grid_price
                    position += size
                    entry_price = grid_price
                    balance -= 150 * (1 + self.maker_fee)
                    filled_buys.append(i)
                    trades += 1
                    
                    # 売り注文配置
                    sell_price = grid_price * (1 + spacing_pct / 100)
                    if sell_price not in grid_sells:
                        grid_sells.append(sell_price)
            
            # 売り約定チェック
            for grid_price in grid_sells[:]:
                if price >= grid_price and position > 0:
                    size = min(150 / grid_price, position)
                    revenue = size * grid_price * (1 - self.maker_fee)
                    balance += revenue
                    position -= size
                    trades += 1
                    
                    if grid_price > entry_price:
                        wins += 1
                    
                    if grid_price in grid_sells:
                        grid_sells.remove(grid_price)
            
            # ドローダウン計算
            if balance > max_balance:
                max_balance = balance
            drawdown = (max_balance - balance) / max_balance
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 最終決済
        if position > 0:
            balance += position * prices[-1]
        
        pnl = balance - self.initial_balance
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        return SimResult("ベースライン（固定）", pnl, trades, win_rate, max_drawdown)
    
    def simulate_range_follow(self, prices: List[float], spacing_pct: float = 0.03,
                              levels: int = 40, range_pct: float = 0.5) -> SimResult:
        """レンジ追従（価格に合わせてレンジ移動）"""
        balance = self.initial_balance
        trades = 0
        wins = 0
        max_balance = balance
        max_drawdown = 0
        
        center = prices[0]
        range_half = center * range_pct / 100 / 2
        
        position = 0.0
        entry_price = 0.0
        
        grid_orders = {}  # price -> {'side': 'buy'/'sell', 'size': size}
        
        # 初期グリッド配置
        for i in range(levels // 2):
            buy_price = center - range_half * (i + 1) / (levels // 2)
            grid_orders[round(buy_price)] = {'side': 'buy', 'size': 150 / buy_price}
            sell_price = center + range_half * (i + 1) / (levels // 2)
            grid_orders[round(sell_price)] = {'side': 'sell', 'size': 150 / sell_price}
        
        filled_orders = []
        
        last_center = center
        
        for idx, price in enumerate(prices):
            # レンジ追従（5分ごと）
            if idx % 30 == 0:
                # 中心価格を現在価格に近づける（徐々に）
                center = center * 0.95 + price * 0.05
                
                # レンジ外れたら再設定
                if price < center - range_half or price > center + range_half:
                    center = price
                    # 全ポジション決済
                    if position > 0:
                        balance += position * price
                        position = 0
                    
                    # グリッド再配置
                    grid_orders = {}
                    for i in range(levels // 2):
                        buy_price = center - range_half * (i + 1) / (levels // 2)
                        grid_orders[round(buy_price)] = {'side': 'buy', 'size': 150 / buy_price}
                        sell_price = center + range_half * (i + 1) / (levels // 2)
                        grid_orders[round(sell_price)] = {'side': 'sell', 'size': 150 / sell_price}
                    filled_orders = []
            
            # 約定チェック
            for grid_price in list(grid_orders.keys()):
                if grid_price in filled_orders:
                    continue
                    
                order = grid_orders[grid_price]
                
                if order['side'] == 'buy' and price <= grid_price:
                    balance -= grid_price * order['size'] * (1 + self.maker_fee)
                    position += order['size']
                    entry_price = grid_price
                    trades += 1
                    filled_orders.append(grid_price)
                    
                    # 反対注文
                    sell_price = round(grid_price * (1 + spacing_pct / 100))
                    if sell_price not in grid_orders:
                        grid_orders[sell_price] = {'side': 'sell', 'size': order['size']}
                
                elif order['side'] == 'sell' and price >= grid_price and position > 0:
                    size = min(order['size'], position)
                    balance += grid_price * size * (1 - self.maker_fee)
                    position -= size
                    trades += 1
                    
                    if grid_price > entry_price:
                        wins += 1
                    
                    filled_orders.append(grid_price)
            
            # ドローダウン
            if balance > max_balance:
                max_balance = balance
            drawdown = (max_balance - balance) / max_balance if max_balance > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 最終決済
        if position > 0:
            balance += position * prices[-1]
        
        pnl = balance - self.initial_balance
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        return SimResult("レンジ追従", pnl, trades, win_rate, max_drawdown)
    
    def simulate_dynamic_spacing(self, prices: List[float], base_spacing: float = 0.03,
                                  levels: int = 40, range_pct: float = 0.5) -> SimResult:
        """動的グリッド間隔（ボラティリティベース）"""
        balance = self.initial_balance
        trades = 0
        wins = 0
        max_balance = balance
        max_drawdown = 0
        
        center = prices[0]
        position = 0.0
        entry_price = 0.0
        
        grid_orders = {}
        filled_orders = []
        
        # 初期ボラティリティ計算
        window = 100
        recent_returns = []
        
        for idx, price in enumerate(prices):
            # ボラティリティ計算
            if idx > 0:
                ret = (price - prices[idx-1]) / prices[idx-1]
                recent_returns.append(ret)
                if len(recent_returns) > window:
                    recent_returns.pop(0)
            
            volatility = np.std(recent_returns) if len(recent_returns) > 10 else 0.001
            
            # 動的間隔（ボラが高い = 広い間隔）
            # 低ボラ: 0.02%, 高ボラ: 0.10%
            dynamic_spacing = base_spacing * (1 + volatility * 1000)
            dynamic_spacing = max(0.02, min(0.10, dynamic_spacing))
            
            # グリッド配置（動的更新）
            if idx % 30 == 0 or len(grid_orders) < levels // 2:
                range_half = center * range_pct / 100 / 2
                
                # 新しいグリッド配置
                for i in range(levels // 2):
                    buy_price = round(center - dynamic_spacing * (i + 1) / 100 * center)
                    if buy_price not in grid_orders and buy_price not in filled_orders:
                        grid_orders[buy_price] = {'side': 'buy', 'size': 150 / buy_price}
                    
                    sell_price = round(center + dynamic_spacing * (i + 1) / 100 * center)
                    if sell_price not in grid_orders and sell_price not in filled_orders:
                        grid_orders[sell_price] = {'side': 'sell', 'size': 150 / sell_price}
            
            # 約定チェック
            for grid_price in list(grid_orders.keys()):
                if grid_price in filled_orders:
                    continue
                    
                order = grid_orders[grid_price]
                
                if order['side'] == 'buy' and price <= grid_price:
                    balance -= grid_price * order['size'] * (1 + self.maker_fee)
                    position += order['size']
                    entry_price = grid_price
                    trades += 1
                    filled_orders.append(grid_price)
                    
                    sell_price = round(grid_price * (1 + dynamic_spacing / 100))
                    grid_orders[sell_price] = {'side': 'sell', 'size': order['size']}
                
                elif order['side'] == 'sell' and price >= grid_price and position > 0:
                    size = min(order['size'], position)
                    balance += grid_price * size * (1 - self.maker_fee)
                    position -= size
                    trades += 1
                    
                    if grid_price > entry_price:
                        wins += 1
                    
                    filled_orders.append(grid_price)
            
            # ドローダウン
            if balance > max_balance:
                max_balance = balance
            drawdown = (max_balance - balance) / max_balance if max_balance > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        if position > 0:
            balance += position * prices[-1]
        
        pnl = balance - self.initial_balance
        win_rate = wins / trades * 100 if trades > 0 else 0
        
        return SimResult("動的グリッド間隔", pnl, trades, win_rate, max_drawdown)

def run_comparison():
    print("=== シャークフィン改善策シミュレーション比較 ===\n")
    
    sim = SharkfinSimulator()
    
    # シナリオ別テスト
    scenarios = [
        ("低ボラ・横ばい", 0.0005, 0.0),
        ("通常ボラ", 0.001, 0.0),
        ("高ボラ", 0.002, 0.0),
        ("上昇トレンド", 0.001, 0.001),
        ("下降トレンド", 0.001, -0.001),
    ]
    
    all_results = []
    
    for scenario_name, vol, trend in scenarios:
        print(f"\n【{scenario_name}】ボラ={vol*100:.2f}%, トレンド={trend*100:.2f}%/h")
        print("-" * 70)
        
        prices = sim.generate_price_series(24, vol, trend)
        
        baseline = sim.simulate_baseline(prices)
        range_follow = sim.simulate_range_follow(prices)
        dynamic = sim.simulate_dynamic_spacing(prices)
        
        results = [baseline, range_follow, dynamic]
        
        for r in results:
            print(f"{r.name:20s}: PnL ${r.pnl:7.2f}, 取引{r.trades:3d}回, 勝率{r.win_rate:5.1f}%, DD{r.max_drawdown*100:4.1f}%")
        
        best = max(results, key=lambda x: x.pnl)
        print(f"→ 最優秀: {best.name}")
        all_results.append((scenario_name, best.name, best.pnl))
    
    # サマリー
    print("\n" + "=" * 70)
    print("【シナリオ別最適戦略】")
    print("-" * 70)
    for scenario, best_name, pnl in all_results:
        print(f"{scenario:20s}: {best_name} (PnL ${pnl:.2f})")
    
    # 総合推奨
    print("\n" + "=" * 70)
    print("【総合推奨】")
    
    # 各戦略が最適だった回数
    strategy_wins = {}
    for _, best_name, _ in all_results:
        strategy_wins[best_name] = strategy_wins.get(best_name, 0) + 1
    
    best_strategy = max(strategy_wins.items(), key=lambda x: x[1])
    print(f"推奨戦略: {best_strategy[0]}（{best_strategy[1]}/5シナリオで最優秀）")

if __name__ == "__main__":
    run_comparison()
