# -*- coding: utf-8 -*-
"""
Trend-Following Long-Only Grid Bot
トレンドフォロー型ロンググリッドボット

特徴:
- Long-Only（ショートなし）
- SMA(15/50)でトレンド判定
- ATRベースの動的グリッド間隔
- 非対称テイクプロフィット
- トレーリングストップ
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path

from pysdk.grvt_ccxt import GrvtCcxt
from pysdk.grvt_ccxt_env import GrvtEnv
from dotenv import load_dotenv

load_dotenv()

# === 設定（最適化済みパラメータ）===
SYMBOL = "BTC_USDT_Perp"
TIMEFRAME = "5m"

# トレンド設定（最適化済み）
SMA_FAST = 15
SMA_SLOW = 50

# ATR設定（最適化済み）
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.0  # グリッド間隔係数
MIN_SPACING_PCT = 0.5
MAX_SPACING_PCT = 2.0

# グリッド設定（最適化済み）
GRID_COUNT = 12
RANGE_DOWN_PCT = 10.0  # 下方範囲（押し目買い）
RANGE_UP_PCT = 14.0    # 上方範囲（利確エリア）

# ポジション設定
TOTAL_INVESTMENT_PCT = 10.0  # 口座残高の10%を使用
MAX_POSITION_PCT = 50.0      # 総投資額の50%が最大ポジション

# リスク管理（最適化済み）
STOP_LOSS_ATR_MULT = 2.0
TRAILING_TRIGGER_PCT = 5.0
TRAILING_ATR_MULT = 1.5

# 手数料
MAKER_FEE = -0.0002  # リベート
TAKER_FEE = 0.00045

# ファイル
STATE_FILE = "trend_grid_state.json"
LOG_FILE = "trend_grid.log"
PRICE_HISTORY_FILE = "price_history.json"

# 環境変数
GRVT_API_KEY = os.getenv("GRVT_API_KEY")
GRVT_API_SECRET = os.getenv("GRVT_API_SECRET")


@dataclass
class GridLevel:
    price: float
    size: float
    side: str = "buy"
    filled: bool = False
    order_id: Optional[str] = None


@dataclass
class Position:
    size: float = 0.0
    avg_price: float = 0.0
    stop_loss: float = 0.0
    trailing_active: bool = False
    trailing_stop: float = 0.0
    max_profit_price: float = 0.0


@dataclass
class TrendGridState:
    running: bool = False
    trend: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    current_price: float = 0.0
    atr: float = 0.0
    sma_fast: float = 0.0
    sma_slow: float = 0.0
    grid_levels: List[Dict] = field(default_factory=list)
    active_orders: Dict = field(default_factory=dict)
    position: Dict = field(default_factory=dict)
    total_pnl: float = 0.0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    daily_pnl: float = 0.0
    last_reset_date: str = ""


def log(msg: str):
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} | {msg}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {msg}\n")
    except:
        pass


def load_state() -> TrendGridState:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return TrendGridState(**data)
        except:
            pass
    return TrendGridState()


def save_state(state: TrendGridState):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, ensure_ascii=False, indent=2)
    except:
        pass


class TrendGridBot:
    def __init__(self, dry_run: bool = False):
        self.client = None
        self.state = load_state()
        self.dry_run = dry_run
        self.price_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        self.close_history: List[float] = []

    async def connect(self) -> bool:
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

    def calculate_sma(self, prices: List[float], period: int) -> float:
        """SMA計算"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period

    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = ATR_PERIOD) -> float:
        """ATR計算"""
        if len(closes) < period + 1:
            return closes[-1] * 0.01 if closes else 100  # デフォルト1%
        
        trs = []
        for i in range(1, min(len(closes), period + 50)):
            idx = len(closes) - i
            if idx <= 0:
                break
            tr = max(
                highs[idx] - lows[idx],
                abs(highs[idx] - closes[idx-1]),
                abs(lows[idx] - closes[idx-1])
            )
            trs.append(tr)
        
        return sum(trs[-period:]) / period if trs else 100

    def detect_trend(self) -> str:
        """トレンド判定"""
        sma_fast = self.calculate_sma(self.close_history, SMA_FAST)
        sma_slow = self.calculate_sma(self.close_history, SMA_SLOW)
        
        self.state.sma_fast = sma_fast
        self.state.sma_slow = sma_slow
        
        # デバッグログ
        if len(self.close_history) > 0:
            log(f"Close history sample: first={self.close_history[0]:.2f}, last={self.close_history[-1]:.2f}")
        log(f"SMA calculation: history_len={len(self.close_history)}, SMA{SMA_FAST}={sma_fast:.2f}, SMA{SMA_SLOW}={sma_slow:.2f}")
        
        if sma_fast > sma_slow:
            return "BULLISH"
        elif sma_fast < sma_slow:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def generate_grid_levels(self, current_price: float, atr: float) -> List[GridLevel]:
        """グリッドレベル生成（下方に集中）"""
        # ATRベースの動的間隔
        atr_pct = (atr / current_price) * 100
        spacing_pct = atr_pct * ATR_MULTIPLIER
        spacing_pct = max(MIN_SPACING_PCT, min(MAX_SPACING_PCT, spacing_pct))
        
        # 価格範囲
        min_price = current_price * (1 - RANGE_DOWN_PCT / 100)
        max_price = current_price * (1 + RANGE_UP_PCT / 100)
        
        # ポジションサイズ計算（口座残高ベース）
        position_per_grid = 0.001  # デフォルト
        if self.client and not self.dry_run:
            try:
                balance = self.client.fetch_balance()
                total_usdt = float(balance.get('total', {}).get('USDT', 0))
                investment = total_usdt * TOTAL_INVESTMENT_PCT / 100
                position_per_grid = (investment / GRID_COUNT) / current_price
                position_per_grid = max(0.001, round(position_per_grid, 4))
            except:
                pass
        
        # 非対称グリッド（下方に集中）
        levels = []
        for i in range(GRID_COUNT):
            # 下方に多く配置（押し目買い重視）
            weight = i / (GRID_COUNT - 1)  # 0 to 1
            price_weight = weight ** 1.5  # 上方に伸ばすカーブ
            price = min_price + (max_price - min_price) * price_weight
            
            levels.append(GridLevel(
                price=round(price, 2),
                size=position_per_grid,
                side='buy' if price < current_price else 'sell',
                filled=False
            ))
        
        return sorted(levels, key=lambda x: x.price)

    async def cancel_all_orders(self):
        """全注文キャンセル"""
        log("Cancelling all orders...")
        try:
            orders = self.client.fetch_open_orders()
            for o in orders:
                try:
                    self.client.cancel_order(o.get('order_id'), SYMBOL)
                    await asyncio.sleep(0.1)
                except:
                    pass
            log(f"Cancelled {len(orders)} orders")
        except Exception as e:
            log(f"Cancel error: {e}")

    async def close_all_positions(self):
        """全ポジション決済"""
        log("Closing all positions...")
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
                        log(f"Closed: {side} {abs(size):.6f}")
                    except Exception as e:
                        log(f"Close error: {e}")
        except Exception as e:
            log(f"Position fetch error: {e}")

    async def place_grid_orders(self):
        """グリッド注文配置"""
        log("Placing grid orders...")
        
        # 現在の買いグリッドのみ配置
        placed = 0
        for level in self.state.grid_levels:
            if level.get('filled', False) or level.get('side') != 'buy':
                continue
            
            price = level['price']
            size = level['size']
            
            # DRY RUN: 注文せずにログのみ
            if self.dry_run:
                log(f"[DRY] BUY order @ ${price:.2f} ({size:.6f} BTC)")
                placed += 1
                continue
            
            try:
                # メーカー注文（best_bid - $1）
                ticker = self.client.fetch_ticker(SYMBOL)
                best_bid = float(ticker.get('best_bid_price', price))
                maker_price = min(price, best_bid - 1)
                
                order = self.client.create_order(
                    symbol=SYMBOL,
                    order_type='limit',
                    side='buy',
                    amount=size,
                    price=round(maker_price, 2),
                    params={'post_only': True}
                )
                order_id = order.get('order_id') or order.get('id')
                level['order_id'] = order_id
                self.state.active_orders[str(price)] = order_id
                placed += 1
                log(f"BUY order @ ${maker_price:.2f} ({size:.6f} BTC)")
                await asyncio.sleep(0.5)  # レート制限
                
            except Exception as e:
                log(f"Order error @ ${price}: {e}")
                await asyncio.sleep(1)
        
        log(f"Placed {placed} buy orders")

    async def check_fills(self):
        """約定確認"""
        # DRY RUN: 注文確認をスキップ
        if self.dry_run:
            return
        
        try:
            open_orders = self.client.fetch_open_orders()
            open_prices = set()
            for o in open_orders:
                legs = o.get('legs', [])
                if legs:
                    price = legs[0].get('limit_price')
                    if price:
                        open_prices.add(round(float(price), 2))
        except Exception as e:
            log(f"Fetch orders error: {e}")
            return
        
        # 約定判定
        for level in self.state.grid_levels:
            if level.get('filled', False) or level.get('side') != 'buy':
                continue
            
            price = level['price']
            order_id = level.get('order_id')
            
            if not order_id:
                continue
            
            # 価格がオープン注文にない = 約定
            if round(price, 2) not in open_prices:
                level['filled'] = True
                self.state.trades += 1
                
                # ポジション更新
                pos = self.state.position
                current_size = pos.get('size', 0)
                current_avg = pos.get('avg_price', 0)
                
                new_size = current_size + level['size']
                new_avg = (current_avg * current_size + price * level['size']) / new_size if new_size > 0 else price
                
                pos['size'] = new_size
                pos['avg_price'] = new_avg
                pos['stop_loss'] = new_avg - self.state.atr * STOP_LOSS_ATR_MULT
                self.state.position = pos
                
                log(f"FILLED BUY @ ${price:.2f} | Position: {new_size:.6f} @ ${new_avg:.2f}")
                
                # 利確注文配置（非対称TP）
                await self.place_take_profit_orders(level['size'], price)

    async def place_take_profit_orders(self, size: float, entry_price: float):
        """利確注文（非対称TP）"""
        atr = self.state.atr
        
        # 50%は近い価格で利確
        tp_near_size = size * 0.5
        tp_near_price = entry_price * (1 + atr * 0.5 / entry_price)
        
        # 50%は高い価格で利確
        tp_far_size = size * 0.5
        tp_far_price = entry_price * (1 + atr * 2.0 / entry_price)
        
        ticker = self.client.fetch_ticker(SYMBOL)
        best_ask = float(ticker.get('best_ask_price', entry_price))
        
        # メーカー注文（best_ask + $1）
        for tp_size, tp_price in [(tp_near_size, tp_near_price), (tp_far_size, tp_far_price)]:
            maker_price = max(tp_price, best_ask + 1)
            
            try:
                order = self.client.create_order(
                    symbol=SYMBOL,
                    order_type='limit',
                    side='sell',
                    amount=tp_size,
                    price=round(maker_price, 2),
                    params={'post_only': True}
                )
                log(f"TP SELL @ ${maker_price:.2f} ({tp_size:.6f} BTC)")
                await asyncio.sleep(0.5)
            except Exception as e:
                log(f"TP order error: {e}")

    async def check_trailing_stop(self):
        """トレーリングストップ判定"""
        pos = self.state.position
        if pos.get('size', 0) <= 0:
            return
        
        current_price = self.state.current_price
        avg_price = pos.get('avg_price', 0)
        
        if avg_price <= 0:
            return
        
        profit_pct = (current_price - avg_price) / avg_price * 100
        
        # トレーリング開始判定
        if profit_pct > TRAILING_TRIGGER_PCT:
            if not pos.get('trailing_active', False):
                pos['trailing_active'] = True
                log(f"Trailing stop activated at {profit_pct:.1f}% profit")
            
            # 最高価格更新
            max_price = pos.get('max_profit_price', current_price)
            if current_price > max_price:
                pos['max_profit_price'] = current_price
            
            # トレーリングストップ価格
            pos['trailing_stop'] = pos['max_profit_price'] - self.state.atr * TRAILING_ATR_MULT
        
        self.state.position = pos
        
        # トレーリングストップ発動
        if pos.get('trailing_active', False) and current_price < pos.get('trailing_stop', 0):
            log(f"TRAILING STOP triggered @ ${current_price:.2f}")
            await self.close_all_positions()
            await self.cancel_all_orders()
            
            # グリッド再設定
            await self.setup_grid()
            
            # PnL記録
            pnl = (current_price - avg_price) * pos['size']
            self.state.total_pnl += pnl
            self.state.wins += 1

    async def check_stop_loss(self):
        """ストップロス判定"""
        pos = self.state.position
        if pos.get('size', 0) <= 0:
            return False
        
        current_price = self.state.current_price
        stop_loss = pos.get('stop_loss', 0)
        
        if stop_loss <= 0:
            return False
        
        if current_price < stop_loss:
            log(f"STOP LOSS @ ${current_price:.2f}")
            await self.close_all_positions()
            await self.cancel_all_orders()
            
            # グリッド再設定
            await self.setup_grid()
            
            # 損失記録
            avg_price = pos.get('avg_price', 0)
            pnl = (current_price - avg_price) * pos['size']
            self.state.total_pnl += pnl
            self.state.losses += 1
            
            return True
        
        return False

    async def update_price_history(self):
        """価格履歴更新"""
        try:
            # OHLCV取得（GRVT形式に対応）
            response = self.client.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
            
            # GRVT APIは辞書形式で返す
            if isinstance(response, dict) and 'result' in response:
                candles = response['result']
            else:
                candles = response
            
            # 履歴をクリアして再構築（重複防止）
            self.close_history = []
            self.high_history = []
            self.low_history = []
            
            # GRVT APIは降順（新しい順）で返す
            # 最新50本を使用（先頭から50個）、その後昇順（古い順）に並べ替え
            recent_candles = candles[:50] if len(candles) >= 50 else candles
            # 昇順に並べ替え（古い順）- SMA計算のため
            recent_candles = list(reversed(recent_candles))
            
            for candle in recent_candles:
                # GRVT形式: {'open': '68364.0', 'high': '68400.0', 'low': '68326.0', 'close': '68326.1', ...}
                if isinstance(candle, dict):
                    self.close_history.append(float(candle['close']))
                    self.high_history.append(float(candle['high']))
                    self.low_history.append(float(candle['low']))
                else:
                    # 標準CCXT形式: [timestamp, open, high, low, close, volume]
                    self.close_history.append(float(candle[4]))
                    self.high_history.append(float(candle[2]))
                    self.low_history.append(float(candle[3]))
            
            # 現在価格
            ticker = self.client.fetch_ticker(SYMBOL)
            self.state.current_price = float(ticker['last_price'])
            
            # ATR計算
            self.state.atr = self.calculate_atr(self.high_history, self.low_history, self.close_history)
            
        except Exception as e:
            log(f"Price history error: {e}")

    async def setup_grid(self):
        """グリッド設定"""
        current_price = self.state.current_price
        atr = self.state.atr
        
        if current_price <= 0 or atr <= 0:
            return
        
        # グリッド生成
        grid_levels = self.generate_grid_levels(current_price, atr)
        self.state.grid_levels = [asdict(l) for l in grid_levels]
        
        # ポジションリセット
        self.state.position = {
            'size': 0,
            'avg_price': 0,
            'stop_loss': 0,
            'trailing_active': False,
            'trailing_stop': 0,
            'max_profit_price': 0
        }
        
        log(f"Grid setup: {len(grid_levels)} levels @ ${current_price:.2f}")
        log(f"ATR: ${atr:.2f} | SMA15: ${self.state.sma_fast:.2f} | SMA50: ${self.state.sma_slow:.2f}")

    async def handle_trend_change(self, new_trend: str):
        """トレンド転換処理"""
        old_trend = self.state.trend
        
        if old_trend == new_trend:
            return
        
        log(f"TREND CHANGE: {old_trend} -> {new_trend}")
        self.state.trend = new_trend
        
        if new_trend == "BEARISH":
            # 全ポジション決済
            log("Bearish trend - closing all positions")
            await self.close_all_positions()
            await self.cancel_all_orders()
            
            # グリッドクリア
            self.state.grid_levels = []
            
        elif new_trend == "BULLISH":
            # グリッド設定
            log("Bullish trend - setting up grid")
            await self.setup_grid()
            await self.place_grid_orders()

    async def run(self):
        """メインループ"""
        log("=== Trend Grid Bot Started ===")
        log(f"Symbol: {SYMBOL}")
        log(f"Grid: {GRID_COUNT} levels")
        log(f"Trend: SMA{SMA_FAST}/{SMA_SLOW}")
        log(f"ATR multiplier: {ATR_MULTIPLIER}")
        log(f"Stop loss: {STOP_LOSS_ATR_MULT}x ATR")
        log(f"Trailing: {TRAILING_TRIGGER_PCT}% trigger, {TRAILING_ATR_MULT}x ATR")
        
        if self.dry_run:
            log("DRY RUN MODE")
        
        if not await self.connect():
            return
        
        # 初期化
        await self.update_price_history()
        
        # トレンド判定
        trend = self.detect_trend()
        self.state.trend = trend
        
        if trend == "BULLISH":
            await self.setup_grid()
            await self.place_grid_orders()
        else:
            log(f"Current trend: {trend} - waiting for bullish trend")
        
        self.state.running = True
        save_state(self.state)
        
        loop_count = 0
        
        while self.state.running:
            try:
                loop_count += 1
                
                # 価格更新（5分ごと）
                if loop_count % 30 == 0:  # 10秒 * 30 = 5分
                    await self.update_price_history()
                    
                    # トレンド判定
                    new_trend = self.detect_trend()
                    await self.handle_trend_change(new_trend)
                
                # トレンド上昇中のみ取引
                if self.state.trend != "BULLISH":
                    await asyncio.sleep(10)
                    continue
                
                # 約定確認
                await self.check_fills()
                
                # トレーリングストップ
                await self.check_trailing_stop()
                
                # ストップロス
                await self.check_stop_loss()
                
                # 定期ログ（10分ごと）
                if loop_count % 60 == 0:
                    pos = self.state.position
                    log(f"Price: ${self.state.current_price:.2f} | Trend: {self.state.trend} | "
                        f"Position: {pos.get('size', 0):.6f} @ ${pos.get('avg_price', 0):.2f} | "
                        f"Trades: {self.state.trades} | PnL: ${self.state.total_pnl:.2f}")
                
                # 状態保存（1分ごと）
                if loop_count % 6 == 0:
                    save_state(self.state)
                
            except Exception as e:
                log(f"Loop error: {e}")
            
            await asyncio.sleep(10)
        
        log("Bot stopped")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    args = parser.parse_args()
    
    bot = TrendGridBot(dry_run=args.dry_run)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
