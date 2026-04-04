# Sharkfin Grid Bot

**指値のみ（LIMIT_MAKER）で運用するレンジグリッドトレーディングボット**

---

## 概要

シャークフィン戦略は、明確な価格レンジ内で細かくグリッド注文を配置し、価格が上下するたびに利益を確定する戦略です。

**特徴:**
- 成行注文は一切使用しない（手数料削減）
- 高頻度でスプレッド収穫
- レンジブレイク時は自動退出

---

## 期待収益

| 期間 | 金額 |
|------|------|
| 日次 | +$0.40-$0.66 |
| 月次 | +$12-$20 |
| 年次 | +$144-$240 |

---

## パラメータ（BTC/USDT最適値）

| パラメータ | 値 |
|-----------|-----|
| ペア | BTC/USDT |
| レベル数 | 40 |
| グリッド間隔 | 0.05% |
| レンジ幅 | 1.0% |
| ポジションサイズ | $25/レベル |
| 利確目標 | 0.15%-0.25% |
| 手数料 | 0.02%（メーカー） |

---

## セットアップ

```bash
# クローン
git clone https://github.com/pnwat/sharkfin-grid-bot
cd sharkfin-grid-bot

# 依存関係
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env
# .envを編集してAPIキーを設定

# 実行
python bot_sharkfin.py
```

---

## ファイル構成

```
sharkfin-grid-bot/
├── bot_sharkfin.py       # メインボット
├── hot_reload.py         # ホットリロード機能
├── order_guard.py        # 注文ガード
├── simulate_btc_grid.py  # シミュレーション
├── SPEC.md               # 仕様書
├── README.md             # 本ファイル
└── requirements.txt      # 依存関係
```

---

## リスク

- レンジブレイク時の損失
- ボラティリティ急増時のスリッページ
- API接続断絶

**最大損失想定: -$15**

---

## ライセンス

MIT

---

## 参考

- NotebookLMリサーチ: 83ソース（グリッド戦略）
- NotebookLMリサーチ: 68ソース（最適パラメータ）
