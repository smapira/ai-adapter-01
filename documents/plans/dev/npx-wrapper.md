# npx Wrapper 開発指示書

**Version:** 1.0
**基準日:** 2026-08-16
**対象:** `ai-adapter` の `npx skills` ラッパー機能
**ステータス:** 開発計画

---

## 1. 目的

`npx` がローカルにインストールされている場合、`ai-adapter` から `npx skills` コマンドを直接実行できるラッパー機能を提供する。

これにより、`ai-adapter skill` サブコマンドと `npx skills` をシームレスに利用できるようになる。

---

## 2. 背景

### 2.1 現状の問題

- `ai-adapter skill` は独自のスキル管理を持つ
- `npx skills`（vercel-labs/skills）は外部のエコシステムSkill管理
- 両方を使い分ける必要がある
- `npx skills` がインストール済みでも `ai-adapter` から直接呼び出せない

### 2.2 解決策

`ai-adapter` に `npx` ラッパーを実装し、`npx skills` のコマンドを透過的に呼び出せるようにする。

---

## 3. 仕様

### 3.1 コマンド構文

```
ai-adapter npx skills <args>...          # npx skills を直接実行
ai-adapter npx --check                   # npx の利用可能性を確認
ai-adapter npx --version                 # npx のバージョンを表示
```

### 3.2 ラッパー動作

| # | シナリオ | 期待結果 |
|---|---------|---------|
| 1 | `npx` が PATH にある場合 | `npx skills <args>` を実行し、結果を表示 |
| 2 | `npx` が PATH にない場合 | エラーメッセージを表示して終了 |
| 3 | `npx --check` | npx の有無とバージョンを表示 |
| 4 | `npx --version` | npx のバージョンのみ表示 |
| 5 | `npx skills` の結果が成功 | その出力をそのまま表示 |
| 6 | `npx skills` の結果が失敗 | エラーコードとエラー出力を表示 |

### 3.3 利用可能な npx skills コマンド

仕様書（npx.md）に基づく主要コマンド:

| コマンド | 説明 | 例 |
|---------|------|-----|
| `skills find` | Skill 検索 | `ai-adapter npx skills find react` |
| `skills add` | Skill インストール | `ai-adapter npx skills add owner/repo` |
| `skills list` | インストール済み Skill 一覧 | `ai-adapter npx skills list` |
| `skills update` | Skill 更新 | `ai-adapter npx skills update` |
| `skills remove` | Skill 削除 | `ai-adapter npx skills remove my-skill` |
| `skills use` | 一時利用 | `ai-adapter npx skills use owner/repo@skill` |
| `skills init` | Skill テンプレート作成 | `ai-adapter npx skills init my-skill` |
| `skills install` | lock state から復元 | `ai-adapter npx skills install` |

### 3.4 オプション

| オプション | 説明 |
|-----------|------|
| `--check` | npx の利用可能性を確認（実行しない） |
| `--version` | npx のバージョンを表示 |
| `--agent <name>` | 対象 Agent を指定（`-a` 短縮形可） |
| `-g` / `--global` | Global scope で実行 |
| `-y` / `--yes` | 確認をスキップ |
| `--list` | Repository 内の Skill を一覧表示（add 時） |
| `--skill <name>` | 特定 Skill を指定 |
| `--copy` | symlink ではなく copy 方式で導入 |
| `--full-depth` | Skill 探索を深く行う |

---

## 4. 実装構成

### 4.1 新規ファイル

```
src/ai_adapter/
├── npx.py                    # npx 検出・実行ロジック
└── commands/
    └── npx.py                # CLI コマンド定義
```

### 4.2 変更ファイル

```
src/ai_adapter/cli.py         # npx_group 登録
```

### 4.3 テストファイル

```
tests/test_npx.py             # ユニットテスト
```

---

## 5. 実装タスク

### Task 1: npx 検出モジュール (`npx.py`)

```python
# 期待する振る舞い:
- shutil.which("npx") で npx のパスを検出
- npx のバージョンを取得 (--version)
- npx skills の実行
- タイムアウト制御
- エラーハンドリング
```

**関数シグネチャ:**

```python
def find_npx() -> str | None:
    """npx のパスを検出。なければ None を返す。"""

def get_npx_version() -> str | None:
    """npx のバージョン文字列を返す。なければ None を返す。"""

def run_npx_skills(
    args: list[str],
    timeout: int = 60,
) -> tuple[int, str, str]:
    """npx skills を実行。

    Returns:
        (exit_code, stdout, stderr)
    """
```

### Task 2: npx CLI コマンド (`commands/npx.py`)

```python
# 期待する振る舞い:
- @click.group(name="npx") で npx グループを定義
- skills サブコマンドで npx skills を透過実行
- --check で npx の有無を確認
- --version で npx のバージョンを表示
```

**コマンド定義:**

```python
@click.group(name="npx")
def npx_group() -> None:
    """Run npx commands (when npx is installed)."""


@npx_group.command(
    name="skills",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_interspersed_args=False,
    ),
)
@click.argument("args", nargs=-1)
@click.option("--check", is_flag=True)
@click.option("--version", is_flag=True)
def npx_skills(args, check, version):
    """Run 'npx skills' with given arguments."""
```

### Task 3: CLI 登録 (`cli.py`)

```python
# cli.py に追加
from ai_adapter.commands.npx import npx_group

main.add_command(npx_group)
```

### Task 4: テスト (`test_npx.py`)

```python
# テストケース:
- test_find_npx_found: npx が見つかる場合
- test_find_npx_not_found: npx が見つからない場合
- test_get_npx_version: バージョン取得
- test_run_npx_skills_success: 正常実行
- test_run_npx_skills_not_found: npx 未インストール時のエラー
- test_npx_skills_cli: CLI 統合テスト
- test_npx_check: --check フラグ
- test_npx_version: --version フラグ
```

---

## 6. 実装仕様

### 6.1 npx 検出ロジック

```python
import shutil
import subprocess

def find_npx() -> str | None:
    """npx のパスを検出。"""
    return shutil.which("npx")

def get_npx_version() -> str | None:
    """npx のバージョンを取得。"""
    npx_path = find_npx()
    if npx_path is None:
        return None
    try:
        result = subprocess.run(
            [npx_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
```

### 6.2 npx skills 実行ロジック

```python
def run_npx_skills(
    args: list[str],
    timeout: int = 60,
) -> tuple[int, str, str]:
    """npx skills を実行。"""
    npx_path = find_npx()
    if npx_path is None:
        return (127, "", "npx is not installed or not in PATH")

    cmd = [npx_path, "skills"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", f"npx skills timed out after {timeout}s")
    except FileNotFoundError:
        return (127, "", f"npx not found at {npx_path}")
```

### 6.3 CLI 実装

```python
import click
from ai_adapter.npx import find_npx, get_npx_version, run_npx_skills


@click.group(name="npx")
def npx_group() -> None:
    """Run npx commands (when npx is installed)."""


@npx_group.command(
    name="skills",
    context_settings=dict(
        ignore_unknown_options=True,
        allow_interspersed_args=False,
    ),
)
@click.argument("args", nargs=-1)
@click.option("--check", is_flag=True, help="Check if npx is available")
@click.option("--version", is_flag=True, help="Show npx version")
def npx_skills(args: tuple[str, ...], check: bool, version: bool) -> None:
    """Run 'npx skills' with given arguments.

    \b
    Examples:
      ai-adapter npx skills find react
      ai-adapter npx skills add owner/repo
      ai-adapter npx skills list
      ai-adapter npx --check
    """
    if check:
        npx_path = find_npx()
        if npx_path:
            click.echo(f"npx found: {npx_path}")
            ver = get_npx_version()
            if ver:
                click.echo(f"version: {ver}")
        else:
            click.echo("npx is not installed or not in PATH", err=True)
            raise click.ClickException("npx not found")
        return

    if version:
        ver = get_npx_version()
        if ver:
            click.echo(ver)
        else:
            click.echo("npx is not installed or not in PATH", err=True)
            raise click.ClickException("npx not found")
        return

    exit_code, stdout, stderr = run_npx_skills(list(args))
    if stdout:
        click.echo(stdout, nl=False)
    if stderr:
        click.echo(stderr, nl=False, err=True)
    if exit_code != 0:
        raise SystemExit(exit_code)
```

---

## 7. エラーハンドリング

| エラー | エラーコード | メッセージ |
|--------|------------|-----------|
| npx 未インストール | 127 | `npx is not installed or not in PATH` |
| タイムアウト | 124 | `npx skills timed out after {timeout}s` |
| npx 実行失敗 | ステータスコード | npx の stderr 出力 |
| 不正な引数 | 2 | Click のヘルプ表示 |

---

## 8. テスト戦略

### 8.1 ユニットテスト

- `find_npx()`: monkeypatch で `shutil.which` をモック
- `get_npx_version()`: monkeypatch で `subprocess.run` をモック
- `run_npx_skills()`: 正常系・異常系・タイムアウトをテスト

### 8.2 CLI テスト

- `--check` フラグの出力
- `--version` フラグの出力
- 引数の伝播
- npx 未インストール時のエラー

### 8.3 統合テスト（オプション）

- 実際の `npx skills find` を実行（環境依存のためスキップ可能）

---

## 9. 既存コードとの整合性

### 9.1 既存の skill サブコマンドとの関係

```
ai-adapter skill          # 独自スキル管理（config.json ベース）
ai-adapter npx skills     # npx skills CLI のラッパー
```

両方ともスキル管理だが、役割が異なる:

| | `ai-adapter skill` | `ai-adapter npx skills` |
|---|---|---|
| **管理方法** | config.json + ファイルコピー | npx skills CLI（外部） |
| **Skill ソース** | ~/.ai-adapter/skills/ | Git/HTTP/Local 等 |
| **Agent 対応** | ai-adapter 管理下の Agent | 70+ Agent に対応 |
| **Lock state** | なし | skills-lock.json |
| **更新管理** | 手動 | hash-based update |

### 9.2 scan との連携

`ai-adapter scan` で検出される `npx skills` のインストール状態を確認し、
ラッパーの利用可否を判断する。

---

## 10. 制約・注意事項

- `npx` は Node.js 環境が必要
- `npx skills` の初回実行はパッケージダウンロードで時間がかかる場合がある
- タイムアウトはデフォルト 60 秒（`--timeout` で変更可能にすることを検討）
- Windows 対応は今回は見送り（macOS/Linux のみ）
- `npx` のバージョン要件: Node.js 16.x 以上

---

## 11. 将来拡張

| 拡張 | 説明 | 優先度 |
|------|------|--------|
| `ai-adapter npx skills sync` | npx skills で取得した Skill を ai-adapter に同期 | 高 |
| `ai-adapter npx skills export` | ai-adapter の Skill を npx skills 形式でエクスポート | 中 |
| `ai-adapter npx --wrap` | npx をラップしたスクリプトを生成 | 低 |
| agent 自動検出 | `npx skills add` 時に利用可能な Agent を自動検出 | 中 |

---

## 12. 完了条件

1. `ai-adapter npx skills <args>` が npx インストール時に動作する
2. `ai-adapter npx --check` が npx の有無を正確に報告する
3. npx 未インストール時にエラーメッセージが表示される
4. 既存テストがすべてパスする
5. 新規テストがすべてパスする
