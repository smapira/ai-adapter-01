# Plan Architect レビュー: 設計書 01-04

- 日付: 2026-10-06
- レビュアー: Plan Architect A (Codex Plan Architect)
- 対象: 設計書 01-04 + マスター設計
- 結果: **全 4 本「要修正」**（Critical 1 件、Major 多数）

---

## 前提となるコードベースの事実（レビューで確認）

- CLI 登録: `agent` = instruction_group（instruction.py）、`sub-agent` = agent_group（agent.py）は別物
- `skill get`（単数）に `--format` は存在せず、`skill get-all` のみ `standard/openclaw/cursor`
- `mcp get --format` は全てプロジェクト（cwd）基準の出力
- `scan_project` は `.github/` を tool=`"project"` で検出（user 側は tool 名でプラットフォーム区別）
- **実テスト数は 606 件**（設計書の「337」は事実誤認）
- `requires-python = ">=3.10"`（`tomllib` は 3.11+ のためフォールバック必要）

---

## 設計書 01: User スコープ指示ファイル対応

**判定: 要修正**

### 🟡 Major

| ID | 指摘 |
|----|------|
| M1 | テスト対象ファイル誤り。`agent`（instruction.py）のテストは `tests/test_instruction.py`（`test_agent.py` は sub-agent のもの）。パスヘルパーは `tests/test_config.py` |
| M2 | `--tool` と既存 `--format` の二重機構。`agent get AGENTS.md --format codex --scope user` が自然。`--tool` を廃し `--format` に統一 |
| M3 | `--path` と既存 `--project-dir/-d` の併存。優先順位が曖昧。`--project-dir` に集約 or precedence 規定 |
| M4 | user スコープデプロイでの `add_to_gitignore` 呼び出し漏れ設計。home 配下の `.gitignore` を辿って dotfiles リポジトリに誤追記する恐れ。user スコープではスキップを明記 |
| M5 | get-all の「ファイル名そのまま」コピーはツールが読まないファイルを生む（STYLE.md → ~/.claude/ は無意味）。ツール別マッピングが必要（claude→CLAUDE.md、codex/opencode→AGENTS.md、gemini→GEMINI.md） |

### 🟢 Minor

- `--tool` に gemini を含める一方、完了定義は gemini を除外（不整合）
- scan の AC に `SCAN_IGNORE_PATTERNS` / `is_ignored()` 適用を明記すべき
- config.py にパスヘルパー集約は既存慣習と整合（妥当）

### 🔴 Critical
なし

---

## 設計書 02: Claude Code ネイティブパス対応

**判定: 要修正**

### 🔴 Critical

| ID | 指摘 |
|----|------|
| C1 | **MCP デプロイ先 `.claude/settings.json` の前提が現行 Claude Code 仕様と合っていない**。Claude Code の MCP 定義はプロジェクトなら `.mcp.json`（`mcpServers` キー）、user スコープなら `~/.claude.json`。`settings.json` は permissions/hooks が主体。さらにプロジェクト用 `.mcp.json` は `mcp get --format standard` が既に書き出しており、本設計の `--format claude` は「Claude が読まないファイルへの書き込み＋既存機能の重複」になる。**実装前に Claude Code の MCP 設定場所を仕様確認の上是正が必要** |

### 🟡 Major

| ID | 指摘 |
|----|------|
| M1 | scan の tool 名タクソノミー変更。project 配下の `.github/` は `"project"`、`.claude/` は `"claude"` と不揃い。全体方針として master に一元決定が必要 |
| M2 | 依存設計の食い違い。`sub-agent` への `--scope` は設計 01 では実装しないため、02 が独自実装することになり重複が生じる。01 で scope 解決ヘルパーまで定義し、02 は再利用として書くべき |
| M3 | `skill get` への `--format` 追加は「選択肢追加」ではなく新規オプション導入（`skill get` に `--format` 自体が存在しない） |

---

## 設計書 03: OpenAI Codex ネイティブパス対応

**判定: 要修正**

### 🟡 Major

| ID | 指摘 |
|----|------|
| M1 | `mcp get --format codex` のデフォルト出力が user home。既存 standard/openclaw/cursor は全て project 基準。`--scope` で 01/04 と同じモデルに揃えるべき |
| M2 | Python 3.10 で `tomllib` が使えない。`try: import tomllib / except ImportError: import tomli as tomllib` 方針を明記 or requires-python 引き上げ |
| M3 | TOML コメント消失が「検読」扱いのまま。tomllib→tomli-w ラウンドトリップはコメントとキー順を丸ごと破壊。**必須要件にすべき**。(a) `[mcp_servers.*]` セクションのみテキスト splice、(b) `tomlkit` 採用 のいずれかを確定 |
| M4 | スキルの二重書き込み（`~/.agents/skills/` と `~/.codex/skills/`）はドリフトを生む。正本一本＋オプトインに整理。「既存 `~/.codex/skills/` へのコピーも継続」は事実誤認（現状 scan 検出のみ、デプロイは新規） |
| M5 | フォーマット名 `codex-agents` は複合名で不整合。`codex` に統一を検討 |

### 🟢 Minor

- 「ファイール」→「ファイル」の typo
- auth.json 非アクセスの防御（mock で open() 検証）は良い設計
- Phase C/D の切り分けは適切

---

## 設計書 04: OpenCode 拡張

**判定: 要修正（軽微）**

### 🟡 Major

| ID | 指摘 |
|----|------|
| M1 | 「OpenCode は `.agent.md` / `.md` 両対応」の根拠が設計内にない。探索規則が拡張子非依存である保証が無い場合、デプロイしたエージェントが無視される。確認の上、必要なら `.md` 正規化に揃える |
| M2 | jsonc のみ存在する場合の validate 挙動が未規定。現行 `opencode_validate` は `opencode.json` が無いと "not found" エラーを返す。「jsonc 単独でも valid」等の明示が必要 |
| M3 | `--scope` の依存関係。01 が sub-agent/command に `--scope` を実装しないため、本設計書側での実装が必要。01 を「横断基盤」とするマスター記述と矛盾 |

### 🟢 Minor

- テスト計画に `tests/test_cli.py` の実行コマンド追記
- `--with-compat-skills` が参照するパスは 02/03 実装前に未整備期間が生じる。パス未存在でも害は無い旨を明記 or 順序見直し
- `opencode install --format jsonc` は `json.dumps` ではコメントを出せない。コメント挿入用ヘルパーが必要

---

## マスター設計への横断指摘

| 指摘 |
|------|
| テスト数 337 は事実誤認。実測 606 件 |
| 成功基準「337→450+」と設計 01 の完了定義「既存 337 テスト通過」は要修正 |
| マスター品質ゲート（ruff / lizard CCN ≤ 20）が各設計の完了定義・テスト計画に反映されていない |
| カバレッジの言及が全設計で皆無 |
| user スコープデプロイ全般での `add_to_gitignore` スキップ方針が設計群に存在しない |

---

## 推奨修正事項（優先度順）

1. **🔴 設計書 02 Phase A の MCP デプロイ先を仕様確認の上是正**（.claude/settings.json → 実態に合わせ project=`.mcp.json`（standard で充足）/ user=`~/.claude.json` 等）
2. **🟡 マスター設計と設計 01 のテスト数前提を 606 件に修正**
3. **🟡 プラットフォーム指定オプションを `--format` に一本化**（設計 01 の `--tool` を廃し、`--format` に codex/claude/opencode/zed を追加）。`--path` も `--project-dir` へ統合 or precedence 規定
4. **🟡 `--scope` の横断基盤を設計 01 に集約**（scope 解決ヘルパー＋`add_to_gitignore` スキップを含む）。02/03/04 は再利用として記述
5. **🟡 設計書 03 の TOML 保持方式を確定**（text-splice か tomlkit）＋ Python 3.10 向け `tomli` フォールバックを明記＋`mcp get` の scope モデルを統一（デフォルト project）
6. **🟡 設計書 01 のテスト計画を正しいファイルへ**（`tests/test_instruction.py`、パスヘルパーは `tests/test_config.py`）。get-all のファイル名マッピング方針を追加
7. **🟡 設計書 02 の scan タクソノミー方針を master に一元決定**
8. **🟡 設計書 03 のスキル二重書き込みを見直し**（正本一本＋オプトイン）、「継続」の事実誤認を修正
9. **🟢 各設計の完了定義に ruff / lizard / カバレッジ確認を追加**、設計 04 の test_cli.py 実行コマンド追記、設計 02 の空 claude_group 登録を後続化、typo 修正

---

## 維持すべき点（コードベース整合性が良い）

- provider パターン（resolve/export/merge/deploy + .bak + preserve）は 02/03 が正しく踏襲
- `agent`（instruction）と `sub-agent` の CLI 命名の区別を設計 01 が正しく把握
- `agent_format.convert_agent_file`、`SCAN_IGNORE_PATTERNS`/`is_ignored()`、cursor/openclaw の merge 関数の再利用方針は適切
- 各設計の「既存デフォルト動作は変更しない」backward-compat 方針は一貫
- `run_tests.sh` の使い方は全設計で正しい
