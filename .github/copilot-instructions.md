# ai-adapter プロジェクト共通指示

## プロジェクト概要
AIエージェント設定・スクリプトを一元管理するCLIツール。
設定データは `~/.ai-adapter/` に集約し、`.github/` との間で双方向同期する。

## ビルド・テスト・lint
- インストール: `pip install -e .` または `uv pip install -e .`
- 全テスト実行: `pytest tests/`
- 特定テスト: `pytest tests/test_xxx.py -v`
- lint: `ruff check src/`
- 型チェック: `mypy src/`
- CLI直接実行: `python -m ai_adapter --help`

## コーディング規約

### Python共通
- Python 3.10+、型ヒント必須
- `from __future__ import annotations` を全ファイルの先頭に記述
- クラス名: PascalCase、関数/変数名: snake_case、定数: UPPER_SNAKE_CASE
- Click CLI: `@click.group()` → `@main.command()` パターン
- エラーハンドリング: ClickException を raise（click.Choiceエラーは適切にcatch）
- 外部依存は最小に（標準ライブラリ優先）
- ログは `logging` モジュール、不要な `print()` / `dd()` は禁止

### アーキテクチャ
- `src/ai_adapter/cli.py` — Clickエントリポイント（コマンド登録はここで集約）
- `src/ai_adapter/commands/` — サブコマンド実装（agent / bin / command / env / mcp / prompt / skill）
- `src/ai_adapter/providers/` — ツール固有の実装（opencode）
- `src/ai_adapter/config.py` — ~/.ai-adapter/ の設定読み書き
- `src/ai_adapter/models.py` — Pydantic/データクラス
- `src/ai_adapter/git.py` — Git操作ラッパー
- `src/ai_adapter/diff.py` — 差分比較
- `src/ai_adapter/sync.py` — GitHub同期
- `src/ai_adapter/agent_format.py` — Agentファイルのフォーマット検証・変換

### テスト
- `tests/` に対応モジュールごとに `test_xxx.py` を配置
- CLIテスト: click.testing.CliRunner を使用
- モック: unittest.mock を優先
- テストデータは pytest fixture で生成

### Git / GitHub
- コミットメッセージ: conventional commits（feat: / fix: / chore: / docs: / refactor: / test:）
- PRタイトルも conventional commits に準拠


## エージェント設定ファイル
- `.github/agents/*.agent.md` — YAML frontmatter + Markdown（name / description / tools）
- `.github/skills/<name>/SKILL.md` — スキル定義（YAML frontmatter + Markdown）
- `.github/bin/` — 実行可能スクリプト
- `.github/commands/` — Copilotカスタムスラッシュコマンド
- `.github/prompts/` — プロンプトテンプレート
- `.mcp.json` — MCPサーバー設定

## 環境
- デフォルト環境名: "default"
- 設定保存先: `~/.ai-adapter/`
- プロジェクト設定: `.github/` 配下
- ai-adapter CLI: `ai-adapter <command>`（または `python -m ai_adapter <command>`）

## CLI サブコマンド一覧
- `init` — ~/.ai-adapter/ 初期化
- `status` — 状態表示
- `sync` — GitHub同期
- `agent` — Agentファイル管理
- `skill` — スキル管理
- `command` — コマンド定義管理
- `prompt` — プロンプト管理
- `bin` — スクリプト管理
- `mcp` — MCPサーバー管理
- `env` — 環境管理
- `opencode` — OpenCode統合（alias / install / uninstall / validate）
