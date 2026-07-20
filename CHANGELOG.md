# Changelog

## [0.1.0] - 2026-07-20

### Added

- **CLI 基盤**: Click フレームワークによる CLI エントリーポイント (`ai-adapter` / `python -m ai_adapter`)
- **`init` コマンド**: `~/.ai-adapter/` ディレクトリの初期化（`agents/`, `bin/`, `skills/`, `mcp/` ディレクトリ + `config.json` 作成）
- **`status` コマンド**: 現在の設定状態（登録数、デフォルト環境、ディレクトリ状態）を表示
- **`uninstall` コマンド**: `~/.ai-adapter/` を削除して初期状態に戻す（`--force`, `--keep-git` オプション対応）
- **`agent` サブコマンド**: AIエージェント指示ファイルの管理（`add`, `get`, `list`, `remove`）
  - `~/.ai-adapter/agents/` にファイルを保存し、`.github/agents/` に展開
- **`env` サブコマンド**: 環境設定の管理（`add`, `remove`, `list`, `default`, `set-default`, `link-agent`, `unlink-agent`）
  - デフォルト環境の保護（削除不可）、エージェントと環境の紐付け機能
- **`bin` サブコマンド**: スクリプトファイルの管理（`add`, `get`, `list`, `remove`）
  - env 省略時の環境解決ロジック（エージェント紐付け → デフォルト環境）
  - `--agent` オプションによる明示的なエージェント指定
- **`skill` サブコマンド**: スキルディレクトリの管理（`add`, `get`, `list`, `remove`, `search`, `link-agent`）
  - SKILL.md の YAML frontmatter 自動パース
  - `.claude/skills/` への展開、タグフィルタ・キーワード検索対応
- **`mcp` サブコマンド**: MCP サーバー設定の管理（`add`, `remove`, `list`, `export`, `enable`, `disable`）
  - 対話的追加・JSON ファイルからの追加に対応
  - `export` で VS Code / Claude / Cursor 形式に出力（`.vscode/mcp.json`, `.mcp.json`, `.cursor/mcp.json`）
  - `--tool`, `--env` フィルタ対応
- **`sync` コマンド**: `~/.ai-adapter/` を GitHub リモートと同期（`git add` → `commit` → `pull --rebase` → `push`）
- **データモデル**: `Agent`, `Env`, `AgentBinding`, `Bin`, `Skill`, `MCPServer`, `Config` の dataclass 定義と JSON シリアライズ
- **設定ファイル管理**: `~/.ai-adapter/config.json` の読み書き（環境変数 `AI_ADAPTER_CONFIG` でパス上書き可能）
- **Git 操作ラッパー**: `subprocess` による git コマンドラッパー（`is_repo`, `init_repo`, `add_all`, `commit`, `pull_rebase`, `push`, `has_remote`, `get_remotes`）
- **テスト**: 81 の単体テスト（Click CliRunner + unittest.mock によるファイル操作/CLI/モックテスト）

### Changed

- 設定ファイル形式を YAML（`.ai-adapter.yaml`）から JSON（`config.json`）に変更
- 全データ保存先をプロジェクトルートから `~/.ai-adapter/` に統一

### Removed

- `pyyaml` 依存を削除（設定ファイルの JSON 化に伴い）

---

## 注意事項

- 本バージョンは開発初期フェーズのため、API は予告なく変更される可能性があります
- `~/.ai-adapter/` に保存されたデータは `ai-adapter uninstall` で削除可能です
