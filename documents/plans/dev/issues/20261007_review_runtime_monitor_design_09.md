# Runtime Monitor 設計書レビュー: Capability モードの値の出所が未明示。および軽微な指摘集

## 優先度
🟢 Minor

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§6.4 / §2.3 / §3 / §7 P5 / §13）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§23 Capability Mode / §14 Adapter Contract）

## 指摘事項
1. **capability テーブル設計の妥当性（観点 7 への回答）:** §6.4 のテーブルは上位仕様 §23 の例と完全一致し、`RuntimeCapabilities` のフィールド（discover / project / agent / activity / working / waiting / done / needs_user）もテーブルの行と 1 対 1 で対応している。PoC 検証に十分な骨格。ただし**値がどこから来るのか**が未記述。上位仕様 §23 は「PoC の目的はこの表を実測によって埋めることでもある」としており、値が `adapter.capabilities()` 由来の実測値であること、`monitor --capabilities` が registry 経由で各 adapter の `RuntimeCapabilities` を集約・転置して描画することを明記する必要がある（ハードコードされた表示テーブルだと PoC 検証手段として機能しない）。
2. `--capabilities` と `--json` の併用時の出力形式（`RuntimeCapabilities` の JSON 配列）が未定義（issue 03 のフラグ併用規則に準拠して決める）。
3. **軽微:** `needs_user: bool` の型ヒントが、同コメントの「True / False / None(unknown)」と矛盾。`bool | None` に修正（Python 3.10+ / PEP 604、`ruff target-version = py310` で問題なし）。
4. **軽微:** §13 変更対象ファイルに `CHANGELOG.md` が含まれない。本リポジトリの規約（`CHANGELOG.md` の `[Unreleased]` に機能追記を載せる — 0.24.0 の `search` / `npx` 追加例参照）に従い、monitor 追加のエントリを §13 に追加する。
5. **軽微:** Adapter Contract（§3）は上位仕様 §14 の概念 interface（discover / inspect / **status / activity** / capabilities）から `status()` / `activity()` を省き `inspect()` に集約している。上位仕様 §14 は「実装方法は変更可能」と明記しており実質問題ではないが、意図的な乖離であることを設計書に一言記すと後のレビュー指摘を防げる。
6. **軽微:** テーブル表示の `Orca` / `VSCode` / `Zed` と canonical 値 `orca` / `vscode` / `zed` の対応（表示用ラベル変換）が未定義。renderer 側の `DISPLAY_LABELS` 定数として明記するとテストの期待値決めが楽になる。

## 改善案
§6.4 に次を追記する:「各 adapter の `capabilities()` が返す `RuntimeCapabilities` を registry が集約して描画する。値は adapter が宣言する観測可能性（実装に埋め込まれた自己申告）であり、PoC Report §31 のマトリクスは実機での `--capabilities` 実行結果から記録する。」上記 3–6 を文書修正する。

## 備考
PoC Report（§14）のマトリクス行（Session discovery / Project / ... / Needs user）と §6.4 テーブル行は同系数であり、報告テンプレートと capability 出力の対応が取れているのは good。§31 の「UNKNOWN / PARTIAL / NOT AVAILABLE を隠さない」と §6.4 の `PARTIAL` / `UNKNOWN` 値も整合。
