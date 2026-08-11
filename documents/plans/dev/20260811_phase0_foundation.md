# フェーズ 0 実装計画: 基盤完成（README 刷新・Cursor 対応・skill search 強化・診断サマリー）

- 日付: 2026-08-11
- 作成者: Product Manager
- 状態: ドラフト（Plan Architect レビュー待ち）
- 上位計画: `documents/plans/dev/20260811_ai_adapter_grand_design.md`（承認済み）
- 対象バージョン: v0.21.1 → v0.22
- 制約: ドキュメント作成フェーズ（本計画は実装前の設計ドキュメント。実装は別途 Implementer 依頼）

---

## 1. 目的

グランドデザインのフェーズ 0（基盤完成）を実装するための BDD タスク分解と受け入れ条件を定義する。
OSS としての完成度を高め、市場投入の土台を作る。

---

## 2. BDD タスク分解

### タスク 0-1: README ファーストビュー刷新

**期待する振る舞い**:
- 入力: README.md 冒頭（`Common management infrastructure CLI tool for AI agent scripts` の現状）
- 応答: 以下の構成に刷新
  1. タイトル + タグライン「One configuration for all your AI coding agents.」
  2. 概要文「Manage and sync your AI agent configuration across Claude Code, Codex, Cursor, VS Code, OpenCode and more.」
  3. 対応ツール図（ASCII: ai-adapter を中心に Claude/Codex/Cursor/OpenCode へ分岐）
  4. 最短 3 コマンド導線（`pip install ai-adapter` → `ai-adapter init` → `ai-adapter start <URL>`）
  5. サムネイル画像（ユーザー提供「ReadMe サムネイル」を `docs/` 配下に配置し参照。画像ファイルはユーザーから受領後に組み込み、それまではプレースホルダー）
  6. Agent Plugins 1.0.0 バッジは維持

**受け入れ条件**:
- AC1: 冒頭 30 行以内に「タグライン + 対応ツール図 + 最短導線」が含まれる
- AC2: 既存の Features 節・Command Reference 節は維持される（削除しない）
- AC3: サムネイル画像は `docs/readme-thumbnail.png`（仮）に配置され、相対パスで参照される
- AC4: 既存 CI バッジ・Agent Plugins バッジが維持される

**データ（仕様例）**:
- タグライン: `One configuration for all your AI coding agents.`
- 対応ツール: Claude Code / Codex / Cursor / VS Code / OpenCode / OpenClaw / Agent Plugins 1.0.0

---

### タスク 0-2: Cursor 対応の一本化（skills + mcp、agent は明示的エラー）

> **スコープ明確化（Plan Architect 指摘反映）**: Cursor にネイティブな「agent」概念は無い。
> CLI の `agent` グループ（`instruction.py`）は AGENTS.md 等のルート命令ファイル管理で、Cursor 形式への
> 意味論（role/behavior）マッピングが存在しない。本タスクは **`skill` と `mcp` のみ対応**とし、
> `agent get --format cursor` は「変換不可エラー」を主経路にする。

**期待する振る舞い**:
- 入力: `ai-adapter skill get-all --format cursor`
- 応答: `.cursor/rules/` 配下に SKILL.md を Cursor 形式（`*.mdc` + YAML frontmatter）でデプロイ。既存非 ai-adapter ルールは保持
- 入力: `ai-adapter mcp get --format cursor`
- 応答: `.cursor/mcp.json` を生成（サーバー定義を Cursor 形式に変換）
- 入力: `ai-adapter agent get --format cursor`
- 応答: **変換不可エラー**を表示（Cursor に agent 概念が無い旨。`sub-agent` 対応は将来タスク）
- 入力: `ai-adapter skill get-all --format cursor --force`
- 応答: 同名ファイルを上書き

**受け入れ条件**:
- AC1: `skill.py` の `--format` Choice に `cursor` を追加（既存 `standard` / `openclaw` と併存）
- AC2: `mcp.py` の `--format` Choice に `cursor` を追加
- AC3: Cursor 形式変換は `src/ai_adapter/providers/cursor.py` に新設（openclaw.py と対称の構造。関数名は `deploy_skills` / `export_mcp` / `resolve_mcp_output_path` に統一）
- AC4: 既存 openclaw / standard の挙動を変更しない（回帰なし）
- AC5: 変換対象外の項目は警告表示し、処理を継続する
- AC6: `agent get --format cursor` は変換不可エラー（exit code 2、メッセージに理由を明記）
- AC7: **`cli.py` への登録（import / `main.add_command`）と CLI スモークテストを含む**（🟢0-6 反映）

**データ（仕様例）**:
- 入力 MCP: `{"mcpServers": {"github": {"command": "npx", "args": ["@modelcontextprotocol/server-github"]}}}`
- 出力 Cursor: `.cursor/mcp.json` に同構造を書き出し（Cursor は MCP 互換のため構造維持）
- 入力 Skill: `~/.ai-adapter/skills/database-schema/SKILL.md`（frontmatter: name/description/tags）
- 出力 Cursor: `.cursor/rules/database-schema.mdc`（frontmatter は `description` / `globs` に変換）

**既存コード再利用**:
- `mcp.py` の `mcp_get` の `--format` Choice と `_mcp_get_openclaw` 分岐（シンボル参照）を土台に `cursor` を追加
- `skill.py` の `_deploy_skills_standard` / `_openclaw_deploy_skills` を参考に `_deploy_skills_cursor` を実装
- 新規 `src/ai_adapter/providers/cursor.py`: `deploy_skills` / `export_mcp` / `resolve_mcp_output_path` を openclaw.py と対称に実装

---

### タスク 0-3: `skill search` のローカル検索強化

**期待する振る舞い**:
- 入力: `ai-adapter skill search postgres`
- 応答: 登録済み Skill から名前/説明/タグに一致するものを一覧表示
- 入力: `ai-adapter skill search postgres --tag database`
- 応答: タグでフィルタした結果を表示
- 入力: `ai-adapter skill search 該当なしキーワード`
- 応答: 「No matching skills found.」+ ヒント表示

**受け入れ条件**:
- AC1: 検索対象はローカル登録済み Skill のみ（パブリックレジストリ検索はフェーズ 4-3 に分離）
- AC2: `--tag` オプションでタグフィルタ追加
- AC3: 検索結果は「名前 / 説明 / タグ」の一覧表示
- AC4: 既存の `skill search` の引数互換を維持

**データ（仕様例）**:
- 登録済み: `database-schema`（tags: database, postgres） / `frontend`（tags: react, typescript）
- 入力: `skill search database` → 出力: `database-schema` が一致
- 入力: `skill search postgres --tag database` → 出力: `database-schema` が一致
- 入力: `skill search unknown` → 出力: 該当なしメッセージ

**既存コード再利用**:
- `skill.py` の既存 `search` コマンド実装を拡張（現状の実装を確認の上、タグフィルタを追加）

---

### タスク 0-4: `get-all-rec` に診断サマリー追加

> **前提の明確化（Plan Architect 指摘反映）**: `get-all-rec` は「取得一覧」ではなく
> **デプロイ**コマンド（`~/.ai-adapter/` → プロジェクト `.github/` へ展開、出力は
> 「agents/: N deployed」等の進捗行）。サマリーは**デプロイ実行前**に差分を算出・表示する。

**期待する振る舞い**:
- 入力: `ai-adapter get-all-rec`
- 応答: デプロイ実行前に差分を算出し、以下の診断サマリーを**先頭に表示**してからデプロイを続行
  - 環境検出数（agents / skills / mcp / prompts / commands / bins）
  - 重複検出（同名ファイルの存在）
  - 不一致検出（`~/.ai-adapter/` とプロジェクト `.github/` の差分: 新規 / 更新 / 一致）
- 入力: `ai-adapter get-all-rec --no-summary`
- 応答: 従来どおりのデプロイ進捗行のみ

**受け入れ条件**:
- AC1: 診断サマリーは `--no-summary` フラグで無効化可能
- AC2: 診断サマリーは `diff.py` の `compare_all` を再利用して実装（新規に差分ロジックを書かない）
- AC3: サマリーは標準エラーではなく標準出力に表示（パイプ互換維持）
- AC4: **サマリーの算出はデプロイ実行前**（差分算出 → サマリー表示 → デプロイの順序を厳守。デプロイ後に算出すると `compare_all` が常に up-to-date を返すため）
- AC5: サマリー表示後、従来のデプロイ動作にそのまま続行する（挙動変更なし）

**データ（仕様例）**:
- 出力形式（デプロイ前の差分状態）:
  ```
  === Summary ===
  Agents: 3 (1 in repo, 2 new)
  Skills: 5 (4 in repo, 1 new)
  MCP: 2 (2 in repo)
  ```
- 差分カテゴリは `CategoryDiff` の `added` / `updated` / `up_to_date` を集約

**既存コード再利用**:
- `diff.py` の `compare_all`（シンボル参照）→ `list[CategoryDiff]` を集約してサマリー生成
- `get_all_rec.py` の既存実装を拡張（デプロイ前フックとしてサマリー算出を挿入）

---

### タスク 0-5: docs 整備（wiki 対応ツール比較を README へ昇格）

**期待する振る舞い**:
- 入力: README.md の 適切な位置
- 応答: `documents/wiki/LLM-Tool-Comparison.md` の内容をユーザー向けに要約した「対応ツール一覧表」を README に追加

**受け入れ条件**:
- AC1: 対応ツールと未対応ツール（Continue 等）の区別が明示される
- AC2: 元の wiki ドキュメントは削除しない（内部資料として維持）

**データ（仕様例）**:
- 対応: GitHub Copilot（部分）/ Claude Code（`.github/` 経由）/ OpenCode / Codex CLI / OpenClaw（部分）/ Agent Plugins 1.0.0
- 未対応: Cursor（0-2 で対応予定）/ Continue（将来）

---

### タスク 0-6: メタデータ整備（pyproject 刷新）

**期待する振る舞い**:
- 入力: `pyproject.toml` の `description` / `keywords`
- 応答: 以下の変更
  - `description`: `"Unified CLI tool for managing AI agent configurations and scripts"` → `"Manage and sync your AI agent configuration across Claude Code, Codex, Cursor, VS Code, OpenCode and more."`
  - `keywords`: `ai-dotfiles` / `ai-agent-config` 等を追加

**受け入れ条件**:
- AC1: PyPI に再公開後、パッケージメタデータが更新される
- AC2: バージョンは v0.22.0 に更新（CHANGELOG 追記含む）

**データ（仕様例）**:
- `keywords = ["ai", "agent", "cli", "mcp", "skill", "copilot", "claude", "opencode", "codex", "cursor", "ai-dotfiles", "ai-agent-config"]`

---

## 3. テスト計画（フェーズ 0）

| タスク | テストファイル | 種別 | 追加数 | 内容 |
|--------|--------------|------|--------|------|
| 0-2 | `tests/test_cursor.py`（新設） | Unit | 10〜15 | cursor 形式変換（skill/mcp/agent エラー）・`--format cursor` スナップショット |
| 0-2 | `tests/test_skill.py` / `test_mcp.py`（拡張） | Unit | 5 | Choice 追加の回帰・既存 openclaw 挙動不変 |
| 0-2 | `tests/test_cli.py`（拡張） | Unit | 2 | `cli.py` 登録・CLI スモーク（`ai-adapter skill get-all --format cursor` がエラーなく起動） |
| 0-3 | `tests/test_skill.py`（拡張） | Unit | 5 | `--tag` フィルタ・該当なし・引数互換 |
| 0-4 | `tests/test_cli.py`（拡張・既存 `test_get_all_rec_*` L620-702 に追記） | Unit | 5 | サマリー出力（デプロイ前タイミング）・`--no-summary`・デプロイ続行 |
| 0-1/0-5/0-6 | 該当なし（ドキュメント/メタデータ） | - | - | README 検証はコードレビューで実施 |

**実行ゲート**: 既存 337 テスト + 追加 20〜30 テストを `scripts/run_tests.sh` で実行（sandbox 方式）。

---

## 4. 既存コード再利用マップ（フェーズ 0）

| タスク | 再利用資産 | 用途 |
|--------|-----------|------|
| 0-2 | `mcp.py` の `mcp_get` の `--format` Choice・`_mcp_get_openclaw` 分岐（シンボル参照）・`skill.py` の `_deploy_skills_standard` | cursor 形式追加の土台 |
| 0-2 | `providers/openclaw.py`（`deploy_skills` / `export_mcp` / `resolve_mcp_output_path`） | `providers/cursor.py` を対称構造で新設 |
| 0-4 | `diff.py` の `compare_all`・`FileDiff` / `CategoryDiff` | 診断サマリーの差分検出 |
| 0-3 | `skill.py` の既存 `search` コマンド | タグフィルタ追加 |

---

## 5. リスクと対策

| リスク | 影響 | 対策 |
|--------|------|------|
| Cursor の閉形式（`.mdc`）が仕様変更 | 変換ロジックの陳腐化 | `providers/cursor.py` に集中実装し、形式変換を一元管理 |
| README 刷新による情報欠落 | ユーザー混乱 | AC2（既存節の維持）を厳守 |
| サムネイル画像の質 | 見た目の劣化 | プレースホルダーから受領画像に差し替え可能な相対パス参照（AC3）で進め、受領後に組み込み |

---

## 6. 実装順序

1. 0-2 Cursor 対応（技術的コア。他の形式変換の土台）
2. 0-3 skill search 強化（小さく独立）
3. 0-4 診断サマリー（diff.py 再利用）
4. 0-1 README 刷新（サムネイル配置済み `docs/readme-thumbnail.png`）
5. 0-5 docs 整備
6. 0-6 メタデータ整備（最後にバージョンアップ）

---

## 7. 次のアクション

1. [x] Plan Architect レビュー（🟡3 / 🟢4 の指摘を反映済み・判定「修正必要（軽微）→ 反映により承認可能」）
2. [x] サムネイル画像を配置（`docs/readme-thumbnail.png`・SVG から生成）
3. [ ] Implementer に実装依頼（0-2 → 0-3 → 0-4 → 0-1 → 0-5 → 0-6）
4. [ ] Reviewer 検収 → QA チェック
