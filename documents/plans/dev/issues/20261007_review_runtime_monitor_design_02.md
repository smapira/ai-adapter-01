# Runtime Monitor 設計書レビュー: フェーズ P1–P4 が P5 の CLI 出力面に依存する内部矛盾

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§7 Phase P0–P5 の「期待する振る舞い」）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§25 Implementation Order）

## 指摘事項
設計書 §7 のフェーズ定義に、実装順序として成立しない依存が含まれる:

| フェーズ | 「入力」として指定された CLI | その出力面の完成フェーズ |
|---|---|---|
| P0 | `ai-adapter monitor`（「Canonical Model で出力する」） | 出力形式が未定義 |
| P1 | `ai-adapter monitor --json` | **P5**（--json 完成） |
| P2–P4 | `ai-adapter monitor`（デフォルト表モード） | **P5**（全出力モード完成） |
| P5 | 出力モード一式 | — |

P1–P4 の受入条件は「CLI を叩いて確認する」形で書かれているが、その入出力面は P5 まで完成しない。このまま実装すると P1–P4 の AC が P5 完了まで検証できず、BDD タスク分解としての意味を失う。上位仕様 §25 の順序（P0→P5）自体は正しいので、問題は設計書側の出力フェーズの置き方にある。

## 改善案
**推奨案 (a): 「最小出力パス」を P0 の完成条件に昇格させる。**
- P0 DoD に追加: Canonical Model → dict 変換（`dataclass.asdict` 相当、`runtime_session_to_dict()`）による最小 `--json` 出力と、1 行 1 セッションのプレーン出力を実装し、`ai-adapter monitor` / `--json` で目視・検証可能にする。
- P5 の責務を「残りの出力完成（AGE 表示付き整形テーブル・`--watch`・`--capabilities`・`--debug`・フラグ併用規則）」に限定して書き直す。
- コストは軽微（dataclass → dict は数行）。縦切り精神（いつでも目視確認できる状態を保つ）にも沿う。

**代替案 (b):** P1–P4 の AC を adapter / normalizer レベルの単体検証（fixture raw 入力 → `RuntimeSession` 出力のアサーション）に書き換え、CLI 入出力の検証を P5 に集約する。

いずれを採るにせよ、§7 の各フェーズの「入力」表記が P5 完成物に依存しない状態に修正すること。

## 備考
P0 AC3「discover() が返す Session は Canonical Model 形式」は adapter レベルの検証であり問題なし。崩れているのは P1–P4 の CLI 入力表記のみ。
