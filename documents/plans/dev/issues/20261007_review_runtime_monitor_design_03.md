# Runtime Monitor 設計書レビュー: JSON 出力契約が未確定（配列 vs {"sessions"}、値の大小、フラグ併用）

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§6.3 / §7 P5 AC2 / §2.3–§2.5 / §6.5）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§8 Canonical Model / §10 Confidence / §22 JSON Mode / §24 Debug Mode）
- 関連ファイル: `src/ai_adapter/commands/scan.py`（`--json` フラグ慣習）、`src/ai_adapter/cli.py`（グローバル logging 設定）

## 指摘事項
1. **JSON 形状が上位仕様と矛盾:** 上位仕様 §22 の JSON 例は `{"sessions": [ ... ]}` ラッパー形式。設計書 §7 P5 は「Canonical Model の **JSON 配列**を出力」と array 形式。上位仕様を正とするなら設計書側の修正が必要。
2. **値の大小表記が文書内で混在:**
   - 設計書 §2.4 / §2.5 の表: UPPERCASE（`WORKING` / `HIGH`）
   - 設計書 §2.3 コメントと P0 サンプルデータ: lowercase（`unknown` / `high`）
   - 上位仕様 §8 の JSON 例: lowercase（`"status": "working"`, `"confidence": "high"`）
   - 上位仕様 §10: uppercase（`HIGH` / `MEDIUM` / `LOW`）
   
   シリアライズ契約が未確定で、JSON 出力テスト（§8「JSON output」）の期待値を決められない。
3. **フラグ併用規則が未定義:** `--watch --json` でストリーム JSON を出すのか、`--debug` のログは stdout か stderr かが不明。`src/ai_adapter/cli.py` はグローバルに `logging.basicConfig(level=logging.INFO)` を設定しており、debug ログが stdout に出ると `--json | jq` パイプが壊れる。
4. 既存 CLI 慣習との対比: `scan` / `doctor` はどちらも `--json` フラグ + `as_json` パラメータ名で統一（`commands/scan.py:23`、`commands/doctor.py:24`）。フラグ名自体は整合しているが、パラメータ名・help 文言の慣習も設計書に記すと実装揺れが減る。

## 改善案
設計書 §6.3 にシリアライズ契約を明記する:

1. **出力形状:** 上位仕様 §22 準拠の `{"sessions": [...]}`（将来フィールド追加の余地も確保できる）。
2. **値の表記:** JSON シリアル化値はすべて lowercase（`status`: `working` / `waiting` / `blocked` / `done` / `idle` / `unknown`、`confidence`: `high` / `medium` / `low`）— 上位仕様 §8 の JSON 例に合わせる。Human-readable テーブルでのみ UPPERCASE 表示とし、大文字化は renderer の責務とする（`DISPLAY_LABELS` 等）。
3. **フラグ併用（PoC 契約）:**
   - `--watch` + `--json` / `--capabilities` → usage error（Click で明示的なエラーメッセージ）
   - `--debug` → 常に **stderr** へ出力。`--json` / `--watch` と併用可
4. **テスト追加:** §8 に「`--json` 出力の完全一致テスト（fixture sessions → expected dict）」を追加。値の大小が確定していないとこのテストは書けない。

## 備考
`--json` / `--watch` / `--capabilities` / `--debug` という単語フラグのスタイル自体は既存 CLI（`--fix` / `--dry-run` / `--force` / `--json`）と整合しており、問題は契約の中身のみ。上位仕様 §24 の debug 出力例（session / source / raw-status / normalized-status / confidence の行）は実装粒度として十分なので、§6.5 の一文からこの例へリンクすればよい。
