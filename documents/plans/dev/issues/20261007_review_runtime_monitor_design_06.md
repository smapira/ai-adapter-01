# Runtime Monitor 設計書レビュー: Event Model（仕様 §19 / 設計書 §5）が実装計画に接続されていない

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§5 lines 232-244 / §6.2 / §7 P0–P5 / §8 / §13）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§19 Event Model / §21 Watch Mode）

## 指摘事項
1. **設計書 §5 はイベント名の羅列のみ:** `SESSION_DISCOVERED` / `AGENT_WORKING` / ... / `SESSION_ENDED` の名前リストと「Host 固有 Event 名を Core へ漏らさない」の 1 行のみ。イベントを保持する dataclass、host イベント名 → canonical イベント名のマッピング表、生成元、消費元が定義されていない。
2. **実装計画のどこにも載っていない:** 変更対象ファイル（§13）に events 系モジュールはなく、フェーズ（§7 P0–P5）のどこでもイベント正規化を納品せず、テスト計画（§8）にもイベントテストがない。モデル（`RuntimeSession`）にイベントフィールドもない。この状態で実装すると §5 は死にコードになる。
3. **消費元が未設計:** 唯一の消費シーンである §6.2「Semantic Event を取得できる場合は即時反映可」も、イベントを誰がどう受け取るか（Orca hooks が書くファイルを tail するのか、CLI ポーリングに留まるのか）が書かれていない。

## 改善案
2 案を提示し、Product Manager の決定を仰ぐ:

**案 A（推奨・軽量実装）— PoC スコープ内に最小イベント系を組み込む:**
- `RuntimeEvent` dataclass を `models.py` に追加（`event_type` / `session_id` / `host` / `source` / `confidence` / `timestamp`）
- 各 adapter に `EVENT_MAP`（host 固有イベント名 → §5 の canonical 名）
- semantic ソースがイベントを提供した場合のみ normalizer が発行（ポーリングだけで完結する session には無理にイベントを生成しない）
- 消費元は 2 つに限定: `--debug` 出力（イベント履歴）と watcher の即時リフレッシュ（ポーリング間の早期更新）
- §8 に「Event normalization table」テストを追加
- トランスポート（hook ファイル監視等）は Post-PoC と明記

**案 B（厳格スコープ）— §5 を Non-Goals へ移動:**
- §5 と §6.2 の「即時反映」文言を §12 Non-Goals へ移し、「スナップショット監視で PoC 成否判定に十分。イベント正規化は Post-PoC。§19 の語彙は将来の正規化目標として保持」と明記
- watcher は 1-3 秒ポーリングのみに統一

いずれの場合も、現状の「§5 は文書にあるが計画に載らない」状態を解消すること。

## 備考
上位仕様 §19 は「**可能な限り**以下へ正規化する」と任意表現であり、PoC 成功判定（上位仕様 §5 PoC Success Criteria）にイベントは含まれない。したがって案 B は上位仕様違反とはならない。案 A のコストも dataclass 1 個 + マッピング表 + テスト 1 本程度で、§6.2 の即時反映を保つなら案 A が自然。
