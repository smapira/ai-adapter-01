# Changelog

## [0.5.0] - 2026-07-20

### Added

- **`opencode` サブコマンド**: OpenCode 連携設定（`alias`, `install`, `uninstall`）
  - `alias`: `.opencode` → `.github` のシンボリックリンクを作成
  - `install`: MCP 設定を元に `opencode.json`（hooks 形式）を生成
  - `uninstall`: `opencode.json` を削除
- **`mcp load --file` コマンド**: `.mcp.json` から MCP サーバー設定を一括読み込み

### Changed

- **`mcp export`**: 出力先をカレントディレクトリに変更、出力ファイルを常に `.mcp.json` に固定
  - `--path` オプションで出力先ディレクトリを指定可能
- **`mcp export` の `--tool` オプションを `--path` に名称変更**
- **`mcp add`**: `--file` オプションを廃止し `--command` 必須に簡略化

## [0.4.1] - 2026-07-20

### Changed

- **スキル展開先を統一**: `get_claude_skills_dir()` → `get_github_skills_dir()` に変更
  - `skill get` / `skill get-all` の出力先を `.claude/skills/` から `.github/skills/` に変更
  - `agent` / `bin` と同じ `.github/` 配下に統一

## [0.4.0] - 2026-07-20

### Added

- **`agent remove-all` コマンド**: 全てのエージェントを一括削除（`--keep-file`, `--force` オプション対応）
- **`env remove-all` コマンド**: デフォルト環境を除く全ての環境を一括削除（`--force` オプション対応）
- **`bin remove-all` コマンド**: 全てのスクリプトの登録を一括解除（`--force` オプション対応）

### Changed

- `bin` コマンドの `env` を位置引数（`click.argument`）から `--env` オプション（`click.option`）に変更
  - `bin get script.py` のように単一引数でファイル名のみ渡せるよう改善
  - `--env` 省略時は従来通り環境解決ロジックで補完

## [0.3.0] - 2026-07-20

### Added

- **`start <URL>` コマンド**: GitHub リモートリポジトリと連携した一発セットアップ
  - `git clone` を試行し、失敗した場合は `git init` + `remote add` で初期化
  - `~/.ai-adapter/` のディレクトリ構造と `config.json` を自動生成
  - リモートURLは `Config.remote` フィールドに保存
- **`init --remote` オプション**: コマンドラインからリモートURLを指定して初期化
- **`init` 対話的プロンプト**: `--remote` 未指定時に対話的にリモートURLを質問（スキップ可能）
- **`sync` リモート未設定時の対話的入力**: `config.remote` の保存値 → 手動入力 → スキップ の順で処理
- **`status` リモート表示**: 設定ファイルに `remote` が保存されていれば表示
- **`git.py`**: `clone()`, `add_remote()`, `get_current_branch()` 関数を追加
- **`Config.remote` フィールド**: 設定ファイルに Git リモートURLを永続化

### Changed

- `init` が Git リポジトリ初期化 + リモート設定まで行うように改善
- `sync` がリモート未設定でもエラー終了せず、対話的入力で補完するように改善

## [0.2.0] - 2026-07-20

### Added

- **`uninstall` コマンド**: `~/.ai-adapter/` を削除して初期状態に戻す（`--force`, `--keep-git` オプション対応）
- **`status` コマンド**: skills/mcp の登録数とディレクトリ状態を表示するように拡張
- **`CHANGELOG.md`**: 新規作成

## [0.1.0] - 2026-07-20

### Added

- **CLI 基盤**: Click フレームワークによる CLI エントリーポイント (`ai-adapter` / `python -m ai_adapter`)
- **`init` コマンド**: `~/.ai-adapter/` ディレクトリの初期化（`agents/`, `bin/`, `skills/`, `mcp/` ディレクトリ + `config.json` 作成）
- **`status` コマンド**: 現在の設定状態（登録数、デフォルト環境、ディレクトリ状態）を表示
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
- **テスト**: 84 の単体テスト（Click CliRunner + unittest.mock によるファイル操作/CLI/モックテスト）

### Changed

- 設定ファイル形式を YAML（`.ai-adapter.yaml`）から JSON（`config.json`）に変更
- 全データ保存先をプロジェクトルートから `~/.ai-adapter/` に統一

### Removed

- `pyyaml` 依存を削除（設定ファイルの JSON 化に伴い）

---

## 注意事項

- 本バージョンは開発初期フェーズのため、API は予告なく変更される可能性があります
- `~/.ai-adapter/` に保存されたデータは `ai-adapter uninstall` で削除可能です
