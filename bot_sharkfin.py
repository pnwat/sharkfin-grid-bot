# -*- coding: utf-8 -*-
"""
シャークフィン/レンジグリッドボット（積極的設定）
"""
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List
from dataclasses import dataclass, asdict

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv
from dotenv import load_dotenv

load_dotenv()

# レート制限準拠設定
SYMBOL = "BTC_USDT_Perp"
GRID_COUNT = 40              # Tier 3相当
GRID_SPACING_PCT = 0.03      # 間隔狭める
RANGE_PCT = 0.5              # レンジ狭める
POSITION_SIZE_USD = 150
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
    active_orders: Dict = None
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
    def __init__(self):
        self.client = None
        self.state = load_state()

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

    async def cancel_all_orders(self):
        """全注文キャンセル"""
        log("Cancelling all orders...")
        try:
            orders = self.client.fetch_open_orders()
            for o in orders:
                try:
                    self.client.cancel_order(o.get('order_id'), SYMBOL)
                    await asyncio.sleep(0.1)  # レート制限対策
                except:
                    pass
            log(f"Cancelled {len(orders)} orders")
        except Exception as e:
            log(f"Cancel error: {e}")

    async def setup_range(self):
        """レンジ設定"""
        ticker = self.client.fetch_ticker(SYMBOL)
        current_price = float(ticker['last_price'])

        half_range = current_price * (RANGE_PCT / 100 / 2)
        self.state.range_center = current_price
        self.state.range_upper = current_price + half_range
        self.state.range_lower = current_price - half_range

        log(f"Range: ${self.state.range_lower:.0f} - ${self.state.range_upper:.0f}")
        log(f"Center: ${current_price:.0f}, Spread: {GRID_SPACING_PCT}%")

        # グリッド生成
        self.state.grid_levels = []
        for i in range(GRID_COUNT):
            if i < GRID_COUNT // 2:
                price = self.state.range_lower + (self.state.range_center - self.state.range_lower) * (i / (GRID_COUNT // 2))
                side = 'buy'
            else:
                price = self.state.range_center + (self.state.range_upper - self.state.range_center) * ((i - GRID_COUNT // 2) / (GRID_COUNT // 2))
                side = 'sell'

            raw_size = POSITION_SIZE_USD / price
            size = max(0.001, round(raw_size, 3))

            self.state.grid_levels.append({
                'price': round(price),
                'side': side,
                'size': size,
                'filled': False
            })

        log(f"Grid levels: {len(self.state.grid_levels)}")

    async def place_grid_orders(self):
        """グリッド注文配置（レート制限対策付き）"""
        log("Placing grid orders...")
        
        placed = 0
        for level in self.state.grid_levels:
            if level['filled']:
                continue

            try:
                order = self.client.create_order(
                    symbol=SYMBOL,
                    order_type='limit',
                    side=level['side'],
                    amount=level['size'],
                    price=level['price'],
                    params={'post_only': True}
                )
                order_id = order.get('order_id') or order.get('id')
                self.state.active_orders[str(level['price'])] = order_id
                placed += 1
                await asyncio.sleep(0.5)  # レート制限対策：0.5秒ウェイト
            except Exception as e:
                log(f"Order error @ ${level['price']}: {e}")
                await asyncio.sleep(1)  # エラー時は1秒待つ

        log(f"Placed {placed} orders")

    async def check_fills(self):
        """約定確認（効率化：fetch_open_orders使用）"""
        try:
            # 全オープン注文を一括取得（1リクエストのみ）
            open_orders = self.client.fetch_open_orders()
            open_order_ids = {o.get('order_id') for o in open_orders if 'BTC' in str(o.get('legs', [{}])[0].get('instrument', ''))}
        except Exception as e:
            log(f"Fetch orders error: {e}")
            return
        
        # 約定した注文を特定
        for level in self.state.grid_levels[:]:
            if level['filled']:
                continue

            price_key = str(level['price'])
            if price_key not in self.state.active_orders:
                continue

            order_id = self.state.active_orders[price_key]
            
            # オープン注文にない = 約定
            if order_id not in open_order_ids:
                level['filled'] = True
                del self.state.active_orders[price_key]

                # 反対注文
                opposite_side = 'sell' if level['side'] == 'buy' else 'buy'
                target_price = level['price'] * (1 + GRID_SPACING_PCT / 100) if level['side'] == 'buy' else level['price'] * (1 - GRID_SPACING_PCT / 100)

                try:
                    self.client.create_order(
                        symbol=SYMBOL,
                        order_type='limit',
                        side=opposite_side,
                        amount=level['size'],
                        price=round(target_price),
                        params={'post_only': True}
                    )
                    log(f"FILLED {level['side']} @ ${level['price']:.0f} -> {opposite_side} @ ${target_price:.0f}")
                    self.state.trades += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    log(f"Opposite order error: {e}")

    async def check_stop_loss(self):
        """ストップロス（発動後は待機して再起動）"""
        ticker = self.client.fetch_ticker(SYMBOL)
        current_price = float(ticker['last_price'])

        stop_price = self.state.range_lower * (1 - STOP_LOSS_PCT / 100)

        if current_price < stop_price:
            log(f"STOP LOSS @ ${current_price:.0f}")
            await self.emergency_close()
            
            # 5分待機してから再起動
            log("Waiting 5 minutes before restart...")
            await asyncio.sleep(300)
            
            # 新しいレンジで再開
            await self.setup_range()
            await self.place_grid_orders()
            log(f"Restarted with new range: ${self.state.range_lower:.0f}-${self.state.range_upper:.0f}")
            
        return False  # 継続

    async def close_all_positions(self):
        """全ポジション決済（レンジ追従用）"""
        try:
            positions = self.client.fetch_positions()
            for pos in positions:
                size = float(pos.get('size', 0))
                if abs(size) > 0.0001 and 'BTC' in pos.get('instrument', ''):
                    side = 'sell' if size > 0 else 'buy'
                    try:
                        self.client.create_order(
                            symbol=SYMBOL,
                            order_type='market',
                            side=side,
                            amount=abs(size)
                        )
                        log(f"Closed position: {side} {abs(size):.6f}")
                    except Exception as e:
                        log(f"Close error: {e}")
        except Exception as e:
            log(f"Position fetch error: {e}")

    async def emergency_close(self):
        """緊急決済"""
        log("Emergency close...")
        
        try:
            orders = self.client.fetch_open_orders()
            for o in orders:
                try:
                    self.client.cancel_order(o.get('order_id'), SYMBOL)
                except:
                    pass
        except:
            pass

        try:
            positions = self.client.fetch_positions()
            for pos in positions:
                size = float(pos.get('size', 0))
                if abs(size) > 0.0001:
                    side = 'sell' if size > 0 else 'buy'
                    try:
                        self.client.create_order(
                            symbol=SYMBOL,
                            order_type='market',
                            side=side,
                            amount=abs(size)
                        )
                        log(f"Emergency closed: {side} {abs(size):.6f}")
                    except Exception as e:
                        log(f"Emergency close error: {e}")
        except Exception as e:
            log(f"Position fetch error: {e}")

        # ボットは停止しない（再起動可能にする）
        log("Emergency close completed, ready to restart")

    async def run(self):
        """メインループ"""
        log("=== Sharkfin Bot (Aggressive) ===")
        log(f"Symbol: {SYMBOL}")
        log(f"Grid: {GRID_COUNT} levels, {GRID_SPACING_PCT}% spacing")
        log(f"Range: {RANGE_PCT}%")

        if not await self.connect():
            return

        # 既存注文キャンセル
        await self.cancel_all_orders()
        await asyncio.sleep(2)

        # レンジ設定＆注文配置
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

                # 定期ログ（10分ごと）
                if loop_count % 60 == 0:  # 10秒 * 60 = 10分
                    log(f"Price: ${current_price:.0f} | Range: ${self.state.range_lower:.0f}-${self.state.range_upper:.0f} | Trades: {self.state.trades}")

                # レンジ追従：価格がレンジ外に出たら再設定
                if current_price > self.state.range_upper or current_price < self.state.range_lower:
                    log(f"Range breakout! Price ${current_price:.0f} outside range")
                    
                    # 全ポジション決済
                    await self.close_all_positions()
                    
                    # 注文キャンセル
                    await self.cancel_all_orders()
                    await asyncio.sleep(2)
                    
                    # 新しいレンジ設定
                    await self.setup_range()
                    await self.place_grid_orders()
                    log(f"New range: ${self.state.range_lower:.0f}-${self.state.range_upper:.0f}")
                    continue

                # 約定確認
                await self.check_fills()

                # ストップロス
                if await self.check_stop_loss():
                    break

                # 状態保存（1分ごと）
                if loop_count % 6 == 0:  # 10秒 * 6 = 1分
                    save_state(self.state)

            except Exception as e:
                log(f"Loop error: {e}")

            await asyncio.sleep(10)  # レート制限対策：10秒間隔

        log("Bot stopped")


async def main():
    bot = SharkfinGridBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
