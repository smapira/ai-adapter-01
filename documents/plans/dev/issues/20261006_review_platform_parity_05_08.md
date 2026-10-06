# Plan Architect レビュー: 設計書 05-08

- 日付: 2026-10-06
- レビュアー: Plan Architect B (Codex Plan Architect)
- 対象: 設計書 05-08（外部仕様を context7 で実照合）
- 結果: **全 4 本 🔴 要修正**（Critical 5 件 = 外部仕様誤り 3 件含む）

---

## 前提: 外部仕様の検証結果（context7 照合）

| 項目 | 設計書の記述 | 実際の仕様（context7 照合済） |
|------|-------------|------------------------------|
| Zed skills パス | `.zed/skills/` | **`~/.agents/skills/`（global）/ `<worktree>/.agents/skills/`（project）**。`.zed/skills/` は存在しない。ネスト非対応 |
| Cursor plugin package | プロジェクトルート `skills/<name>/SKILL.md` | **`plugin-name/.cursor-plugin/plugin.json` + `skills/`**。インストール先は `~/.cursor/plugins/local/<name>/` |
| Gemini extension manifest | プロジェクトルートに生成、`${extensionPath}` 不使用 | 拡張は `~/.gemini/extensions/<name>/` + `gemini extensions install`。公式は **`${extensionPath}` 使用を推奨** |
| Zed MCP | キー名未記載 | キーは **`context_servers`** |
| VS Code mcp.json | `servers` + `type: stdio` | **一致** ✅ |
| Gemini commands/settings | `.gemini/commands/**/*.toml`、settings.json mcpServers | **一致** ✅ |
| Zed tasks/settings 路 | `.zed/tasks.json` 等 | **一致** ✅ |
| Cursor .cursorrules | プロジェクトルート legacy | **一致** ✅ |

---

## 設計書 05: Gemini CLI（🔴 要修正）

### 🔴 Critical

| ID | 指摘 |
|----|------|
| C5-1 | `gemini-extension.json` の生成場所が Gemini CLI に読み込まれない。`~/.gemini/extensions/<name>/` 配置 + `gemini extensions install` フローにするか non-scope 化。AC2「`${extensionPath}` 不使用」は公式仕様と逆（削除必須） |
| C5-2 | `scan_gemini` の extension 検出パス誤り。`~/.gemini/extensions/<name>/gemini-extension.json`（`rglob` 必要） |

### 🟡 Major

| ID | 指摘 |
|----|------|
| M5-1 | 設計書 01 が定義済みの `--format gemini` を再定義する指示は二重編集。01 準拠・変更なしと明記 |
| M5-2 | `TOOL_ORDER` タプル全体の再定義は実装順序で衝突。`TOOL_LABELS` 未追加は KeyError で scan クラッシュ。`scan_all` 登録も未言及 |
| M5-3 | TOML 変換のエスケープ規則未定義（`"""` 含有時） |
| M5-4 | merge ロジックが 4 実装目になるリスク。共通ヘルパー抽出を検討 |
| M5-5 | `SCAN_IGNORE_PATTERNS` への `.gemini/*cred*` 等の追加が未言及（マスター §2.4 必須） |
| M5-6 | 行 42（sandbox）がギャップ表にあるがタスク化されていない |

### 🟢 Minor

| ID | 指摘 |
|----|------|
| G5-1 | 「opencode validate と同じ UX + `--json`」— opencode に `--json` は存在しない |
| G5-2 | 変更対象 `src/ai_adapter/doctor.py` はパス誤り（実体は `commands/doctor.py`） |
| G5-3 | `gemini install` に `--project-dir` 相当のオプションがない |

---

## 設計書 06: Zed（🔴 要修正）

### 🔴 Critical

| ID | 指摘 |
|----|------|
| C6-1 | **skills デプロイ先 `.zed/skills/` は Zed の仕様外**。実際は `~/.agents/skills/`（global）/ `<worktree>/.agents/skills/`（project）。ネスト非対応（ルート直下のみ）。このまま実装すると Zed に認識されない |

### 🟡 Major

| ID | 指摘 |
|----|------|
| M6-1 | Zed MCP（行 64）が設計書から丸ごと落ちている。キーは `context_servers`。known gap として明文化必要 |
| M6-2 | `skill get-all --scope user` が設計書 01 のスコープ外。skill 側 `--scope` の所有設計書が不明 |
| M6-3 | Zed ユーザーパス解決の重複実装。config.py に集約すべき |
| M6-4 | `zed install` の内部矛盾（§3.2 は settings.json を install 成果物に挙げるが §3.4 は validate のみ） |
| M6-5 | TOOL_ORDER / TOOL_LABELS / scan_all の問題（05 と同じ） |

### 🟢 Minor

| ID | 指摘 |
|----|------|
| G6-1 | 「opencode validate と同じ UX + `--json`」の記述不正確 |
| G6-2 | `src/ai_adapter/doctor.py` のパス誤り |
| G6-3 | `SCAN_IGNORE_PATTERNS` 追加の言及なし |
| G6-4 | tasks.json / keymap.json のスコープアウト判断は妥当 ✅ |
| G6-5 | OS 依存パステストは良い計画 ✅ |

---

## 設計書 07: Cursor 拡張（🔴 要修正）

### 🔴 Critical

| ID | 指摘 |
|----|------|
| C7-1 | **plugin package の構造・配置が Cursor 仕様外**。実際は `<plugin>/.cursor-plugin/plugin.json`（マニフェスト必須）+ `skills/` + `rules/`。インストール先は `~/.cursor/plugins/local/<plugin-name>/`。プロジェクトルート `skills/` は探索対象外 |

### 🟡 Major

| ID | 指摘 |
|----|------|
| M7-1 | `agent get --format cursor-rules` の振る舞いが `get <name>` のセマンティクスと矛盾（全件連結される）。get-all に分離すべき |
| M7-2 | `--format cursor`（Exit 2）と `--format cursor-rules`（新規）の命名衝突。`cursorrules` 等への改称を検討 |
| M7-3 | `skill get`（単数）に `--format` が存在しない。どちらへの追加か不明 |

### 🟢 Minor

| ID | 指摘 |
|----|------|
| G7-1 | `skill get --format cursor-plugin`（単数）のテストケース追加 |
| G7-2 | `--env` フィルタ対応のテストが T 系列にない |
| G7-3 | `--project-dir` 未対応 |
| G7-4 | `.cursorrules` の位置づけは適切 ✅ |

---

## 設計書 08: VS Code（🔴 要修正）

### 🔴 Critical

| ID | 指摘 |
|----|------|
| C8-1 | TOOL_ORDER が未実装プラットフォーム（gemini/zed）を含む。マスター実装順 08→05→06 と矛盾。`TOOL_LABELS` 未追加で scan クラッシュ |

### 🟡 Major

| ID | 指摘 |
|----|------|
| M8-1 | `--format`（01）と `--target`（08）の相互作用が未定義 |
| M8-2 | `vscode install --path` が設計書 01 の「新規 `--path` は作らない」方針に反する。`--project-dir` に変更 |
| M8-3 | `mcp get --format vscode` が存在せず CLI UX が非対称 |
| M8-4 | VS Code の env プレースホルダ構文が未検証（`${env:API_KEY}` vs `${API_KEY}`） |
| M8-5 | HTTP/SSE 型 MCP サーバーの挙動（スキップ？警告？）が未定義 |
| M8-6 | TOOL_ORDER / TOOL_LABELS / scan_all の問題 |

### 🟢 Minor

| ID | 指摘 |
|----|------|
| G8-1 | `vscode uninstall` の有無（非対称） |
| G8-2 | `src/ai_adapter/doctor.py` のパス誤り |
| G8-3 | settings.json / launch.json / tasks.json を「管理しない」判断は妥当 ✅ |
| G8-4 | scan_project の `.github/copilot-instructions.md` 未検出の指摘は実コードと一致 ✅ |
| G8-5 | `.github/instructions/` の scan フィルタ精度（`*.instructions.md` 限定の余地） |
| G8-6 | `--format`×`--target` 排他テスト、TOOL_LABELS クラッシュ防止テスト追加推奨 |

---

## 共通の構造的課題（全設計書横断）

1. **TOOL_ORDER のタプル再定義衝突** + `TOOL_LABELS` 未言及（scan クラッシュリスク）+ `scan_all` 登録未言及
2. **設計書 01 との `--format` / `--scope` 所有権の重複**
3. **merge / deploy_skills ロジックの 4 実装化**（既存 cursor/openclaw + 新規 gemini/vscode/zed/cursor-plugin）
4. **`src/ai_adapter/doctor.py` のパス誤り**（05/06/08 共通。実体は `commands/doctor.py`）
5. **「opencode validate と同じ UX + `--json`」の記述**（opencode に --json は存在しない）

---

## 推奨修正事項（優先度順）

### P0: Critical 解消（実装着手前の必須修正）

1. **【設計書 06】Zed skills デプロイ先を `.agents/skills/`（project）/ `~/.agents/skills/`（user）に修正**。ネスト非対応の制約も AC に追加
2. **【設計書 07】Cursor plugin package 対応を再設計**。`~/.cursor/plugins/local/<name>/` に `.cursor-plugin/plugin.json` + `skills/` を生成する真の plugin 対応に
3. **【設計書 05】`gemini-extension.json` の配置・読み込みフローを修正**。`~/.gemini/extensions/<name>/` 配置 + `gemini extensions install` フローにするか non-scope 化。AC2（`${extensionPath}` 不使用）は削除

### P1: Major 解消

4. **【全設計書共通】TOOL_ORDER 更新ルールを明文化**。各設計書は自ツールのみ append、タプル全体の再定義禁止、`TOOL_LABELS` へのラベル追加を必須とする。`scan_all` 登録を各設計書の変更対象に明記。設計書 08 の TOOL_ORDER から gemini/zed を除去
5. **【設計書 01/05/06/08】`--format` と `--scope` の所有権を設計書 01 に一本化**
6. **【設計書 06】`skill get-all --scope user` の依存を明確化**
7. **【設計書 05/06/08】merge ロジックの共通ヘルパー抽出を検討**
8. **【設計書 07】`agent get --format cursor-rules` の振る舞いを get セマンティクスに整合**。命名衝突も解消
9. **【設計書 06】`zed install` 内部矛盾を解消**。`context_servers` キー名と Phase B の位置づけをギャップ表に明記
10. **【設計書 08】`--path` を `--project-dir` に変更**。env 構文を公式確認。stdio のみ制約時の警告出力を AC に追加

### P2: Minor 整備

11. 【全設計書】`src/ai_adapter/doctor.py` → `src/ai_adapter/commands/doctor.py` にパス修正
12. 【設計書 05】TOML 変換のエスケープ規則を明記
13. 【設計書 05/06】`SCAN_IGNORE_PATTERNS` 追加を変更対象に明記
14. 【設計書 05】行 42（sandbox）を scan 検出タスク化するか非スコープを明示
15. 【設計書 06】OS 依存 Zed パス解決を config.py に集約
16. 【設計書 07】`skill get`（単数）への `--format` 追加を明記
17. 【設計書 08】`vscode uninstall` の追加または non-scope 明記。「opencode validate と同じ UX」の記述修正

---

## 維持すべき点

- scan_project の `.github/copilot-instructions.md` 未検出の指摘は実コードと一致（正確な現状分析）
- VS Code mcp.json の `servers` + `type: stdio` 形式は実仕様と一致
- settings.json / launch.json / tasks.json を「管理しない」判断は妥当（過剰設計回避）
- `.cursorrules` の非推奨・移行用という位置づけは適切
- merge（.bak + preserve）パターン、`add_to_gitignore`、`tomllib` パース検証など既存パターンの再用意図は良好
- BDD タスク分解・AC・テストケースの粒度は全体として実装可能な水準
