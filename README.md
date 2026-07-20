# ai-adapter

**AIエージェント・スクリプトの共通管理基盤 CLI ツール**

CLI で操作し、AIエージェントの指示ファイル（`.github/instructions` 等）やスクリプトをグループ単位で管理。環境を切り替えて簡単に共有・移行できます。

---

## 特徴

- **集中管理**: すべてのデータは `~/.ai-adapter/` に集約。プロジェクトを跨いで設定を一元管理
- **環境切り替え**: 会社・自宅など環境ごとにエージェント設定やスクリプトを切り替え
- **GitHub 同期**: `ai-adapter sync` で `~/.ai-adapter/` を GitHub リモートと同期。チーム共有やPC移行が簡単
- **エージェント紐付け**: エージェント名と環境を紐付け、コンテキストに応じた自動解決

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

# 5. プロジェクトに展開
cd your-project
ai-adapter agent get reviewer      # → .github/agents/reviewer.md
ai-adapter bin get myhome deploy   # → .github/bin/deploy.sh

# 6. GitHub と同期（設定を共有）
ai-adapter sync
```

---

## コマンドリファレンス

### `ai-adapter init`

`~/.ai-adapter/` ディレクトリと設定ファイルを初期化します。

```bash
ai-adapter init
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
| `agent list` | 登録済みエージェント一覧を表示 |
| `agent remove <name>` | エージェントを削除（`--keep-file` でファイル保持） |

```bash
ai-adapter agent add ~/dotfiles/agents/reviewer.md
ai-adapter agent list
ai-adapter agent get reviewer
ai-adapter agent remove reviewer
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

```bash
ai-adapter env add office
ai-adapter env list
ai-adapter env set-default office
ai-adapter env link-agent reviewer office
```

### `ai-adapter bin`

スクリプトファイルを管理します。`[env]` は省略可能で、その場合は環境解決ロジックが動作します。

| コマンド | 説明 |
|---------|------|
| `bin add [env] <path>` | スクリプトを `~/.ai-adapter/bin/` に追加 |
| `bin get [env] <name>` | スクリプトを `.github/bin/` にコピー |
| `bin list [env]` | スクリプト一覧を表示（省略時は全環境） |
| `bin remove [env] <name>` | スクリプトの登録を解除（ファイルは保持） |

```bash
ai-adapter bin add myhome ~/scripts/deploy.sh
ai-adapter bin list
ai-adapter bin get deploy
ai-adapter bin remove deploy
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
└── bin/                        # スクリプトファイル
    ├── deploy-prod.sh
    └── deploy-staging.sh
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
│       ├── sync.py             # sync コマンド（GitHub同期）
│       └── git.py              # Git 操作ラッパー
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_agent.py
│   ├── test_env.py
│   ├── test_bin.py
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
