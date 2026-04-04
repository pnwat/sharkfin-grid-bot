"""
Order Execution Guard モジュール
成行注文を禁止し、指値注文のみを許可
"""
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class GuardConfig:
    """ガード設定"""
    max_price_deviation_pct: float = 0.5  # 仲値から最大0.5%以内
    enforce_limit_only: bool = True       # 成行注文を強制拒否
    post_only: bool = True                # メーカー注文のみ
    min_order_size_usd: float = 10.0      # 最小注文サイズ
    max_order_size_usd: float = 1000.0    # 最大注文サイズ
    emergency_mode: bool = False          # 緊急モード（成行許可）


class OrderExecutionGuard:
    """注文実行ガード"""
    
    def __init__(self, config: Optional[GuardConfig] = None):
        self.config = config or GuardConfig()
        self.rejected_orders = []
    
    def validate_order(self,
                       order_type: str,
                       side: str,
                       amount: float,
                       price: Optional[float],
                       mid_price: float,
                       symbol: str) -> Dict:
        """注文バリデーション"""
        
        errors = []
        warnings = []
        
        # 1. 成行注文チェック
        if self.config.enforce_limit_only and order_type.lower() == 'market':
            # 緊急モード時は成行注文を許可
            if self.config.emergency_mode:
                warnings.append("EMERGENCY_MODE: Market order allowed")
            else:
                errors.append("MARKET_ORDERS_BLOCKED: Only limit orders are allowed")
        
        # 2. 指値価格チェック
        if order_type.lower() == 'limit':
            if price is None:
                errors.append("LIMIT_ORDER_NO_PRICE: Limit order must have a price")
            elif mid_price > 0:
                deviation = abs(price - mid_price) / mid_price * 100
                if deviation > self.config.max_price_deviation_pct:
                    errors.append(
                        f"PRICE_DEVIATION_TOO_HIGH: {deviation:.3f}% > {self.config.max_price_deviation_pct}%"
                    )
        
        # 3. サイズチェック
        notional = amount * (price or mid_price)
        if notional < self.config.min_order_size_usd:
            warnings.append(f"ORDER_SIZE_SMALL: ${notional:.2f} < ${self.config.min_order_size_usd}")
        if notional > self.config.max_order_size_usd:
            errors.append(f"ORDER_SIZE_TOO_LARGE: ${notional:.2f} > ${self.config.max_order_size_usd}")
        
        # 結果
        is_valid = len(errors) == 0
        
        result = {
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'order_type': order_type,
            'side': side,
            'amount': amount,
            'price': price,
            'mid_price': mid_price,
            'notional_usd': notional
        }
        
        if not is_valid:
            self.rejected_orders.append(result)
        
        return result
    
    def suggest_limit_price(self,
                             side: str,
                             mid_price: float,
                             best_bid: float,
                             best_ask: float) -> Dict:
        """最適な指値価格を提案"""
        
        if side.lower() == 'buy':
            # 買い: ビッド価格またはそれより少し高い価格
            if self.config.post_only:
                # メーカー: ビッドより少し下
                suggested = best_bid * 0.9998  # 0.02%下
            else:
                # テイカーも許可: ビッド〜アスクの中間
                suggested = (best_bid + mid_price) / 2
        else:
            # 売り: アスク価格またはそれより少し安い価格
            if self.config.post_only:
                # メーカー: アスクより少し上
                suggested = best_ask * 1.0002  # 0.02%上
            else:
                suggested = (best_ask + mid_price) / 2
        
        # 仲値からの偏差をチェック
        deviation = abs(suggested - mid_price) / mid_price * 100
        
        return {
            'suggested_price': suggested,
            'side': side,
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'deviation_pct': deviation,
            'within_threshold': deviation <= self.config.max_price_deviation_pct,
            'post_only': self.config.post_only
        }
    
    def get_rejected_count(self) -> int:
        """拒否された注文数"""
        return len(self.rejected_orders)
    
    def clear_rejected(self):
        """拒否履歴をクリア"""
        self.rejected_orders = []
    
    def set_emergency_mode(self, enabled: bool = True):
        """緊急モード設定"""
        self.config.emergency_mode = enabled
        if enabled:
            log("EMERGENCY_MODE_ENABLED: Market orders are now allowed")
        else:
            log("EMERGENCY_MODE_DISABLED: Market orders are blocked")
    
    def is_emergency_mode(self) -> bool:
        """緊急モードかどうか"""
        return self.config.emergency_mode
    
    def get_status(self) -> Dict:
        """状態取得"""
        return {
            'enforce_limit_only': self.config.enforce_limit_only,
            'max_price_deviation_pct': self.config.max_price_deviation_pct,
            'post_only': self.config.post_only,
            'rejected_orders_count': len(self.rejected_orders),
            'min_order_size_usd': self.config.min_order_size_usd,
            'max_order_size_usd': self.config.max_order_size_usd
        }


# グローバルインスタンス
order_guard = OrderExecutionGuard()
