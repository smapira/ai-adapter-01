# 開発者向け指示書 — ai-adapter

> **プロジェクト**: AIエージェント・スクリプトの共通管理基盤 CLI ツール  
> **言語**: Python 3.10+  
> **パッケージ管理**: uv  
> **CLI フレームワーク**: Click  
> **設定ファイル**: YAML (`~/.ai-adapter/config.yaml`)  
> **テスト**: unittest  
> **ライセンス**: MIT

---

## 1. 開発環境のセットアップ

### 前提条件

- Python 3.10 以上がインストール済みであること
- [uv](https://docs.astral.sh/uv/) がインストール済みであること

```bash
# uv のインストール（未導入の場合）
curl -LsSf https://astral.sh/uv/install.sh | sh

# バージョン確認
uv --version
python3 --version
```

### リポジトリのクローンと初期設定

```bash
# クローン
git clone <repository-url>
cd ai-adapter

# 仮想環境の作成と同期
uv sync

# 動作確認（開発モードでインストール）
uv pip install -e .

# ヘルプ表示
ai-adapter --help
```

### 開発用コマンド集

| 目的 | コマンド |
|------|---------|
| 仮想環境の同期 | `uv sync` |
| 全テスト実行 | `uv run python -m unittest discover tests` |
| 特定テスト実行 | `uv run python -m unittest tests/test_config.py` |
| lint チェック | `uv run ruff check .` |
| 型チェック | `uv run mypy src/` |
| 書式整形 | `uv run ruff format .` |

---

## 2. データ保存先の設計（最重要）

**すべてのデータは `~/.ai-adapter/` ディレクトリに保存する。**

### ディレクトリ構成

```
~/.ai-adapter/
├── config.yaml                 # メイン設定ファイル
├── agents/                     # AIエージェント指示ファイル（add agent の保存先）
│   ├── reviewer.md
│   ├── implementer.md
│   └── researcher.md
├── env/                        # 環境設定（add env の保存先）
│   └── ...                     # （名前のみ or 設定ファイル）
└── bin/                        # スクリプトファイル（add bin のコピー先）
    ├── deploy-prod.sh
    ├── deploy-staging.sh
    └── ...
```

### 各コマンドのデータフロー

```
# agent: 外部 → ~/.ai-adapter/ → プロジェクトへ展開
ai_adapter.py add agent X.md    →  X.md を ~/.ai-adapter/agents/ にコピー
ai_adapter.py get agent XXXX    →  ~/.ai-adapter/agents/XXXX.md を .github/agents/ にコピー
ai_adapter.py del agent XXXX    →  ~/.ai-adapter/agents/XXXX.md を削除（config からも削除）

# env: 名前管理 + デフォルト設定 + ユーザー紐付け
ai_adapter.py add env X         →  config.yaml に env 名を保存
ai_adapter.py list              →  config.yaml から env 一覧を表示（* 付きでデフォルト環境）
ai_adapter.py del env X         →  config.yaml から env 名を削除（デフォルト環境は削除不可）
ai_adapter.py set-default X     →  config.yaml の default_env を更新
ai_adapter.py link-user <U> <E> →  config.yaml の user_bindings に追加

# bin: 外部 → ~/.ai-adapter/ → プロジェクトへ展開（env 省略可）
ai_adapter.py add bin [env] X.sh →  X.sh を ~/.ai-adapter/bin/ にコピー（env補完→ユーザー→デフォルト）
ai_adapter.py get bin [env] X    →  ~/.ai-adapter/bin/X を .github/bin/ にコピー（env補完→ユーザー→デフォルト）
ai_adapter.py list bin [env]     →  ~/.ai-adapter/bin/ の一覧を表示（省略時は全環境）
ai_adapter.py del bin [env] X    →  ~/.ai-adapter/bin/X を削除（config からも削除）

# sync: ~/.ai-adapter/ 全体を GitHub リモートと同期
ai_adapter.py sync               →  ~/.ai-adapter/ を git push/pull
```

### 環境解決の優先順位（bin コマンドで env 省略時）

```
bin コマンド実行
  │
  ├─ env が明示指定されている → その env を使用
  │
  └─ env が省略されている
       ├─ OS ユーザー名が user_bindings に存在 → その紐付け env を使用
       └─ 存在しない → config.default_env を使用
```

### なぜ `~/.ai-adapter/` なのか

| ユースケース | 仕組み |
|-------------|--------|
| 会社と家で設定を共有 | `~/.ai-adapter/` を Git リポジトリ化し、GitHub を介して同期（`sync` コマンド） |
| 新PCに移行 | `git clone <url> ~/.ai-adapter` するだけ |
| プロジェクトごとに展開 | `get agent` / `get bin` で必要なファイルだけ `.github/` に取り出す |

---

## 3. CLI コマンド設計

### 全体構造

```
ai-adapter
  ├── init                      # ~/.ai-adapter/ の初期化
  ├── status                    # 現在の状態表示
  ├── agent
  │   ├── list                  # エージェント一覧
  │   ├── add <path>            # エージェントファイルを ~/.ai-adapter/agents/ に追加
  │   ├── get <name>            # エージェントを .github/agents/ にコピー
  │   └── remove <name>         # エージェント削除
  ├── env
  │   ├── list                  # 環境一覧（* 付きでデフォルト環境を表示）
  │   ├── default               # 現在のデフォルト環境を表示
  │   ├── set-default <name>    # デフォルト環境を変更
  │   ├── add <name>            # 環境名を追加
  │   ├── remove <name>         # 環境名を削除（デフォルトは削除不可）
  │   ├── link-user <user> <env>  # OSユーザー名と環境を紐付け
  │   └── unlink-user <user>    # ユーザーと環境の紐付けを解除
  ├── bin
  │   ├── list [env]            # スクリプト一覧（省略時はデフォルト環境）
  │   ├── add [env] <path>      # スクリプトを ~/.ai-adapter/bin/ にコピー
  │   ├── get [env] <name>      # スクリプトを .github/bin/ にコピー
  │   └── remove [env] <name>   # スクリプト削除
  └── sync                      # ~/.ai-adapter/ を GitHub リモートと同期
```

### README のコマンドとの対応

| README | 実際のコマンド | 動作 |
|--------|---------------|------|
| `add agent PATH` | `ai-adapter agent add PATH` | `~/.ai-adapter/agents/` にコピー |
| `get agent XXXX` | `ai-adapter agent get XXXX` | `~/.ai-adapter/agents/` → `.github/agents/` にコピー |
| `del agent XXXX` | `ai-adapter agent remove XXXX` | `~/.ai-adapter/agents/` から削除 |
| `add env X` | `ai-adapter env add X` | `config.yaml` に env 名を保存 |
| `list` (env) | `ai-adapter env list` | env 一覧を表示（* 付きでデフォルト環境） |
| `del env X` | `ai-adapter env remove X` | `config.yaml` から env 名を削除（デフォルトは削除不可） |
| `add bin [env] PATH` | `ai-adapter bin add [env] PATH` | `~/.ai-adapter/bin/` にコピー（env 省略時は環境解決） |
| `get bin [env] SCRIPT` | `ai-adapter bin get [env] SCRIPT` | `~/.ai-adapter/bin/` → `.github/bin/` にコピー（env 省略時は環境解決） |
| `list bin [env]` | `ai-adapter bin list [env]` | `~/.ai-adapter/bin/` の一覧表示（省略時は全環境） |
| `del bin [env] SCRIPT` | `ai-adapter bin remove [env] SCRIPT` | `~/.ai-adapter/bin/` から削除（env 省略時は環境解決） |
| `sync` | `ai-adapter sync` | `~/.ai-adapter/` を GitHub と同期 |

### 追加コマンド一覧（README にはないが実装するもの）

| コマンド | 動作 |
|---------|------|
| `env default` | 現在のデフォルト環境名を表示 |
| `env set-default <name>` | デフォルト環境を変更 |
| `env link-user <user> <env>` | OS ユーザーと環境を紐付け |
| `env unlink-user <user>` | OS ユーザーと環境の紐付けを解除 |

---

## 4. プロジェクト構造

```
ai-adapter/
├── pyproject.toml              # プロジェクト設定・依存・エントリーポイント
├── README.md                   # プロジェクト説明
├── LICENSE                     # MIT ライセンス
├── CONTRIBUTING.md             # コントリビューションガイド（フェーズ4）
├── CHANGELOG.md                # バージョン履歴（フェーズ4）
├── .gitignore                  # Git 除外設定
├── src/
│   └── ai_adapter/
│       ├── __init__.py         # __version__ = "0.1.0"
│       ├── __main__.py         # python -m ai_adapter 対応
│       ├── cli.py              # Click グループ定義
│       ├── config.py           # ConfigManager: ~/.ai-adapter/config.yaml の読み書き
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
│   └── test_cli.py             # CliRunner 統合テスト
└── examples/
    └── sample-config.yaml      # サンプル設定ファイル
```

---

## 5. 開発の進め方（実装順序）

### フェーズ 1 — プロジェクト基盤

| Step | 内容 | ファイル | 並列可否 |
|------|------|---------|---------|
| 1.1 | プロジェクトスキャフォールディング | `pyproject.toml`, `.gitignore`, ディレクトリ構造 | 不可 |
| 1.2 | データモデル定義 | `src/ai_adapter/models.py` | 1.3, 1.4, 1.5 と並列可 |
| 1.3 | 設定ファイル管理 | `src/ai_adapter/config.py` | 1.2 と並列可 |
| 1.4 | CLI エントリーポイント | `src/ai_adapter/cli.py` | 1.3 と並列可 |
| 1.5 | テスト基盤 | `tests/` 一式 | 全 Step と並列可 |

### フェーズ 2 — コア機能

| Step | 内容 | 依存 | 並列可否 |
|------|------|------|---------|
| 2.1 | `agent` コマンド | 1.2, 1.3, 1.4 | 2.2, 2.3 と並列可 |
| 2.2 | `env` コマンド | 1.2, 1.3, 1.4 | 2.1, 2.3 と並列可 |
| 2.3 | `bin` コマンド | 1.2, 1.3, 1.4 | 2.1, 2.2 と並列可 |

### フェーズ 3 — 基盤機能

| Step | 内容 | 依存 | 並列可否 |
|------|------|------|---------|
| 3.1 | `init` / `status` コマンド | フェーズ2完了 | 3.2 と並列可 |
| 3.2 | `sync` コマンド（GitHub同期） | `git.py` | 3.1 と並列可 |
| 3.3 | `git.py`（Git操作ラッパー） | なし | 3.1, 3.2 と並列可 |

### フェーズ 4 — 品質・公開準備

| Step | 内容 | 依存 |
|------|------|------|
| 4.1 | ログ・エラーハンドリング統一 | フェーズ2,3完了 |
| 4.2 | テスト充実 | フェーズ2,3完了 |
| 4.3 | ドキュメント整備 | — |
| 4.4 | PyPI 公開準備 | — |

---

## 6. データモデル設計

### Config の YAML 構造

```yaml
# ~/.ai-adapter/config.yaml
version: 1
default_env: default              # デフォルト環境の名前
user_bindings:
  - user: smapira                # OSのユーザー名
    env: myhome                  # 紐付ける環境名
  - user: smapira-office
    env: office
agents:
  - name: reviewer
    description: "コードレビュー用エージェント"
  - name: implementer
    description: "実装用エージェント"
envs:
  - name: default                 # デフォルト環境（init 時に自動生成、削除不可）
    description: "デフォルト環境"
  - name: myhome
    description: "自宅開発環境"
  - name: office
    description: "会社開発環境"
bins:
  - name: deploy-prod.sh
    env: myhome
    description: "本番デプロイ"
  - name: deploy-staging.sh
    env: myhome
    description: "ステージングデプロイ"
  - name: format-all.sh
    env: default
    description: "コード整形"
```

### Python dataclass 定義

```python
@dataclass
class Agent:
    name: str
    description: str = ""

@dataclass
class Env:
    name: str
    description: str = ""
    is_default: bool = False      # デフォルト環境かどうか

@dataclass
class UserBinding:
    user: str                     # OS ユーザー名（getpass.getuser()）
    env: str                      # 紐付ける環境名

@dataclass
class Bin:
    name: str
    env: str | None = None
    description: str = ""

@dataclass
class Config:
    version: int = 1
    agents: list[Agent] = field(default_factory=list)
    envs: list[Env] = field(default_factory=list)
    bins: list[Bin] = field(default_factory=list)
    default_env: str = "default"  # デフォルト環境名
    user_bindings: list[UserBinding] = field(default_factory=list)
```

各 dataclass に `to_dict()` / `from_dict()` メソッドを実装し、YAML とのシリアライズを可能にすること。

---

## 7. 各コマンドの実装詳細

### 共通: 環境解決ロジック

`bin` コマンドで `[env]` が省略された場合の環境解決順序:

1. カレントOSユーザー名（`getpass.getuser()`）が `user_bindings` に存在すれば、その env を使用
2. 存在しなければ `config.default_env` の値（デフォルトは `"default"`）を使用

```python
import getpass
from pathlib import Path

def resolve_env(config: Config, env_arg: str | None) -> str:
    """env 引数が省略された場合に、ユーザー紐付け → デフォルト環境 の順で解決する"""
    if env_arg:
        return env_arg
    # ユーザー紐付けをチェック
    current_user = getpass.getuser()
    for binding in config.user_bindings:
        if binding.user == current_user:
            return binding.env
    # デフォルト環境を返す
    return config.default_env
```

### `init`

1. `~/.ai-adapter/` + `agents/` + `bin/` ディレクトリを作成
2. `config.yaml` が存在しなければ、デフォルト設定で初期化:
   - `default_env: "default"`
   - `envs` に `name: default, description: "デフォルト環境"` を自動登録
   - `user_bindings` は空
3. 既存の設定があれば上書きしない

### `agent add <path>`

1. `<path>` のファイルを `~/.ai-adapter/agents/` にコピー
2. `config.yaml` の `agents` にエントリを追加
3. ファイル名（拡張子除く）をエージェント名として使用

### `agent get <name>`

1. `config.yaml` からエージェント名を検索
2. `~/.ai-adapter/agents/<name>.md` をカレントプロジェクトの `.github/agents/<name>.md` にコピー
3. コピー先ディレクトリが存在しなければ作成

### `env add <name>`

1. 同名の env が既に存在すればエラー
2. `config.yaml` の `envs` に新しい Env を追加

### `env remove <name>`

1. env が存在しなければエラー
2. `is_default == True` の env は削除不可（デフォルト環境は削除できない）
3. `bins` でこの env を参照しているものがなければ削除
4. 参照がある場合は警告メッセージを表示してから削除（または削除をブロック）

### `env default`

1. 現在の `config.default_env` を表示

### `env set-default <name>`

1. 指定された env が存在するか確認
2. 存在すれば `config.default_env` を更新
3. 存在しなければエラー

### `env link-user <user> <env>`

1. 指定された env が存在するか確認
2. 同名のユーザー紐付けが既にあれば上書き
3. `user_bindings` に新しい UserBinding を追加
4. 使用例:
   ```bash
   ai-adapter env link-user "$(whoami)" myhome
   # → このPCでは自動的に myhome 環境が使われる
   ```

### `env unlink-user <user>`

1. 指定されたユーザーの紐付けを削除
2. 存在しなければエラー

### `bin add [env] <path>`

1. `[env]` が省略された場合は環境解決ロジックで補完
2. `<path>` のファイルを `~/.ai-adapter/bin/` にコピー
3. `config.yaml` の `bins` にエントリを追加（env 名も記録）

### `bin get [env] <name>`

1. `[env]` が省略された場合は環境解決ロジックで補完
2. `config.yaml` から env + name でスクリプトを検索
3. `~/.ai-adapter/bin/<name>` を `.github/bin/<name>` にコピー
4. コピー先ディレクトリが存在しなければ作成

### `bin list [env]`

1. `[env]` が省略された場合は全環境のスクリプトを表示
2. 指定された場合はフィルタリングして表示

### `bin remove [env] <name>`

1. `[env]` が省略された場合は環境解決ロジックで補完
2. `config.yaml` からエントリを削除
3. `~/.ai-adapter/bin/<name>` のファイルは削除しない（config 登録のみ解除）

### `sync`

1. `~/.ai-adapter/` が Git リポジトリとして初期化されているか確認
2. 未初期化なら `git init` を実行し、リモート登録を促す
3. `git add -A && git commit` でローカルの変更をコミット
4. `git pull --rebase` でリモートの変更を取り込み
5. `git push` でローカルの変更を反映

---

## 8. コーディング規約

### Python スタイル

- **Python 3.10+** の型ヒントを積極的に使用する（`| None` 構文、`list[str]` など）
- 文字列は **ダブルクォート** `"` を優先する
- 1行あたり最大 **120文字**
- インデントは **4スペース**
- 命名規則:
  - クラス: `PascalCase`
  - 関数・変数: `snake_case`
  - 定数: `UPPER_SNAKE_CASE`
  - プライベート: `_leading_underscore`

### モジュール分割ルール

- **`models.py`**: dataclass 定義と YAML シリアライズのみ。ビジネスロジックは書かない。
- **`config.py`**: `~/.ai-adapter/config.yaml` の読み書き・バリデーション。
- **`cli.py`**: Click グループとサブコマンドの定義。薄く保つ。
- **`agent.py` / `env.py` / `bin.py`**: 各サブコマンドの実装。ファイルコピー操作を含む。
- **`sync.py`**: GitHub 同期ロジック。`git.py` を利用。
- **`git.py`**: `subprocess` で git コマンドをラップ。

### エラーハンドリング

- ユーザー向けエラーは `click.ClickException` を継承したカスタム例外を使用
- 予期せぬエラーは `logging` モジュールで記録
- 終了コードは一貫させる（成功: 0, ユーザーエラー: 1, システムエラー: 2）

---

## 9. テスト方針

### フレームワーク

- **unittest**（標準ライブラリ）
- CLI テストには **Click の `CliRunner`** を使用

### テストファイル対応表

| テストファイル | テスト対象 | テクニック |
|--------------|-----------|-----------|
| `test_config.py` | `config.py` | `tempfile.TemporaryDirectory` + `monkeypatch` で `~/.ai-adapter` を一時ディレクトリに差し替え |
| `test_agent.py` | `agent.py` | ファイルのコピー・削除の検証 |
| `test_env.py` | `env.py` | CRUD操作の検証 |
| `test_bin.py` | `bin.py` | ファイルコピー・削除・一覧表示の検証 |
| `test_sync.py` | `sync.py` | `subprocess` 呼び出しのモック化 |
| `test_git.py` | `git.py` | `subprocess` 呼び出しのモック化 |
| `test_cli.py` | `cli.py` | `CliRunner` で CLI 統合テスト |

### テスト実行

```bash
# 全テスト実行
uv run python -m unittest discover tests

# 特定ファイルのみ
uv run python -m unittest tests/test_config.py

# 詳細表示（-v）
uv run python -m unittest discover tests -v
```

---

## 10. config.py の実装詳細

### 設定ディレクトリのパス解決

```python
import os
from pathlib import Path

AI_ADAPTER_DIR = Path.home() / ".ai-adapter"

def get_config_path() -> Path:
    """設定ファイルのパスを返す。"""
    env = os.environ.get("AI_ADAPTER_CONFIG")
    if env:
        return Path(env)
    return AI_ADAPTER_DIR / "config.yaml"

def get_agents_dir() -> Path:
    return AI_ADAPTER_DIR / "agents"

def get_bins_dir() -> Path:
    return AI_ADAPTER_DIR / "bin"
```

### `init` コマンドの処理

```python
def init():
    """~/.ai-adapter/ ディレクトリを初期化"""
    dirs = [
        AI_ADAPTER_DIR,
        AI_ADAPTER_DIR / "agents",
        AI_ADAPTER_DIR / "bin",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    # config.yaml が存在しなければデフォルト設定を書き込み
    if not get_config_path().exists():
        config = Config(
            version=1,
            default_env="default",
            envs=[
                Env(name="default", description="デフォルト環境"),
            ],
            user_bindings=[],
        )
        save_config(config)
```

---

## 11. Git 運用ルール

### ブランチ戦略

- `main`: リリースブランチ。常に安定。
- `feat/xxx`: 機能開発ブランチ。
- `fix/xxx`: バグ修正ブランチ。

### コミットメッセージのプレフィックス

| プレフィックス | 用途 |
|--------------|------|
| `feat:` | 新機能 |
| `fix:` | バグ修正 |
| `docs:` | ドキュメント |
| `test:` | テスト |
| `refactor:` | リファクタリング |
| `chore:` | ビルド・CI・ツール |

### 開発の流れ

1. `main` ブランチから作業ブランチを作成
2. 実装 + テスト
3. `uv run python -m unittest discover tests` で全テスト PASS 確認
4. PR 作成 → レビュー → `main` にマージ

---

## 12. `sync` コマンドの設計（重要）

### 処理フロー

```
ai-adapter sync
  │
  ├─ Step 1: ~/.ai-adapter/ が Git リポジトリか確認
  │   ├─ Yes → そのまま
  │   └─ No  → git init + リモート登録を促すメッセージ
  │
  ├─ Step 2: git add -A && git commit
  │   └─ 変更がない場合はスキップ
  │
  ├─ Step 3: git pull --rebase origin main
  │   └─ コンフリクトがあればユーザーに手動解決を促す
  │
  └─ Step 4: git push origin main
```

### リモートリポジトリの管理

- リモートURLは `config.yaml` の `remote` フィールドに保存する案と、`git remote` で管理する案がある
- シンプルさ優先で **`git remote` で管理** とする
- `sync` 初回実行時にリモートが未設定なら設定を促す

### コンフリクト対応

- `pull --rebase` でコンフリクトが発生した場合は `git rebase --abort` してエラーメッセージを表示
- ユーザーに手動解決を促す（自動解決は行わない）

---

## 13. 検証手順（リリース前チェックリスト）

- [ ] `uv run python -m unittest discover tests` が全件 PASS
- [ ] `ai-adapter init` で `~/.ai-adapter/` + `agents/` + `bin/` が生成される
- [ ] `ai-adapter agent add test.md` で `~/.ai-adapter/agents/` にコピーされる
- [ ] `ai-adapter agent get test` で `.github/agents/test.md` にコピーされる
- [ ] `ai-adapter env add myenv` で env が追加される
- [ ] `ai-adapter env list` で env 一覧が表示される
- [ ] `ai-adapter env default` でデフォルト環境名が表示される
- [ ] `ai-adapter env set-default myenv` でデフォルト環境が変更される
- [ ] `ai-adapter env link-user $(whoami) myenv` でユーザーと環境が紐付く
- [ ] `ai-adapter env unlink-user $(whoami)` で紐付けが解除される
- [ ] デフォルト環境 (`default`) は削除できない
- [ ] `ai-adapter bin add script.sh` で `~/.ai-adapter/bin/` にコピーされる
- [ ] `ai-adapter bin get script.sh` で `.github/bin/script.sh` にコピーされる
- [ ] `ai-adapter bin list` でスクリプト一覧が表示される
- [ ] `ai-adapter del agent/bin/env` で該当エントリが削除される
- [ ] `ai-adapter sync` で Git 同期が実行される（または未初期化の促し）
- [ ] `README.md` の全コマンドが正常動作する

---

## 14. README のコマンドとの対応（リファレンス）

```
# agent: ~/.ai-adapter/agents/ が実体保存先
add agent PATH   →  PATH を ~/.ai-adapter/agents/ にコピー
get agent NAME   →  ~/.ai-adapter/agents/NAME.md → .github/agents/NAME.md にコピー
del agent NAME   →  ~/.ai-adapter/agents/NAME.md を削除

# env: config.yaml で管理（デフォルト環境 + ユーザー紐付け）
add env NAME     →  config.yaml に env 名を追加
list             →  config.yaml の env 一覧を表示（* デフォルト環境）
del env NAME     →  config.yaml から env 名を削除（デフォルトは削除不可）
default          →  現在のデフォルト環境名を表示
set-default NAME →  デフォルト環境を変更
link-user U E    →  OS ユーザー U を環境 E に紐付け
unlink-user U    →  OS ユーザー U の紐付けを解除

# bin: ~/.ai-adapter/bin/ が実体保存先（env 省略時は環境解決）
add bin [env] PATH   →  PATH を ~/.ai-adapter/bin/ にコピー
get bin [env] NAME   →  ~/.ai-adapter/bin/NAME → .github/bin/NAME にコピー
list bin [env]       →  スクリプト一覧表示（省略時は全環境）
del bin [env] NAME   →  ~/.ai-adapter/bin/NAME の登録を解除（ファイルは残す）

# sync
sync             →  ~/.ai-adapter/ を git push/pull で GitHub と同期
```
