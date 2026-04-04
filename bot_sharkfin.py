# -*- coding: utf-8 -*-
"""
シャークフィン/レンジグリッドボット

指値のみ（LIMIT_MAKER）で運用するグリッドボット
成行注文は一切使用しない
"""
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv
from dotenv import load_dotenv
from atr_dynamic_grid import ATRDynamicGrid, ATRConfig

load_dotenv()

# 設定（BTC/USDT最適パラメータ + ATR動的調整）
SYMBOL = "BTC_USDT_Perp"
GRID_COUNT = 40
BASE_GRID_SPACING_PCT = 0.05
BASE_RANGE_PCT = 1.0
USE_ATR_DYNAMIC = True  # ATR動的調整を有効化
POSITION_SIZE_USD = 25
STOP_LOSS_PCT = 1.5

STATE_FILE = "sharkfin_state.json"
LOG_FILE = "sharkfin.log"

GRVT_API_KEY = os.getenv("GRVT_API_KEY")
GRVT_API_SECRET = os.getenv("GRVT_API_SECRET")


@dataclass
class SharkfinState:
    running: bool = False
    range_center: float = 0.0
    range_upper: float = 0.0
    range_lower: float = 0.0
    grid_levels: List[Dict] = None
    active_orders: Dict = None  # {price: order_id}
    position: float = 0.0
    total_pnl: float = 0.0
    trades: int = 0

    def __post_init__(self):
        if self.grid_levels is None:
            self.grid_levels = []
        if self.active_orders is None:
            self.active_orders = {}


def log(msg: str):
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} | {msg}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {msg}\n")
    except:
        pass


def load_state() -> SharkfinState:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return SharkfinState(**data)
        except:
            pass
    return SharkfinState()


def save_state(state: SharkfinState):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False, indent=2)
    except:
        pass


class SharkfinGridBot:
    """シャークフィン/レンジグリッドボット"""

    def __init__(self):
        self.client = None
        self.state = load_state()
        self.atr_grid = ATRDynamicGrid() if USE_ATR_DYNAMIC else None
        self.grid_spacing_pct = BASE_GRID_SPACING_PCT
        self.range_pct = BASE_RANGE_PCT

    async def connect(self):
        try:
            params = {}
            if GRVT_API_KEY:
                params['api_key'] = GRVT_API_KEY
            if GRVT_API_SECRET:
                params['private_key'] = GRVT_API_SECRET
            if os.getenv("GRVT_TRADING_ACCOUNT_ID"):
                params['trading_account_id'] = os.getenv("GRVT_TRADING_ACCOUNT_ID")

            self.client = GrvtCcxt(env=GrvtEnv.PROD, parameters=params)
            log("Connected to GRVT")
            return True
        except Exception as e:
            log(f"Connection error: {e}")
            return False

    def calculate_grid_levels(self, center_price: float) -> List[Dict]:
        """グリッドレベルを計算（幾何学的間隔）"""
        levels = []
        
        spacing_pct = self.grid_spacing_pct  # 動的間隔を使用
        
        # 下方向（買い）
        for i in range(GRID_COUNT // 2):
            price = center_price * (1 - spacing_pct / 100) ** (i + 1)
            levels.append({
                'price': round(price, 2),
                'side': 'buy',
                'size': round(POSITION_SIZE_USD / price, 4),
                'level': i + 1,
            })
        
        # 上方向（売り）
        for i in range(GRID_COUNT // 2):
            price = center_price * (1 + spacing_pct / 100) ** (i + 1)
            levels.append({
                'price': round(price, 2),
                'side': 'sell',
                'size': round(POSITION_SIZE_USD / price, 4),
                'level': i + 1,
            })
        
        return sorted(levels, key=lambda x: x['price'])

    async def setup_range(self):
        """レンジ設定"""
        # 現在価格を取得
        ticker = self.client.fetch_ticker(SYMBOL)
        center_price = float(ticker['last_price'])
        
        # ATR動的調整（有効な場合）
        if self.atr_grid and USE_ATR_DYNAMIC:
            # OHLCV取得（直近50本）
            ohlcv = self.client.fetch_ohlcv(SYMBOL, timeframe='5m', limit=50)
            highs = [c[2] for c in ohlcv]
            lows = [c[3] for c in ohlcv]
            closes = [c[4] for c in ohlcv]
            
            self.grid_spacing_pct, self.range_pct = self.atr_grid.get_grid_params(highs, lows, closes)
            
            atr_status = self.atr_grid.get_status()
            log(f"ATR Dynamic: {atr_status['volatility_level']}, spacing={self.grid_spacing_pct:.3f}%, range={self.range_pct:.2f}%")
        
        # レンジ設定
        self.state.range_center = center_price
        self.state.range_upper = center_price * (1 + self.range_pct / 100)
        self.state.range_lower = center_price * (1 - self.range_pct / 100)
        
        # グリッドレベル計算
        self.state.grid_levels = self.calculate_grid_levels(center_price)
        
        log(f"Range setup: {self.state.range_lower:.2f} - {self.state.range_upper:.2f}")
        log(f"Center: {center_price:.2f}, Grid levels: {len(self.state.grid_levels)}")
        
        save_state(self.state)

    async def place_grid_orders(self):
        """グリッド注文を配置（LIMIT_MAKER）"""
        if not self.state.grid_levels:
            await self.setup_range()
        
        # 既存注文をキャンセル
        await self.cancel_all_orders()
        
        # 新しい注文を配置
        for level in self.state.grid_levels:
            try:
                order = self.client.create_order(
                    symbol=SYMBOL,
                    order_type='limit',
                    side=level['side'],
                    amount=level['size'],
                    price=level['price'],
                    params={'post_only': True}  # LIMIT_MAKER
                )
                
                order_id = order.get('id') or order.get('order_id')
                if order_id:
                    self.state.active_orders[str(level['price'])] = order_id
                    log(f"Placed {level['side']} order: {level['size']} @ {level['price']}")
                
            except Exception as e:
                log(f"Order error at {level['price']}: {e}")
        
        save_state(self.state)

    async def cancel_all_orders(self):
        """全注文をキャンセル"""
        try:
            open_orders = self.client.fetch_open_orders(SYMBOL)
            for order in open_orders:
                order_id = order.get('id') or order.get('order_id')
                if order_id:
                    self.client.cancel_order(order_id, SYMBOL)
            
            self.state.active_orders = {}
            save_state(self.state)
            log("Cancelled all orders")
        except Exception as e:
            log(f"Cancel error: {e}")

    async def place_opposite_order(self, filled_side: str, filled_price: float, filled_size: float):
        """約定後の逆注文を配置"""
        # 買い約定 → 売り注文
        # 売り約定 → 買い注文
        opposite_side = 'sell' if filled_side == 'buy' else 'buy'
        
        # 価格はグリッド間隔分ずらす
        if opposite_side == 'sell':
            new_price = filled_price * (1 + GRID_SPACING_PCT / 100)
        else:
            new_price = filled_price * (1 - GRID_SPACING_PCT / 100)
        
        new_price = round(new_price, 2)
        new_size = round(POSITION_SIZE_USD / new_price, 4)
        
        try:
            order = self.client.create_order(
                symbol=SYMBOL,
                order_type='limit',
                side=opposite_side,
                amount=new_size,
                price=new_price,
                params={'post_only': True}
            )
            log(f"Placed opposite order: {opposite_side} {new_size} @ {new_price}")
        except Exception as e:
            log(f"Opposite order error: {e}")

    async def place_stop_loss(self):
        """ストップロス注文（LIMIT）"""
        if self.state.position <= 0:
            return
        
        stop_price = self.state.range_lower * (1 - STOP_LOSS_PCT / 100)
        stop_price = round(stop_price, 2)
        
        try:
            # ストップロスはLIMIT注文で（成行禁止）
            self.client.create_order(
                symbol=SYMBOL,
                order_type='limit',
                side='sell',
                amount=abs(self.state.position),
                price=stop_price,
                params={'post_only': False}  # ストップは即座に約定させたい
            )
            log(f"Stop loss placed: sell @ {stop_price}")
        except Exception as e:
            log(f"Stop loss error: {e}")

    async def check_range_breakout(self, current_price: float) -> bool:
        """レンジブレイクアウト検出"""
        if current_price > self.state.range_upper:
            log(f"Range breakout UP: {current_price} > {self.state.range_upper}")
            return True
        if current_price < self.state.range_lower:
            log(f"Range breakout DOWN: {current_price} < {self.state.range_lower}")
            return True
        return False

    async def close_position(self, reason: str = ""):
        """ポジション決済（LIMIT）"""
        if abs(self.state.position) < 0.001:
            return
        
        ticker = self.client.fetch_ticker(SYMBOL)
        best_bid = float(ticker['best_bid_price'])
        
        try:
            side = 'sell' if self.state.position > 0 else 'buy'
            self.client.create_order(
                symbol=SYMBOL,
                order_type='limit',
                side=side,
                amount=abs(self.state.position),
                price=best_bid,
                params={'post_only': False}
            )
            log(f"Closing position: {reason}")
            self.state.position = 0
            save_state(self.state)
        except Exception as e:
            log(f"Close error: {e}")

    async def run(self):
        """メインループ"""
        log("Sharkfin Grid Bot started")
        log(f"  Symbol: {SYMBOL}")
        log(f"  Grid count: {GRID_COUNT}")
        log(f"  Grid spacing: {GRID_SPACING_PCT}%")
        log(f"  Range: {RANGE_PCT}%")

        if not await self.connect():
            return

        # 初回セットアップ
        await self.setup_range()
        await self.place_grid_orders()

        self.state.running = True
        save_state(self.state)

        loop_count = 0

        while self.state.running:
            try:
                loop_count += 1

                ticker = self.client.fetch_ticker(SYMBOL)
                current_price = float(ticker['last_price'])

                # 定期ログ（5分ごと）
                if loop_count % 300 == 0:
                    log(f"Price: {current_price:.2f} | Range: {self.state.range_lower:.2f} - {self.state.range_upper:.2f} | Position: {self.state.position:.4f}")

                # レンジブレイクアウトチェック
                if await self.check_range_breakout(current_price):
                    await self.close_position("Range breakout")
                    # 新しいレンジに再設定
                    await self.setup_range()
                    await self.place_grid_orders()

                # ポジション更新（簡易版）
                positions = self.client.fetch_positions()
                for pos in positions:
                    if pos.get('instrument') == SYMBOL:
                        self.state.position = float(pos.get('size', 0))

                await asyncio.sleep(10)

            except Exception as e:
                log(f"Loop error: {e}")
                await asyncio.sleep(30)

        log("Bot stopped")


async def main():
    bot = SharkfinGridBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
