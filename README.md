# ai-adapter

**AIエージェント・スクリプトの共通管理基盤 CLI ツール**

CLI で操作し、AIエージェントの指示ファイル（`.github/instructions` 等）やスクリプトをグループ単位で管理。環境を切り替えて簡単に共有・移行できます。

---

## 特徴

- **集中管理**: すべてのデータは `~/.ai-adapter/` に集約。プロジェクトを跨いで設定を一元管理
- **環境切り替え**: 会社・自宅など環境ごとにエージェント設定やスクリプトを切り替え
- **GitHub 同期**: `ai-adapter sync` で `~/.ai-adapter/` を GitHub リモートと同期。チーム共有やPC移行が簡単
- **エージェント紐付け**: エージェント名と環境を紐付け、コンテキストに応じた自動解決
- **スキル管理**: SKILL.md 形式のスキルを管理・展開（`.github/skills/`）
- **MCP サーバー管理**: MCP サーバー設定を一元管理し、各ツール形式で出力

---

## インストール

### 前提条件

- Python 3.10 以上
- [uv](https://docs.astral.sh/uv/)（パッケージ管理）

```bash
# pip でもインストール可能
pip install ai-adapter

# または uv を使用
uv pip install ai-adapter
```

### 開発版

```bash
git clone <repository-url>
cd ai-adapter
uv sync
uv pip install -e .
```

### 動作確認

```bash
ai-adapter --help
ai-adapter --version
```

---

## クイックスタート

```bash
# 1. 初期化
ai-adapter init

# 2. エージェントファイルを追加
ai-adapter agent add ~/my-agents/reviewer.md

# 3. 環境を追加
ai-adapter env add myhome

# 4. スクリプトを追加
ai-adapter bin add myhome ~/scripts/deploy.sh

# 5. スキルを追加
ai-adapter skill add ~/my-skills/database-schema

# 6. MCP サーバーを追加
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# 7. プロジェクトに展開
cd your-project
ai-adapter agent get reviewer      # → .github/agents/reviewer.md
ai-adapter bin get --env myhome deploy   # → .github/bin/deploy.sh
ai-adapter skill get database-schema  # → .github/skills/database-schema/
ai-adapter mcp export --path vscode   # → .vscode/mcp.json

# 8. GitHub と同期（設定を共有）
ai-adapter sync
```

---

## コマンドリファレンス

### `ai-adapter start <URL>`

GitHub リモートリポジトリと連携して `~/.ai-adapter/` を一発セットアップします。
クローンを試み、失敗した場合は新規リポジトリとして初期化します。

```bash
# 新規または既存のリポジトリからセットアップ
ai-adapter start git@github.com:user/my-agent-config.git
```

### `ai-adapter init`

`~/.ai-adapter/` ディレクトリと設定ファイルを初期化します。
`--remote` オプション、または対話的プロンプトでリモートリポジトリを設定できます。

```bash
# 最小限の初期化（後からリモートを設定可能）
ai-adapter init

# リモートを指定して初期化
ai-adapter init --remote git@github.com:user/my-agent-config.git
```

### `ai-adapter status`

現在の状態（登録数、デフォルト環境など）を表示します。

```bash
ai-adapter status
```

### `ai-adapter agent`

AIエージェントの指示ファイル（`.md` 等）を管理します。

| コマンド | 説明 |
|---------|------|
| `agent add <path>` | エージェントファイルを `~/.ai-adapter/agents/` に追加 |
| `agent get <name>` | エージェントを `.github/agents/` にコピー |
| `agent get-all` | 全ての登録済みエージェントを `.github/agents/` にコピー |
| `agent list` | 登録済みエージェント一覧を表示 |
| `agent remove <name>` | エージェントを削除（`--keep-file` でファイル保持） |
| `agent remove-all` | 全てのエージェントを削除（`--keep-file`, `--force` 対応） |

```bash
ai-adapter agent add ~/dotfiles/agents/reviewer.md
ai-adapter agent list
ai-adapter agent get reviewer
ai-adapter agent remove reviewer
ai-adapter agent remove-all --force
```

### `ai-adapter env`

環境設定を管理します。

| コマンド | 説明 |
|---------|------|
| `env add <name>` | 新しい環境を追加 |
| `env remove <name>` | 環境を削除（デフォルト環境は削除不可） |
| `env list` | 環境一覧を表示（`*` はデフォルト環境） |
| `env default` | 現在のデフォルト環境名を表示 |
| `env set-default <name>` | デフォルト環境を変更 |
| `env link-agent <agent> <env>` | エージェントと環境を紐付け |
| `env unlink-agent <agent>` | エージェントの紐付けを解除 |
| `env remove-all` | デフォルト環境を除く全ての環境を削除（`--force` 対応） |

```bash
ai-adapter env add office
ai-adapter env list
ai-adapter env set-default office
ai-adapter env link-agent reviewer office
ai-adapter env remove-all --force
```

### `ai-adapter bin`

スクリプトファイルを管理します。`[env]` は省略可能で、その場合は環境解決ロジックが動作します。

| コマンド | 説明 |
|---------|------|
| `bin add --env <env> <path>` | スクリプトを `~/.ai-adapter/bin/` に追加（--env省略時は環境解決） |
| `bin get --env <env> <name>` | スクリプトを `.github/bin/` にコピー（--env省略時は環境解決） |
| `bin get-all` | 全ての登録済みスクリプトを `.github/bin/` にコピー |
| `bin list --env <env>` | スクリプト一覧を表示（--env省略時は全環境） |
| `bin remove --env <env> <name>` | スクリプトの登録を解除（--env省略時は環境解決） |
| `bin remove-all` | 全てのスクリプトの登録を解除（`--force` 対応） |

```bash
ai-adapter bin add --env myhome ~/scripts/deploy.sh
ai-adapter bin list
ai-adapter bin get deploy
ai-adapter bin remove deploy
ai-adapter bin remove-all --force
```

また、`--env` は省略可能で、省略時は環境解決ロジックが動作します。

### `ai-adapter skill`

スキル（SKILL.md を含むディレクトリ）を管理します。

| コマンド | 説明 |
|---------|------|
| `skill add <path>` | スキルディレクトリを `~/.ai-adapter/skills/` に追加 |
| `skill get <name>` | スキルを `.github/skills/` にコピー |
| `skill get-all` | 全ての登録済みスキルを `.github/skills/` にコピー |
| `skill list` | 登録済みスキル一覧を表示（`--tag` でフィルタ） |
| `skill remove <name>` | スキルを削除（`--purge` でファイルも削除） |
| `skill remove-all` | 全てのスキルを削除（`--purge`, `--force` 対応） |
| `skill search <keyword>` | スキルをキーワード検索 |
| `skill link-agent <skill> <agent>` | スキルとエージェントを紐付け |

```bash
ai-adapter skill add ~/skills/database-schema/
ai-adapter skill list
ai-adapter skill get database-schema
ai-adapter skill search prisma
ai-adapter skill link-agent database-schema reviewer
```

### `ai-adapter mcp`

MCP サーバー設定を管理します。

| コマンド | 説明 |
|---------|------|
| `mcp add <name>` | MCP サーバー設定を追加（`--command`, `--args` 等） |
| `mcp load --file <path>` | `.mcp.json` から MCP サーバー設定を一括読み込み |
| `mcp remove <name>` | MCP サーバー設定を削除 |
| `mcp list` | MCP サーバー一覧を表示（`--tool`, `--env` でフィルタ） |
| `mcp export --path <dir>` | MCP 設定を `.mcp.json` に出力（--path省略時はカレントディレクトリ） |
| `mcp enable <name>` | MCP サーバーを有効化 |
| `mcp disable <name>` | MCP サーバーを無効化 |\n| `mcp remove-all` | 全ての MCP サーバー設定を削除（`--force` 対応） |

```bash
# 対話的追加
ai-adapter mcp add github --command npx --args @modelcontextprotocol/server-github

# .mcp.json から一括読み込み
echo '{"mcpServers":{"github":{"command":"npx","args":["@modelcontextprotocol/server-github"]}}}' > .mcp.json
ai-adapter mcp load

# 一覧表示
ai-adapter mcp list

# カレントディレクトリに出力
ai-adapter mcp export
# 指定ディレクトリに出力
ai-adapter mcp export --path /path/to/project
```

### `ai-adapter opencode`

OpenCode 連携設定を管理します。

| コマンド | 説明 |
|---------|------|
| `opencode alias` | `.opencode` → `.github` のシンボリックリンクを作成 |
| `opencode install` | `opencode.json` をカレントディレクトリに生成 |
| `opencode uninstall` | `opencode.json` を削除 |

```bash
# .opencode から .github へのエイリアスを作成
ai-adapter opencode alias

# opencode.json テンプレートを生成
ai-adapter opencode install

# 削除
ai-adapter opencode uninstall
```

### `ai-adapter export`

カレントプロジェクトの `.github/bin/` を PATH に追加するシェル設定を出力・適用します。
これにより `.github/bin/add_task.sh` を `add_task.sh` として直接実行できるようになります。

```bash
# 対話的にシェル設定ファイルを選択
ai-adapter export

# 直接 zshrc に書き込む
ai-adapter export --shell zshrc
ai-adapter export --shell bash_profile
```

### `ai-adapter uninstall`

`~/.ai-adapter/` を削除して初期状態に戻します。

| オプション | 説明 |
|-----------|------|
| `--force` | 確認プロンプトを表示せずに削除 |
| `--keep-git` | Git リポジトリ（`.git`）を保持してデータのみ削除 |

```bash
ai-adapter uninstall
ai-adapter uninstall --force
ai-adapter uninstall --keep-git
```

### `ai-adapter sync`

`~/.ai-adapter/` を GitHub リモートと同期します。

```bash
ai-adapter sync
```

内部では以下の処理を実行します：
1. Git リポジトリ確認（未初期化なら `git init`）
2. `git add -A && git commit`
3. `git pull --rebase origin main`
4. `git push origin main`

---

## データ保存先

すべてのデータは `~/.ai-adapter/` に保存されます。

```
~/.ai-adapter/
├── config.json                 # メイン設定ファイル
├── agents/                     # AIエージェント指示ファイル
│   ├── reviewer.md
│   ├── implementer.md
│   └── researcher.md
├── bin/                        # スクリプトファイル
│   ├── deploy-prod.sh
│   └── deploy-staging.sh
├── skills/                     # スキルディレクトリ
│   ├── database-schema/
│   │   ├── SKILL.md
│   │   └── examples/
│   └── security-review/
│       └── SKILL.md
└── mcp/                        # MCP サーバー設定
    └── servers.json
```

このディレクトリを Git リポジトリ化し、GitHub を介して複数PC間で同期できます。

### 環境解決の優先順位

`bin` コマンドで `[env]` を省略した場合：

1. 明示的に `--agent` オプションが指定されていれば、そのエージェントの紐付け環境を使用
2. `agent_bindings` に該当エージェントが存在すれば、その紐付け環境を使用
3. 上記いずれもなければ `default_env`（デフォルトは `"default"`）を使用

---

## 設定ファイル

`~/.ai-adapter/config.json` に全設定が保存されます。

```json
{
  "version": 1,
  "default_env": "default",
  "agent_bindings": [
    { "agent": "reviewer", "env": "myhome" },
    { "agent": "implementer", "env": "office" }
  ],
  "agents": [
    { "name": "reviewer", "description": "コードレビュー用エージェント" },
    { "name": "implementer", "description": "実装用エージェント" }
  ],
  "envs": [
    { "name": "default", "description": "デフォルト環境" },
    { "name": "myhome", "description": "自宅開発環境" },
    { "name": "office", "description": "会社開発環境" }
  ],
  "bins": [
    { "name": "deploy-prod.sh", "env": "myhome", "description": "本番デプロイ" },
    { "name": "format-all.sh", "env": "default", "description": "コード整形" }
  ],
  "skills": [
    {
      "name": "database-schema",
      "description": "DBスキーマ設計・レビューの知識",
      "path": "skills/database-schema",
      "tags": ["database", "prisma", "schema"],
      "agent": "reviewer"
    }
  ],
  "mcp_servers": [
    {
      "name": "github",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env_keys": ["GITHUB_TOKEN"],
      "enabled": true,
      "tools": ["vscode", "claude", "cursor"]
    }
  ]
}
```

---

## ユースケース

### 会社と家で LLM 設定ファイルを共有

```bash
# 会社のPC
ai-adapter init
ai-adapter agent add ~/company-agent.md
ai-adapter env add office
ai-adapter sync

# 家のPC
git clone <your-ai-adapter-repo> ~/.ai-adapter
ai-adapter agent get company-agent   # → .github/agents/company-agent.md
```

### 新PCへの移行

```bash
# 新PC
git clone <your-ai-adapter-repo> ~/.ai-adapter
ai-adapter bin list                  # 登録済みスクリプトを確認
ai-adapter bin get deploy-prod       # 必要なスクリプトを展開
```

### プロジェクトごとに異なるエージェント設定

```bash
ai-adapter env add project-a
ai-adapter env add project-b
ai-adapter agent add reviewer-a.md
ai-adapter env link-agent reviewer-a project-a

# project-a で実行すると自動的に project-a 環境が使われる
cd /path/to/project-a
ai-adapter bin add deploy.sh
```

---

## 開発

### 開発環境

```bash
uv sync
uv pip install -e .
```

### テスト実行

```bash
# 全テスト
uv run python -m unittest discover tests

# 特定ファイル
uv run python -m unittest tests/test_env.py

# 詳細表示
uv run python -m unittest discover tests -v
```

### リンター・型チェック

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

---

## プロジェクト構成

```
ai-adapter/
├── pyproject.toml              # プロジェクト設定・依存・エントリーポイント
├── README.md                   # このファイル
├── LICENSE                     # MIT ライセンス
├── .gitignore                  # Git 除外設定
├── src/
│   └── ai_adapter/
│       ├── __init__.py         # バージョン情報
│       ├── __main__.py         # python -m ai_adapter 対応
│       ├── cli.py              # CLI エントリーポイント
│       ├── config.py           # ~/.ai-adapter/config.json の読み書き
│       ├── models.py           # データモデル（dataclass）
│       ├── agent.py            # agent サブコマンド
│       ├── env.py              # env サブコマンド
│       ├── bin.py              # bin サブコマンド
│       ├── skill.py            # skill サブコマンド
│       ├── mcp.py              # mcp サブコマンド
│       ├── sync.py             # sync コマンド（GitHub同期）
│       └── git.py              # Git 操作ラッパー
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_agent.py
│   ├── test_env.py
│   ├── test_bin.py
│   ├── test_skill.py
│   ├── test_mcp.py
│   ├── test_sync.py
│   ├── test_git.py
│   └── test_cli.py
└── examples/
    └── sample-config.json      # サンプル設定ファイル
```

---

## 技術スタック

| 項目 | 採用技術 |
|------|---------|
| 言語 | Python 3.10+ |
| CLI フレームワーク | Click |
| 設定ファイル | JSON（標準ライブラリ） |
| テスト | unittest（標準ライブラリ） |
| パッケージ管理 | uv |

---

## ライセンス

MIT License
