# Sharkfin Grid Bot - 仕様書

## 1. システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                     GRVT Exchange API                        │
│                    (pysdk/grvt_ccxt)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │ bot_sharkfin  │
                    │  メインボット  │
                    └───────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
   │ hot_reload.py │  │ order_guard.py│  │ simulate.py   │
   │ 自動再起動    │  │ 注文ガード    │  │ シミュレーション│
   └───────────────┘  └───────────────┘  └───────────────┘
```

---

## 2. メインボット (bot_sharkfin.py)

### 2.1 初期化

```python
class SharkfinGridBot:
    def __init__(self):
        self.client = None          # GRVT APIクライアント
        self.state = load_state()   # 状態読み込み
```

### 2.2 状態管理

```python
@dataclass
class SharkfinState:
    running: bool              # 稼働中フラグ
    range_center: float        # レンジ中心価格
    range_upper: float         # レンジ上限
    range_lower: float         # レンジ下限
    grid_levels: List[Dict]    # グリッドレベル
    active_orders: Dict        # アクティブ注文
    position: float            # 現在ポジション
    total_pnl: float           # 総損益
    trades: int                # 取引回数
```

---

## 3. グリッド計算

### 3.1 幾何学的グリッド

```python
def calculate_grid_levels(self, center_price: float) -> List[Dict]:
    """
    幾何学的間隔でグリッドレベルを計算
    
    Args:
        center_price: レンジ中心価格
    
    Returns:
        グリッドレベルのリスト
    """
    levels = []
    
    # 下方向（買い）
    for i in range(GRID_COUNT // 2):
        price = center_price * (1 - GRID_SPACING_PCT / 100) ** (i + 1)
        levels.append({
            'price': round(price, 2),
            'side': 'buy',
            'size': round(POSITION_SIZE_USD / price, 4),
        })
    
    # 上方向（売り）
    for i in range(GRID_COUNT // 2):
        price = center_price * (1 + GRID_SPACING_PCT / 100) ** (i + 1)
        levels.append({
            'price': round(price, 2),
            'side': 'sell',
            'size': round(POSITION_SIZE_USD / price, 4),
        })
    
    return sorted(levels, key=lambda x: x['price'])
```

### 3.2 グリッド例（BTC $67,000）

| レベル | 価格 | 偏差 | サイド |
|--------|------|------|--------|
| 1 | $66,966.50 | -0.05% | BUY |
| 2 | $66,933.01 | -0.10% | BUY |
| ... | ... | ... | ... |
| 20 | $66,333.39 | -1.0% | BUY |
| 21 | $67,033.50 | +0.05% | SELL |
| ... | ... | ... | ... |
| 40 | $67,670.00 | +1.0% | SELL |

---

## 4. 注文実行

### 4.1 LIMIT_MAKER注文

```python
async def place_grid_orders(self):
    """
    グリッド注文を配置（LIMIT_MAKER）
    
    注文タイプ: limit
    パラメータ: {'post_only': True}
    """
    for level in self.state.grid_levels:
        order = self.client.create_order(
            symbol=SYMBOL,
            order_type='limit',
            side=level['side'],
            amount=level['size'],
            price=level['price'],
            params={'post_only': True}  # LIMIT_MAKER
        )
```

### 4.2 逆注文配置

```python
async def place_opposite_order(self, filled_side: str, filled_price: float, filled_size: float):
    """
    約定後の逆注文を配置
    
    買い約定 → 売り指値（価格×1.001）
    売り約定 → 買い指値（価格×0.999）
    """
    opposite_side = 'sell' if filled_side == 'buy' else 'buy'
    
    if opposite_side == 'sell':
        new_price = filled_price * (1 + GRID_SPACING_PCT / 100)
    else:
        new_price = filled_price * (1 - GRID_SPACING_PCT / 100)
    
    self.client.create_order(
        symbol=SYMBOL,
        order_type='limit',
        side=opposite_side,
        amount=new_size,
        price=new_price,
        params={'post_only': True}
    )
```

---

## 5. リスク管理

### 5.1 ストップロス

```python
async def place_stop_loss(self):
    """
    ストップロス注文（LIMIT）
    
    価格: レンジ下限 × (1 - STOP_LOSS_PCT%)
    """
    stop_price = self.state.range_lower * (1 - STOP_LOSS_PCT / 100)
    
    self.client.create_order(
        symbol=SYMBOL,
        order_type='limit',
        side='sell',
        amount=abs(self.state.position),
        price=stop_price,
        params={'post_only': False}  # 即座に約定させる
    )
```

### 5.2 レンジブレイクアウト

```python
async def check_range_breakout(self, current_price: float) -> bool:
    """
    レンジブレイクアウト検出
    
    条件:
    - 価格 > レンジ上限
    - 価格 < レンジ下限
    
    アクション:
    - 全ポジション決済
    - 新しいレンジに再設定
    """
    if current_price > self.state.range_upper:
        return True
    if current_price < self.state.range_lower:
        return True
    return False
```

---

## 6. 設定パラメータ

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `SYMBOL` | BTC_USDT_Perp | 取引ペア |
| `GRID_COUNT` | 40 | グリッドレベル数 |
| `GRID_SPACING_PCT` | 0.05 | グリッド間隔（%） |
| `RANGE_PCT` | 1.0 | レンジ幅（%） |
| `POSITION_SIZE_USD` | 25 | 1レベルあたりのサイズ（$） |
| `STOP_LOSS_PCT` | 1.5 | ストップロス（%） |
| `maker_fee` | 0.0002 | メーカー手数料（%） |

---

## 7. ログ

### 7.1 ログファイル

```
sharkfin.log
```

### 7.2 ログ形式

```
2026-04-04 17:35:10 | Sharkfin Grid Bot started
2026-04-04 17:35:10 | Symbol: BTC_USDT_Perp
2026-04-04 17:35:10 | Grid count: 40
2026-04-04 17:35:10 | Grid spacing: 0.05%
2026-04-04 17:35:11 | Connected to GRVT
2026-04-04 17:35:12 | Range setup: 66333.39 - 67670.00
2026-04-04 17:35:12 | Placed buy order: 0.0004 @ 66966.50
...
```

---

## 8. 環境変数

```bash
# .envファイル
GRVT_API_KEY=your_api_key
GRVT_API_SECRET=your_secret
GRVT_TRADING_ACCOUNT_ID=your_account_id
```

---

## 9. 実行方法

### 9.1 通常起動

```bash
python bot_sharkfin.py
```

### 9.2 ホットリロード付き

```bash
python hot_reload.py bot_sharkfin.py
```

---

## 10. トラブルシューティング

| 問題 | 原因 | 対処 |
|------|------|------|
| 注文が約定しない | Post-Only拒否 | 価格を調整 |
| レンジブレイク | 価格変動 | 自動決済・再設定 |
| 接続エラー | API障害 | 自動再接続 |

---

## 11. 変更履歴

| 日付 | バージョン | 変更内容 |
|------|----------|---------|
| 2026-04-04 | 1.0 | 初版 |
