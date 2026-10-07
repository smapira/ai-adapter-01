# Runtime Monitor 設計書レビュー: P0 Discovery の実現可能性設計が不足

## 優先度
🟡 Major

## 対象
- 計画書: `documents/plans/dev/20261007_runtime_monitor_design.md`（§7 Phase P0、§4.2 / §4.3、§1 Core Design Rule）
- 上位仕様書: `documents/plans/user/AI Adapter Runtime Monitor.md`（§25 Phase P0、§33 Core Design Rule）
- 関連ファイル: `src/ai_adapter/runtime/adapters/{orca,vscode,zed}.py`（未作成）

## 指摘事項
1. **P0 AC1「Orca / VS Code / Zed の 3 つすべてで Session Discovery が可能」の到達性が未検証。** 2026-10-07 の実地確認では:
   - Orca: ✅ 実装可能。`orca terminal list --json` に `agentIdentity`（例 `"opencode"`）、`worktreePath`、`lastOutputAt`、`preview` が含まれ、`orca worktree ps --json` に `workspaceStatus: "in-progress"`、`lastActivityAt` が含まれる。P1 Identity / P2 Activity の主要フィールドが公式 CLI で取得できる。
   - VS Code: ⚠️ 未検証。`code --status` はプロセス/GPU 診断のみで agent session 情報を返さない。Agent Session を列挙する公式 CLI/API は未確認。
   - Zed: ⚠️ 未検証。`zed --help` に status / session 系コマンドは存在しない。ACP / thread metadata が唯一の候補。
2. **設計書内部の矛盾:** §4.3 は「ACP で Runtime State が十分取得できない場合、その事実自体を PoC 結果として記録する。無理に状態を推測しない」と逃げ道を認める一方、P0 AC1 は 3 ホストすべての Discovery 成功を硬性要件としており、逃げ道が機能しない。
3. **スパイク工程が存在しない。** 実装開始前に各 Host の公式インターフェースを実地検証するフェーズが P0–P5 のどこにもない。3 ホスト縦切り（Core Design Rule）が最初の障害で停止するリスクが高い。
4. **Orca 調査対象（§4.1）は実在コマンドで正当だが、より上位の公式ソース候補が欠落:**
   - `orca search --json` — agent session 全文検索インデックス（`--agent` / `--path` / `--since` フィルタ付き）。Session Discovery の第一候補になり得る。
   - `orca agent-context --json` — 239 コマンドの機械可読スキーマ。
   - `orca status --json` — app/runtime readiness（pid / state）→ registry の可用性プローブに最適（§4.1 には載っているが用途が未記述）。

## 改善案
1. **P0 の前に「P0-Spike（タイムボックス 1 日）」を追加:** 各 Host で official discovery interface を実地検証し、利用可否・取得フィールド・confidence を PoC Report（§14）の Observation source に記録する義務とする。
2. **P0 AC1 を修正:** 「公式インターフェースで Session Discovery 可能、または §4.4 Fallback（source=process, confidence=low）により発見可能なこと」に緩和。fallback 到達時は PoC Report の Unsupported observations に明記する。
3. **§4.2 / §4.3 に discovery 経路候補を追記:** VS Code（extension session metadata ファイル / agent hooks / process + lsof cwd）、Zed（ACP / thread metadata files / process）。各候補の検証結果を P0-Spike で埋める。
4. **§4.1 の Orca 調査対象に `orca search --json` と `orca terminal list --json` の取得可能フィールド（agentIdentity 等）を追記**し、`orca status --json` を「可用性プローブ用」と明記する。

## 備考
Orca 腿は実装可能と判断（本機で CLI を実地確認済み）。リスクは VS Code / Zed の discovery 経路。fallback 許容に緩和しても仕様 §25「3つ成功するまでStatus詳細実装へ進まない」の縦切り精神は維持される（発見自体は fallback でも成立する）。
