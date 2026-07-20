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

## 2. プロジェクト構造

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
│       ├── cli.py              # Click グループ定義 + plugin ロード
│       ├── config.py           # ConfigManager: 設定読み書き
│       ├── models.py           # Script, Group, InstructionSet, Config
│       ├── group.py            # group サブコマンド
│       ├── script.py           # script サブコマンド
│       ├── instructions.py     # instructions サブコマンド
│       ├── git.py              # Git 操作ラッパー
│       └── plugin.py           # プラグイン管理
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_group.py
│   ├── test_script.py
│   ├── test_instructions.py
│   ├── test_git.py
│   ├── test_plugin.py
│   └── test_cli.py             # CliRunner 統合テスト
└── examples/
    └── sample-config.yaml      # サンプル設定ファイル
```

---

## 3. データ保存先の設計（最重要）

**すべてのデータは `~/.ai-adapter/` ディレクトリに保存する。**

### ディレクトリ構成

```
~/.ai-adapter/
├── config.yaml                 # メイン設定ファイル（グループ・スクリプト・指示セット管理）
└── instructions/               # 指示セット（agent）の実体ファイル格納先
    ├── code-assist.md
    ├── review.md
    └── ...
```

### なぜ `~/.ai-adapter/` なのか

| ユースケース | 課題 | 解決策 |
|-------------|------|--------|
| 会社と家で同じLLM設定を使いたい | プロジェクト単位だと共有が面倒 | `~/.ai-adapter/` に一元保存し、`.github/instructions/` にシンボリックリンク or コピー |
| 新PCに設定を移行したい | 設定が各プロジェクトに散らばっている | `~/.ai-adapter/` ごとコピーすれば移行完了 |
| GitHubで設定を管理したい | グローバル設定はGit管理しづらい | `git init` & `git remote add` で `~/.ai-adapter/` 自体をGitリポジトリ化可能 |

### 設定ファイルのパス

- **パス**: `~/.ai-adapter/config.yaml`
- **環境変数でオーバーライド可能**（必要に応じて）: `AI_ADAPTER_CONFIG=/path/to/config.yaml`
- 設定ファイルが見つからない場合は `ai-adapter init` で新規作成する

---

## 4. CLI コマンド設計

### 全体構造

```
ai-adapter
  ├── init                      # ~/.ai-adapter/ の初期化
  ├── status                    # 現在の状態表示
  ├── group
  │   ├── list                  # グループ一覧
  │   ├── create <name>         # グループ作成
  │   ├── delete <name>         # グループ削除
  │   ├── rename <old> <new>    # グループ名変更
  │   └── show <name>           # グループ詳細（スクリプト一覧含む）
  ├── script
  │   ├── list [group]          # スクリプト一覧（グループ指定でフィルタ）
  │   ├── add <group> <path>    # スクリプト追加
  │   ├── remove <group> <name> # スクリプト削除
  │   ├── run <group> <name>    # スクリプト実行
  │   └── show <group> <name>   # スクリプト詳細
  ├── instructions
  │   ├── list                  # 指示セット一覧
  │   ├── use <name>            # 指示セット切替
  │   ├── show [name]           # 指示セット内容表示
  │   ├── add <path>            # 指示セット追加
  │   └── remove <name>         # 指示セット削除
  └── plugin
      ├── list                  # 有効プラグイン一覧
      └── info <name>           # プラグイン詳細
```

### README の希望コマンドとの対応

| README での希望 | 実際のコマンド | データの保存先 |
|----------------|---------------|---------------|
| `ai_adapter.py add agent X` | `ai-adapter instructions add X` | `~/.ai-adapter/instructions/` にコピー + `config.yaml` に登録 |
| `ai_adapter.py get agent X` | `ai-adapter instructions use X` | `config.yaml` の `current` を更新 |
| `ai_adapter.py del agent X` | `ai-adapter instructions remove X` | `config.yaml` から削除（ファイルはオプションで残せる） |
| `ai_adapter.py add env X` | `ai-adapter group create X` | `config.yaml` にグループを追加 |
| `ai_adapter.py list` | `ai-adapter group list` | `config.yaml` から読み取り |
| `ai_adapter.py del env X` | `ai-adapter group delete X` | `config.yaml` からグループを削除 |
| `ai_adapter.py add bin [env] X` | `ai-adapter script add [group] X` | `config.yaml` にスクリプトパスを追加 |
| `ai_adapter.py get bin [env] X` | `ai-adapter script run [group] X` | `config.yaml` からパスを読み取り実行 |
| `ai_adapter.py list bin [env]` | `ai-adapter script list [group]` | `config.yaml` から読み取り |
| `ai_adapter.py del bin [env] X` | `ai-adapter script remove [group] X` | `config.yaml` から削除 |

---

## 5. 開発の進め方（実装順序）

### フェーズ 1 — プロジェクト基盤（最初にやること）

| Step | 内容 | ファイル | 並列可否 |
|------|------|---------|---------|
| 1.1 | プロジェクトスキャフォールディング | `pyproject.toml`, `.gitignore`, ディレクトリ構造 | 不可 |
| 1.2 | データモデル定義 | `src/ai_adapter/models.py` | 1.3, 1.4, 1.5 と並列可 |
| 1.3 | 設定ファイル管理 | `src/ai_adapter/config.py` | 1.2 と並列可 |
| 1.4 | CLI エントリーポイント | `src/ai_adapter/cli.py` | 1.3 と並列可 |
| 1.5 | テスト基盤 | `tests/` 一式 | 全 Step と並列可 |

**実装のコツ**: Step 1.1 でディレクトリ構造と `pyproject.toml` を作ったら、Step 1.2〜1.5 は同時並行で進めてよい。models → config → cli の依存関係だけ守ること。

### フェーズ 2 — コア機能（メイン実装）

| Step | 内容 | 依存 | 並列可否 |
|------|------|------|---------|
| 2.1 | `group` コマンド | 1.2, 1.3, 1.4 | 2.2, 2.3 と並列可 |
| 2.2 | `script` コマンド | 1.2, 1.3, 1.4 | 2.1, 2.3 と並列可 |
| 2.3 | `instructions` コマンド | 1.2, 1.3, 1.4 | 2.1, 2.2 と並列可 |

**実装のコツ**: 3 つのコマンドは互いに独立しているので同時並行で実装可能。各コマンドは `config.py` を介して設定ファイルを操作する。

### フェーズ 3 — 基盤機能

| Step | 内容 | 依存 | 並列可否 |
|------|------|------|---------|
| 3.1 | `init` / `status` コマンド | フェーズ2完了 | 3.2, 3.3 と並列可 |
| 3.2 | Git 連携 (`git.py`) | なし | 3.1, 3.3 と並列可 |
| 3.3 | プラグイン機構 (`plugin.py`) | なし | 3.1, 3.2 と並列可 |

### フェーズ 4 — 品質・公開準備

| Step | 内容 | 依存 | 並列可否 |
|------|------|------|---------|
| 4.1 | ログ・エラーハンドリング統一 | フェーズ2,3完了 | 不可 |
| 4.2 | テスト充実 | フェーズ2,3完了 | 不可 |
| 4.3 | ドキュメント整備 | — | 不可 |
| 4.4 | PyPI 公開準備 | — | 不可 |

---

## 6. データモデル設計

### Config の YAML 構造

```yaml
# ~/.ai-adapter/config.yaml
version: 1
groups:
  - name: deploy
    description: デプロイ関連スクリプト
    scripts:
      - name: deploy-prod
        path: scripts/deploy-prod.sh
        description: 本番デプロイ
      - name: deploy-staging
        path: scripts/deploy-staging.sh
        description: ステージングデプロイ
instructions:
  current: code-assist
  items:
    - name: code-assist
      path: instructions/code-assist.md
      description: コーディングアシスト用指示
    - name: review
      path: instructions/review.md
      description: コードレビュー用指示
plugins: {}
```

### Python dataclass 定義

```python
@dataclass
class Script:
    name: str
    path: Path
    description: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class Group:
    name: str
    description: str = ""
    scripts: list[Script] = field(default_factory=list)

@dataclass
class InstructionSet:
    name: str
    path: Path
    description: str = ""

@dataclass
class Config:
    groups: list[Group] = field(default_factory=list)
    current_instructions: str | None = None
    instructions: list[InstructionSet] = field(default_factory=list)
```

各 dataclass に `to_dict()` / `from_dict()` メソッドを実装し、YAML とのシリアライズを可能にすること。

---

## 7. コーディング規約

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
- **`config.py`**: 設定ファイルの読み書き・パス解決・バリデーションのみ。
  - `~/.ai-adapter/` のパス解決を担当（`Path.home() / ".ai-adapter"`）
  - 環境変数 `AI_ADAPTER_CONFIG` によるオーバーライド対応
- **`cli.py`**: Click グループとサブコマンドの定義、プラグインロード。薄く保つ。
- **`group.py` / `script.py` / `instructions.py`**: 各サブコマンドの実装。`config.py` を介してデータを操作。
- **`git.py`**: `subprocess` で git コマンドをラップ。エラーハンドリングを丁寧に。
- **`plugin.py`**: `importlib.metadata.entry_points` でプラグイン検出。

### エラーハンドリング

- ユーザー向けエラーは `click.ClickException` を継承したカスタム例外を使用
- 予期せぬエラーは `logging` モジュールで記録し、一般的なメッセージを表示
- 終了コードは一貫させる（成功: 0, ユーザーエラー: 1, システムエラー: 2）

---

## 8. テスト方針

### フレームワーク

- **unittest**（標準ライブラリ）
- CLI テストには **Click の `CliRunner`** を使用

### テストファイル対応表

| テストファイル | テスト対象 | テクニック |
|--------------|-----------|-----------|
| `test_config.py` | `config.py` | `tempfile.TemporaryDirectory` + `monkeypatch` で `~/.ai-adapter` を一時ディレクトリに差し替え |
| `test_group.py` | `group.py` | 設定ファイルを介したCRUD操作の検証 |
| `test_script.py` | `script.py` | スクリプト追加・削除・実行の検証 |
| `test_instructions.py` | `instructions.py` | 指示セットの追加・切替・削除の検証 |
| `test_git.py` | `git.py` | `subprocess` 呼び出しのモック化 |
| `test_plugin.py` | `plugin.py` | エントリーポイントのモック化 |
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

## 9. Git 運用ルール

### ブランチ戦略

- `main`: リリースブランチ。常に安定。
- `feat/xxx`: 機能開発ブランチ。`main` から分岐して `main` にマージ。
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

## 10. config.py の実装詳細（重要）

### 設定ファイルのパス解決

```python
import os
from pathlib import Path

def get_config_dir() -> Path:
    """設定ディレクトリ ~/.ai-adapter/ を返す。環境変数でオーバーライド可能。"""
    env = os.environ.get("AI_ADAPTER_CONFIG")
    if env:
        return Path(env).parent
    return Path.home() / ".ai-adapter"

def get_config_path() -> Path:
    """設定ファイルのパスを返す。"""
    env = os.environ.get("AI_ADAPTER_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".ai-adapter" / "config.yaml"
```

### 設定ファイルの探索ルール

1. 環境変数 `AI_ADAPTER_CONFIG` が設定されていればそのパスを使用
2. デフォルトは `~/.ai-adapter/config.yaml`
3. ファイルが存在しなければ `ai-adapter init` で作成するよう促す
4. `init` コマンドは `~/.ai-adapter/` ディレクトリと `config.yaml`、`instructions/` ディレクトリを作成

### パスの解決ルール

- スクリプトの `path` は**絶対パスとして保存する**（どのディレクトリから実行しても正しく動作するように）
- 指示セットの `path` は `~/.ai-adapter/` からの相対パスで保存する

---

## 11. アーキテクチャ上の注意点

### プラグイン設計

- プラグインは **オプション**。コア機能はプラグインなしで完結する。
- エントリーポイントグループ名: `ai_adapter.plugins`
- 各プラグインは Click の `Group` または `Command` を提供する
- `cli.py` の起動時に自動ロードされる

### Git 連携

- `subprocess` ベース。追加依存なし。
- シンプルな操作のみラップ（`init`, `add`, `commit`）
- Git 未インストール時は適切なエラーメッセージ
- `~/.ai-adapter/` をGitリポジトリとして初期化し、設定をGit管理可能にする

### 指示セット管理

- `~/.ai-adapter/instructions/` ディレクトリ配下で実体ファイルを管理
- `ai-adapter instructions add <path>`: ファイルを `~/.ai-adapter/instructions/` にコピーし、`config.yaml` に登録
- `ai-adapter instructions use <name>`: `config.yaml` の `current` フィールドを更新
  - 必要に応じて `.github/instructions/current` へのシンボリックリンクも作成
- `ai-adapter instructions show [name]`: `~/.ai-adapter/instructions/` のファイル内容を表示

---

## 12. 検証手順（リリース前チェックリスト）

- [ ] `uv run python -m unittest discover tests` が全件 PASS
- [ ] `ai-adapter init` で `~/.ai-adapter/` が生成される
- [ ] `ai-adapter group create test-group` でグループ作成できる
- [ ] `ai-adapter script add test-group /path/to/script.sh` でスクリプト追加できる
- [ ] `ai-adapter script run test-group script.sh` でスクリプト実行できる
- [ ] `ai-adapter instructions list` で指示セット一覧が表示される
- [ ] 存在しないグループの削除でエラーになる
- [ ] 重複作成でエラーになる
- [ ] `AI_ADAPTER_CONFIG` 環境変数で設定ファイルパスをオーバーライドできる
- [ ] `README.md` の手順通りに操作できる

---

## 13. 参考: README の希望仕様との対応

README では `ai_adapter.py` というスクリプト名で例示されているが、本プロジェクトでは **`ai-adapter`** という CLI コマンド名で提供する（`pyproject.toml` の `[project.scripts]` で登録）。

また、README では「データはローカルの `~/.ai-adapter` の中に格納する」と明記されている。すべての設定・データはこのディレクトリ配下に一元管理する。

```
README での希望例:
  ai_adapter.py add agent MARKDOWN_FILE_PATH
  ai_adapter.py get agent XXXX
  ai_adapter.py del agent XXXX

実際のコマンド:
  ai-adapter instructions add MARKDOWN_FILE_PATH   → ~/.ai-adapter/instructions/ に保存
  ai-adapter instructions use XXXX                  → config.yaml の current を更新
  ai-adapter instructions remove XXXX               → config.yaml から削除

ユースケース:
  # 会社の設定を ~/.ai-adapter/ ごとGitHubで管理
  cd ~/.ai-adapter
  git init && git add . && git commit -m "Initial config"
  git remote add origin <url>
  git push

  # 新しいPCに移行
  git clone <url> ~/.ai-adapter
  # → 設定と指示セットがすべて復元される
```

README の「environment」は本設計では **「group」** として実装する（環境＝スクリプトのグループ）。
