# -*- coding: utf-8 -*-
"""
ATR（Average True Range）ベースの動的グリッド間隔調整
"""
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ATRConfig:
    """ATR設定"""
    period: int = 14           # ATR期間
    multiplier_low: float = 0.5  # 低ボラ時の乗数
    multiplier_high: float = 2.0  # 高ボラ時の乗数
    base_spacing: float = 0.05    # ベース間隔（%）
    min_spacing: float = 0.03     # 最小間隔（%）
    max_spacing: float = 0.15     # 最大間隔（%）


class ATRDynamicGrid:
    """ATRベースの動的グリッド"""
    
    def __init__(self, config: ATRConfig = None):
        self.config = config or ATRConfig()
        self.atr_value: float = 0.0
        self.atr_pct: float = 0.0
        self.volatility_level: str = "normal"
    
    def calculate_tr(self, high: float, low: float, close_prev: float) -> float:
        """True Range計算"""
        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)
        return max(tr1, tr2, tr3)
    
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float]) -> float:
        """
        ATR計算
        
        Args:
            highs: 高値リスト
            lows: 安値リスト
            closes: 終値リスト
        
        Returns:
            ATR値
        """
        if len(closes) < self.config.period + 1:
            return 0.0
        
        # True Range計算
        trs = []
        for i in range(1, len(closes)):
            tr = self.calculate_tr(highs[i], lows[i], closes[i-1])
            trs.append(tr)
        
        # ATR（移動平均）
        if len(trs) >= self.config.period:
            atr = np.mean(trs[-self.config.period:])
        else:
            atr = np.mean(trs)
        
        self.atr_value = atr
        
        # ATR%（価格に対する割合）
        if closes[-1] > 0:
            self.atr_pct = (atr / closes[-1]) * 100
        
        return atr
    
    def get_volatility_level(self) -> str:
        """ボラティリティレベル判定"""
        if self.atr_pct < 0.5:
            self.volatility_level = "low"
        elif self.atr_pct > 2.0:
            self.volatility_level = "high"
        else:
            self.volatility_level = "normal"
        
        return self.volatility_level
    
    def calculate_dynamic_spacing(self) -> float:
        """
        動的グリッド間隔計算
        
        Returns:
            グリッド間隔（%）
        """
        level = self.get_volatility_level()
        
        if level == "low":
            # 低ボラ: 間隔を狭める
            spacing = self.config.base_spacing * self.config.multiplier_low
        elif level == "high":
            # 高ボラ: 間隔を広げる
            spacing = self.config.base_spacing * self.config.multiplier_high
        else:
            # 通常: ベース間隔
            spacing = self.config.base_spacing
        
        # 範囲内にクリップ
        spacing = np.clip(spacing, self.config.min_spacing, self.config.max_spacing)
        
        return spacing
    
    def calculate_dynamic_range(self) -> float:
        """
        動的レンジ幅計算
        
        Returns:
            レンジ幅（%）
        """
        # ATR%に基づいてレンジ幅を調整
        # 低ボラ: 狭いレンジ
        # 高ボラ: 広いレンジ
        range_pct = self.atr_pct * 2  # ATRの2倍
        
        # 最小1.0%、最大3.0%
        range_pct = np.clip(range_pct, 1.0, 3.0)
        
        return range_pct
    
    def get_grid_params(self, highs: List[float], lows: List[float], closes: List[float]) -> Tuple[float, float]:
        """
        グリッドパラメータ取得
        
        Returns:
            (spacing_pct, range_pct)
        """
        self.calculate_atr(highs, lows, closes)
        spacing = self.calculate_dynamic_spacing()
        range_pct = self.calculate_dynamic_range()
        
        return spacing, range_pct
    
    def get_status(self) -> dict:
        """状態取得"""
        return {
            'atr_value': self.atr_value,
            'atr_pct': self.atr_pct,
            'volatility_level': self.volatility_level,
            'spacing_pct': self.calculate_dynamic_spacing(),
            'range_pct': self.calculate_dynamic_range(),
        }


# 使用例
if __name__ == "__main__":
    import random
    
    # ダミーデータ生成
    random.seed(42)
    closes = [67000 + random.gauss(0, 100) for _ in range(50)]
    highs = [c + random.uniform(50, 150) for c in closes]
    lows = [c - random.uniform(50, 150) for c in closes]
    
    atr = ATRDynamicGrid()
    spacing, range_pct = atr.get_grid_params(highs, lows, closes)
    
    print("=== ATR Dynamic Grid ===")
    print(f"ATR Value: ${atr.atr_value:.2f}")
    print(f"ATR %: {atr.atr_pct:.3f}%")
    print(f"Volatility: {atr.volatility_level}")
    print(f"Grid Spacing: {spacing:.3f}%")
    print(f"Grid Range: {range_pct:.2f}%")
